from __future__ import annotations
from pathlib import Path
import json
from .project import ProjectState


def autosave_path(project_path, recovery_root):
    root = Path(recovery_root)
    root.mkdir(parents=True, exist_ok=True)
    stem = Path(project_path).stem if project_path else "Untitled"
    return root / f"{stem}.drellion.autosave"


def write_autosave(state: ProjectState, project_path, recovery_root):
    target = autosave_path(project_path, recovery_root)
    state.touch()
    target.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    return target


def newer_autosave(project_path, recovery_root):
    target = autosave_path(project_path, recovery_root)
    if not target.is_file():
        return None
    if not project_path:
        return target
    saved = Path(project_path)
    if not saved.is_file():
        return target
    try:
        if target.stat().st_mtime <= saved.stat().st_mtime:
            return None
        saved_payload = json.loads(saved.read_text(encoding="utf-8"))
        recovery_payload = json.loads(target.read_text(encoding="utf-8"))
        saved_payload.pop("updated_at", None)
        recovery_payload.pop("updated_at", None)
        return target if saved_payload != recovery_payload else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def load_autosave(path) -> ProjectState:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ProjectState.from_dict(payload)


def clear_autosave(project_path, recovery_root) -> bool:
    target = autosave_path(project_path, recovery_root)
    if not target.exists():
        return False
    try:
        target.unlink()
        return True
    except OSError:
        return False
