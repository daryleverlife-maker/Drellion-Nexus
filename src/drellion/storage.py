from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import shutil


@dataclass
class StorageSettings:
    projects: str
    sound_library: str
    models: str
    cache: str
    exports: str = ""

    @classmethod
    def defaults(cls):
        home = Path.home()
        base = home / "Music" / "Drellion Nexus"
        return cls(
            projects=str(base / "Projects"),
            sound_library=str(base / "Sound Library"),
            models=str(base / "Models"),
            cache=str(Path.home() / ".drellion" / "cache"),
            exports="",
        )

    def ensure(self):
        for value in (self.projects, self.sound_library, self.models, self.cache):
            Path(value).mkdir(parents=True, exist_ok=True)

    def usage(self) -> dict[str, int]:
        result = {}
        for key, value in asdict(self).items():
            if not value:
                result[key] = 0
                continue
            root = Path(value)
            total = 0
            if root.exists():
                for path in root.rglob("*"):
                    try:
                        if path.is_file():
                            total += path.stat().st_size
                    except OSError:
                        pass
            result[key] = total
        return result


    def save(self, path: str | Path):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path):
        source = Path(path)
        if not source.exists():
            return cls.defaults()
        try:
            return cls(**json.loads(source.read_text(encoding="utf-8")))
        except Exception:
            return cls.defaults()

    def free_bytes(self, path: str | None = None) -> int:
        root = Path(path or self.projects)
        root.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(root).free
