"""
Persistent settings stored in ~/.vita/settings.json.
"""

import json
import os
from pathlib import Path
from typing import Optional

_SETTINGS_DIR  = Path.home() / ".vita"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

_DEFAULTS = {
    "mode":          "companion",  # "companion" | "pill"
    "serial_port":   "",           # e.g. "COM3" or "/dev/tty.usbmodem2439"
    "api_provider":  "",           # "anthropic" | "openai" | ""
    "api_key":       "",
    "voice_enabled": False,
    "sound_enabled": False,        # opt-in sound effects
}


def _load() -> dict:
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**_DEFAULTS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULTS)


def _save(data: dict):
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class Settings:
    def __init__(self):
        self._data = _load()

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        _save(self._data)

    # Convenience properties
    @property
    def mode(self) -> str:
        return self._data.get("mode", "companion")

    @mode.setter
    def mode(self, value: str):
        self.set("mode", value)

    @property
    def serial_port(self) -> str:
        return self._data.get("serial_port", "")

    @serial_port.setter
    def serial_port(self, value: str):
        self.set("serial_port", value)

    @property
    def api_provider(self) -> str:
        return self._data.get("api_provider", "")

    @property
    def api_key(self) -> str:
        return self._data.get("api_key", "")

    @property
    def voice_enabled(self) -> bool:
        return bool(self._data.get("voice_enabled", False))

    @property
    def sound_enabled(self) -> bool:
        return bool(self._data.get("sound_enabled", False))

    @sound_enabled.setter
    def sound_enabled(self, value: bool):
        self.set("sound_enabled", value)

    def has_llm(self) -> bool:
        return bool(self.api_provider and self.api_key)
