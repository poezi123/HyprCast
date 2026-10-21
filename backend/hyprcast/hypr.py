"""Zugriff auf Hyprland: hyprctl-Aufrufe und der Event-Socket (socket2)."""

import asyncio
import json
import os


def _socket_dir() -> str:
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        raise RuntimeError("HYPRLAND_INSTANCE_SIGNATURE fehlt - laeuft Hyprland?")
    return os.path.join(os.environ["XDG_RUNTIME_DIR"], "hypr", sig)


async def hyprctl(*args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "hyprctl", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"hyprctl {' '.join(args)}: {err.decode().strip()}")
    return out.decode()


async def monitors() -> list[dict]:
    """Alle Monitore, auch deaktivierte."""
    return json.loads(await hyprctl("monitors", "all", "-j"))


def lua_table(fields: dict) -> str:
    """Baut eine Lua-Tabelle fuer hl.monitor({...})."""
    parts = []
    for key, value in fields.items():
        if isinstance(value, bool):
            parts.append(f"{key} = {'true' if value else 'false'}")
        else:
            text = str(value).replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{key} = "{text}"')
    return "{ " + ", ".join(parts) + " }"


async def set_monitor(**fields) -> None:
    """Setzt eine Monitor-Regel nur zur Laufzeit (nichts landet in der Config).

    Die Config ist Lua, deshalb geht `hyprctl keyword` nicht - nur `eval`.
    """
    result = await hyprctl("eval", f"hl.monitor({lua_table(fields)})")
    if result.strip() != "ok":
        raise RuntimeError(f"hl.monitor abgelehnt: {result.strip()}")


async def reload() -> None:
    """Laedt die Config neu und verwirft damit alle Laufzeit-Regeln."""
    await hyprctl("reload")


async def events():
    """Liefert (event, daten) aus socket2, endlos."""
    path = os.path.join(_socket_dir(), ".socket2.sock")
    reader, _ = await asyncio.open_unix_connection(path)
    while line := await reader.readline():
        name, _, data = line.decode(errors="replace").rstrip("\n").partition(">>")
        yield name, data
