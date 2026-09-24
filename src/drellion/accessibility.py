from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

from .storage import settings_path


@dataclass
class AccessibilitySettings:
    ui_scale: int = 100
    text_scale: int = 100
    font_family: str = "System"
    density: str = "Comfortable"
    theme: str = "Dark"
    color_vision: str = "Default"
    focus: str = "Enhanced"
    motion: str = "Reduced"
    screen_reader: str = "Auto"
    keyboard_only: bool = False
    control_size: str = "Large"
    waveform_contrast: str = "Enhanced"
    meter_mode: str = "Color + numeric"
    spoken_feedback: bool = False


def accessibility_path() -> Path:
    return settings_path().with_name("accessibility.json")


def load_accessibility_settings() -> AccessibilitySettings:
    path = accessibility_path()
    if not path.exists():
        return AccessibilitySettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        allowed = AccessibilitySettings.__dataclass_fields__.keys()
        return AccessibilitySettings(**{k: v for k, v in data.items() if k in allowed})
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AccessibilitySettings()


def save_accessibility_settings(settings: AccessibilitySettings) -> Path:
    path = accessibility_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return path
