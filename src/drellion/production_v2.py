from __future__ import annotations

from pathlib import Path
from typing import Callable
import hashlib
import json
import shutil

from .audio_core import crop, mix_tracks, read_wav, write_wav
from .master_v2 import master_wav
from .project import BuildRecord, GeneratedStem, MasterRecord, PreviewRecord, ProjectState
from .providers import EngineBroker, GenerationRequest, GenerationResult
from .quality import evaluate_preview

ProgressFn = Callable[[str], None]


def lead_vocal(project: ProjectState):
    for source in project.sources:
        if source.enabled and source.role.lower() in {"lead vocal", "vocal", "vocals", "acapella"}:
            return source
    for source in project.sources:
        if source.enabled:
            return source
    return None


def reference_paths(project: ProjectState) -> list[str]:
    refs = [r for r in project.references if r.enabled and r.path and Path(r.path).exists()]
    refs.sort(key=lambda r: r.weight, reverse=True)
    return [r.path for r in refs]


def direction_prompt(project: ProjectState) -> str:
    tags: list[str] = []
    direction = project.direction
    for key in ("cinematic", "harder", "cleaner", "darker"):
        if direction.get(key): tags.append(key)
    notes = str(direction.get("notes") or "").strip()
    if notes: tags.append(notes)
    descriptions: list[str] = []
    for ref in project.references:
        if not ref.enabled: continue
        profile = ref.analysis or {}
        pieces = [str(profile.get(k)) for k in ("energy","low_end","dynamics","stereo") if profile.get(k)]
        if pieces: descriptions.append(", ".join(pieces))
    base = "Original accompaniment built around the supplied vocal performance. Preserve vocal timing and phrasing."
    if descriptions: base += " Reference production characteristics: " + "; ".join(descriptions[:3]) + "."
    if tags: base += " Direction: " + ", ".join(tags) + "."
    base += " Do not reproduce exact melodies, hooks, samples, or beat sequences from references."
    return base


def representative_preview_region(project: ProjectState, duration: float = 25.0) -> tuple[float,float]:
    source = lead_vocal(project)
    if not source or not Path(source.path).exists() or Path(source.path).suffix.lower() != ".wav":
        return 0.0, duration
    audio = read_wav(source.path)
    if audio.duration <= duration: return 0.0, audio.duration
    window=max(1,int(duration*audio.sample_rate)); step=max(1,int(2.5*audio.sample_rate))
    mono=audio.samples.mean(axis=1); best_start=0; best_energy=-1.0
    for start in range(0,max(1,len(mono)-window),step):
        segment=mono[start:start+window]
        energy=float((segment.astype("float64")**2).mean()) if len(segment) else 0.0
        if energy>best_energy: best_energy=energy; best_start=start
    return best_start/audio.sample_rate, min(duration,audio.duration-best_start/audio.sample_rate)


def _seed_for(project: ProjectState,index:int)->int:
    raw=f"{project.id}:{project.updated_at}:{index}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8],16)&0x7FFFFFFF


def _make_preview_vocal(project:ProjectState,start:float,duration:float,index:int)->str:
    source=lead_vocal(project)
    if not source: raise RuntimeError("Add a vocal/source before generating previews")
    path=Path(source.path)
    if path.suffix.lower()!=".wav": return str(path)
    audio=read_wav(path); clip=crop(audio,start,duration)
    out=project.folder("Previews")/f"preview-vocal-{index+1:02d}.wav"
    write_wav(out,clip.samples,clip.sample_rate); return str(out)


def _copy_generated(result:GenerationResult,destination:Path)->Path:
    source=Path(result.audio_path)
    if not source.exists(): raise RuntimeError(f"Generation engine returned missing audio: {source}")
    destination.parent.mkdir(parents=True,exist_ok=True)
    if source.resolve()!=destination.resolve(): shutil.copy2(source,destination)
    return destination


