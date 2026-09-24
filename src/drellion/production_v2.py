from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import random
import subprocess

from .audio.analysis import analyze_vocal_file
from .audio.runtime import require_ffmpeg
from .project import ProjectState
from .providers import AceStepHttpProvider, DiffRhythmLocalProvider, EngineBroker, GenerationRequest
from .quality import PreviewQualityReport, evaluate_preview, write_quality_report
from .reference_blend import normalize_references
from .master_v2 import blend_reference_analysis, master_v2
from .stems import available_stem_engines


@dataclass
class PreviewCandidate:
    name: str
    audio_path: str
    provider_id: str
    seed: int
    quality: PreviewQualityReport
    accepted: bool


@dataclass
class V2BuildResult:
    audio_path: str
    provider_id: str
    seed: int | None
    metadata_path: str


def create_broker(project: ProjectState) -> EngineBroker:
    broker = EngineBroker()
    ace_endpoint = str(project.settings.get("ace_step_endpoint", "")).strip()
    ace_key = str(project.settings.get("ace_step_api_key", "")).strip()
    if ace_endpoint:
        broker.register(AceStepHttpProvider(ace_endpoint, ace_key))

    diff_repo = str(project.settings.get("diffrhythm_repo", "")).strip()
    if diff_repo:
        broker.register(DiffRhythmLocalProvider(
            diff_repo,
            str(project.settings.get("diffrhythm_python", "")).strip(),
        ))
    return broker


def _lead_vocal(project: ProjectState) -> str:
    for source in project.sources:
        if source.enabled and source.path and source.role == "Lead Vocal":
            return source.path
    if project.vocal.path:
        return project.vocal.path
    for source in project.sources:
        if source.enabled and source.path:
            return source.path
    raise ValueError("A source vocal/audio file is required.")


def _reference_paths(project: ProjectState) -> list[str]:
    refs = []
    for ref in project.references:
        if ref.enabled and ref.path and Path(ref.path).is_file():
            refs.append(ref.path)
    if not refs and project.reference.path and Path(project.reference.path).is_file():
        refs.append(project.reference.path)
    return refs


def _prompt(project: ProjectState) -> str:
    direction = str(project.settings.get("production_direction", "")).strip()
    blend = normalize_references(project.references)
    dimensions = [name for name, weights in blend.dimensions.items() if weights]
    base = direction or "Original professional vocal-first production with strong drums, bass, arrangement movement and space for the lead vocal."
    if dimensions:
        base += " Reference-guided dimensions: " + ", ".join(dimensions) + "."
    base += " Do not copy exact melody, hooks, samples, or exact drum-hit sequences from references."
    return base


def _preview_window(vocal, window: float = 28.0) -> tuple[float, float]:
    duration=max(1.0,float(vocal.duration))
    window=min(window,duration)
    if not vocal.phrase_regions:
        return 0.0,window
    candidates=[]
    starts={max(0.0,min(duration-window,start-1.0)) for start,_ in vocal.phrase_regions}
    for start in starts:
        end=start+window
        active=sum(max(0.0,min(end,b)-max(start,a)) for a,b in vocal.phrase_regions)
        candidates.append((active,start,end))
    _,start,end=max(candidates,key=lambda row:row[0])
    return start,min(duration,end)


def _crop_audio(source: str | Path, target: str | Path, start: float, end: float) -> str:
    target=Path(target); target.parent.mkdir(parents=True,exist_ok=True)
    duration=max(0.5,end-start)
    result=subprocess.run([
        require_ffmpeg(),"-y","-v","error","-ss",f"{start:.3f}","-i",str(source),
        "-t",f"{duration:.3f}","-vn","-c:a","pcm_s24le",str(target)
    ],capture_output=True,text=True,check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:] or "Could not create preview vocal window.")
    return str(target)


