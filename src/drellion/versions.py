from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import re

from .project import ProjectState, VersionSnapshot
from .storage import ensure_project_folders


def _safe(value: str) -> str:
    clean = re.sub(r'[^A-Za-z0-9._ -]+', '_', value or 'Snapshot').strip()
    return clean or 'Snapshot'


def create_version(
    project: ProjectState,
    label: str,
    *,
    project_path: str | Path | None = None,
    note: str = '',
) -> Path:
    folders = ensure_project_folders(project, project_path)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    meta = VersionSnapshot(label=label or 'Snapshot', note=note)
    project.versions.append(meta)
    snapshot = deepcopy(project)
    target = folders.versions / f'{stamp} - {_safe(label)}.drellion'
    snapshot.save(target)
    project.touch()
    return target


def list_versions(project: ProjectState, project_path: str | Path | None = None) -> list[Path]:
    folders = ensure_project_folders(project, project_path)
    return sorted(folders.versions.glob('*.drellion'), key=lambda p: p.stat().st_mtime, reverse=True)


def load_version(path: str | Path) -> ProjectState:
    return ProjectState.load(path)
