from __future__ import annotations

from pathlib import Path
import json
import math
import re
import subprocess

import numpy as np

from .analysis import analyze_reference_file
from .contracts import ReferenceAnalysis
from .runtime import require_ffmpeg


BANDS = (
    ("sub_20_60", 20.0, 60.0),
    ("bass_60_120", 60.0, 120.0),
    ("lowmid_120_250", 120.0, 250.0),
    ("mid_250_500", 250.0, 500.0),
    ("mid_500_1000", 500.0, 1000.0),
    ("presence_1_2k", 1000.0, 2000.0),
    ("presence_2_4k", 2000.0, 4000.0),
    ("high_4_8k", 4000.0, 8000.0),
    ("air_8_11k", 8000.0, 11000.0),
)


def _decode_stereo(path: str | Path, sample_rate: int = 22050) -> np.ndarray:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)

    result = subprocess.run(
        [
            require_ffmpeg(),
            "-v", "error",
            "-i", str(source),
            "-vn",
            "-ac", "2",
            "-ar", str(sample_rate),
            "-f", "f32le",
            "pipe:1",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.decode("utf-8", errors="replace")[-4000:]
            or "Could not decode audio for mix analysis."
        )

    values = np.frombuffer(result.stdout, dtype="<f4")
    if values.size < 2:
        raise ValueError("Audio contains no decodable stereo samples.")
    if values.size % 2:
        values = values[:-1]
    return values.reshape(-1, 2)


def _spectral_profile(stereo: np.ndarray, sample_rate: int = 22050) -> dict[str, float]:
    mono = stereo.mean(axis=1, dtype=np.float32)
    n_fft = 4096
    if mono.size < n_fft:
        mono = np.pad(mono, (0, n_fft - mono.size))

    window = np.hanning(n_fft).astype(np.float32)
    hop = n_fft // 2
    possible = max(1, 1 + (mono.size - n_fft) // hop)
    stride = max(1, possible // 600)

    power = np.zeros(n_fft // 2 + 1, dtype=np.float64)
    used = 0
    for frame_index in range(0, possible, stride):
        start = frame_index * hop
        frame = mono[start:start + n_fft]
        if frame.size < n_fft:
            break
        spectrum = np.fft.rfft(frame * window)
        power += np.abs(spectrum) ** 2
        used += 1

    if not used or float(power.sum()) <= 1e-20:
        return {name: -120.0 for name, _, _ in BANDS}

    frequencies = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)
    total = float(power.sum()) + 1e-20
    result: dict[str, float] = {}
    for name, low, high in BANDS:
        mask = (frequencies >= low) & (frequencies < min(high, sample_rate / 2.0))
        band_power = float(power[mask].sum()) if np.any(mask) else 0.0
        result[name] = 10.0 * math.log10((band_power + 1e-20) / total)
    return result


def _stereo_profile(stereo: np.ndarray) -> dict[str, float]:
    left = stereo[:, 0].astype(np.float64)
    right = stereo[:, 1].astype(np.float64)
    mid = (left + right) * 0.5
    side = (left - right) * 0.5

    mid_rms = math.sqrt(float(np.mean(mid * mid)) + 1e-20)
    side_rms = math.sqrt(float(np.mean(side * side)) + 1e-20)
    side_mid_db = 20.0 * math.log10((side_rms + 1e-12) / (mid_rms + 1e-12))

    denom = math.sqrt(float(np.dot(left, left) * np.dot(right, right))) + 1e-20
    correlation = float(np.dot(left, right) / denom)
    return {
        "side_mid_db": side_mid_db,
        "correlation": max(-1.0, min(1.0, correlation)),
    }


def _dynamic_profile(stereo: np.ndarray, sample_rate: int = 22050) -> dict[str, float]:
    mono = stereo.mean(axis=1, dtype=np.float64)
    frame = max(1, round(sample_rate * 0.4))
    hop = max(1, round(sample_rate * 0.2))
    values = []
    for start in range(0, max(1, mono.size - frame + 1), hop):
        block = mono[start:start + frame]
        if not block.size:
            continue
        rms = math.sqrt(float(np.mean(block * block)) + 1e-20)
        values.append(20.0 * math.log10(rms + 1e-12))

    if values:
        arr = np.asarray(values, dtype=np.float64)
        p10 = float(np.percentile(arr, 10))
        p95 = float(np.percentile(arr, 95))
        mean_db = float(np.mean(arr))
        range_db = p95 - p10
    else:
        mean_db = -120.0
        range_db = 0.0

    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    peak_dbfs = 20.0 * math.log10(peak + 1e-12)
    return {
        "frame_mean_dbfs": mean_db,
        "range_db": range_db,
        "sample_peak_dbfs": peak_dbfs,
    }


def _number(value, fallback: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else fallback
    except (TypeError, ValueError):
        return fallback


def measure_loudness(path: str | Path) -> dict[str, float]:
    result = subprocess.run(
        [
            require_ffmpeg(),
            "-hide_banner",
            "-nostats",
            "-i", str(path),
            "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
            "-f", "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    text = result.stderr
    blocks = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", text, flags=re.DOTALL)
    if not blocks:
        return {}
    try:
        data = json.loads(blocks[-1])
    except json.JSONDecodeError:
        return {}
    return {
        "integrated_lufs": _number(data.get("input_i"), -120.0),
        "true_peak_dbtp": _number(data.get("input_tp"), 0.0),
        "lra": _number(data.get("input_lra"), 0.0),
        "threshold_lufs": _number(data.get("input_thresh"), -120.0),
    }


def analyze_mix_file(path: str | Path) -> ReferenceAnalysis:
    base = analyze_reference_file(path)
    stereo = _decode_stereo(path)
    dynamics = _dynamic_profile(stereo)
    dynamics.update(measure_loudness(path))

    return ReferenceAnalysis(
        bpm=base.bpm,
        duration=base.duration,
        energy_curve=base.energy_curve,
        groove=base.groove,
        tone=_spectral_profile(stereo),
        stereo=_stereo_profile(stereo),
        dynamics=dynamics,
    )
