from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json
import time
import uuid


def _id() -> str:
    return uuid.uuid4().hex


@dataclass
class MediaSlot:
    path: str = ""
    label: str = ""


@dataclass
class SourceSlot:
    id: str = field(default_factory=_id)
    path: str = ""
    label: str = ""
    role: str = "Other"
    preserve: bool = False
    use_in_build: bool = True
    enabled: bool = True
    gain_db: float = 0.0
    notes: str = ""


@dataclass
class ReferenceSlot:
    id: str = field(default_factory=_id)
    path: str = ""
    youtube_url: str = ""
    title: str = ""
    artist: str = ""
    enabled: bool = True
    influence: float = 1.0
    roles: dict[str, float] = field(default_factory=lambda: {
        "drums": 1.0,
        "bass": 1.0,
        "energy": 1.0,
        "arrangement": 1.0,
        "harmony": 0.5,
        "tone": 1.0,
        "stereo": 1.0,
        "master": 1.0,
    })
    analysis: dict[str, Any] = field(default_factory=dict)


@dataclass
class StorageSettings:
    project_root: str = ""
    export_root: str = ""
    sound_library_root: str = ""
    model_root: str = ""
    cache_root: str = ""


@dataclass
class VersionSnapshot:
    id: str = field(default_factory=_id)
    label: str = "Snapshot"
    created_at: float = field(default_factory=time.time)
    note: str = ""


@dataclass
class ClipState:
    id: str = field(default_factory=_id)
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
    id: str = field(default_factory=_id)
    name: str = "Track"
    role: str = "audio"
    clips: list[ClipState] = field(default_factory=list)
    volume_db: float = 0.0
    pan: float = 0.0
    muted: bool = False
    solo: bool = False


