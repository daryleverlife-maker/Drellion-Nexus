from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path

from .audio.mix_analysis import analyze_mix_file


@dataclass
class QualityCheck:
    name: str
    passed: bool
    value: float | str
    detail: str


@dataclass
class QualityReport:
    path: str
    passed: bool
    score: float
    checks: list[QualityCheck] = field(default_factory=list)

    @property
    def failures(self) -> list[QualityCheck]:
        return [item for item in self.checks if not item.passed]


def _linear(db: float) -> float:
    return 10.0 ** (db / 10.0)


def inspect_preview(path: str | Path) -> QualityReport:
    analysis = analyze_mix_file(path)
    tone = analysis.tone
    dynamics = analysis.dynamics
    groove = analysis.groove

    low = _linear(tone.get('sub_20_60', -120.0)) + _linear(tone.get('bass_60_120', -120.0))
    audible = sum(_linear(value) for value in tone.values()) or 1.0
    low_ratio = low / audible

    peak = float(dynamics.get('sample_peak_dbfs', -120.0))
    lufs = float(dynamics.get('integrated_lufs', -120.0))
    onset_density = float(groove.get('onset_density', 0.0) or 0.0)
    energy = analysis.energy_curve or []
    energy_spread = max(energy) - min(energy) if energy else 0.0

    checks = [
        QualityCheck(
            'No clipping',
            peak <= -0.05,
            round(peak, 2),
            'Sample peak should remain below digital full scale.',
        ),
        QualityCheck(
            'Useful low-end foundation',
            low_ratio >= 0.12,
            round(low_ratio, 3),
            'Preview needs enough sub/bass energy to read as a complete production.',
        ),
        QualityCheck(
            'Rhythmic activity',
            onset_density >= 0.45,
            round(onset_density, 3),
            'Too little transient activity usually means the beat is not carrying the track.',
        ),
        QualityCheck(
            'Audible render',
            lufs > -32.0,
            round(lufs, 2),
            'Very quiet previews are rejected before user review.',
        ),
        QualityCheck(
            'Section movement',
            energy_spread >= 0.08,
            round(energy_spread, 3),
            'A near-flat energy curve suggests an overly repetitive arrangement.',
        ),
    ]
    passed_count = sum(1 for item in checks if item.passed)
    score = 100.0 * passed_count / max(1, len(checks))
    return QualityReport(
        path=str(path),
        passed=all(item.passed for item in checks),
        score=round(score, 1),
        checks=checks,
    )
