"""Gemerkte Einstellungen pro Geraet, z.B. "Beamer Raum 204 -> immer spiegeln".

Liegt in der eigenen Datei der App, nicht in der Hyprland-Config.
"""

import json
import os
from pathlib import Path

PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "hyprcast" / "profiles.json"


def load() -> dict:
    try:
        return json.loads(PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(profiles: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(profiles, indent=2, ensure_ascii=False))
    tmp.replace(PATH)
