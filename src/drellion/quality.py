from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import math

import numpy as np

from .audio_core import AudioData, dbfs, mono, peak, read_wav, rms


@dataclass
class QCMetrics:
    peak_dbfs: float = -120.0
    rms_dbfs: float = -120.0
    low_energy_ratio: float = 0.0
    transient_density: float = 0.0
    repetition_score: float = 0.0
    stereo_correlation: float = 1.0
    vocal_to_music_db: float | None = None


@dataclass
class QCResult:
    accepted: bool
    metrics: QCMetrics
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "metrics": asdict(self.metrics),
            "checks": self.checks,
            "reasons": self.reasons,
            "warnings": self.warnings,
        }


def _spectral_low_ratio(x: np.ndarray, sample_rate: int) -> float:
    if len(x) < 512:
        return 0.0
    max_n = min(len(x), sample_rate * 60)
    x = x[:max_n]
    window = np.hanning(len(x))
    power = np.abs(np.fft.rfft(x * window)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1.0 / sample_rate)
    total = float(power.sum()) + 1e-12
    return float(power[freqs < 180.0].sum() / total)


def _transient_density(x: np.ndarray, sample_rate: int) -> float:
    if len(x) < sample_rate:
        return 0.0
    hop = max(64, sample_rate // 200)
    count = len(x) // hop
    env = np.array([np.max(np.abs(x[i * hop:(i + 1) * hop])) for i in range(count)], dtype=np.float64)
    if len(env) < 3:
        return 0.0
    delta = np.diff(env, prepend=env[0])
    threshold = max(float(np.median(np.abs(delta))) * 4.0, 0.015)
    events = np.count_nonzero(delta > threshold)
    duration = len(x) / sample_rate
    return float(events / max(duration, 1e-6))


def _repetition_score(x: np.ndarray, sample_rate: int) -> float:
    segment = int(sample_rate * 2.0)
    if len(x) < segment * 3:
        return 0.0
    windows = []
    for start in range(0, min(len(x) - segment + 1, segment * 12), segment):
        w = x[start:start + segment]
        norm = np.linalg.norm(w)
        if norm > 1e-8:
            windows.append(w / norm)
    if len(windows) < 3:
        return 0.0
    similarities = [float(np.dot(a, b)) for a, b in zip(windows, windows[1:])]
    return float(np.mean(np.abs(similarities))) if similarities else 0.0


def _stereo_correlation(audio: AudioData) -> float:
    if audio.channels < 2 or len(audio.samples) < 100:
        return 1.0
    l = audio.samples[:, 0]
    r = audio.samples[:, 1]
    if np.std(l) < 1e-8 or np.std(r) < 1e-8:
        return 1.0
    value = float(np.corrcoef(l, r)[0, 1])
    return value if math.isfinite(value) else 1.0


def evaluate_preview(instrumental_path: str | Path, vocal_path: str | Path | None = None) -> QCResult:
    audio = read_wav(instrumental_path)
    x = mono(audio.samples)
    metrics = QCMetrics(
        peak_dbfs=dbfs(peak(x)),
        rms_dbfs=dbfs(rms(x)),
        low_energy_ratio=_spectral_low_ratio(x, audio.sample_rate),
        transient_density=_transient_density(x, audio.sample_rate),
        repetition_score=_repetition_score(x, audio.sample_rate),
        stereo_correlation=_stereo_correlation(audio),
    )
    if vocal_path and Path(vocal_path).exists() and Path(vocal_path).suffix.lower() == ".wav":
        vocal = read_wav(vocal_path)
        vrms = rms(mono(vocal.samples))
        mrms = rms(x)
        metrics.vocal_to_music_db = dbfs(vrms) - dbfs(mrms)

    checks = {
        "no_clipping": metrics.peak_dbfs <= -0.05,
        "bass_foundation": metrics.low_energy_ratio >= 0.08,
        "drum_activity": metrics.transient_density >= 0.35,
        "not_silent": metrics.rms_dbfs > -45.0,
        "stereo_phase": metrics.stereo_correlation > -0.65,
        "not_excessively_repetitive": metrics.repetition_score < 0.985,
    }
    if metrics.vocal_to_music_db is not None:
        checks["vocal_balance"] = -12.0 <= metrics.vocal_to_music_db <= 18.0
    hard_checks = ("no_clipping", "not_silent", "stereo_phase", "not_excessively_repetitive")
    soft_checks = ("bass_foundation", "drum_activity", "vocal_balance")
    reasons = [name.replace("_", " ") for name in hard_checks if name in checks and not checks[name]]
    warnings = [name.replace("_", " ") for name in soft_checks if name in checks and not checks[name]]
    accepted = all(checks.get(name, True) for name in hard_checks)
    return QCResult(accepted, metrics, checks, reasons, warnings)
