from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .audio.mix_analysis import analyze_mix_file
from .project import ProjectState


def analyze_project_references(project: ProjectState) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for ref in project.references:
        if not ref.enabled or not ref.path or not Path(ref.path).is_file():
            continue
        analysis = analyze_mix_file(ref.path)
        low_end = max(
            float(analysis.tone.get("sub_20_60", -120.0)),
            float(analysis.tone.get("bass_60_120", -120.0)),
        )
        profiles[ref.id] = {
            "title": ref.title or Path(ref.path).stem,
            "artist": ref.artist,
            "bpm": analysis.bpm,
            "duration": analysis.duration,
            "low_end_db": low_end,
            "stereo_side_mid_db": analysis.stereo.get("side_mid_db"),
            "correlation": analysis.stereo.get("correlation"),
            "integrated_lufs": analysis.dynamics.get("integrated_lufs"),
            "lra": analysis.dynamics.get("lra"),
            "analysis": asdict(analysis),
        }
    project.settings["reference_profiles"] = profiles
    project.touch()
    return profiles
