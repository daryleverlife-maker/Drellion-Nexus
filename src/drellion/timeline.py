from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess

from .audio.runtime import media_duration, require_ffmpeg
from .project import ClipState, ProjectState, TrackState


def ensure_track(project: ProjectState, name: str, role: str = "audio") -> TrackState:
    for track in project.tracks:
        if track.role == role:
            return track
    track = TrackState(name=name, role=role)
    project.tracks.append(track)
    project.touch()
    return track


def add_clip(
    track: TrackState,
    path: str | Path,
    *,
    label: str | None = None,
    start: float = 0.0,
    source_offset: float = 0.0,
    duration: float = 0.0,
) -> ClipState:
    source = Path(path)
    detected_duration = max(0.0, float(duration))
    if detected_duration <= 0.0 and source.is_file():
        try:
            detected_duration = media_duration(source)
        except Exception:
            detected_duration = 0.0

    clip = ClipState(
        label=label or source.stem or "Clip",
        path=str(source),
        start=max(0.0, float(start)),
        source_offset=max(0.0, float(source_offset)),
        duration=detected_duration,
    )
    track.clips.append(clip)
    return clip


def duplicate_clip(track: TrackState, clip_id: str, offset: float = 0.25) -> ClipState:
    original = next(clip for clip in track.clips if clip.id == clip_id)
    clone = deepcopy(original)
    clone.id = ClipState().id
    clone.label = original.label + " Copy"
    clone.start = max(0.0, original.start + max(0.0, float(offset)))
    track.clips.append(clone)
    return clone


def split_clip(track: TrackState, clip_id: str, timeline_position: float) -> tuple[ClipState, ClipState]:
    original = next(clip for clip in track.clips if clip.id == clip_id)
    if original.duration <= 0:
        raise ValueError("Set or detect the clip duration before splitting it.")

    split_at = float(timeline_position) - original.start
    if split_at <= 0.0 or split_at >= original.duration:
        raise ValueError("Split point must be inside the clip.")

    left = deepcopy(original)
    right = deepcopy(original)
    left.id = ClipState().id
    right.id = ClipState().id
    left.label = original.label + " A"
    right.label = original.label + " B"
    left.duration = split_at
    right.start = original.start + split_at
    right.source_offset = original.source_offset + split_at
    right.duration = original.duration - split_at

    index = track.clips.index(original)
    track.clips[index:index + 1] = [left, right]
    return left, right


def remove_clip(track: TrackState, clip_id: str) -> None:
    track.clips[:] = [clip for clip in track.clips if clip.id != clip_id]


def sync_generated_tracks(project: ProjectState) -> None:
    project._ensure_v2_slots()
    if project.vocal.path:
        vocal = ensure_track(project, "Vocal", "vocal")
        if not any(clip.path == project.vocal.path for clip in vocal.clips):
            add_clip(vocal, project.vocal.path, label=project.vocal.label or "Vocal")

    # Add every user source as an editable track while avoiding duplicates.
    for source in project.sources:
        if not source.path or not Path(source.path).is_file():
            continue
        role = source.role.lower().replace(" ", "_")
        track = ensure_track(project, source.role or "Source", "source_" + role)
        if not any(clip.path == source.path for clip in track.clips):
            add_clip(track, source.path, label=source.label or Path(source.path).stem)

    stem_paths = list(project.settings.get("generated_stems", []) or [])
    stem_roles = {
        "drums": ("Generated Drums", "generated_drums"),
        "bass": ("Generated Bass", "generated_bass"),
        "vocals": ("Generated Vocal Stem", "generated_vocals"),
        "vocal": ("Generated Vocal Stem", "generated_vocals"),
        "other": ("Generated Music", "generated_other"),
    }
    for path in stem_paths:
        source = Path(path)
        if not source.is_file():
            continue
        lowered = source.stem.lower()
        role_key = next((key for key in stem_roles if key in lowered), "other")
        name, role = stem_roles[role_key]
        track = ensure_track(project, name, role)
        if not any(clip.path == str(source) for clip in track.clips):
            add_clip(track, source, label=source.stem)

    instrumental_path = str(project.settings.get("generated_instrumental", "") or "")
    if instrumental_path:
        instrumental = ensure_track(project, "Generated Instrumental", "instrumental")
        if not any(clip.path == instrumental_path for clip in instrumental.clips):
            add_clip(instrumental, instrumental_path, label="Generated Instrumental")

    if project.build_path and Path(project.build_path).is_file() and not stem_paths and not instrumental_path:
        generated = ensure_track(project, "AI Build", "generated_build")
        if not any(clip.path == project.build_path for clip in generated.clips):
            add_clip(generated, project.build_path, label="AI Build")