def generate_three_previews(project:ProjectState,broker:EngineBroker,preferred_engine:str|None=None,progress:ProgressFn|None=None,region:tuple[float,float]|None=None)->list[PreviewRecord]:
    project.ensure_layout()
    source=lead_vocal(project)
    if source is None or not Path(source.path).exists():
        raise RuntimeError("A valid source vocal is required")
    start,duration=region or representative_preview_region(project)
    duration=max(18.0,min(30.0,float(duration)))
    prompt=direction_prompt(project)
    refs=reference_paths(project)
    accepted:list[PreviewRecord]=[]
    max_attempts=9
    for attempt in range(max_attempts):
        slot=len(accepted)+1
        if progress:
            progress(f"Generating QC candidate {attempt+1} of {max_attempts} — {len(accepted)} of 3 passed")
        seed=_seed_for(project,attempt)
        preview_vocal=_make_preview_vocal(project,start,duration,attempt)
        request=GenerationRequest(
            source_audio=preview_vocal,reference_audio=refs,prompt=prompt,lyrics=project.lyrics_text,
            seed=seed,duration_seconds=duration,start_seconds=start,task="complete",
            reference_strength=float(project.direction.get("reference_strength",0.55)),
            output_dir=str(project.folder("Previews")/f"engine-attempt-{attempt+1}")
        )
        result=broker.generate(request,preferred=preferred_engine,progress=progress)
        raw=_copy_generated(result,project.folder("Previews")/f"attempt-{attempt+1:02d}-instrumental.wav")
        vocal_for_qc=preview_vocal if Path(preview_vocal).suffix.lower()==".wav" else None
        qc=evaluate_preview(raw,vocal_for_qc)
        (project.folder("Previews")/f"attempt-{attempt+1:02d}-qc.json").write_text(json.dumps(qc.to_dict(),indent=2),encoding="utf-8")
        if not qc.accepted:
            continue
        instrumental=project.folder("Previews")/f"candidate-{slot:02d}-instrumental.wav"
        if raw.resolve()!=instrumental.resolve():
            shutil.copy2(raw,instrumental)
        mix_path=instrumental
        if vocal_for_qc:
            try:
                music=read_wav(instrumental); vocal_audio=read_wav(vocal_for_qc)
                mixed=mix_tracks([(music,-3.0),(vocal_audio,0.0)],headroom_db=1.0)
                mix_path=project.folder("Previews")/f"candidate-{slot:02d}-together.wav"
                write_wav(mix_path,mixed.samples,mixed.sample_rate)
            except Exception:
                mix_path=instrumental
        record=PreviewRecord(
            label=f"Preview {chr(64+slot)}",audio_path=str(mix_path),instrumental_path=str(instrumental),
            vocal_path=str(preview_vocal),engine=result.engine,engine_version=result.engine_version,seed=seed,
            prompt=prompt,region_start=start,region_duration=duration,accepted=True,qc=qc.to_dict()
        )
        accepted.append(record)
        if len(accepted)==3:
            break
    project.previews=accepted
    project.selected_preview_id=""
    project.save()
    if len(accepted)<3:
        raise RuntimeError(f"Only {len(accepted)} of 3 previews passed Drellion QC after {max_attempts} attempts. No full Build is allowed; adjust the engine, reference, or direction and regenerate.")
    return accepted


