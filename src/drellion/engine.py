from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

from .project import ProjectState
from .audio.analysis import analyze_reference_file, analyze_vocal_file
from .audio.contracts import ArrangementPreview, ReferenceAnalysis, VocalAnalysis
from .audio.render import master_audio, mix_vocal_and_instrumental
from .audio.synthesis import synthesize_instrumental


@dataclass
class BuildResult:
    build_path: str
    instrumental_path: str = ""
    report_path: str = ""


class NexusEngine:
    """Stable boundary between the UI/project model and local audio backends."""

    def analyze_vocal(self, state: ProjectState) -> VocalAnalysis:
        if not state.vocal.path:
            raise ValueError("A vocal stem is required for vocal-first generation.")
        return analyze_vocal_file(state.vocal.path)

    def analyze_reference(self, state: ProjectState) -> ReferenceAnalysis:
        if not state.reference.path:
            raise ValueError("A reference track is required.")
        return analyze_reference_file(state.reference.path)

    @staticmethod
    def _variant_from_selection(selection: str) -> int:
        text = (selection or "").strip().lower()
        if text.endswith("b"):
            return 1
        if text.endswith("c"):
            return 2
        return 0

    def generate_previews(
        self, state: ProjectState, output_dir: str | Path
    ) -> list[ArrangementPreview]:
        vocal = self.analyze_vocal(state)
        reference = self.analyze_reference(state)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        preview_duration = min(28.0, max(4.0, vocal.duration))
        vocal_start = 0.0
        if vocal.phrase_regions:
            vocal_start = max(0.0, vocal.phrase_regions[0][0] - 0.5)

        previews: list[ArrangementPreview] = []
        descriptions = (
            "Punch-first: fewer kicks, wider spaces, restrained hats.",
            "Drive-first: denser kick movement and more active hats.",
            "Contrast-first: syncopated accents and stronger transition energy.",
        )

        for variant, name in enumerate(("Preview A", "Preview B", "Preview C")):
            instrumental = synthesize_instrumental(
                out / f"preview-{variant + 1}-instrumental.wav",
                preview_duration,
                reference.bpm or 90.0,
                reference.energy_curve,
                variant=variant,
            )
            mixed = mix_vocal_and_instrumental(
                state.vocal.path,
                instrumental,
                out / f"preview-{variant + 1}.wav",
                vocal_start=vocal_start,
                duration=preview_duration,
            )
            previews.append(
                ArrangementPreview(
                    name=name,
                    audio_path=str(mixed),
                    description=descriptions[variant],
                    similarity={
                        "reference_bpm": reference.bpm or 90.0,
                        "energy_guidance": 1.0,
                        "exact_reference_hits_reused": 0.0,
                    },
                )
            )

        manifest = out / "previews.json"
        manifest.write_text(
            json.dumps([asdict(item) for item in previews], indent=2),
            encoding="utf-8",
        )
        return previews

    def build(self, state: ProjectState, output_dir: str | Path) -> BuildResult:
        vocal = self.analyze_vocal(state)
        reference = self.analyze_reference(state)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        variant = self._variant_from_selection(state.selected_preview)
        duration = max(1.0, vocal.duration)

        instrumental = synthesize_instrumental(
            out / "generated-instrumental.wav",
            duration,
            reference.bpm or 90.0,
            reference.energy_curve,
            variant=variant,
        )
        build_path = mix_vocal_and_instrumental(
            state.vocal.path,
            instrumental,
            out / "build.wav",
            duration=duration,
        )

        report = {
            "engine": "drellion-local-alpha",
            "vocal": asdict(vocal),
            "reference": asdict(reference),
            "selected_preview": state.selected_preview or "Preview A",
            "generation": {
                "reference_audio_copied": False,
                "reference_exact_onsets_copied": False,
                "reference_melody_copied": False,
                "instrumental_is_newly_generated": True,
            },
            "outputs": {
                "instrumental": str(instrumental),
                "build": str(build_path),
            },
        }
        report_path = out / "report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        return BuildResult(
            build_path=str(build_path),
            instrumental_path=str(instrumental),
            report_path=str(report_path),
        )

    def master(self, state: ProjectState, output_dir: str | Path) -> str:
        source = state.build_path or state.finished_song.path
        if not source:
            raise ValueError("Build the song or choose a finished song before mastering.")

        target_lufs = float(state.settings.get("target_lufs", -14.0))
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        mastered = master_audio(
            source,
            out / "master.wav",
            target_lufs=target_lufs,
            true_peak=-1.0,
        )
        return str(mastered)