def _audible_tracks(project: ProjectState) -> list[TrackState]:
    soloed = [track for track in project.tracks if track.solo and not track.muted]
    return soloed if soloed else [track for track in project.tracks if not track.muted]


def render_timeline(project: ProjectState, target_path: str | Path) -> Path:
    clips: list[tuple[TrackState, ClipState]] = []
    for track in _audible_tracks(project):
        for clip in track.clips:
            if clip.muted:
                continue
            if Path(clip.path).is_file():
                clips.append((track, clip))

    if not clips:
        raise ValueError("The Studio timeline has no audible audio clips.")

    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    command = [require_ffmpeg(), "-y", "-v", "error"]
    for _, clip in clips:
        command += ["-i", clip.path]

    filters: list[str] = []
    labels: list[str] = []
    for index, (track, clip) in enumerate(clips):
        source_label = f"[{index}:a]"
        chain = [
            f"atrim=start={clip.source_offset:.6f}"
            + (f":duration={clip.duration:.6f}" if clip.duration > 0 else ""),
            "asetpts=PTS-STARTPTS",
            "aformat=sample_rates=44100:channel_layouts=stereo",
        ]

        gain_db = float(track.volume_db) + float(clip.gain_db)
        if abs(gain_db) > 0.001:
            chain.append(f"volume={gain_db:.3f}dB")

        pan = max(-1.0, min(1.0, float(track.pan) + float(clip.pan)))
        if abs(pan) > 0.001:
            left = 1.0 if pan <= 0 else 1.0 - pan
            right = 1.0 if pan >= 0 else 1.0 + pan
            chain.append(f"pan=stereo|c0={left:.5f}*c0|c1={right:.5f}*c1")

        if clip.fade_in > 0:
            chain.append(f"afade=t=in:st=0:d={clip.fade_in:.6f}")
        if clip.fade_out > 0 and clip.duration > clip.fade_out:
            fade_start = clip.duration - clip.fade_out
            chain.append(f"afade=t=out:st={fade_start:.6f}:d={clip.fade_out:.6f}")

        delay = round(max(0.0, clip.start) * 1000.0)
        if delay:
            chain.append(f"adelay={delay}|{delay}")

        label = f"clip{index}"
        filters.append(source_label + ",".join(chain) + f"[{label}]")
        labels.append(f"[{label}]")

    filters.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
        + "alimiter=limit=0.97:attack=5:release=80[out]"
    )

    command += [
        "-filter_complex", ";".join(filters),
        "-map", "[out]",
        "-c:a", "pcm_s24le",
        str(target),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:] or "Studio render failed.")
    return target


def render_track_stem(project: ProjectState, track_id: str, target_path: str | Path) -> Path:
    clone = deepcopy(project)
    found = False
    for track in clone.tracks:
        track.solo = track.id == track_id
        track.muted = track.id != track_id
        if track.id == track_id:
            found = True
    if not found:
        raise ValueError(f'Unknown track id: {track_id}')
    return render_timeline(clone, target_path)


def render_all_stems(project: ProjectState, output_dir: str | Path) -> list[Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for index, track in enumerate(project.tracks, start=1):
        if not track.clips:
            continue
        safe = ''.join(ch if ch.isalnum() or ch in ' ._-' else '_' for ch in track.name).strip() or f'Track {index}'
        target = root / f'{index:02d} - {safe}.wav'
        outputs.append(render_track_stem(project, track.id, target))
    return outputs
