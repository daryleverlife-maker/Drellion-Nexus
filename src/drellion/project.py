from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json
import time
import uuid


@dataclass
class MediaSlot:
    path: str = ""
    label: str = ""


@dataclass
class ClipState:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    label: str = "Clip"
    path: str = ""
    start: float = 0.0
    source_offset: float = 0.0
    duration: float = 0.0
    gain_db: float = 0.0
    pan: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    muted: bool = False


@dataclass
class TrackState:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "Track"
    role: str = "audio"
    clips: list[ClipState] = field(default_factory=list)
    volume_db: float = 0.0
    pan: float = 0.0
    muted: bool = False
    solo: bool = False


@dataclass
class ProjectState:
    schema_version: int = 2
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
    tracks: list[TrackState] = field(default_factory=list)
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

        tracks: list[TrackState] = []
        for raw_track in data.get("tracks", []) or []:
            raw = dict(raw_track)
            raw["clips"] = [
                ClipState(**dict(raw_clip))
                for raw_clip in (raw.get("clips", []) or [])
            ]
            tracks.append(TrackState(**raw))
        data["tracks"] = tracks

        # Older project files remain loadable.
        data["schema_version"] = max(2, int(data.get("schema_version", 1)))
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
