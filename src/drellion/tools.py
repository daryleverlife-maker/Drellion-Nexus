from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class ToolStatus:
    id: str
    name: str
    available: bool
    command: str = ""
    detail: str = ""


TOOLS = {
    "open_unmix": ("Open-Unmix", "umx"),
    "deepfilternet": ("DeepFilterNet", "deepFilter"),
    "basic_pitch": ("Basic Pitch", "basic-pitch"),
    "whisper": ("Whisper", "whisper"),
}


def tool_statuses() -> list[ToolStatus]:
    output = []
    for tool_id, (name, command) in TOOLS.items():
        location = shutil.which(command)
        output.append(ToolStatus(
            id=tool_id,
            name=name,
            available=bool(location),
            command=location or command,
            detail=location or f"{command} is not installed in PATH.",
        ))
    try:
        import faster_whisper  # noqa: F401
        output.append(ToolStatus("faster_whisper", "faster-whisper", True, "python", "Python package available."))
    except Exception:
        output.append(ToolStatus("faster_whisper", "faster-whisper", False, "python", "Optional Python package not installed."))
    return output


def separate_open_unmix(source: str | Path, output_dir: str | Path, *, model: str = "umxhq") -> list[Path]:
    command = shutil.which("umx")
    if not command:
        raise RuntimeError("Open-Unmix CLI is not installed. Install the optional stem tool first.")
    source = Path(source)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [command, "--model", model, "--outdir", str(root), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:] or result.stdout[-5000:] or "Open-Unmix failed.")
    outputs = [p for p in root.rglob("*") if p.suffix.lower() in {".wav", ".flac"}]
    if not outputs:
        raise RuntimeError("Open-Unmix completed but no stem files were found.")
    return sorted(outputs)


def clean_vocal_deepfilter(source: str | Path, output_dir: str | Path) -> Path:
    command = shutil.which("deepFilter")
    if not command:
        raise RuntimeError("DeepFilterNet CLI is not installed.")
    source = Path(source)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    before = {p.resolve() for p in root.glob("*") if p.is_file()}
    result = subprocess.run(
        [command, "--output-dir", str(root), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:] or result.stdout[-5000:] or "DeepFilterNet failed.")
    candidates = [p for p in root.glob("*") if p.is_file() and p.resolve() not in before]
    if not candidates:
        candidates = list(root.glob("*"))
    if not candidates:
        raise RuntimeError("DeepFilterNet completed but no enhanced file was found.")
    return max(candidates, key=lambda p: p.stat().st_mtime_ns)


def audio_to_midi(source: str | Path, output_dir: str | Path) -> Path:
    command = shutil.which("basic-pitch")
    if not command:
        raise RuntimeError("Basic Pitch CLI is not installed.")
    source = Path(source)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [command, str(root), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:] or result.stdout[-5000:] or "Basic Pitch failed.")
    midi = list(root.glob("*.mid")) + list(root.glob("*.midi"))
    if not midi:
        raise RuntimeError("Basic Pitch completed but no MIDI file was found.")
    return max(midi, key=lambda p: p.stat().st_mtime_ns)
