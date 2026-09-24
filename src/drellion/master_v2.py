from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math
import shutil
import subprocess

import numpy as np

from .audio_core import dbfs, peak, read_wav, rms, write_wav


@dataclass(frozen=True)
class MasterMeasurements:
    peak_dbfs: float
    rms_dbfs: float
    loudness_lufs: float | None = None
    true_peak_dbtp: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def basic_measure(path: str | Path) -> MasterMeasurements:
    audio = read_wav(path)
    return MasterMeasurements(peak_dbfs=dbfs(peak(audio.samples)), rms_dbfs=dbfs(rms(audio.samples)))


def ffmpeg_path() -> str | None:
    bundled = Path(__file__).resolve().parents[2] / "bin" / ("ffmpeg.exe" if __import__("os").name == "nt" else "ffmpeg")
    return str(bundled) if bundled.exists() else shutil.which("ffmpeg")


def _extract_loudnorm_json(stderr: str) -> dict:
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(stderr[start:end + 1])
    except json.JSONDecodeError:
        return {}


def measure_ffmpeg(path: str | Path) -> MasterMeasurements:
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        return basic_measure(path)
    proc = subprocess.run([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
        "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-",
    ], capture_output=True, text=True)
    payload = _extract_loudnorm_json(proc.stderr)
    base = basic_measure(path)
    try:
        lufs = float(payload.get("input_i"))
    except (TypeError, ValueError):
        lufs = None
    try:
        tp = float(payload.get("input_tp"))
    except (TypeError, ValueError):
        tp = None
    return MasterMeasurements(base.peak_dbfs, base.rms_dbfs, lufs, tp)


def master_wav(input_path: str | Path, output_path: str | Path, target_lufs: float = -14.0, target_true_peak: float = -1.0) -> tuple[Path, str, MasterMeasurements]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_path()
    if ffmpeg:
        proc = subprocess.run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(input_path),
            "-af", f"loudnorm=I={target_lufs}:TP={target_true_peak}:LRA=11",
            "-ar", "48000", "-c:a", "pcm_s24le", str(output),
        ], capture_output=True, text=True)
        if proc.returncode == 0 and output.exists():
            return output, "FFmpeg EBU R128 loudnorm", measure_ffmpeg(output)
    audio = read_wav(input_path)
    p = peak(audio.samples)
    target_peak_linear = 10.0 ** (target_true_peak / 20.0)
    gain = target_peak_linear / max(p, 1e-9)
    gain = min(gain, 10.0 ** (12.0 / 20.0))
    samples = np.clip(audio.samples * gain, -target_peak_linear, target_peak_linear)
    write_wav(output, samples, audio.sample_rate)
    return output, "Safe PCM peak normalizer (FFmpeg unavailable)", basic_measure(output)
