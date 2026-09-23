from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

from .project import ProjectState
from .audio.analysis import analyze_reference_file, analyze_vocal_file, dominant_vocal_pitch_class
from .audio.contracts import ArrangementPreview, ReferenceAnalysis, VocalAnalysis
from .audio.render import master_audio, mix_vocal_and_instrumental
from .audio.synthesis import synthesize_instrumental
from .lyrics import align_lyrics, to_lrc
from .library import SoundLibrary, SoundPalette


@dataclass
class BuildResult:
    build_path: str
    instrumental_path: str = ""
    report_path: str = ""
    lyric_path: str = ""


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
    def _reference_guidance(state: ProjectState, reference: ReferenceAnalysis, variant: int = 0) -> tuple[float, list[float]]:
        influence = (state.reference_influence or "Strong").strip().lower()
        influence_weight = {"light": 0.35, "balanced": 0.65, "strong": 1.0}.get(influence, 1.0)

        reference_bpm = reference.bpm or 90.0
        bpm = 90.0 + (reference_bpm - 90.0) * influence_weight

        originality = (state.originality_protection or "Maximum").strip().lower()
        variation = {"standard": 0.0, "high": 0.006, "maximum": 0.012}.get(originality, 0.012)
        direction = (-1.0, 0.5, 1.0)[variant % 3]
        bpm *= 1.0 + direction * variation

        guided_energy = [
            0.72 * (1.0 - influence_weight) + value * influence_weight
            for value in (reference.energy_curve or [0.72] * 12)
        ]
        return max(60.0, min(180.0, bpm)), guided_energy

    @staticmethod
    def _palette(state: ProjectState, variant: int) -> SoundPalette:
        root = (state.sound_library_path or "").strip()
        if not root:
            return SoundPalette()
        library = SoundLibrary(root)
        library.scan()
        return library.pick_palette(variant)

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
        pitch_class = dominant_vocal_pitch_class(vocal.pitch_track)
        tonic_midi = 48 + (pitch_class if pitch_class is not None else 0)
        descriptions = (
            "Punch-first: fewer kicks, wider spaces, restrained hats.",
            "Drive-first: denser kick movement and more active hats.",
            "Contrast-first: syncopated accents and stronger transition energy.",
        )

        for variant, name in enumerate(("Preview A", "Preview B", "Preview C")):
            bpm, guided_energy = self._reference_guidance(state, reference, variant)
            palette = self._palette(state, variant)
            instrumental = synthesize_instrumental(
                out / f"preview-{variant + 1}-instrumental.wav",
                preview_duration,
                bpm,
                guided_energy,
                variant=variant,
                tonic_midi=tonic_midi,
                sample_paths=palette.sample_paths(),
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
                    description=(
                        descriptions[variant]
                        + (" Library drums are active." if palette.sample_paths() else " Synthetic fallback drums are active.")
                    ),
                    similarity={
                        "reference_bpm": reference.bpm or 90.0,
                        "generated_bpm": bpm,
                        "energy_guidance": {"Light": 0.35, "Balanced": 0.65, "Strong": 1.0}.get(state.reference_influence, 1.0),
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
        pitch_class = dominant_vocal_pitch_class(vocal.pitch_track)
        tonic_midi = 48 + (pitch_class if pitch_class is not None else 0)
        bpm, guided_energy = self._reference_guidance(state, reference, variant)
        palette = self._palette(state, variant)

        instrumental = synthesize_instrumental(
            out / "generated-instrumental.wav",
            duration,
            bpm,
            guided_energy,
            variant=variant,
            tonic_midi=tonic_midi,
            sample_paths=palette.sample_paths(),
        )
        build_path = mix_vocal_and_instrumental(
            state.vocal.path,
            instrumental,
            out / "build.wav",
            duration=duration,
        )

        lyric_cues = align_lyrics(state.lyrics, vocal.phrase_regions, vocal.duration)
        lyric_path = ""
        if lyric_cues:
            lrc = out / "lyrics.lrc"
            lrc.write_text(to_lrc(lyric_cues), encoding="utf-8")
            lyric_path = str(lrc)

        report = {
            "engine": "drellion-local-alpha",
            "vocal": asdict(vocal),
            "reference": asdict(reference),
            "selected_preview": state.selected_preview or "Preview A",
            "lyrics": {
                "cue_count": len(lyric_cues),
                "cues": [asdict(cue) for cue in lyric_cues],
                "lrc_path": lyric_path,
            },
            "generation": {
                "reference_audio_copied": False,
                "reference_exact_onsets_copied": False,
                "reference_melody_copied": False,
                "instrumental_is_newly_generated": True,
                "vocal_pitch_class": pitch_class,
                "generated_tonic_midi": tonic_midi,
                "generated_bpm": bpm,
                "reference_influence": state.reference_influence,
                "originality_protection": state.originality_protection,
                "sound_palette": palette.to_dict(),
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
            lyric_path=lyric_path,
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
