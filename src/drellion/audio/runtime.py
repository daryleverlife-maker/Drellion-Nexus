from __future__ import annotations

from pathlib import Path
import os
import shutil
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
