from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import copy
import json
import os
import shutil
import uuid

PROJECT_SCHEMA = 4
PROJECT_FILENAME = "Project.drellion"
PROJECT_FOLDERS = (
    "Sources", "References", "Stems", "Generated", "Previews", "Masters",
    "Exports", "Lyrics", "Autosaves", "Versions", "Cache",
)
AUTO_SOURCE_LIMIT = 6
AUTO_REFERENCE_LIMIT = 6


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _safe_name(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in " .-_" else "_" for c in name).strip(" .")
    return cleaned or "Untitled"


@dataclass
class SourceAsset:
    id: str = field(default_factory=lambda: _id("src"))
    path: str = ""
    label: str = "Source"
    role: str = "Lead Vocal"
    enabled: bool = True
    preserve: bool = True
    rebuild: bool = False
    gain_db: float = 0.0
    duration_seconds: float | None = None
    analysis: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferenceAsset:
    id: str = field(default_factory=lambda: _id("ref"))
    path: str = ""
    youtube_url: str = ""
    title: str = "Reference"
    artist: str = ""
    channel: str = ""
    weight: float = 1.0
    enabled: bool = True
    influences: dict[str, bool] = field(default_factory=lambda: {
        "drums": True, "bass": True, "energy": True, "arrangement": True,
        "tone": True, "stereo": True, "master": True,
    })
    analysis: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedStem:
    id: str = field(default_factory=lambda: _id("stem"))
    role: str = "Instrumental"
    path: str = ""
    engine: str = ""
    engine_version: str = ""
    seed: int | None = None
    source_generation_id: str = ""
    gain_db: float = 0.0
    pan: float = 0.0
    mute: bool = False
    solo: bool = False


@dataclass
class PreviewRecord:
    id: str = field(default_factory=lambda: _id("preview"))
    label: str = "Preview"
    audio_path: str = ""
    instrumental_path: str = ""
    vocal_path: str = ""
    engine: str = ""
    engine_version: str = ""
    seed: int = 0
    prompt: str = ""
    region_start: float = 0.0
    region_duration: float = 25.0
    accepted: bool = False
    qc: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)


@dataclass
class BuildRecord:
    id: str = field(default_factory=lambda: _id("build"))
    label: str = "Build"
    mix_path: str = ""
    instrumental_path: str = ""
    engine: str = ""
    engine_version: str = ""
    seed: int = 0
    prompt: str = ""
    stems: list[GeneratedStem] = field(default_factory=list)
    source_preview_id: str = ""
    created_at: str = field(default_factory=_now)
    starred: bool = False


@dataclass
class MasterRecord:
    id: str = field(default_factory=lambda: _id("master"))
    source_build_id: str = ""
    path: str = ""
    target_lufs: float = -14.0
    target_true_peak: float = -1.0
    engine: str = ""
    measurements: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)


@dataclass
class StudioClip:
    id: str = field(default_factory=lambda: _id("clip"))
    track_id: str = ""
    source_path: str = ""
    label: str = "Clip"
    start_seconds: float = 0.0
    source_offset_seconds: float = 0.0
    duration_seconds: float = 0.0
    gain_db: float = 0.0
    fade_in_seconds: float = 0.0
    fade_out_seconds: float = 0.0
    crossfade_seconds: float = 0.0
    locked: bool = False


@dataclass
class StudioTrack:
    id: str = field(default_factory=lambda: _id("track"))
    name: str = "Track"
    role: str = "Audio"
    volume_db: float = 0.0
    pan: float = 0.0
    mute: bool = False
    solo: bool = False
    clips: list[StudioClip] = field(default_factory=list)


