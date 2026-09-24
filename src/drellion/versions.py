from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re

from .project import ProjectState


def create_snapshot(project: ProjectState, name: str) -> Path:
    project.ensure_layout()
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip() or "Snapshot"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = project.folder("Versions") / f"{stamp}-{safe}.drellion"
    path.write_text(json.dumps(project.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def list_snapshots(project: ProjectState) -> list[Path]:
    project.ensure_layout()
    return sorted(project.folder("Versions").glob("*.drellion"), key=lambda p: p.stat().st_mtime, reverse=True)


def restore_snapshot(path: str | Path) -> ProjectState:
    return ProjectState.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
