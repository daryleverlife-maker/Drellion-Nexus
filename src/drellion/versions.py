from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time

from .project import ProjectState


@dataclass
class VersionEntry:
    path: Path
    label: str
    created_at: float


def create_snapshot(project: ProjectState, label: str = "") -> Path:
    folders = project.ensure_layout()
    versions = folders["versions"]
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in (label or "Snapshot")).strip()
    path = versions / f"{timestamp} - {safe}.drellion"
    project.save(path)
    return path


def list_snapshots(project: ProjectState) -> list[VersionEntry]:
    if not project.project_root:
        return []
    folder = Path(project.project_root) / "Versions"
    if not folder.is_dir():
        return []
    result = []
    for path in sorted(folder.glob("*.drellion"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            created = float(payload.get("updated_at", path.stat().st_mtime))
        except Exception:
            created = path.stat().st_mtime
        label = path.stem.split(" - ", 1)[-1]
        result.append(VersionEntry(path, label, created))
    return result
