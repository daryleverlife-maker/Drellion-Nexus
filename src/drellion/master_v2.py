from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from .audio.contracts import ReferenceAnalysis
from .audio.mix_analysis import analyze_mix_file
from .audio.render import master_audio
from .project import ProjectState
from .reference_blend import normalize_references


def _weighted_dict(rows: list[tuple[float, dict[str, float]]]) -> dict[str, float]:
    keys = {key for _, row in rows for key in row}
    result = {}
    for key in keys:
        total = 0.0
        weight = 0.0
        for w, row in rows:
            if key in row:
                total += float(row[key]) * w
                weight += w
        if weight:
            result[key] = total / weight
    return result


def blend_reference_analysis(project: ProjectState) -> ReferenceAnalysis | None:
    blend = normalize_references(project.references)
    analyses: list[tuple[float, ReferenceAnalysis]] = []
    for ref in project.references:
        if ref.id not in blend.weights or not ref.path or not Path(ref.path).is_file():
            continue
        analyses.append((blend.weights[ref.id], analyze_mix_file(ref.path)))
    if not analyses:
        if project.reference.path and Path(project.reference.path).is_file():
            return analyze_mix_file(project.reference.path)
        return None

    bpm = sum(w * a.bpm for w, a in analyses)
    duration = sum(w * a.duration for w, a in analyses)
    length = max((len(a.energy_curve) for _, a in analyses), default=0)
    energy = []
    for index in range(length):
        total = 0.0
        weight = 0.0
        for w, a in analyses:
            if index < len(a.energy_curve):
                total += w * a.energy_curve[index]
                weight += w
        energy.append(total / weight if weight else 0.0)

    return ReferenceAnalysis(
        bpm=bpm,
        duration=duration,
        energy_curve=energy,
        groove=_weighted_dict([(w, a.groove) for w,a in analyses]),
        tone=_weighted_dict([(w, a.tone) for w,a in analyses]),
        stereo=_weighted_dict([(w, a.stereo) for w,a in analyses]),
        dynamics=_weighted_dict([(w, a.dynamics) for w,a in analyses]),
    )


def master_v2(project: ProjectState, output_dir: str | Path) -> str:
    source = project.build_path or project.finished_song.path
    if not source or not Path(source).is_file():
        raise ValueError("Build the song or choose a finished song before mastering.")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    source_analysis = analyze_mix_file(source)
    reference_analysis = blend_reference_analysis(project)
    target_lufs = float(project.settings.get("target_lufs", -14.0))
    result = master_audio(
        source,
        out / "master.wav",
        target_lufs=target_lufs,
        true_peak=float(project.settings.get("true_peak", -1.0)),
        source_analysis=source_analysis,
        reference_analysis=reference_analysis,
        reference_influence="Strong",
        custom_reference_strength=float(project.settings.get("master_reference_strength", 70.0)) / 100.0,
        custom_punch=float(project.settings.get("master_punch", 50.0)) / 100.0,
        custom_width=float(project.settings.get("master_width", 50.0)) / 100.0,
    )
    report = {
        "source": asdict(source_analysis),
        "reference_blend": asdict(reference_analysis) if reference_analysis else None,
        "target_lufs": target_lufs,
        "output": str(result),
    }
    report_path = out / "master-report-v2.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    project.master_path = str(result)
    project.settings["master_report"] = str(report_path)
    project.touch()
    return str(result)
