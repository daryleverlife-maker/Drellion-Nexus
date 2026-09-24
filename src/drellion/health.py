from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .providers import ProviderBroker, ProviderState
from .storage import disk_space, ensure_project_folders
from .tools import tool_statuses


@dataclass(frozen=True)
class HealthItem:
    name: str
    ok: bool
    detail: str
    warning: bool = False


def project_health(project, project_path=None) -> list[HealthItem]:
    project._ensure_v2_slots()
    items: list[HealthItem] = []
    vocal = project.primary_vocal_source()
    items.append(HealthItem(
        "Lead vocal",
        bool(vocal and vocal.path and Path(vocal.path).is_file()),
        vocal.path if vocal and vocal.path else "No lead vocal loaded.",
    ))

    enabled_refs = [r for r in project.references if r.enabled and (r.path or r.youtube_url)]
    local_refs = [r for r in enabled_refs if r.path and Path(r.path).is_file()]
    items.append(HealthItem(
        "References",
        bool(enabled_refs),
        f"{len(enabled_refs)} enabled · {len(local_refs)} local audio reference(s)",
    ))

    broker = ProviderBroker()
    statuses = broker.statuses(project.settings)
    ready = [item for item in statuses if item.state == ProviderState.READY and item.id != "basic_test"]
    items.append(HealthItem(
        "Production AI",
        bool(ready),
        ", ".join(item.name for item in ready) if ready else "No production-quality provider is ready.",
    ))

    sounds = Path(project.sound_library_path) if project.sound_library_path else None
    items.append(HealthItem(
        "Sound library",
        bool(sounds and sounds.is_dir()),
        str(sounds) if sounds else "No library folder selected.",
        warning=not bool(sounds and sounds.is_dir()),
    ))

    folders = ensure_project_folders(project, project_path)
    free = disk_space(folders.root).free
    items.append(HealthItem(
        "Disk space",
        free >= 10 * 1024**3,
        f"{free / 1024**3:.1f} GB free",
        warning=free < 25 * 1024**3,
    ))

    missing = []
    for source in project.sources:
        if source.path and not Path(source.path).is_file():
            missing.append(source.path)
    for reference in project.references:
        if reference.path and not Path(reference.path).is_file():
            missing.append(reference.path)
    items.append(HealthItem(
        "Media links",
        not missing,
        "All linked media found." if not missing else f"{len(missing)} missing file(s).",
    ))

    tools = tool_statuses()
    available = [tool.name for tool in tools if tool.available]
    items.append(HealthItem(
        "Optional tools",
        True,
        ", ".join(available) if available else "No optional analysis/stem tools installed.",
        warning=not bool(available),
    ))
    return items
