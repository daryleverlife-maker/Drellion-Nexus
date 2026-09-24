from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from .project import ProjectState


@dataclass
class HealthItem:
    name: str
    ok: bool
    detail: str


def check_project(project: ProjectState) -> list[HealthItem]:
    items: list[HealthItem] = []
    active_sources = [s for s in project.sources if s.enabled and s.path]
    valid_sources = [s for s in active_sources if Path(s.path).is_file()]
    items.append(HealthItem("Sources", bool(valid_sources), f"{len(valid_sources)} of {len(active_sources)} available"))

    active_refs = [r for r in project.references if r.enabled and (r.path or r.youtube_url)]
    missing_local = [r for r in active_refs if r.path and not Path(r.path).is_file()]
    items.append(HealthItem("References", not missing_local and bool(active_refs), f"{len(active_refs)} configured; {len(missing_local)} missing local files"))

    library = Path(project.sound_library_path) if project.sound_library_path else None
    items.append(HealthItem("Sound library", bool(library and library.is_dir()), str(library or "Not configured")))

    root = Path(project.project_root) if project.project_root else Path.home()
    try:
        free = shutil.disk_usage(root if root.exists() else Path.home()).free
        items.append(HealthItem("Disk space", free >= 10 * 1024**3, f"{free / 1024**3:.1f} GB free"))
    except OSError as exc:
        items.append(HealthItem("Disk space", False, str(exc)))

    if project.build_path:
        items.append(HealthItem("Build", Path(project.build_path).is_file(), project.build_path))
    if project.master_path:
        items.append(HealthItem("Master", Path(project.master_path).is_file(), project.master_path))
    return items
