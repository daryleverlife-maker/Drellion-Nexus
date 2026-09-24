from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json


@dataclass
class AccessibilitySettings:
    ui_scale: int = 100
    text_scale: int = 100
    font_family: str = "System"
    theme: str = "Dark"
    density: str = "Comfortable"
    high_contrast: bool = False
    reduced_motion: bool = False
    large_controls: bool = False
    enhanced_focus: bool = True
    enhanced_screen_reader: bool = False
    numeric_meters: bool = False

    def normalized(self):
        self.ui_scale = min(200, max(100, int(self.ui_scale)))
        self.text_scale = min(200, max(100, int(self.text_scale)))
        return self

    def save(self, path: str | Path):
        self.normalized()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path):
        source = Path(path)
        if not source.exists():
            return cls()
        return cls(**json.loads(source.read_text(encoding="utf-8"))).normalized()
