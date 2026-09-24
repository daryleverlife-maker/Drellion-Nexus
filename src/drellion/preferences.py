from __future__ import annotations

from pathlib import Path
from typing import Any
import json


DEFAULTS: dict[str, Any] = {
    "project_root": str(Path.home() / "Drellion Nexus" / "Projects"),
    "export_root": "",
    "sound_library_root": "",
    "model_root": str(Path.home() / "Drellion Nexus" / "Models"),
    "cache_root": str(Path.home() / "Drellion Nexus" / "Cache"),
    "generation_provider": "auto",
    "provider_ace_step_url": "http://127.0.0.1:8001",
    "provider_diff_rhythm_url": "",
    "provider_yue_url": "",
    "autosave_enabled": True,
    "autosave_seconds": 120,
    "consolidate_imports": True,
    "accessibility": {},
}


def preferences_path() -> Path:
    root = Path.home() / "Drellion Nexus"
    root.mkdir(parents=True, exist_ok=True)
    return root / "preferences.json"


def load_preferences() -> dict[str, Any]:
    result = dict(DEFAULTS)
    path = preferences_path()
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                result.update(payload)
        except Exception:
            pass
    return result


def save_preferences(values: dict[str, Any]) -> Path:
    payload = dict(DEFAULTS)
    payload.update(values)
    path = preferences_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def apply_preferences_to_project(project, values: dict[str, Any]) -> None:
    project.storage.project_root = str(values.get("project_root", "") or "")
    project.storage.export_root = str(values.get("export_root", "") or "")
    project.storage.sound_library_root = str(values.get("sound_library_root", "") or "")
    project.storage.model_root = str(values.get("model_root", "") or "")
    project.storage.cache_root = str(values.get("cache_root", "") or "")
    if project.storage.sound_library_root and not project.sound_library_path:
        project.sound_library_path = project.storage.sound_library_root
    for key in (
        "generation_provider", "provider_ace_step_url", "provider_diff_rhythm_url",
        "provider_yue_url", "autosave_enabled", "consolidate_imports",
    ):
        if key in values:
            project.settings.setdefault(key, values[key])
    if values.get("accessibility"):
        project.settings.setdefault("accessibility", dict(values["accessibility"]))