def build_from_preview(project:ProjectState,broker:EngineBroker,preview_id:str|None=None,preferred_engine:str|None=None,progress:ProgressFn|None=None)->BuildRecord:
    preview=next((p for p in project.previews if p.id==(preview_id or project.selected_preview_id)),None)
    if preview is None: raise RuntimeError("Select an accepted preview before building")
    if not preview.accepted: raise RuntimeError("The selected preview failed QC and cannot be built")
    source=lead_vocal(project)
    if source is None or not Path(source.path).exists(): raise RuntimeError("Source vocal is missing")
    duration=read_wav(source.path).duration if Path(source.path).suffix.lower()==".wav" else None
    request=GenerationRequest(source_audio=source.path,reference_audio=reference_paths(project),prompt=preview.prompt,lyrics=project.lyrics_text,seed=preview.seed,duration_seconds=duration,task="complete",reference_strength=float(project.direction.get("reference_strength",0.55)),output_dir=str(project.folder("Generated")/preview.id))
    if progress: progress("Generating full arrangement from selected preview")
    result=broker.generate(request,preferred=preferred_engine or preview.engine,progress=progress); build_index=len(project.builds)+1
    instrumental=_copy_generated(result,project.folder("Generated")/f"Build-{build_index:02d}-Instrumental.wav"); stems=[]
    if result.stems:
        for role,stem_path in result.stems.items():
            source_stem=Path(stem_path); target=project.folder("Generated")/f"Build-{build_index:02d}-{role}.wav"
            if source_stem.exists():
                shutil.copy2(source_stem,target); stems.append(GeneratedStem(role=role,path=str(target),engine=result.engine,engine_version=result.engine_version,seed=result.seed))
    if not stems:
        try:
            from .stems import best_available_separator
            separator=best_available_separator()
            separated=separator.split(instrumental,project.folder("Stems")/f"Build-{build_index:02d}") if separator else None
            if separated:
                role_map={"vocals":"Generated Vocal","drums":"Drums","bass":"Bass","piano":"Piano","other":"Music","accompaniment":"Music"}
                for role,stem_path in separated.stems.items():
                    stems.append(GeneratedStem(role=role_map.get(role,role.title()),path=str(stem_path),engine=f"{result.engine} + {separated.engine}",engine_version=result.engine_version,seed=result.seed))
        except Exception: stems=[]
    if not stems: stems.append(GeneratedStem(role="Instrumental",path=str(instrumental),engine=result.engine,engine_version=result.engine_version,seed=result.seed))
    mix_path=instrumental
    if Path(source.path).suffix.lower()==".wav" and instrumental.suffix.lower()==".wav":
        try:
            music=read_wav(instrumental); vocal_audio=read_wav(source.path)
            mixed=mix_tracks([(music,-3.0),(vocal_audio,source.gain_db)],headroom_db=1.0)
            mix_path=project.folder("Generated")/f"Build-{build_index:02d}-Mix.wav"; write_wav(mix_path,mixed.samples,mixed.sample_rate)
        except Exception: mix_path=instrumental
    build=BuildRecord(label=f"Build {build_index:02d}",mix_path=str(mix_path),instrumental_path=str(instrumental),engine=result.engine,engine_version=result.engine_version,seed=result.seed,prompt=preview.prompt,stems=stems,source_preview_id=preview.id)
    for stem in build.stems: stem.source_generation_id=build.id
    project.builds.append(build); project.selected_build_id=build.id; _seed_studio_from_build(project,build); project.save(); return build


def _seed_studio_from_build(project:ProjectState,build:BuildRecord)->None:
    from .project import StudioClip,StudioTrack
    tracks=[]
    for source in project.sources:
        if not source.enabled: continue
        duration=source.duration_seconds or 0.0
        if not duration and Path(source.path).suffix.lower()==".wav" and Path(source.path).exists():
            try: duration=read_wav(source.path).duration
            except Exception: pass
        track=StudioTrack(name=source.label,role=source.role); track.clips.append(StudioClip(track_id=track.id,source_path=source.path,label=source.label,duration_seconds=duration)); tracks.append(track)
    for stem in build.stems:
        duration=0.0
        if Path(stem.path).suffix.lower()==".wav" and Path(stem.path).exists():
            try: duration=read_wav(stem.path).duration
            except Exception: pass
        track=StudioTrack(name=stem.role,role=stem.role); track.clips.append(StudioClip(track_id=track.id,source_path=stem.path,label=stem.role,duration_seconds=duration)); tracks.append(track)
    project.studio_tracks=tracks


def master_selected_build(project:ProjectState,target_lufs:float=-14.0,true_peak:float=-1.0)->MasterRecord:
    build=project.selected_build()
    if build is None or not Path(build.mix_path).exists(): raise RuntimeError("Build a song before mastering")
    index=len(project.masters)+1; output=project.folder("Masters")/f"Master-{index:02d}.wav"
    path,engine,measurements=master_wav(build.mix_path,output,target_lufs,true_peak)
    record=MasterRecord(source_build_id=build.id,path=str(path),target_lufs=target_lufs,target_true_peak=true_peak,engine=engine,measurements=measurements.to_dict())
    project.masters.append(record); project.selected_master_id=record.id; project.save(); return record
