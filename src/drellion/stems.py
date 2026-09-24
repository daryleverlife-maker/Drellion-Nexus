from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib.util
import shutil
import subprocess


@dataclass(frozen=True)
class SeparationResult:
    engine: str
    stems: dict[str, Path]


class StemSeparator:
    name = "separator"

    def available(self) -> bool:
        raise NotImplementedError

    def split(self, input_path: str | Path, output_dir: str | Path) -> SeparationResult:
        raise NotImplementedError


class OpenUnmixSeparator(StemSeparator):
    name = "Open-Unmix"

    def available(self) -> bool:
        return importlib.util.find_spec("openunmix") is not None

    def split(self, input_path: str | Path, output_dir: str | Path) -> SeparationResult:
        if not self.available():
            raise RuntimeError("Open-Unmix is not installed")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            shutil.which("python") or "python", "-m", "openunmix.predict", str(input_path),
            "--outdir", str(output_dir), "--targets", "vocals", "drums", "bass", "other",
        ], check=True)
        nested = output_dir / Path(input_path).stem
        stems = {role: nested / f"{role}.wav" for role in ("vocals", "drums", "bass", "other")}
        missing = [str(p) for p in stems.values() if not p.exists()]
        if missing:
            raise RuntimeError("Open-Unmix did not create expected stems: " + ", ".join(missing))
        return SeparationResult(self.name, stems)


class SpleeterSeparator(StemSeparator):
    name = "Spleeter"

    def __init__(self, stem_count: int = 5) -> None:
        if stem_count not in (2, 4, 5):
            raise ValueError("Spleeter supports 2, 4, or 5 stems")
        self.stem_count = stem_count

    def available(self) -> bool:
        return importlib.util.find_spec("spleeter") is not None

    def split(self, input_path: str | Path, output_dir: str | Path) -> SeparationResult:
        if not self.available():
            raise RuntimeError("Spleeter is not installed")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            shutil.which("python") or "python", "-m", "spleeter", "separate",
            "-p", f"spleeter:{self.stem_count}stems", "-o", str(output_dir), str(input_path),
        ], check=True)
        nested = output_dir / Path(input_path).stem
        roles = ["vocals", "accompaniment"] if self.stem_count == 2 else ["vocals", "drums", "bass", "other"]
        if self.stem_count == 5:
            roles = ["vocals", "drums", "bass", "piano", "other"]
        stems = {role: nested / f"{role}.wav" for role in roles}
        return SeparationResult(self.name, stems)


def best_available_separator(prefer_five: bool = True) -> StemSeparator | None:
    openunmix = OpenUnmixSeparator()
    if openunmix.available():
        return openunmix
    spleeter = SpleeterSeparator(5 if prefer_five else 4)
    return spleeter if spleeter.available() else None
