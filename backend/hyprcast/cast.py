"""Kabellos zur Tafel (iiyama iiShare / EShare).

Laut iiyama kann iiShare Miracast, AirPlay, teils Chromecast und "Webcast"
(Teilen ueber eine URL). Unter Linux realistisch:
  - Webcast/URL: im Browser oeffnen, Bildschirmfreigabe laeuft ueber
    xdg-desktop-portal-hyprland.
  - Miracast/Chromecast: ueber gnome-network-displays, falls installiert.
Welche Variante die Tafel in der Schule wirklich anbietet, ist noch offen.
"""

import asyncio
import shutil

GND = "gnome-network-displays"


def capabilities() -> dict:
    return {
        "webcast": shutil.which("xdg-open") is not None,
        "miracast": shutil.which(GND) is not None or shutil.which("flatpak") is not None,
        "miracastInstalled": shutil.which(GND) is not None,
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


async def launch_miracast() -> None:
    if shutil.which(GND):
        await _spawn(GND)
    else:
        await _spawn("flatpak", "run", "org.gnome.NetworkDisplays")
