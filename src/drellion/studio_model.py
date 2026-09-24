from __future__ import annotations

from dataclasses import replace

from .project import ProjectState, StudioClip, StudioTrack


def track(project: ProjectState, track_id: str) -> StudioTrack:
    return next(t for t in project.studio_tracks if t.id == track_id)


def clip(project: ProjectState, clip_id: str) -> tuple[StudioTrack, StudioClip]:
    for t in project.studio_tracks:
        for c in t.clips:
            if c.id == clip_id:
                return t, c
    raise KeyError(clip_id)


def add_track(project: ProjectState, name: str, role: str = "Audio") -> StudioTrack:
    t = StudioTrack(name=name or "Track", role=role)
    project.studio_tracks.append(t)
    project.touch()
    return t


def add_clip(project: ProjectState, track_id: str, source_path: str, label: str, start_seconds: float = 0.0, duration_seconds: float = 0.0) -> StudioClip:
    t = track(project, track_id)
    c = StudioClip(track_id=t.id, source_path=source_path, label=label, start_seconds=max(0.0, start_seconds), duration_seconds=max(0.0, duration_seconds))
    t.clips.append(c)
    project.touch()
    return c


def move_clip(project: ProjectState, clip_id: str, start_seconds: float, target_track_id: str | None = None) -> StudioClip:
    source_track, c = clip(project, clip_id)
    c.start_seconds = max(0.0, float(start_seconds))
    if target_track_id and target_track_id != source_track.id:
        target = track(project, target_track_id)
        source_track.clips = [x for x in source_track.clips if x.id != c.id]
        c.track_id = target.id
        target.clips.append(c)
    project.touch()
    return c


def trim_clip(project: ProjectState, clip_id: str, source_offset_seconds: float, duration_seconds: float) -> StudioClip:
    _t, c = clip(project, clip_id)
    c.source_offset_seconds = max(0.0, float(source_offset_seconds))
    c.duration_seconds = max(0.0, float(duration_seconds))
    project.touch()
    return c


def split_clip(project: ProjectState, clip_id: str, at_project_seconds: float) -> tuple[StudioClip, StudioClip]:
    t, c = clip(project, clip_id)
    local = float(at_project_seconds) - c.start_seconds
    if local <= 0 or (c.duration_seconds and local >= c.duration_seconds):
        raise ValueError("Split point must be inside the clip")
    original_duration = c.duration_seconds
    c.duration_seconds = local
    right = replace(c)
    from .project import _id
    right.id = _id("clip")
    right.start_seconds = float(at_project_seconds)
    right.source_offset_seconds = c.source_offset_seconds + local
    right.duration_seconds = max(0.0, original_duration - local)
    t.clips.append(right)
    project.touch()
    return c, right


def duplicate_clip(project: ProjectState, clip_id: str, offset_seconds: float = 0.25) -> StudioClip:
    t, c = clip(project, clip_id)
    clone = replace(c)
    from .project import _id
    clone.id = _id("clip")
    clone.start_seconds = c.start_seconds + max(0.0, offset_seconds)
    t.clips.append(clone)
    project.touch()
    return clone


def set_fades(project: ProjectState, clip_id: str, fade_in: float, fade_out: float, crossfade: float = 0.0) -> StudioClip:
    _t, c = clip(project, clip_id)
    c.fade_in_seconds = max(0.0, float(fade_in))
    c.fade_out_seconds = max(0.0, float(fade_out))
    c.crossfade_seconds = max(0.0, float(crossfade))
    project.touch()
    return c


def remove_clip(project: ProjectState, clip_id: str) -> bool:
    for t in project.studio_tracks:
        before = len(t.clips)
        t.clips = [c for c in t.clips if c.id != clip_id]
        if len(t.clips) != before:
            project.touch()
            return True
    return False
