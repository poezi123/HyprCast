"""Bildschirm-Modi: spiegeln, erweitern, nur extern - alles nur zur Laufzeit."""

import re

from . import hypr

INTERNAL_PREFIXES = ("eDP", "LVDS", "DSI")
MODES = ("mirror", "extend", "external_only")


def is_internal(name: str) -> bool:
    return name.startswith(INTERNAL_PREFIXES)


def device_key(mon: dict) -> str:
    """Stabiler Schluessel fuer ein Geraet (Beamer, Tafel), unabhaengig vom Port."""
    return "|".join(mon.get(k) or "" for k in ("make", "model", "serial"))


def _parse_mode(mode: str) -> tuple[int, int, float] | None:
    m = re.match(r"(\d+)x(\d+)@([\d.]+)", mode)
    return (int(m[1]), int(m[2]), float(m[3])) if m else None


def common_mode(internal: dict, external: dict) -> str | None:
    """Groesste Aufloesung, die beide koennen - damit beim Spiegeln nichts
    abgeschnitten oder verzerrt wird. Pro Aufloesung die hoechste Rate des
    Laptops."""
    ext_res = {p[:2] for m in external.get("availableModes", []) if (p := _parse_mode(m))}
    best = None
    for m in internal.get("availableModes", []):
        p = _parse_mode(m)
        if p and p[:2] in ext_res and (best is None or (p[0] * p[1], p[2]) > (best[0] * best[1], best[2])):
            best = p
    return f"{best[0]}x{best[1]}@{best[2]:g}" if best else None


def summarize(mon: dict) -> dict:
    return {
        "name": mon["name"],
        "description": mon.get("description", ""),
        "key": device_key(mon),
        "internal": is_internal(mon["name"]),
        "disabled": mon.get("disabled", False),
        "mirrorOf": mon.get("mirrorOf", "none"),
        "mode": f"{mon['width']}x{mon['height']}@{mon['refreshRate']:.0f}",
        "availableModes": mon.get("availableModes", []),
    }


async def apply(mode: str, external_name: str, side: str = "right", match_resolution: bool = True) -> None:
    if mode not in MODES:
        raise ValueError(f"Unbekannter Modus: {mode}")
    mons = await hypr.monitors()
    internal = next((m for m in mons if is_internal(m["name"])), None)
    external = next((m for m in mons if m["name"] == external_name), None)
    if external is None:
        raise ValueError(f"Monitor {external_name} nicht gefunden")
    if internal is None:
        raise ValueError("Kein Laptop-Bildschirm gefunden")

    if mode == "mirror":
        common = common_mode(internal, external) if match_resolution else None
        await hypr.set_monitor(output=internal["name"], mode=common or "preferred",
                               position="0x0", scale="1")
        await hypr.set_monitor(output=external["name"], mode=common or "preferred",
                               position="auto", scale="1", mirror=internal["name"])
    elif mode == "extend":
        await hypr.set_monitor(output=internal["name"], mode="preferred", position="0x0", scale="1")
        await hypr.set_monitor(output=external["name"], mode="preferred",
                               position=f"auto-{side}", scale="1")
    else:  # external_only
        await hypr.set_monitor(output=external["name"], mode="preferred", position="0x0", scale="1")
        await hypr.set_monitor(output=internal["name"], disabled=True)
