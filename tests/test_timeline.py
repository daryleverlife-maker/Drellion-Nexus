from __future__ import annotations

from array import array
from pathlib import Path
import math
import shutil
import wave

import pytest

from drellion.project import ProjectState, TrackState
from drellion.timeline import add_clip, duplicate_clip, render_timeline, split_clip


def _tone(path: Path, seconds: float = 1.0, hz: float = 220.0) -> None:
    rate = 16000
    pcm = array("h")
    for i in range(round(rate * seconds)):
        value = math.sin(2 * math.pi * hz * (i / rate)) * 0.2
        pcm.append(round(value * 32767))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())


def test_track_clip_round_trip_and_editing(tmp_path: Path):
    source = tmp_path / "clip.wav"
    _tone(source, 2.0)

    state = ProjectState(name="Studio")
    track = TrackState(name="Vocal", role="vocal")
    state.tracks.append(track)

    clip = add_clip(track, source, duration=2.0)
    clone = duplicate_clip(track, clip.id, offset=2.0)
    assert clone.start == 2.0
    assert len(track.clips) == 2

    left, right = split_clip(track, clip.id, 1.0)
    assert left.duration == pytest.approx(1.0)
    assert right.source_offset == pytest.approx(1.0)
    assert len(track.clips) == 3

    project_path = state.save(tmp_path / "studio.drellion")
    loaded = ProjectState.load(project_path)
    assert loaded.schema_version >= 2
    assert len(loaded.tracks) == 1
    assert len(loaded.tracks[0].clips) == 3


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is required")
def test_timeline_render(tmp_path: Path):
    one = tmp_path / "one.wav"
    two = tmp_path / "two.wav"
    _tone(one, 1.0, 220.0)
    _tone(two, 1.0, 330.0)

    state = ProjectState(name="Render")
    first = TrackState(name="One")
    second = TrackState(name="Two")
    state.tracks.extend([first, second])
    add_clip(first, one, start=0.0, duration=1.0)
    add_clip(second, two, start=0.25, duration=1.0)

    target = render_timeline(state, tmp_path / "mix.wav")
    assert target.is_file()
    assert target.stat().st_size > 1024
