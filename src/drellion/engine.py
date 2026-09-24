from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

from .project import ProjectState
from .audio.analysis import analyze_vocal_file, dominant_vocal_pitch_class
from .audio.mix_analysis import analyze_mix_file
from .audio.contracts import ArrangementPreview, ReferenceAnalysis, VocalAnalysis
from .audio.render import master_audio, mix_sfx_events, mix_vocal_and_instrumental
from .audio.synthesis import synthesize_instrumental
from .providers import ProviderBroker, AceStepProvider, BasicTestProvider
from .qc import inspect_preview
from .audio.vocal import process_vocal
from .lyrics import align_lyrics, to_lrc
from .library import SoundLibrary, SoundPalette
from .sfx import SfxSuggestion, suggest_sfx
from .tools import separate_open_unmix, tool_statuses


@dataclass
class BuildResult:
    build_path: str
    instrumental_path: str = ""
    report_path: str = ""
    lyric_path: str = ""
    stem_paths: list[str] | None = None


class NexusEngine:
    """Stable boundary between the UI/project model and local audio backends."""

    def __init__(self):
        self._vocal_cache: dict[tuple, VocalAnalysis] = {}
        self._mix_cache: dict[tuple, ReferenceAnalysis] = {}
        self.providers = ProviderBroker()

    @staticmethod
    def _file_key(path: str) -> tuple:
        source = Path(path).resolve()
        stat = source.stat()
        return (str(source), stat.st_size, stat.st_mtime_ns)

    def analyze_vocal(self, state: ProjectState) -> VocalAnalysis:
        if not state.vocal.path:
            raise ValueError("A vocal stem is required for vocal-first generation.")
        key = self._file_key(state.vocal.path)
        if key not in self._vocal_cache:
            self._vocal_cache[key] = analyze_vocal_file(state.vocal.path)
        return self._vocal_cache[key]

    def analyze_mix(self, path: str) -> ReferenceAnalysis:
        key = self._file_key(path)
        if key not in self._mix_cache:
            self._mix_cache[key] = analyze_mix_file(path)
        return self._mix_cache[key]

    def analyze_reference(self, state: ProjectState) -> ReferenceAnalysis:
        if not state.reference.path:
            raise ValueError("A reference track is required.")
        return self.analyze_mix(state.reference.path)

    @staticmethod
    def _reference_guidance(state: ProjectState, reference: ReferenceAnalysis, variant: int = 0) -> tuple[float, list[float]]:
        influence = (state.reference_influence or "Strong").strip().lower()
        preset_weight = {"light": 0.35, "balanced": 0.65, "strong": 1.0}.get(influence, 1.0)

        custom_overall = float(state.settings.get("reference_strength", round(preset_weight * 100))) / 100.0
        custom_groove = float(state.settings.get("groove_strength", round(custom_overall * 100))) / 100.0
        custom_energy = float(state.settings.get("energy_strength", round(custom_overall * 100))) / 100.0
        overall = max(0.0, min(1.0, custom_overall))
        groove_weight = max(0.0, min(1.0, custom_groove))
        energy_weight = max(0.0, min(1.0, custom_energy))

        reference_bpm = reference.bpm or 90.0
        bpm = 90.0 + (reference_bpm - 90.0) * groove_weight

        originality = (state.originality_protection or "Maximum").strip().lower()
        variation = {"standard": 0.0, "high": 0.006, "maximum": 0.012}.get(originality, 0.012)
        direction = (-1.0, 0.5, 1.0)[variant % 3]
        bpm *= 1.0 + direction * variation

        guided_energy = [
            0.72 * (1.0 - energy_weight) + value * energy_weight
            for value in (reference.energy_curve or [0.72] * 12)
        ]
        state.settings["effective_reference_strength"] = round(overall, 4)
        state.settings["effective_groove_strength"] = round(groove_weight, 4)
        state.settings["effective_energy_strength"] = round(energy_weight, 4)
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

    def _enabled_references(self, state: ProjectState):
        state._ensure_v2_slots()
        return [item for item in state.references if item.enabled and (item.path or item.youtube_url)]

    def _reference_for_audio(self, state: ProjectState):
        references = [item for item in self._enabled_references(state) if item.path and Path(item.path).is_file()]
        if not references:
            return None
        return max(references, key=lambda item: float(item.influence))

    def _blended_reference(self, state: ProjectState) -> ReferenceAnalysis:
        references = [item for item in self._enabled_references(state) if item.path and Path(item.path).is_file()]
        if not references:
            if state.reference.path:
                return self.analyze_reference(state)
            return ReferenceAnalysis(bpm=90.0, energy_curve=[0.72] * 12)

        analyses = []
        for item in references:
            analysis = self.analyze_mix(item.path)
            item.analysis = asdict(analysis)
            analyses.append((item, analysis))

        def weight(item, role: str) -> float:
            return max(0.0, float(item.influence)) * max(0.0, float(item.roles.get(role, 1.0)))

        bpm_pairs = [
            (weight(item, 'drums'), analysis.bpm)
            for item, analysis in analyses
            if analysis.bpm > 0 and weight(item, 'drums') > 0
        ]
        bpm_total = sum(w for w, _ in bpm_pairs)
        bpm = sum(w * value for w, value in bpm_pairs) / bpm_total if bpm_total else 90.0

        curve_len = max((len(a.energy_curve) for _, a in analyses), default=12)
        curve = []
        for index in range(curve_len):
            value = 0.0
            weight_sum = 0.0
            for item, analysis in analyses:
                w = weight(item, 'energy')
                if analysis.energy_curve and w > 0:
                    src_index = min(len(analysis.energy_curve) - 1, int(index * len(analysis.energy_curve) / curve_len))
                    value += w * analysis.energy_curve[src_index]
                    weight_sum += w
            curve.append(value / weight_sum if weight_sum else 0.72)

        def blend_dict(attr: str, role: str) -> dict[str, float]:
            keys = set().union(*(getattr(a, attr).keys() for _, a in analyses))
            out = {}
            for key in keys:
                pairs = [
                    (weight(item, role), getattr(a, attr).get(key))
                    for item, a in analyses
                    if getattr(a, attr).get(key) is not None and weight(item, role) > 0
                ]
                denom = sum(w for w, _ in pairs)
                if denom:
                    out[key] = sum(w * float(v) for w, v in pairs) / denom
            return out

        return ReferenceAnalysis(
            bpm=bpm,
            duration=max((a.duration for _, a in analyses), default=0.0),
            energy_curve=curve,
            groove=blend_dict('groove', 'drums'),
            tone=blend_dict('tone', 'tone'),
            stereo=blend_dict('stereo', 'stereo'),
            dynamics=blend_dict('dynamics', 'master'),
        )

    def _production_prompt(self, state: ProjectState, reference: ReferenceAnalysis) -> str:
        custom = str(state.settings.get('production_direction_prompt', '') or '').strip()
        descriptors = ['original vocal-first production', 'arranged around the supplied vocal performance']
        if reference.bpm:
            descriptors.append(f'around {reference.bpm:.0f} BPM')
        bass_db = reference.tone.get('bass_60_120')
        sub_db = reference.tone.get('sub_20_60')
        if bass_db is not None or sub_db is not None:
            descriptors.append('solid controlled low-end and real drum impact')
        if reference.dynamics.get('range_db', 0.0) > 8.0:
            descriptors.append('clear verse-to-chorus dynamic contrast')
        descriptors.extend([
            'distinct verse chorus bridge transitions',
            'punchy kick and snare',
            'supportive bass',
            'harmonic layers that leave space for the vocal',
            'no copied melody hooks samples or exact reference drum patterns',
        ])
        if custom:
            descriptors.append(custom)
        return ', '.join(descriptors)

    def provider_statuses(self, state: ProjectState):
        return self.providers.statuses(state.settings)

    def smart_sfx(self, state: ProjectState) -> list[SfxSuggestion]:
        if not state.sound_library_path:
            return []
        vocal = self.analyze_vocal(state)
        cues = align_lyrics(state.lyrics, vocal.phrase_regions, vocal.duration)
        library = SoundLibrary(state.sound_library_path)
        library.scan()
        return suggest_sfx(cues, library)

    def _generate_previews_basic(
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

        processed_vocal = process_vocal(
            state.vocal.path,
            out / "preview-vocal.wav",
            state.vocal_preservation,
        )

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
                processed_vocal,
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

    def _build_basic(self, state: ProjectState, output_dir: str | Path) -> BuildResult:
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

        selected_sfx = list(state.settings.get("selected_sfx", []) or [])
        if selected_sfx:
            core_instrumental = synthesize_instrumental(
                out / "generated-instrumental-core.wav",
                duration,
                bpm,
                guided_energy,
                variant=variant,
                tonic_midi=tonic_midi,
                sample_paths=palette.sample_paths(),
            )
            instrumental = mix_sfx_events(
                core_instrumental,
                selected_sfx,
                out / "generated-instrumental.wav",
            )
        else:
            instrumental = synthesize_instrumental(
                out / "generated-instrumental.wav",
                duration,
                bpm,
                guided_energy,
                variant=variant,
                tonic_midi=tonic_midi,
                sample_paths=palette.sample_paths(),
            )

        processed_vocal = process_vocal(
            state.vocal.path,
            out / "processed-vocal.wav",
            state.vocal_preservation,
        )
        build_path = mix_vocal_and_instrumental(
            processed_vocal,
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
                "selected_sfx_count": len(selected_sfx),
                "selected_sfx": selected_sfx,
            },
            "outputs": {
                "processed_vocal": str(processed_vocal),
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

    def generate_previews(
        self, state: ProjectState, output_dir: str | Path
    ) -> list[ArrangementPreview]:
        state._ensure_v2_slots()
        provider = self.providers.choose(state.settings, require_vocal=True)
        if isinstance(provider, BasicTestProvider):
            return self._generate_previews_basic(state, output_dir)
        if not isinstance(provider, AceStepProvider):
            raise RuntimeError(
                f'{provider.name} is configured but v2 vocal-conditioned accompaniment routing is not enabled for it yet.'
            )

        vocal = self.analyze_vocal(state)
        reference = self._blended_reference(state)
        audio_reference = self._reference_for_audio(state)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        preview_duration = min(30.0, max(12.0, vocal.duration))
        prompt = self._production_prompt(state, reference)
        cover_strength = float(state.settings.get('reference_audio_strength', 25.0)) / 100.0
        processed_vocal = process_vocal(
            state.vocal.path,
            out / 'preview-vocal.wav',
            state.vocal_preservation,
        )

        accepted: list[tuple[Path, Path, float]] = []
        attempts = 0
        while len(accepted) < 3 and attempts < 2:
            attempts += 1
            generated = provider.generate_complete(
                state.settings,
                source_audio=state.vocal.path,
                reference_audio=audio_reference.path if audio_reference else None,
                lyrics=state.lyrics,
                prompt=prompt,
                output_dir=out / f'provider-pass-{attempts}',
                duration=preview_duration,
                batch_size=3 - len(accepted),
                bpm=reference.bpm,
                cover_strength=cover_strength,
            )
            for accompaniment in generated:
                inst_qc = inspect_preview(accompaniment)
                mixed = out / f'candidate-{attempts}-{len(accepted) + 1}.wav'
                mix_vocal_and_instrumental(
                    processed_vocal,
                    accompaniment,
                    mixed,
                    instrumental_gain_db=float(state.settings.get('preview_instrumental_gain_db', -3.0)),
                    duration=preview_duration,
                )
                mix_qc = inspect_preview(mixed)
                passed = inst_qc.passed and mix_qc.passed
                score = min(inst_qc.score, mix_qc.score)
                if passed:
                    accepted.append((accompaniment, mixed, score))
                else:
                    reject = out / 'rejected-qc.jsonl'
                    with reject.open('a', encoding='utf-8') as handle:
                        handle.write(json.dumps({
                            'accompaniment': str(accompaniment),
                            'mix': str(mixed),
                            'score': score,
                            'instrument_failures': [asdict(item) for item in inst_qc.failures],
                            'mix_failures': [asdict(item) for item in mix_qc.failures],
                        }) + '\n')
                if len(accepted) >= 3:
                    break

        if len(accepted) < 3:
            raise RuntimeError(
                'Generation completed, but fewer than three vocal + accompaniment previews '
                'passed Drellion Beat QC. Weak candidates were rejected automatically.'
            )

        previews: list[ArrangementPreview] = []
        instrumental_map: dict[str, str] = {}
        for index, (accompaniment, mixed, score) in enumerate(accepted[:3]):
            name = ('Preview A', 'Preview B', 'Preview C')[index]
            target = out / f'preview-{index + 1}.wav'
            target.write_bytes(mixed.read_bytes())
            inst_target = out / f'preview-{index + 1}-instrumental{accompaniment.suffix}'
            if accompaniment.resolve() != inst_target.resolve():
                inst_target.write_bytes(accompaniment.read_bytes())
            instrumental_map[name] = str(inst_target)
            previews.append(ArrangementPreview(
                name=name,
                audio_path=str(target),
                description=(
                    f'{provider.name} Base Complete accompaniment + preserved vocal · '
                    f'Beat QC {score:.0f}/100 · {reference.bpm:.1f} BPM reference blend'
                ),
                similarity={
                    'reference_bpm': reference.bpm,
                    'generated_bpm': self.analyze_mix(inst_target).bpm,
                    'qc_score': score,
                    'exact_reference_hits_reused': 0.0,
                },
            ))

        state.settings['preview_provider'] = provider.id
        state.settings['preview_paths'] = {item.name: item.audio_path for item in previews}
        state.settings['preview_instrumentals'] = instrumental_map
        state.settings['preview_reference_prompt'] = prompt
        (out / 'previews.json').write_text(
            json.dumps([asdict(item) for item in previews], indent=2),
            encoding='utf-8',
        )
        return previews

    def build(self, state: ProjectState, output_dir: str | Path) -> BuildResult:
        state._ensure_v2_slots()
        provider = self.providers.choose(state.settings, require_vocal=True)
        if isinstance(provider, BasicTestProvider):
            return self._build_basic(state, output_dir)
        if not isinstance(provider, AceStepProvider):
            raise RuntimeError(
                f'{provider.name} is configured but v2 vocal-conditioned accompaniment Build routing is not enabled for it yet.'
            )

        vocal = self.analyze_vocal(state)
        reference = self._blended_reference(state)
        audio_reference = self._reference_for_audio(state)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        prompt = self._production_prompt(state, reference)
        cover_strength = float(state.settings.get('reference_audio_strength', 25.0)) / 100.0

        generated = provider.generate_complete(
            state.settings,
            source_audio=state.vocal.path,
            reference_audio=audio_reference.path if audio_reference else None,
            lyrics=state.lyrics,
            prompt=prompt,
            output_dir=out / 'provider',
            duration=max(12.0, vocal.duration),
            batch_size=1,
            bpm=reference.bpm,
            cover_strength=cover_strength,
        )
        raw_accompaniment = generated[0]
        instrumental = out / ('generated-instrumental' + raw_accompaniment.suffix)
        if raw_accompaniment.resolve() != instrumental.resolve():
            instrumental.write_bytes(raw_accompaniment.read_bytes())

        selected_sfx = list(state.settings.get('selected_sfx', []) or [])
        if selected_sfx:
            instrumental = mix_sfx_events(
                instrumental,
                selected_sfx,
                out / 'generated-instrumental-with-sfx.wav',
            )

        inst_qc = inspect_preview(instrumental)
        if not inst_qc.passed:
            raise RuntimeError(
                'Generated accompaniment failed Drellion Beat QC: '
                + '; '.join(item.name for item in inst_qc.failures)
            )

        processed_vocal = process_vocal(
            state.vocal.path,
            out / 'processed-vocal.wav',
            state.vocal_preservation,
        )
        build_path = mix_vocal_and_instrumental(
            processed_vocal,
            instrumental,
            out / 'build.wav',
            instrumental_gain_db=float(state.settings.get('build_instrumental_gain_db', -3.0)),
            duration=max(vocal.duration, self.analyze_mix(instrumental).duration),
        )
        mix_qc = inspect_preview(build_path)
        if not mix_qc.passed:
            raise RuntimeError(
                'Vocal + accompaniment build failed Drellion Beat QC: '
                + '; '.join(item.name for item in mix_qc.failures)
            )

        lyric_cues = align_lyrics(state.lyrics, vocal.phrase_regions, vocal.duration)
        lyric_path = ''
        if lyric_cues:
            lrc = out / 'lyrics.lrc'
            lrc.write_text(to_lrc(lyric_cues), encoding='utf-8')
            lyric_path = str(lrc)

        stem_paths: list[str] = []
        stem_warning = ''
        if bool(state.settings.get('auto_split_generated', True)):
            open_unmix = next((item for item in tool_statuses() if item.id == 'open_unmix'), None)
            if open_unmix and open_unmix.available:
                try:
                    stem_paths = [
                        str(path)
                        for path in separate_open_unmix(instrumental, out / 'Stems')
                    ]
                    state.settings['generated_stems'] = stem_paths
                except Exception as exc:
                    stem_warning = str(exc)
            else:
                stem_warning = 'Open-Unmix is not installed; accompaniment remains a stereo instrumental.'

        state.settings['generated_instrumental'] = str(instrumental)
        state.settings['processed_vocal'] = str(processed_vocal)
        report_path = out / 'report.json'
        report_path.write_text(json.dumps({
            'engine': provider.name,
            'provider_id': provider.id,
            'accompaniment_qc_score': inst_qc.score,
            'mix_qc_score': mix_qc.score,
            'reference_blend': asdict(reference),
            'reference_count': len(self._enabled_references(state)),
            'prompt': prompt,
            'source_vocal_preserved_separately': True,
            'ace_task': 'complete',
            'ace_model': state.settings.get('provider_ace_step_model', 'acestep-v15-base'),
            'exact_reference_audio_copied': False,
            'selected_sfx': selected_sfx,
            'stem_paths': stem_paths,
            'stem_warning': stem_warning,
            'outputs': {
                'processed_vocal': str(processed_vocal),
                'instrumental': str(instrumental),
                'build': str(build_path),
            },
        }, indent=2), encoding='utf-8')

        return BuildResult(
            build_path=str(build_path),
            instrumental_path=str(instrumental),
            report_path=str(report_path),
            lyric_path=lyric_path,
            stem_paths=stem_paths,
        )

    def master(self, state: ProjectState, output_dir: str | Path) -> str:
        source = state.build_path or state.finished_song.path
        if not source:
            raise ValueError("Build the song or choose a finished song before mastering.")

        target_lufs = float(state.settings.get("target_lufs", -14.0))
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        source_analysis = self.analyze_mix(source)
        reference_analysis = (
            self.analyze_reference(state) if state.reference.path else None
        )
        mastered = master_audio(
            source,
            out / "master.wav",
            target_lufs=target_lufs,
            true_peak=-1.0,
            source_analysis=source_analysis,
            reference_analysis=reference_analysis,
            reference_influence=state.reference_influence,
            custom_reference_strength=float(state.settings.get("master_reference_strength", 70.0)) / 100.0,
            custom_punch=float(state.settings.get("master_punch", 50.0)) / 100.0,
            custom_width=float(state.settings.get("master_width", 50.0)) / 100.0,
        )

        report = {
            "target_lufs": target_lufs,
            "reference_influence": state.reference_influence,
            "source": asdict(source_analysis),
            "reference": asdict(reference_analysis) if reference_analysis else None,
            "output": str(mastered),
        }
        report_path = out / "master-report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        state.settings["master_report"] = str(report_path)
        return str(mastered)
