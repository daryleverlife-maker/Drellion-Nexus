from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .audio.contracts import ArrangementPreview
from .engine import BuildResult, NexusEngine
from .project import ProjectState


@dataclass
class AutoResult:
    state: ProjectState
    previews: list[ArrangementPreview]
    chosen_preview: str
    build: BuildResult
    master_path: str


def _choose_preview(previews: list[ArrangementPreview]) -> ArrangementPreview:
    if not previews:
        raise ValueError("No arrangement previews were generated.")

    def score(preview: ArrangementPreview) -> tuple[float, str]:
        reference_bpm = float(preview.similarity.get("reference_bpm", 0.0) or 0.0)
        generated_bpm = float(preview.similarity.get("generated_bpm", 0.0) or 0.0)
        bpm_distance = abs(reference_bpm - generated_bpm)
        return bpm_distance, preview.name

    return min(previews, key=score)


def run_full_auto(
    source_state: ProjectState,
    output_dir: str | Path,
    *,
    engine: NexusEngine | None = None,
) -> AutoResult:
    """Run the complete local AI Auto pipeline on a project-state copy."""
    state = deepcopy(source_state)
    engine = engine or NexusEngine()
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    if not state.vocal.path:
        raise ValueError("AI Auto needs a vocal stem.")
    if not state.reference.path:
        raise ValueError("AI Auto needs a reference track.")

    previews = engine.generate_previews(state, root / "Previews")
    chosen = _choose_preview(previews)
    state.selected_preview = chosen.name

    # Auto mode uses a conservative subset of lyric-aware SFX. Users can still
    # replace or clear every event later in Preview or Custom Studio.
    suggestions = engine.smart_sfx(state)
    selected_sfx = []
    for suggestion in suggestions[:8]:
        if not suggestion.options:
            continue
        selected_sfx.append(
            {
                "time": float(suggestion.time),
                "path": str(suggestion.options[0]),
                "gain_db": -12.0,
                "lyric": suggestion.lyric,
                "reason": suggestion.reason,
            }
        )
    state.settings["selected_sfx"] = selected_sfx

    build = engine.build(state, root / "Build")
    state.build_path = build.build_path
    state.settings["generated_instrumental"] = build.instrumental_path
    state.settings["build_report"] = build.report_path
    state.settings["lyrics_lrc"] = build.lyric_path

    master_path = engine.master(state, root / "Master")
    state.master_path = master_path
    state.settings["auto_last_run"] = {
        "chosen_preview": chosen.name,
        "preview_count": len(previews),
        "smart_sfx_count": len(selected_sfx),
    }
    state.touch()

    return AutoResult(
        state=state,
        previews=previews,
        chosen_preview=chosen.name,
        build=build,
        master_path=master_path,
    )
