"""Kabellos zur Tafel (iiyama iiShare / EShare).

Laut iiyama kann iiShare Miracast, AirPlay, teils Chromecast und "Webcast"
(Teilen ueber eine URL). Unter Linux realistisch:
  - Webcast/URL: im Browser oeffnen, Bildschirmfreigabe laeuft ueber
    xdg-desktop-portal-hyprland.
  - Miracast/Chromecast: ueber gnome-network-displays. Das gibt es nicht in
    den Arch-Paketquellen, aber auf Flathub - die App installiert es dort nur
    fuer den Benutzer (--user, kein root).
Welche Variante die Tafel in der Schule wirklich anbietet, ist noch offen.
"""

import asyncio
import shutil

GND = "gnome-network-displays"
FLATPAK_ID = "org.gnome.NetworkDisplays"
FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"


async def _run(*cmd: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    return proc.returncode, out.decode(errors="replace")


async def _flatpak_installed() -> bool:
    if not shutil.which("flatpak"):
        return False
    code, _ = await _run("flatpak", "info", FLATPAK_ID)
    return code == 0


async def capabilities() -> dict:
    installed = shutil.which(GND) is not None or await _flatpak_installed()
    return {
        "webcast": shutil.which("xdg-open") is not None,
        "miracastInstalled": installed,
        # Ohne flatpak koennen wir nichts nachinstallieren.
        "miracastInstallable": not installed and shutil.which("flatpak") is not None,
    }


async def _spawn(*cmd: str) -> None:
    await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )


async def open_url(url: str) -> None:
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    await _spawn("xdg-open", url)


async def install_miracast() -> None:
    """Installiert gnome-network-displays von Flathub, nur fuer diesen Benutzer."""
    if not shutil.which("flatpak"):
        raise RuntimeError("flatpak ist nicht installiert")
    code, out = await _run("flatpak", "remote-add", "--user", "--if-not-exists", "flathub", FLATHUB)
    if code != 0:
        raise RuntimeError(f"Flathub konnte nicht eingerichtet werden: {out.strip()[-300:]}")
    code, out = await _run("flatpak", "install", "--user", "--noninteractive", "-y", "flathub", FLATPAK_ID)
    if code != 0:
        raise RuntimeError(f"Installation fehlgeschlagen: {out.strip()[-300:]}")


async def launch_miracast() -> None:
    if shutil.which(GND):
        await _spawn(GND)
    elif await _flatpak_installed():
        await _spawn("flatpak", "run", FLATPAK_ID)
    else:
        raise RuntimeError("gnome-network-displays ist nicht installiert")
