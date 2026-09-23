from __future__ import annotations

from array import array
from pathlib import Path
import math
import shutil
import wave

import pytest

from drellion.engine import NexusEngine
from drellion.project import ProjectState


def _write_fixture(path: Path, *, seconds: float, rhythmic: bool) -> None:
    rate = 16000
    total = round(seconds * rate)
    pcm = array("h")

    for i in range(total):
        t = i / rate
        voice = math.sin(2 * math.pi * 220.0 * t) * 0.16
        pulse = 0.0
        if rhythmic:
            # 100 BPM quarter-note transient bed.
            beat = (t % 0.6)
            if beat < 0.06:
                pulse = math.sin(2 * math.pi * 90.0 * beat) * math.exp(-beat * 30.0) * 0.55
        else:
            # Phrase-like amplitude gaps for vocal analysis.
            phrase = 1.0 if int(t / 0.7) % 2 == 0 else 0.08
            voice *= phrase
        sample = max(-0.95, min(0.95, voice + pulse))
        pcm.append(round(sample * 32767))

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is required")
def test_preview_build_master_pipeline(tmp_path: Path):
    vocal = tmp_path / "vocal.wav"
    reference = tmp_path / "reference.wav"
    _write_fixture(vocal, seconds=5.0, rhythmic=False)
    _write_fixture(reference, seconds=5.0, rhythmic=True)

    state = ProjectState(name="Engine Test")
    state.vocal.path = str(vocal)
    state.reference.path = str(reference)
    state.selected_preview = "Preview B"
    state.settings["target_lufs"] = -14.0

    engine = NexusEngine()

    vocal_analysis = engine.analyze_vocal(state)
    reference_analysis = engine.analyze_reference(state)
    assert vocal_analysis.duration > 4.5
    assert vocal_analysis.phrase_regions
    assert reference_analysis.duration > 4.5
    assert reference_analysis.energy_curve

    previews = engine.generate_previews(state, tmp_path / "previews")
    assert len(previews) == 3
    assert all(Path(item.audio_path).is_file() for item in previews)
    assert len({Path(item.audio_path).read_bytes()[:4096] for item in previews}) >= 2

    build = engine.build(state, tmp_path / "build")
    assert Path(build.instrumental_path).is_file()
    assert Path(build.build_path).is_file()
    assert Path(build.report_path).is_file()

    state.build_path = build.build_path
    master = engine.master(state, tmp_path / "master")
    assert Path(master).is_file()
    assert Path(master).stat().st_size > 1024
