from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import random

from .audio.analysis import analyze_vocal_file
from .project import ProjectState
from .providers import AceStepHttpProvider, EngineBroker, GenerationRequest, GenerationResult, LocalCommandProvider
from .quality import PreviewQualityReport, evaluate_preview, write_quality_report
from .reference_blend import normalize_references
from .master_v2 import blend_reference_analysis


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

    ace_local = str(project.settings.get("ace_step_local_command", "")).strip()
    if ace_local:
        broker.register(LocalCommandProvider("ace-step-local", "ACE-Step Local", ace_local))

    diff_local = str(project.settings.get("diffrhythm_local_command", "")).strip()
    if diff_local:
        broker.register(LocalCommandProvider("diffrhythm-local", "DiffRhythm Local", diff_local, reference=True, source=False))
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
    base_seed = int(project.settings.get("preview_seed", random.randint(1, 2_000_000_000)))
    candidates = []
    reference_analysis = blend_reference_analysis(project)

    for index, label in enumerate(("Preview A", "Preview B", "Preview C")):
        seed = base_seed + index * 1009
        generation = provider.generate(GenerationRequest(
            vocal_path=vocal_path,
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
    report = {
        "provider": generation.provider_id,
        "seed": generation.seed,
        "audio_path": generation.audio_path,
        "references": references,
        "source_count": len(project.sources),
        "policy": "Source-conditioned original generation; references guide production direction only.",
        "provider_metadata": generation.metadata,
    }
    report_path = out / "v2-build.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return V2BuildResult(generation.audio_path, generation.provider_id, generation.seed, str(report_path))
