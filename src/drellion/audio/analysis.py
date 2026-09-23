from __future__ import annotations

from pathlib import Path
import numpy as np
import librosa
import pyloudnorm as pyln

from .contracts import VocalAnalysis, ReferenceAnalysis


def _load(path: str | Path, sr: int = 48000):
    y, rate = librosa.load(str(path), sr=sr, mono=False)
    if y.ndim == 1:
        stereo = np.vstack([y, y])
    else:
        stereo = y[:2]
        if stereo.shape[0] == 1:
            stereo = np.vstack([stereo[0], stereo[0]])
    mono = np.mean(stereo, axis=0)
    return stereo.astype(np.float32), mono.astype(np.float32), rate


def _phrase_regions(mono: np.ndarray, sr: int, hop: int = 512) -> list[tuple[float, float]]:
    rms = librosa.feature.rms(y=mono, frame_length=2048, hop_length=hop)[0]
    if not len(rms):
        return []
    peak = float(np.max(rms))
    if peak <= 1e-8:
        return []
    active = rms > max(peak * 0.06, float(np.percentile(rms, 55)) * 0.55)
    regions: list[tuple[float, float]] = []
    start = None
    for i, on in enumerate(active):
        if on and start is None:
            start = i
        elif not on and start is not None:
            a = start * hop / sr
            b = i * hop / sr
            if b - a >= 0.10:
                regions.append((a, b))
            start = None
    if start is not None:
        a = start * hop / sr
        b = len(active) * hop / sr
        if b - a >= 0.10:
            regions.append((a, b))
    if not regions:
        return []
    merged = [regions[0]]
    for a, b in regions[1:]:
        pa, pb = merged[-1]
        if a - pb < 0.30:
            merged[-1] = (pa, b)
        else:
            merged.append((a, b))
    return merged


def analyze_vocal_file(path: str | Path) -> VocalAnalysis:
    _, mono, sr = _load(path)
    hop = 512
    f0, voiced, _ = librosa.pyin(
        mono,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
        frame_length=2048,
        hop_length=hop,
    )
    times = librosa.times_like(f0, sr=sr, hop_length=hop)
    pitch_track: list[tuple[float, float]] = []
    for t, hz, is_voiced in zip(times, f0, voiced):
        if bool(is_voiced) and np.isfinite(hz):
            pitch_track.append((float(t), float(hz)))
    result = VocalAnalysis(
        duration=float(len(mono) / sr),
        phrase_regions=_phrase_regions(mono, sr, hop),
        pitch_track=pitch_track,
    )
    return result


def _energy_curve(mono: np.ndarray, parts: int = 16) -> list[float]:
    if len(mono) == 0:
        return [0.0] * parts
    chunks = np.array_split(mono, parts)
    values = [float(np.sqrt(np.mean(np.square(x))) if len(x) else 0.0) for x in chunks]
    peak = max(values) or 1.0
    return [v / peak for v in values]


def _safe_lufs(stereo: np.ndarray, sr: int) -> float:
    data = stereo.T
    try:
        meter = pyln.Meter(sr)
        value = float(meter.integrated_loudness(data))
        return value if np.isfinite(value) else -70.0
    except Exception:
        return -70.0


def analyze_reference_file(path: str | Path) -> ReferenceAnalysis:
    stereo, mono, sr = _load(path)
    hop = 512
    onset = librosa.onset.onset_strength(y=mono, sr=sr, hop_length=hop)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop)
    bpm = float(np.atleast_1d(tempo)[0]) if np.size(tempo) else 0.0
    duration = float(len(mono) / sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)
    beat_density = float(len(beat_times) / max(duration, 1e-6))
    onset_times = librosa.onset.onset_detect(onset_envelope=onset, sr=sr, hop_length=hop, units="time")
    onset_density = float(len(onset_times) / max(duration, 1e-6))

    centroid = float(np.mean(librosa.feature.spectral_centroid(y=mono, sr=sr)))
    rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=mono, sr=sr, roll_percent=0.85)))
    flatness = float(np.mean(librosa.feature.spectral_flatness(y=mono)))
    rms = librosa.feature.rms(y=mono)[0]
    dyn = float(np.percentile(librosa.amplitude_to_db(np.maximum(rms, 1e-8), ref=1.0), 90) - np.percentile(librosa.amplitude_to_db(np.maximum(rms, 1e-8), ref=1.0), 10))

    mid = (stereo[0] + stereo[1]) * 0.5
    side = (stereo[0] - stereo[1]) * 0.5
    mid_rms = float(np.sqrt(np.mean(mid * mid)) + 1e-9)
    side_rms = float(np.sqrt(np.mean(side * side)) + 1e-9)
    side_mid_db = float(20.0 * np.log10(side_rms / mid_rms))

    return ReferenceAnalysis(
        bpm=bpm,
        duration=duration,
        energy_curve=_energy_curve(mono, 16),
        groove={
            "beat_density": beat_density,
            "onset_density": onset_density,
        },
        tone={
            "centroid_hz": centroid,
            "rolloff_hz": rolloff,
            "flatness": flatness,
        },
        stereo={
            "side_mid_db": side_mid_db,
        },
        dynamics={
            "range_db": dyn,
            "lufs": _safe_lufs(stereo, sr),
        },
    )


def vocal_pitch_class(pitch_track: list[tuple[float, float]]) -> int:
    if not pitch_track:
        return 0
    hz = np.array([p[1] for p in pitch_track if p[1] > 0], dtype=float)
    if not len(hz):
        return 0
    midi = np.rint(librosa.hz_to_midi(hz)).astype(int) % 12
    counts = np.bincount(midi, minlength=12)
    return int(np.argmax(counts))
