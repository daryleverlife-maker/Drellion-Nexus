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
