from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

from .project import ProjectState


def autosave_path(project: ProjectState) -> Path:
    return project.folder("Autosaves") / "Recovery.drellion"


def write_autosave(project: ProjectState) -> Path:
    project.ensure_layout()
    path = autosave_path(project)
    payload = project.to_dict()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _normalized(payload: dict) -> dict:
    data = dict(payload)
    data.pop("updated_at", None)
    return data


def newer_autosave(project_file: str | Path) -> Path | None:
    project_file = Path(project_file)
    if not project_file.exists():
        return None
    try:
        saved = json.loads(project_file.read_text(encoding="utf-8"))
        root = Path(saved.get("root") or project_file.parent)
        recovery = root / "Autosaves" / "Recovery.drellion"
        if not recovery.exists() or recovery.stat().st_mtime <= project_file.stat().st_mtime:
            return None
        recovered = json.loads(recovery.read_text(encoding="utf-8"))
        if _normalized(saved) == _normalized(recovered):
            return None
        return recovery
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def load_autosave(path: str | Path) -> ProjectState:
    return ProjectState.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def clear_autosave(project: ProjectState) -> None:
    path = autosave_path(project)
    if path.exists():
        path.unlink()


def autosave_timestamp(project: ProjectState) -> datetime | None:
    path = autosave_path(project)
    return datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else None
