from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import math
import subprocess
import json

from .audio.contracts import ReferenceAnalysis
from .audio.mix_analysis import analyze_mix_file
from .audio.runtime import require_ffmpeg


@dataclass
class QualityMetric:
    name: str
    passed: bool
    value: float
    target: str
    detail: str = ""


@dataclass
class PreviewQualityReport:
    path: str
    passed: bool
    metrics: list[QualityMetric]

    def to_dict(self):
        return {"path": self.path, "passed": self.passed, "metrics": [asdict(x) for x in self.metrics]}


def _astats(path: str | Path) -> dict[str, float]:
    cmd = [require_ffmpeg(), "-hide_banner", "-nostats", "-i", str(path), "-af",
           "astats=metadata=1:reset=0,ametadata=print:file=-", "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    text = result.stdout + "\n" + result.stderr
    values: dict[str, float] = {}
    for line in text.splitlines():
        if "lavfi.astats.Overall." not in line or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        key = key.split("lavfi.astats.Overall.", 1)[-1].strip()
        try:
            values[key] = float(raw.strip())
        except ValueError:
            pass
    return values


def evaluate_preview(path: str | Path, reference: ReferenceAnalysis | None = None) -> PreviewQualityReport:
    p = Path(path)
    stats = _astats(p)
    analysis = analyze_mix_file(p)

    peak = stats.get("Peak_level", -120.0)
    rms = stats.get("RMS_level", -120.0)
    crest = peak - rms if math.isfinite(peak) and math.isfinite(rms) else 99.0
    dynamic = stats.get("Dynamic_range", 0.0)

    bass = float(analysis.tone.get("bass_60_120", -120.0))
    sub = float(analysis.tone.get("sub_20_60", -120.0))
    onset_density = float(analysis.groove.get("onset_density", 0.0))
    correlation = float(analysis.stereo.get("correlation", 1.0))

    metrics = [
        QualityMetric("No clipping", peak <= -0.1, peak, "<= -0.1 dBFS"),
        QualityMetric("Audible level", rms > -35.0, rms, "> -35 dBFS"),
        QualityMetric("Transient life", 3.0 <= crest <= 24.0, crest, "3–24 dB crest"),
        QualityMetric("Dynamic movement", dynamic >= 3.0, dynamic, ">= 3 dB"),
        QualityMetric("Low-end foundation", max(bass, sub) > -18.0, max(bass, sub), "> -18 dB relative band energy"),
        QualityMetric("Rhythmic activity", onset_density >= 0.12, onset_density, ">= 0.12 onsets/sec"),
        QualityMetric("Stereo sanity", correlation >= -0.25, correlation, ">= -0.25 correlation"),
    ]

    if reference is not None:
        ref_bass = max(float(reference.tone.get("bass_60_120", -120.0)), float(reference.tone.get("sub_20_60", -120.0)))
        low_end_deficit = ref_bass - max(bass, sub)
        metrics.append(QualityMetric(
            "Reference-relative low end",
            low_end_deficit <= 12.0,
            low_end_deficit,
            "<= 12 dB below reference",
            "Production may differ from the reference, but should not collapse the low-end foundation.",
        ))

        ref_density = float(reference.groove.get("onset_density", 0.0))
        if ref_density > 0.05:
            ratio = onset_density / ref_density
            metrics.append(QualityMetric(
                "Reference-relative rhythm",
                ratio >= 0.25,
                ratio,
                ">= 25% of reference onset density",
                "This is a structural sanity check, not an instruction to copy the reference beat.",
            ))

    return PreviewQualityReport(str(p), all(x.passed for x in metrics), metrics)


def write_quality_report(report: PreviewQualityReport, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return target