def generate_three_previews(project: ProjectState, output_dir: str | Path) -> list[PreviewCandidate]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    vocal_path = _lead_vocal(project)
    vocal = analyze_vocal_file(vocal_path)
    references = _reference_paths(project)
    broker = create_broker(project)
    requested = str(project.settings.get("engine_id", "auto"))
    provider = broker.choose(requested)

    preview_seconds = min(30.0, max(18.0, vocal.duration))
    preview_start, preview_end = _preview_window(vocal, preview_seconds)
    preview_vocal_path = _crop_audio(vocal_path, out / "preview-source-vocal.wav", preview_start, preview_end)
    preview_seconds = preview_end - preview_start
    project.settings["preview_region"] = {"start": preview_start, "end": preview_end}
    base_seed = int(project.settings.get("preview_seed", random.randint(1, 2_000_000_000)))
    candidates = []
    reference_analysis = blend_reference_analysis(project)

    for index, label in enumerate(("Preview A", "Preview B", "Preview C")):
        seed = base_seed + index * 1009
        generation = provider.generate(GenerationRequest(
            vocal_path=preview_vocal_path,
            lyrics=project.lyrics,
            reference_paths=references,
            prompt=_prompt(project),
            duration=preview_seconds,
            seed=seed,
            output_dir=str(out / label.replace(" ", "-").lower()),
            source_roles={s.path: s.role for s in project.sources if s.path},
        ))
        quality = evaluate_preview(generation.audio_path, reference_analysis)
        write_quality_report(quality, out / f"quality-{index+1}.json")
        candidates.append(PreviewCandidate(label, generation.audio_path, generation.provider_id, seed, quality, quality.passed))

    manifest = out / "v2-previews.json"
    manifest.write_text(json.dumps([
        {
            "name": c.name,
            "audio_path": c.audio_path,
            "provider_id": c.provider_id,
            "seed": c.seed,
            "accepted": c.accepted,
            "quality": c.quality.to_dict(),
        } for c in candidates
    ], indent=2), encoding="utf-8")
    return candidates


def build_full_song(project: ProjectState, output_dir: str | Path, seed: int | None = None) -> V2BuildResult:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    vocal_path = _lead_vocal(project)
    vocal = analyze_vocal_file(vocal_path)
    references = _reference_paths(project)
    provider = create_broker(project).choose(str(project.settings.get("engine_id", "auto")))

    generation = provider.generate(GenerationRequest(
        vocal_path=vocal_path,
        lyrics=project.lyrics,
        reference_paths=references,
        prompt=_prompt(project),
        duration=max(10.0, vocal.duration),
        seed=seed,
        output_dir=str(out),
        source_roles={s.path: s.role for s in project.sources if s.path},
    ))
    generated_stems = {}
    if bool(project.settings.get("auto_separate_generated", True)):
        selected = next(((engine, status) for engine, status in available_stem_engines() if status.available), None)
        if selected is not None:
            stem_engine, stem_status = selected
            try:
                generated_stems = stem_engine.separate(generation.audio_path, out / "Stems")
                project.settings["generated_stems"] = generated_stems
                project.settings["generated_stem_engine"] = stem_status.name
            except Exception as exc:
                project.settings["generated_stem_error"] = str(exc)

    report = {
        "provider": generation.provider_id,
        "seed": generation.seed,
        "audio_path": generation.audio_path,
        "references": references,
        "source_count": len(project.sources),
        "generated_stems": generated_stems,
        "policy": "Source-conditioned original generation; references guide production direction only.",
        "provider_metadata": generation.metadata,
    }
    report_path = out / "v2-build.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return V2BuildResult(generation.audio_path, generation.provider_id, generation.seed, str(report_path))


@dataclass
class V2AutoResult:
    previews: list[PreviewCandidate]
    selected: PreviewCandidate
    build: V2BuildResult
    master_path: str


def run_full_auto_v2(project: ProjectState, project_root: str | Path) -> V2AutoResult:
    root = Path(project_root)
    previews = generate_three_previews(project, root / "Previews")
    accepted = [candidate for candidate in previews if candidate.accepted]
    if not accepted:
        raise RuntimeError("All three generated previews failed Drellion quality control. Change the engine/direction and regenerate.")
    selected = accepted[0]
    project.selected_preview = selected.name
    project.settings["selected_preview_seed"] = selected.seed
    project.settings["selected_preview_provider"] = selected.provider_id
    project.settings["selected_preview_path"] = selected.audio_path
    build = build_full_song(project, root / "Generated", selected.seed)
    project.build_path = build.audio_path
    project.settings["build_provider"] = build.provider_id
    project.settings["build_report"] = build.metadata_path
    master_path = master_v2(project, root / "Masters")
    return V2AutoResult(previews, selected, build, master_path)
