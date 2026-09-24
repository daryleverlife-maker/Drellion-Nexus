from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import math

import numpy as np

from .audio_core import mono, read_wav, rms


@dataclass
class Phrase:
    start: float
    end: float
    rms: float


@dataclass
class VocalAnalysis:
    duration_seconds: float
    phrase_count: int
    phrases: list[dict]
    voiced_ratio: float
    pitch_median_hz: float | None
    pitch_low_hz: float | None
    pitch_high_hz: float | None
    pitch_confidence: float
    peak_dbfs: float
    rms_dbfs: float

    def to_dict(self) -> dict:
        return asdict(self)


def _db(v: float) -> float:
    return -120.0 if v <= 1e-12 else 20 * math.log10(v)


def _pitch_fft_autocorr(frame: np.ndarray, sr: int, min_hz: float = 70.0, max_hz: float = 1000.0) -> tuple[float | None, float]:
    x = frame.astype(np.float64)
    x -= x.mean()
    energy = float(np.dot(x, x))
    if energy < 1e-7:
        return None, 0.0
    window = np.hanning(len(x))
    x *= window
    size = 1 << int(math.ceil(math.log2(max(2, len(x) * 2 - 1))))
    spec = np.fft.rfft(x, size)
    ac = np.fft.irfft(spec * np.conj(spec), size)[:len(x)]
    if ac[0] <= 1e-12:
        return None, 0.0
    min_lag = max(1, int(sr / max_hz))
    max_lag = min(len(ac) - 1, int(sr / min_hz))
    if max_lag <= min_lag:
        return None, 0.0
    region = ac[min_lag:max_lag + 1]
    lag = int(np.argmax(region)) + min_lag
    confidence = float(ac[lag] / ac[0])
    if confidence < 0.20:
        return None, max(0.0, confidence)
    return float(sr / lag), max(0.0, min(1.0, confidence))


def analyze_vocal(path: str | Path) -> VocalAnalysis:
    audio = read_wav(path)
    x = mono(audio.samples)
    sr = audio.sample_rate
    if len(x) == 0:
        return VocalAnalysis(0.0, 0, [], 0.0, None, None, None, 0.0, -120.0, -120.0)
    frame_seconds = 0.04
    hop_seconds = 0.02
    frame = max(256, int(sr * frame_seconds))
    hop = max(128, int(sr * hop_seconds))
    starts = list(range(0, max(1, len(x) - frame + 1), hop))
    levels = []
    for start in starts:
        chunk = x[start:start + frame]
        levels.append(rms(chunk))
    levels_arr = np.asarray(levels, dtype=np.float64)
    noise = float(np.percentile(levels_arr, 25)) if len(levels_arr) else 0.0
    active_threshold = max(noise * 2.5, 0.008)
    active = levels_arr >= active_threshold
    max_gap_frames = max(1, int(0.22 / hop_seconds))
    for i in range(1, len(active) - 1):
        if active[i]:
            continue
        left = i - 1
        while left >= 0 and not active[left] and i - left <= max_gap_frames:
            left -= 1
        right = i + 1
        while right < len(active) and not active[right] and right - i <= max_gap_frames:
            right += 1
        if left >= 0 and right < len(active) and active[left] and active[right] and right - left - 1 <= max_gap_frames:
            active[left + 1:right] = True
    phrases: list[Phrase] = []
    i = 0
    while i < len(active):
        if not active[i]:
            i += 1
            continue
        start_i = i
        while i + 1 < len(active) and active[i + 1]:
            i += 1
        end_i = i
        start_s = starts[start_i] / sr
        end_s = min(audio.duration, (starts[end_i] + frame) / sr)
        if end_s - start_s >= 0.12:
            segment = x[int(start_s * sr):int(end_s * sr)]
            phrases.append(Phrase(start_s, end_s, rms(segment)))
        i += 1
    pitches: list[float] = []
    confidences: list[float] = []
    analysis_frame = max(1024, int(sr * 0.06))
    pitch_hop = max(1, int(sr * 0.08))
    for start in range(0, min(len(x), sr * 720) - analysis_frame + 1, pitch_hop):
        chunk = x[start:start + analysis_frame]
        if rms(chunk) < active_threshold:
            continue
        hz, conf = _pitch_fft_autocorr(chunk, sr)
        if hz is not None:
            pitches.append(hz)
            confidences.append(conf)
    peak = float(np.max(np.abs(x)))
    all_rms = rms(x)
    if pitches:
        q10, median, q90 = np.percentile(np.asarray(pitches), [10, 50, 90])
        pmed, plow, phigh = float(median), float(q10), float(q90)
        confidence = float(np.mean(confidences))
    else:
        pmed = plow = phigh = None
        confidence = 0.0
    return VocalAnalysis(
        duration_seconds=audio.duration,
        phrase_count=len(phrases),
        phrases=[asdict(p) for p in phrases],
        voiced_ratio=float(np.mean(active)) if len(active) else 0.0,
        pitch_median_hz=pmed,
        pitch_low_hz=plow,
        pitch_high_hz=phigh,
        pitch_confidence=confidence,
        peak_dbfs=_db(peak),
        rms_dbfs=_db(all_rms),
    )