@dataclass
class ProjectState:
    """Serializable project model.

    Schema v3 keeps the v1/v2 single vocal/reference fields for compatibility
    while adding multi-source and multi-reference collections used by v2.
    """

    schema_version: int = 3
    name: str = "Untitled"
    artist: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Legacy/current single-slot fields used by the v1 engine and older projects.
    vocal: MediaSlot = field(default_factory=MediaSlot)
    lyrics: str = ""
    reference: MediaSlot = field(default_factory=MediaSlot)
    finished_song: MediaSlot = field(default_factory=MediaSlot)

    # v2 multi-source/reference system.
    sources: list[SourceSlot] = field(default_factory=list)
    references: list[ReferenceSlot] = field(default_factory=list)
    active_vocal_source_id: str = ""
    active_reference_id: str = ""

    sound_library_path: str = ""
    storage: StorageSettings = field(default_factory=StorageSettings)
    selected_preview: str = ""
    build_path: str = ""
    master_path: str = ""
    mode: str = "auto"
    vocal_preservation: str = "Polished"
    reference_influence: str = "Strong"
    originality_protection: str = "Maximum"
    tracks: list[TrackState] = field(default_factory=list)
    versions: list[VersionSnapshot] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = time.time()

    def _ensure_v2_slots(self) -> None:
        """Mirror legacy slots into v2 lists without deleting user data."""
        if self.vocal.path and not any(s.path == self.vocal.path and s.role.lower() in {"vocal", "lead vocal"} for s in self.sources):
            slot = SourceSlot(
                path=self.vocal.path,
                label=self.vocal.label or Path(self.vocal.path).stem,
                role="Lead Vocal",
                preserve=True,
            )
            self.sources.insert(0, slot)
            if not self.active_vocal_source_id:
                self.active_vocal_source_id = slot.id

        if self.finished_song.path and not any(s.path == self.finished_song.path for s in self.sources):
            self.sources.append(SourceSlot(
                path=self.finished_song.path,
                label=self.finished_song.label or Path(self.finished_song.path).stem,
                role="Finished Song",
                preserve=True,
            ))

        if self.reference.path and not any(r.path == self.reference.path for r in self.references):
            slot = ReferenceSlot(
                path=self.reference.path,
                title=self.reference.label or Path(self.reference.path).stem,
            )
            self.references.insert(0, slot)
            if not self.active_reference_id:
                self.active_reference_id = slot.id

        if not self.active_vocal_source_id:
            for source in self.sources:
                if source.role.lower() in {"lead vocal", "vocal", "vocals"}:
                    self.active_vocal_source_id = source.id
                    break
        if not self.active_reference_id and self.references:
            self.active_reference_id = self.references[0].id

        self.sync_legacy_slots()

    def sync_legacy_slots(self) -> None:
        """Keep the current v1 engine usable during the rolling v2 migration."""
        if self.active_vocal_source_id:
            source = next((s for s in self.sources if s.id == self.active_vocal_source_id), None)
            if source and source.path:
                self.vocal = MediaSlot(source.path, source.label)
        if self.active_reference_id:
            reference = next((r for r in self.references if r.id == self.active_reference_id), None)
            if reference and reference.path:
                self.reference = MediaSlot(reference.path, reference.title)

    def add_source(
        self,
        path: str = "",
        *,
        label: str = "",
        role: str = "Other",
        preserve: bool = False,
        use_in_build: bool = True,
    ) -> SourceSlot:
        slot = SourceSlot(
            path=path,
            label=label or (Path(path).stem if path else role),
            role=role,
            preserve=preserve,
            use_in_build=use_in_build,
        )
        self.sources.append(slot)
        if role.lower() in {"lead vocal", "vocal", "vocals"} and not self.active_vocal_source_id:
            self.active_vocal_source_id = slot.id
        self.sync_legacy_slots()
        self.touch()
        return slot

    def add_reference(
        self,
        *,
        path: str = "",
        youtube_url: str = "",
        title: str = "",
        artist: str = "",
        influence: float = 1.0,
    ) -> ReferenceSlot:
        slot = ReferenceSlot(
            path=path,
            youtube_url=youtube_url,
            title=title or (Path(path).stem if path else "Reference"),
            artist=artist,
            influence=max(0.0, min(1.0, float(influence))),
        )
        self.references.append(slot)
        if not self.active_reference_id:
            self.active_reference_id = slot.id
        self.sync_legacy_slots()
        self.touch()
        return slot

    def primary_vocal_source(self) -> SourceSlot | None:
        return next((s for s in self.sources if s.id == self.active_vocal_source_id), None)

    def primary_reference(self) -> ReferenceSlot | None:
        return next((r for r in self.references if r.id == self.active_reference_id), None)

    def to_dict(self) -> dict[str, Any]:
        self._ensure_v2_slots()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectState":
        data = dict(payload)
        for key in ("vocal", "reference", "finished_song"):
            data[key] = MediaSlot(**(data.get(key, {}) or {}))

        data["sources"] = [
            SourceSlot(**dict(item))
            for item in (data.get("sources", []) or [])
        ]
        data["references"] = [
            ReferenceSlot(**dict(item))
            for item in (data.get("references", []) or [])
        ]
        data["storage"] = StorageSettings(**(data.get("storage", {}) or {}))
        data["versions"] = [
            VersionSnapshot(**dict(item))
            for item in (data.get("versions", []) or [])
        ]

        tracks: list[TrackState] = []
        for raw_track in data.get("tracks", []) or []:
            raw = dict(raw_track)
            raw["clips"] = [
                ClipState(**dict(raw_clip))
                for raw_clip in (raw.get("clips", []) or [])
            ]
            tracks.append(TrackState(**raw))
        data["tracks"] = tracks

        # Ignore future/unknown fields instead of making older builds explode.
        known = cls.__dataclass_fields__
        data = {key: value for key, value in data.items() if key in known}
        data["schema_version"] = max(3, int(data.get("schema_version", 1)))
        state = cls(**data)
        state._ensure_v2_slots()
        return state

    def save(self, path: str | Path) -> Path:
        self.touch()
        self._ensure_v2_slots()
        target = Path(path)
        if target.suffix.lower() != ".drellion":
            target = target.with_suffix(".drellion")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "ProjectState":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
