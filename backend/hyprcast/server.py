"""Backend-Server: JSON-Zeilen ueber einen Unix-Socket.

Anfrage:  {"id": 1, "cmd": "set_mode", "args": {...}}
Antwort:  {"id": 1, "ok": true, "result": ...}  bzw. {"id": 1, "ok": false, "error": "..."}
Event:    {"event": "state", "data": {...}}  /  {"event": "monitor_added", "data": {...}}

Beim Beenden wird alles zurueckgesetzt: Hyprland-Config neu laden,
Praesentationsmodus aus.
"""

import asyncio
import json
import os
import signal

from . import cast, displays, hypr, profiles
from .presentation import Presentation

SOCKET = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "hyprcast.sock")


class Backend:
    def __init__(self) -> None:
        self.clients: set[asyncio.StreamWriter] = set()
        self.presentation = Presentation()
        self.active: dict | None = None  # {"mode", "external"} solange wir etwas geaendert haben
        self.profiles = profiles.load()
        self.installing = False

    # --- Zustand -----------------------------------------------------------
    async def state(self) -> dict:
        raw = await hypr.monitors()
        mons = [displays.summarize(m, raw) for m in raw]
        for m in mons:
            m["profile"] = self.profiles.get(m["key"])
        return {
            "monitors": mons,
            "active": self.active,
            "presentation": self.presentation.active,
            "cast": {**await cast.capabilities(), "installing": self.installing},
        }

    async def broadcast(self, event: str, data) -> None:
        line = (json.dumps({"event": event, "data": data}) + "\n").encode()
        for w in list(self.clients):
            try:
                w.write(line)
                await w.drain()
            except (ConnectionError, OSError):
                self.clients.discard(w)

    async def push_state(self) -> None:
        await self.broadcast("state", await self.state())

    # --- Befehle -----------------------------------------------------------
    async def cmd_get_state(self):
        return await self.state()

    async def cmd_set_mode(self, mode: str, external: str, side: str = "right",
                           match_resolution: bool = True, remember: bool = False):
        await displays.apply(mode, external, side, match_resolution)
        self.active = {"mode": mode, "external": external}
        if remember:
            mon = next(m for m in await hypr.monitors() if m["name"] == external)
            self.profiles[displays.device_key(mon)] = {
                "mode": mode, "side": side, "matchResolution": match_resolution,
                "presentation": self.presentation.active,
            }
            profiles.save(self.profiles)

    async def cmd_forget_profile(self, key: str):
        if self.profiles.pop(key, None) is not None:
            profiles.save(self.profiles)

    async def cmd_restore(self):
        await self.restore()

    async def cmd_set_presentation(self, on: bool):
        await self.presentation.set(on)

    async def cmd_open_url(self, url: str):
        await cast.open_url(url)

    async def cmd_launch_miracast(self):
        await cast.launch_miracast()

    async def cmd_install_miracast(self):
        """Startet die Installation im Hintergrund; Fortschritt kommt per state,
        das Ergebnis per Event "install_done"."""
        if self.installing:
            return
        self.installing = True
        asyncio.create_task(self._install_miracast())

    async def _install_miracast(self) -> None:
        try:
            await cast.install_miracast()
            result = {"ok": True}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self.installing = False
        await self.broadcast("install_done", result)
        await self.push_state()

    async def restore(self) -> None:
        if self.active is not None:
            await hypr.reload()
            self.active = None

    # --- Hyprland-Events -----------------------------------------------------
    async def on_monitor_added(self, name: str) -> None:
        mon = next((m for m in await hypr.monitors() if m["name"] == name), None)
        if mon is None or displays.is_internal(name):
            return
        profile = self.profiles.get(displays.device_key(mon))
        if profile:
            await self.cmd_set_mode(profile["mode"], name, profile.get("side", "right"),
                                    profile.get("matchResolution", True))
            if profile.get("presentation"):
                await self.presentation.set(True)
        await self.broadcast("monitor_added", {"monitor": displays.summarize(mon, [mon]),
                                               "autoApplied": bool(profile)})

    async def on_monitor_removed(self, name: str) -> None:
        if self.active and self.active["external"] == name:
            await self.restore()
            await self.presentation.set(False)

    async def watch_hyprland(self) -> None:
        async for event, data in hypr.events():
            # v2: "id,name,beschreibung"; v1: "name"
            if event == "monitoraddedv2":
                await self.on_monitor_added(data.split(",")[1])
            elif event == "monitorremovedv2":
                await self.on_monitor_removed(data.split(",")[1])
            else:
                continue
            await self.push_state()

    # --- Clients -------------------------------------------------------------
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.clients.add(writer)
        try:
            while line := await reader.readline():
                try:
                    req = json.loads(line)
                    handler = getattr(self, "cmd_" + req["cmd"], None)
                    if handler is None:
                        raise ValueError(f"Unbekannter Befehl: {req['cmd']}")
                    resp = {"id": req.get("id"), "ok": True,
                            "result": await handler(**req.get("args", {}))}
                except Exception as e:  # Fehler gehen an die App, nicht in den Absturz
                    resp = {"id": req.get("id") if isinstance(req, dict) else None,
                            "ok": False, "error": str(e)}
                writer.write((json.dumps(resp) + "\n").encode())
                await writer.drain()
                if resp["ok"] and req["cmd"] != "get_state":
                    await self.push_state()
        except ConnectionError:
            pass  # App hat die Verbindung getrennt
        finally:
            self.clients.discard(writer)
            writer.close()

    async def shutdown(self) -> None:
        await self.restore()
        await self.presentation.set(False)


async def watch_parent(stop: asyncio.Event) -> None:
    """Beenden, wenn die App weg ist (auch bei Absturz der App)."""
    parent = os.getppid()
    while os.getppid() == parent:
        await asyncio.sleep(1)
    stop.set()


async def _socket_alive() -> bool:
    try:
        _, writer = await asyncio.open_unix_connection(SOCKET)
    except OSError:
        return False
    writer.close()
    return True


async def main(exit_with_parent: bool = False) -> None:
    backend = Backend()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, stop.set)

    if os.path.exists(SOCKET):
        if await _socket_alive():
            # Ein anderes Backend laeuft schon - die App verbindet sich dann dorthin.
            print(f"HyprCast-Backend laeuft bereits: {SOCKET}", flush=True)
            return
        os.unlink(SOCKET)
    server = await asyncio.start_unix_server(backend.handle_client, SOCKET)
    os.chmod(SOCKET, 0o600)
    tasks = [asyncio.create_task(backend.watch_hyprland())]
    if exit_with_parent:
        tasks.append(asyncio.create_task(watch_parent(stop)))
    print(f"HyprCast-Backend laeuft: {SOCKET}", flush=True)

    try:
        await stop.wait()
    finally:
        for t in tasks:
            t.cancel()
        server.close()
        await backend.shutdown()
        if os.path.exists(SOCKET):
            os.unlink(SOCKET)
