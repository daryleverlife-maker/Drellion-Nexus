from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json
import time

@dataclass
class MediaSlot:
    path: str = ""
    label: str = ""

@dataclass
class ProjectState:
    schema_version: int = 1
    name: str = "Untitled"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    vocal: MediaSlot = field(default_factory=MediaSlot)
    lyrics: str = ""
    reference: MediaSlot = field(default_factory=MediaSlot)
    finished_song: MediaSlot = field(default_factory=MediaSlot)
    sound_library_path: str = ""
    selected_preview: str = ""
    build_path: str = ""
    master_path: str = ""
    mode: str = "auto"
    vocal_preservation: str = "Polished"
    reference_influence: str = "Strong"
    originality_protection: str = "Maximum"
    settings: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectState":
        data = dict(payload)
        for key in ("vocal", "reference", "finished_song"):
            data[key] = MediaSlot(**(data.get(key, {}) or {}))
        return cls(**data)

    def save(self, path: str | Path) -> Path:
        self.touch()
        target = Path(path)
        if target.suffix.lower() != ".drellion":
            target = target.with_suffix(".drellion")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "ProjectState":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
