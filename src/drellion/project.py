from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json
import shutil
import time
import uuid


@dataclass
class MediaSlot:
    path: str = ""
    label: str = ""


@dataclass
class SourceAsset:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    path: str = ""
    label: str = ""
    role: str = "Other"
    preserve: bool = False
    rebuild: bool = False
    enabled: bool = True
    gain_db: float = 0.0


@dataclass
class ReferenceAsset:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    path: str = ""
    youtube_url: str = ""
    title: str = ""
    artist: str = ""
    weight: float = 1.0
    enabled: bool = True
    influences: dict[str, float] = field(default_factory=lambda: {
        "drums": 1.0,
        "bass": 1.0,
        "energy": 1.0,
        "arrangement": 1.0,
        "tone": 1.0,
        "stereo": 1.0,
        "master": 1.0,
    })


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
    schema_version: int = 3
    name: str = "Untitled"
    artist: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # v1/v2 compatibility slots
    vocal: MediaSlot = field(default_factory=MediaSlot)
    lyrics: str = ""
    reference: MediaSlot = field(default_factory=MediaSlot)
    finished_song: MediaSlot = field(default_factory=MediaSlot)

    # v2.0 source/reference architecture
    sources: list[SourceAsset] = field(default_factory=list)
    references: list[ReferenceAsset] = field(default_factory=list)
    project_root: str = ""
    export_root: str = ""

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

    def ensure_layout(self, root: str | Path | None = None) -> dict[str, Path]:
        base = Path(root or self.project_root or Path.home() / "Music" / "Drellion Nexus" / "Projects" / self.name)
        self.project_root = str(base)
        folders = {
            "root": base,
            "sources": base / "Sources",
            "references": base / "References",
            "stems": base / "Stems",
            "generated": base / "Generated",
            "previews": base / "Previews",
            "masters": base / "Masters",
            "exports": base / "Exports",
            "lyrics": base / "Lyrics",
            "autosaves": base / "Autosaves",
            "versions": base / "Versions",
        }
        for path in folders.values():
            path.mkdir(parents=True, exist_ok=True)
        if not self.export_root:
            self.export_root = str(folders["exports"])
        return folders

    def add_source(self, path: str = "", role: str = "Other", label: str = "") -> SourceAsset:
        source = SourceAsset(path=path, role=role, label=label or Path(path).stem if path else label)
        self.sources.append(source)
        self.touch()
        return source

    def add_reference(self, *, path: str = "", youtube_url: str = "", title: str = "") -> ReferenceAsset:
        if len(self.references) >= 6 and self.mode == "auto":
            raise ValueError("Auto mode supports up to six references. Use Studio for additional references.")
        reference = ReferenceAsset(path=path, youtube_url=youtube_url, title=title)
        self.references.append(reference)
        self.touch()
        return reference

    def remove_source(self, source_id: str) -> bool:
        before = len(self.sources)
        self.sources = [item for item in self.sources if item.id != source_id]
        changed = len(self.sources) != before
        if changed:
            self.touch()
        return changed

    def remove_reference(self, reference_id: str) -> bool:
        before = len(self.references)
        self.references = [item for item in self.references if item.id != reference_id]
        changed = len(self.references) != before
        if changed:
            self.touch()
        return changed

    def consolidate_imported_media(self) -> dict[str, int]:
        """Copy external source/reference files into the project without deleting originals."""
        folders = self.ensure_layout()
        counts = {"sources": 0, "references": 0}

        def copy_into(raw_path: str, destination: Path, asset_id: str) -> str:
            if not raw_path:
                return raw_path
            source = Path(raw_path)
            if not source.is_file():
                return raw_path
            try:
                if destination.resolve() in source.resolve().parents:
                    return str(source)
            except OSError:
                pass
            destination.mkdir(parents=True, exist_ok=True)
            safe_name = source.name
            target = destination / f"{asset_id[:8]}-{safe_name}"
            if not target.exists() or target.stat().st_size != source.stat().st_size:
                shutil.copy2(source, target)
            return str(target)

        for item in self.sources:
            new_path = copy_into(item.path, folders["sources"], item.id)
            if new_path != item.path:
                item.path = new_path
                counts["sources"] += 1

        for item in self.references:
            new_path = copy_into(item.path, folders["references"], item.id)
            if new_path != item.path:
                item.path = new_path
                counts["references"] += 1

        if counts["sources"] or counts["references"]:
            self.touch()
        return counts

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectState":
        data = dict(payload)
        for key in ("vocal", "reference", "finished_song"):
            data[key] = MediaSlot(**(data.get(key, {}) or {}))

        data["sources"] = [SourceAsset(**dict(item)) for item in (data.get("sources", []) or [])]
        data["references"] = [ReferenceAsset(**dict(item)) for item in (data.get("references", []) or [])]

        tracks: list[TrackState] = []
        for raw_track in data.get("tracks", []) or []:
            raw = dict(raw_track)
            raw["clips"] = [ClipState(**dict(raw_clip)) for raw_clip in (raw.get("clips", []) or [])]
            tracks.append(TrackState(**raw))
        data["tracks"] = tracks

        # Migrate older projects into the v2 source/reference model without deleting legacy fields.
        if not data["sources"] and data["vocal"].path:
            data["sources"].append(SourceAsset(path=data["vocal"].path, label=data["vocal"].label, role="Lead Vocal", preserve=True))
        if not data["references"] and data["reference"].path:
            data["references"].append(ReferenceAsset(path=data["reference"].path, title=data["reference"].label))

        data["schema_version"] = 3
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
