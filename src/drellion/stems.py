from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


@dataclass
class StemEngineStatus:
    id: str
    name: str
    available: bool
    detail: str


class StemEngine:
    id = "base"
    name = "Stem Engine"
    def status(self) -> StemEngineStatus:
        return StemEngineStatus(self.id, self.name, False, "Not implemented")
    def separate(self, source: str | Path, output_dir: str | Path) -> dict[str, str]:
        raise NotImplementedError


class SpleeterEngine(StemEngine):
    id = "spleeter"
    name = "Spleeter"

    def status(self):
        command = shutil.which("spleeter")
        return StemEngineStatus(self.id, self.name, bool(command), command or "spleeter command not installed")

    def separate(self, source, output_dir):
        source = Path(source); output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
        command = shutil.which("spleeter")
        if not command: raise RuntimeError("Spleeter is not installed.")
        result = subprocess.run([command, "separate", "-p", "spleeter:4stems", "-o", str(output_dir), str(source)], capture_output=True, text=True)
        if result.returncode: raise RuntimeError(result.stderr[-4000:])
        folder = output_dir / source.stem
        roles = {"vocals":"vocals.wav","drums":"drums.wav","bass":"bass.wav","other":"other.wav"}
        return {role:str(folder/name) for role,name in roles.items() if (folder/name).is_file()}


class OpenUnmixEngine(StemEngine):
    id = "open-unmix"
    name = "Open-Unmix"

    def status(self):
        command = shutil.which("umx")
        return StemEngineStatus(self.id, self.name, bool(command), command or "umx command not installed")

    def separate(self, source, output_dir):
        source = Path(source); output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
        command = shutil.which("umx")
        if not command: raise RuntimeError("Open-Unmix is not installed.")
        result = subprocess.run([command, str(source), "--outdir", str(output_dir)], capture_output=True, text=True)
        if result.returncode: raise RuntimeError(result.stderr[-4000:])
        folder = output_dir / source.stem
        result_paths = {}
        for role in ("vocals","drums","bass","other"):
            path = folder / f"{role}.wav"
            if path.is_file(): result_paths[role]=str(path)
        return result_paths


def available_stem_engines():
    engines = [OpenUnmixEngine(), SpleeterEngine()]
    return [(engine, engine.status()) for engine in engines]
