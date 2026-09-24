from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from .project import ProjectState


FOLDERS = (
    "Sources",
    "References",
    "Stems",
    "Generated",
    "Previews",
    "Masters",
    "Exports",
    "Lyrics",
    "Autosaves",
    "Versions",
    "Cache",
)


def safe_name(value: str) -> str:
    clean = re.sub(r'[^A-Za-z0-9._ -]+', '_', value or 'Untitled').strip()
    return clean or 'Untitled'


@dataclass(frozen=True)
class ProjectFolders:
    root: Path
    project_file: Path
    sources: Path
    references: Path
    stems: Path
    generated: Path
    previews: Path
    masters: Path
    exports: Path
    lyrics: Path
    autosaves: Path
    versions: Path
    cache: Path


def project_folders(state: ProjectState, project_path: str | Path | None = None) -> ProjectFolders:
    if project_path:
        project_file = Path(project_path)
        root = project_file.parent
    else:
        configured = (state.storage.project_root or '').strip()
        base = Path(configured).expanduser() if configured else Path.home() / 'Drellion Nexus' / 'Projects'
        root = base / safe_name(state.name)
        project_file = root / f'{safe_name(state.name)}.drellion'

    mapping = {name.lower(): root / name for name in FOLDERS}
    return ProjectFolders(
        root=root,
        project_file=project_file,
        sources=mapping['sources'],
        references=mapping['references'],
        stems=mapping['stems'],
        generated=mapping['generated'],
        previews=mapping['previews'],
        masters=mapping['masters'],
        exports=mapping['exports'],
        lyrics=mapping['lyrics'],
        autosaves=mapping['autosaves'],
        versions=mapping['versions'],
        cache=mapping['cache'],
    )


def ensure_project_folders(state: ProjectState, project_path: str | Path | None = None) -> ProjectFolders:
    folders = project_folders(state, project_path)
    folders.root.mkdir(parents=True, exist_ok=True)
    for name in FOLDERS:
        (folders.root / name).mkdir(parents=True, exist_ok=True)
    return folders


def disk_space(path: str | Path) -> tuple[int, int, int]:
    p = Path(path).expanduser()
    probe = p if p.exists() else p.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe)


def consolidate_file(source: str | Path, destination_dir: str | Path) -> Path:
    src = Path(source)
    if not src.is_file():
        raise FileNotFoundError(src)
    dest_dir = Path(destination_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / src.name
    if target.resolve() == src.resolve():
        return target
    if target.exists():
        stem, suffix = target.stem, target.suffix
        index = 2
        while target.exists():
            target = dest_dir / f'{stem} ({index}){suffix}'
            index += 1
    shutil.copy2(src, target)
    return target
