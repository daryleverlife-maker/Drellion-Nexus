from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))
    roots.extend([
        Path(__file__).resolve().parents[2],
        Path.cwd(),
    ])
    return roots


def find_binary(name: str) -> str:
    exe = name + (".exe" if os.name == "nt" and not name.lower().endswith(".exe") else "")
    for root in _candidate_roots():
        for candidate in (
            root / exe,
            root / "bin" / exe,
            root / "tools" / "ffmpeg" / "bin" / exe,
        ):
            if candidate.is_file():
                return str(candidate)
    return shutil.which(name) or shutil.which(exe) or ""


def ffmpeg() -> str:
    return find_binary("ffmpeg")


def ffprobe() -> str:
    return find_binary("ffprobe")


def require_ffmpeg() -> str:
    path = ffmpeg()
    if not path:
        raise RuntimeError(
            "FFmpeg was not found. Reinstall Drellion Nexus or configure a valid FFmpeg path."
        )
    return path


def require_ffprobe() -> str:
    path = ffprobe()
    if not path:
        raise RuntimeError(
            "FFprobe was not found. Reinstall Drellion Nexus or configure a valid FFmpeg path."
        )
    return path


def media_duration(path: str | Path) -> float:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    result = subprocess.run(
        [
            require_ffprobe(),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:] or "Could not read media duration.")
    try:
        return max(0.0, float(result.stdout.strip()))
    except ValueError as exc:
        raise RuntimeError("FFprobe did not return a valid duration.") from exc