@dataclass
class ProjectState:
    schema_version: int = PROJECT_SCHEMA
    id: str = field(default_factory=lambda: _id("project"))
    title: str = "Untitled"
    artist: str = ""
    root: str = ""
    mode: str = "Vocal / Acapella"
    keep_imported_files: bool = True
    autosave_seconds: int = 120
    create_recovery_versions: bool = True
    keep_generated_versions: bool = True
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    sources: list[SourceAsset] = field(default_factory=list)
    references: list[ReferenceAsset] = field(default_factory=list)
    previews: list[PreviewRecord] = field(default_factory=list)
    selected_preview_id: str = ""
    builds: list[BuildRecord] = field(default_factory=list)
    selected_build_id: str = ""
    masters: list[MasterRecord] = field(default_factory=list)
    selected_master_id: str = ""
    direction: dict[str, Any] = field(default_factory=lambda: {
        "reference_strength": 0.55,
        "cinematic": False,
        "harder": False,
        "cleaner": False,
        "darker": False,
        "notes": "",
    })
    lyrics_text: str = ""
    lyrics_timed: list[dict[str, Any]] = field(default_factory=list)
    engine_preferences: dict[str, Any] = field(default_factory=lambda: {
        "mode": "auto",
        "ace_step_url": "http://127.0.0.1:8001",
        "diffrhythm_url": "",
        "diffrhythm_local": "",
        "explicit_basic_test_engine": False,
    })
    studio_tracks: list[StudioTrack] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def root_path(self) -> Path:
        if not self.root:
            raise ValueError("Project root is not set")
        return Path(self.root)

    @property
    def project_file(self) -> Path:
        return self.root_path / PROJECT_FILENAME

    def folder(self, name: str) -> Path:
        if name not in PROJECT_FOLDERS:
            raise KeyError(name)
        return self.root_path / name

    def ensure_layout(self) -> None:
        self.root_path.mkdir(parents=True, exist_ok=True)
        for name in PROJECT_FOLDERS:
            self.folder(name).mkdir(parents=True, exist_ok=True)

    def touch(self) -> None:
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectState":
        data = _migrate_payload(copy.deepcopy(payload))
        data["sources"] = [SourceAsset(**x) for x in data.get("sources", [])]
        data["references"] = [ReferenceAsset(**x) for x in data.get("references", [])]
        data["previews"] = [PreviewRecord(**x) for x in data.get("previews", [])]
        builds: list[BuildRecord] = []
        for b in data.get("builds", []):
            b = dict(b)
            b["stems"] = [GeneratedStem(**s) for s in b.get("stems", [])]
            builds.append(BuildRecord(**b))
        data["builds"] = builds
        data["masters"] = [MasterRecord(**x) for x in data.get("masters", [])]
        tracks: list[StudioTrack] = []
        for t in data.get("studio_tracks", []):
            t = dict(t)
            t["clips"] = [StudioClip(**c) for c in t.get("clips", [])]
            tracks.append(StudioTrack(**t))
        data["studio_tracks"] = tracks
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        clean = {k: v for k, v in data.items() if k in allowed}
        return cls(**clean)

    def save(self, path: str | Path | None = None) -> Path:
        self.ensure_layout()
        self.touch()
        target = Path(path) if path else self.project_file
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, target)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "ProjectState":
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        project = cls.from_dict(payload)
        if not project.root:
            project.root = str(path.parent)
        project.ensure_layout()
        return project

    @classmethod
    def create(
        cls,
        parent: str | Path,
        title: str,
        artist: str = "",
        mode: str = "Vocal / Acapella",
        keep_imported_files: bool = True,
    ) -> "ProjectState":
        root = Path(parent) / _safe_name(title)
        suffix = 2
        candidate = root
        while candidate.exists() and any(candidate.iterdir()):
            candidate = root.with_name(f"{root.name} {suffix}")
            suffix += 1
        project = cls(title=title or "Untitled", artist=artist, root=str(candidate), mode=mode, keep_imported_files=keep_imported_files)
        project.ensure_layout()
        project.save()
        return project

    def add_source(
        self,
        path: str | Path,
        role: str = "Lead Vocal",
        label: str | None = None,
        preserve: bool = True,
        rebuild: bool = False,
        studio_mode: bool = False,
    ) -> SourceAsset:
        if not studio_mode and len(self.sources) >= AUTO_SOURCE_LIMIT:
            raise ValueError(f"Auto mode supports up to {AUTO_SOURCE_LIMIT} sources")
        src = Path(path)
        stored = self._ingest(src, "Sources") if self.keep_imported_files else src
        asset = SourceAsset(path=str(stored), label=label or src.stem, role=role, preserve=preserve, rebuild=rebuild)
        self.sources.append(asset)
        self.touch()
        return asset

    def add_reference(
        self,
        path: str | Path | None = None,
        youtube_url: str = "",
        title: str = "Reference",
        artist: str = "",
        weight: float = 1.0,
        studio_mode: bool = False,
    ) -> ReferenceAsset:
        if not studio_mode and len(self.references) >= AUTO_REFERENCE_LIMIT:
            raise ValueError(f"Auto mode supports up to {AUTO_REFERENCE_LIMIT} references")
        stored = ""
        if path:
            src = Path(path)
            stored = str(self._ingest(src, "References") if self.keep_imported_files else src)
            if title == "Reference":
                title = src.stem
        ref = ReferenceAsset(path=stored, youtube_url=youtube_url, title=title, artist=artist, weight=float(weight))
        self.references.append(ref)
        self.normalize_reference_weights()
        self.touch()
        return ref

    def remove_source(self, source_id: str) -> bool:
        before = len(self.sources)
        self.sources = [s for s in self.sources if s.id != source_id]
        changed = len(self.sources) != before
        if changed:
            self.touch()
        return changed

    def remove_reference(self, reference_id: str) -> bool:
        before = len(self.references)
        self.references = [r for r in self.references if r.id != reference_id]
        changed = len(self.references) != before
        if changed:
            self.normalize_reference_weights()
            self.touch()
        return changed

    def replace_source(self, source_id: str, new_path: str | Path) -> SourceAsset:
        source = self.source(source_id)
        src = Path(new_path)
        source.path = str(self._ingest(src, "Sources") if self.keep_imported_files else src)
        source.label = src.stem
        self.touch()
        return source

    def replace_reference(self, reference_id: str, new_path: str | Path) -> ReferenceAsset:
        ref = self.reference(reference_id)
        src = Path(new_path)
        ref.path = str(self._ingest(src, "References") if self.keep_imported_files else src)
        self.touch()
        return ref

    def source(self, source_id: str) -> SourceAsset:
        return next(s for s in self.sources if s.id == source_id)

    def reference(self, reference_id: str) -> ReferenceAsset:
        return next(r for r in self.references if r.id == reference_id)

    def selected_preview(self) -> PreviewRecord | None:
        return next((x for x in self.previews if x.id == self.selected_preview_id), None)

    def selected_build(self) -> BuildRecord | None:
        return next((x for x in self.builds if x.id == self.selected_build_id), None)

    def selected_master(self) -> MasterRecord | None:
        return next((x for x in self.masters if x.id == self.selected_master_id), None)

    def normalize_reference_weights(self) -> None:
        enabled = [r for r in self.references if r.enabled]
        total = sum(max(0.0, r.weight) for r in enabled)
        if not enabled:
            return
        if total <= 0:
            each = 1.0 / len(enabled)
            for r in enabled:
                r.weight = each
        else:
            for r in enabled:
                r.weight = max(0.0, r.weight) / total

    def consolidate_imported_media(self) -> dict[str, int]:
        counts = {"sources": 0, "references": 0}
        for source in self.sources:
            if source.path:
                before = Path(source.path)
                after = self._ingest(before, "Sources")
                if after != before:
                    source.path = str(after)
                    counts["sources"] += 1
        for ref in self.references:
            if ref.path:
                before = Path(ref.path)
                after = self._ingest(before, "References")
                if after != before:
                    ref.path = str(after)
                    counts["references"] += 1
        if sum(counts.values()):
            self.touch()
        return counts

    def relink_missing(self, search_roots: Iterable[str | Path]) -> list[tuple[str, str]]:
        roots = [Path(p) for p in search_roots if Path(p).exists()]
        fixed: list[tuple[str, str]] = []
        assets: list[tuple[str, Any]] = [("source", s) for s in self.sources] + [("reference", r) for r in self.references if r.path]
        for kind, asset in assets:
            old = Path(asset.path)
            if old.exists():
                continue
            filename = old.name
            candidates: list[Path] = []
            for root in roots:
                try:
                    candidates.extend(p for p in root.rglob(filename) if p.is_file())
                except OSError:
                    continue
            if candidates:
                best = min(candidates, key=lambda p: len(str(p)))
                asset.path = str(best)
                fixed.append((kind, str(best)))
        if fixed:
            self.touch()
        return fixed

    def save_as(self, new_root: str | Path) -> "ProjectState":
        target = Path(new_root)
        target.mkdir(parents=True, exist_ok=True)
        clone = ProjectState.from_dict(self.to_dict())
        clone.id = _id("project")
        clone.root = str(target)
        clone.created_at = _now()
        clone.updated_at = _now()
        clone.ensure_layout()
        for folder in ("Sources", "References", "Stems", "Generated", "Previews", "Masters", "Lyrics"):
            src_dir = self.root_path / folder
            dst_dir = clone.root_path / folder
            if src_dir.exists():
                shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
        clone._rebase_media_paths(self.root_path, clone.root_path)
        clone.save()
        return clone

    def save_copy(self, target_file: str | Path) -> Path:
        target = Path(target_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return target

    def _rebase_media_paths(self, old_root: Path, new_root: Path) -> None:
        def rebase(value: str) -> str:
            if not value:
                return value
            try:
                rel = Path(value).resolve().relative_to(old_root.resolve())
                return str(new_root / rel)
            except (ValueError, OSError):
                return value
        for s in self.sources:
            s.path = rebase(s.path)
        for r in self.references:
            r.path = rebase(r.path)
        for p in self.previews:
            p.audio_path = rebase(p.audio_path)
            p.instrumental_path = rebase(p.instrumental_path)
            p.vocal_path = rebase(p.vocal_path)
        for b in self.builds:
            b.mix_path = rebase(b.mix_path)
            b.instrumental_path = rebase(b.instrumental_path)
            for stem in b.stems:
                stem.path = rebase(stem.path)
        for m in self.masters:
            m.path = rebase(m.path)

    def _ingest(self, source: Path, folder: str) -> Path:
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(source)
        self.ensure_layout()
        destination_dir = self.folder(folder)
        try:
            source.resolve().relative_to(destination_dir.resolve())
            return source
        except ValueError:
            pass
        stem = _safe_name(source.stem)
        candidate = destination_dir / f"{stem}{source.suffix.lower()}"
        n = 2
        while candidate.exists():
            try:
                if candidate.samefile(source):
                    return candidate
            except OSError:
                pass
            candidate = destination_dir / f"{stem}-{n}{source.suffix.lower()}"
            n += 1
        shutil.copy2(source, candidate)
        return candidate


def _migrate_payload(data: dict[str, Any]) -> dict[str, Any]:
    version = int(data.get("schema_version", 1))
    if version < 2:
        if data.get("vocal_path") and not data.get("sources"):
            data["sources"] = [{"path": data["vocal_path"], "label": "Lead Vocal", "role": "Lead Vocal", "preserve": True}]
        if data.get("reference_path") and not data.get("references"):
            data["references"] = [{"path": data["reference_path"], "title": "Reference"}]
    if version < 3:
        data.setdefault("engine_preferences", {})
        data.setdefault("studio_tracks", [])
    if version < 4:
        data.setdefault("masters", [])
        data.setdefault("lyrics_timed", [])
    data["schema_version"] = PROJECT_SCHEMA
    return data
