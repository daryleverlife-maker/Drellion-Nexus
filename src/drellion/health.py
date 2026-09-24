from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shutil

from .autosave import newer_autosave
from .project import ProjectState
from .providers import EngineBroker


@dataclass(frozen=True)
class HealthItem:
    name: str
    ok: bool
    detail: str = ""
    severity: str = "error"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProjectHealth:
    items: list[HealthItem]

    @property
    def ready(self) -> bool:
        return all(x.ok or x.severity == "warning" for x in self.items)

    def to_dict(self) -> dict:
        return {"ready": self.ready, "items": [x.to_dict() for x in self.items]}


def check_project(project: ProjectState, broker: EngineBroker | None = None) -> ProjectHealth:
    items: list[HealthItem] = []
    project.ensure_layout()
    source_missing = [s.label for s in project.sources if s.enabled and (not s.path or not Path(s.path).exists())]
    items.append(HealthItem("Sources", not source_missing and bool(project.sources), "Missing: " + ", ".join(source_missing) if source_missing else f"{len(project.sources)} configured"))
    ref_missing = [r.title for r in project.references if r.enabled and r.path and not Path(r.path).exists()]
    items.append(HealthItem("References", not ref_missing, "Missing local audio: " + ", ".join(ref_missing) if ref_missing else f"{len(project.references)} configured", severity="warning"))
    if broker:
        statuses = broker.statuses()
        production_ready = [s for s in statuses if s.ready and s.name != "Basic Test Engine"]
        detail = "; ".join(f"{s.name}: {'Ready' if s.ready else s.detail}" for s in statuses)
        items.append(HealthItem("AI engine", bool(production_ready), detail))
    free = shutil.disk_usage(project.root_path).free
    items.append(HealthItem("Disk space", free >= 2 * 1024**3, f"{free / 1024**3:.1f} GB free", severity="warning" if free < 10 * 1024**3 else "error"))
    recovery = newer_autosave(project.project_file) if project.project_file.exists() else None
    items.append(HealthItem("Autosave", recovery is None, "Newer recovery exists" if recovery else "No unresolved recovery", severity="warning"))
    broken_stems = []
    for build in project.builds:
        for stem in build.stems:
            if stem.path and not Path(stem.path).exists():
                broken_stems.append(stem.role)
    items.append(HealthItem("Generated stems", not broken_stems, "Missing: " + ", ".join(broken_stems) if broken_stems else "OK"))
    selected = project.selected_build()
    items.append(HealthItem("Build", bool(selected and Path(selected.mix_path).exists()), selected.label if selected else "No selected build", severity="warning"))
    master = project.selected_master()
    items.append(HealthItem("Master", bool(master and Path(master.path).exists()), "Ready" if master else "Not mastered", severity="warning"))
    export_ready = bool(master and Path(master.path).exists()) or bool(selected and Path(selected.mix_path).exists())
    items.append(HealthItem("Export readiness", export_ready, "Ready" if export_ready else "Build or master required", severity="warning"))
    return ProjectHealth(items)
