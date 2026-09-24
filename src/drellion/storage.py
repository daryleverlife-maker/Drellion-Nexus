from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import shutil


def _app_data() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "DrellionNexus"


def default_projects_dir() -> Path:
    return Path.home() / "Music" / "Drellion" / "Projects"


@dataclass
class StorageSettings:
    projects: str = str(default_projects_dir())
    sound_library: str = ""
    ai_models: str = str(Path.home() / "DrellionModels")
    temporary: str = str(_app_data() / "Temp")
    exports_mode: str = "project"
    custom_exports: str = ""

    def ensure(self) -> None:
        for value in (self.projects, self.ai_models, self.temporary):
            if value:
                Path(value).mkdir(parents=True, exist_ok=True)


def settings_path() -> Path:
    path = _app_data() / "storage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_storage_settings() -> StorageSettings:
    path = settings_path()
    if not path.exists():
        settings = StorageSettings()
        settings.ensure()
        return settings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        allowed = StorageSettings.__dataclass_fields__.keys()
        settings = StorageSettings(**{k: v for k, v in data.items() if k in allowed})
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        settings = StorageSettings()
    settings.ensure()
    return settings


def save_storage_settings(settings: StorageSettings) -> Path:
    settings.ensure()
    path = settings_path()
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return path


def folder_size(path: str | Path) -> int:
    root = Path(path)
    total = 0
    if not root.exists():
        return 0
    for p in root.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def free_bytes(path: str | Path) -> int:
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    return shutil.disk_usage(p).free


def format_bytes(value: int) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"
