from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import numpy as np
import soundfile as sf

from .analysis import vocal_pitch_class
from .contracts import ReferenceAnalysis, VocalAnalysis

SR = 48000


def _env(n: int, attack: float, release: float, sr: int = SR) -> np.ndarray:
    e = np.ones(n, dtype=np.float32)
    a = min(n, max(1, int(attack * sr)))
    r = min(n, max(1, int(release * sr)))
    e[:a] = np.linspace(0, 1, a, dtype=np.float32)
    e[-r:] *= np.linspace(1, 0, r, dtype=np.float32)
    return e


def _kick(length: float = 0.34) -> np.ndarray:
    n = int(length * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = 52 + 95 * np.exp(-t * 18)
    phase = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(phase) * np.exp(-t * 12)
    return (sig * 0.9).astype(np.float32)


def _snare(length: float = 0.22, seed: int = 7) -> np.ndarray:
    n = int(length * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / SR
    noise = rng.normal(0, 1, n).astype(np.float32)
    tone = np.sin(2*np.pi*190*t).astype(np.float32)
    sig = (0.72*noise + 0.28*tone) * np.exp(-t*20)
    return sig.astype(np.float32)


def _hat(length: float = 0.055, seed: int = 13) -> np.ndarray:
    n = int(length * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / SR
    noise = rng.normal(0, 1, n).astype(np.float32)
    hp = np.concatenate([[0], np.diff(noise)]).astype(np.float32)
    return (hp * np.exp(-t*45) * 0.22).astype(np.float32)


def _note_freq(pc: int, octave: int) -> float:
    midi = (octave + 1) * 12 + pc
    return float(440.0 * 2 ** ((midi - 69) / 12))


def _synth_note(freq: float, seconds: float, amp: float = 0.12) -> np.ndarray:
    n = max(1, int(seconds * SR))
    t = np.arange(n, dtype=np.float32) / SR
    s = (
        np.sin(2*np.pi*freq*t)
        + 0.32*np.sin(2*np.pi*freq*2*t)
        + 0.14*np.sin(2*np.pi*freq*3*t)
    )
    return (s * _env(n, 0.04, min(0.25, seconds*0.3)) * amp / 1.46).astype(np.float32)


def _add(dst: np.ndarray, src: np.ndarray, at: int, gain: float = 1.0) -> None:
    if at >= len(dst):
        return
    n = min(len(src), len(dst)-at)
    dst[at:at+n] += src[:n] * gain


def _section_energy(ref: ReferenceAnalysis, t: float, duration: float) -> float:
    curve = ref.energy_curve or [1.0]
    idx = min(len(curve)-1, int((t/max(duration,1e-6))*len(curve)))
    return float(max(0.18, curve[idx]))


@dataclass
class GeneratedArrangement:
    stereo: np.ndarray
    bpm: float
    root_pc: int


def generate_original_arrangement(
    vocal: VocalAnalysis,
    reference: ReferenceAnalysis,
    duration: float,
    variant: int = 0,
    sr: int = SR,
) -> GeneratedArrangement:
    bpm = float(reference.bpm if 55 <= reference.bpm <= 190 else 88.0)
    seconds_per_beat = 60.0 / bpm
    n = int(duration * sr)
    drums = np.zeros(n, dtype=np.float32)
    bass = np.zeros(n, dtype=np.float32)
    music = np.zeros(n, dtype=np.float32)

    root = vocal_pitch_class(vocal.pitch_track)
    # Generic, intentionally independent progressions; no reference harmony is extracted.
    progressions = [
        [0, 8, 3, 10],
        [0, 5, 8, 3],
        [0, 10, 8, 5],
    ]
    progression = progressions[variant % len(progressions)]

    beat = 0
    while beat * seconds_per_beat < duration:
        t = beat * seconds_per_beat
        energy = _section_energy(reference, t, duration)
        pos = beat % 4
        at = int(t * sr)

        if pos in (0, 2) or (variant == 1 and pos == 3 and beat % 8 == 7):
            _add(drums, _kick(), at, 0.78 + 0.24*energy)
        if pos in (1, 3):
            _add(drums, _snare(seed=7+variant), at, 0.48 + 0.25*energy)

        subdivisions = 2 if energy < 0.70 else 4
        for sub in range(subdivisions):
            ht = t + sub * (seconds_per_beat / subdivisions)
            if variant == 2 and sub == 1 and beat % 2 == 0:
                ht += seconds_per_beat * 0.035
            _add(drums, _hat(seed=13+variant+beat%5), int(ht*sr), 0.65 + 0.25*energy)

        if pos == 0:
            bar = beat // 4
            degree = progression[bar % len(progression)]
            bass_pc = (root + degree) % 12
            note = _synth_note(_note_freq(bass_pc, 2), seconds_per_beat*1.65, 0.18 + 0.08*energy)
            _add(bass, note, at)

            chord_pcs = [bass_pc, (bass_pc + 3 + (bar % 2)) % 12, (bass_pc + 7) % 12]
            chord_len = seconds_per_beat * 3.8
            for j, pc in enumerate(chord_pcs):
                tone = _synth_note(_note_freq(pc, 4 + (1 if j == 2 else 0)), chord_len, 0.050 + 0.035*energy)
                _add(music, tone, at, 1.0)
        beat += 1

    mono = drums + bass + music
    peak = float(np.max(np.abs(mono)) or 1.0)
    mono = mono / max(1.0, peak / 0.86)

    # Gentle original stereo spread using decorrelated delay, not reference audio.
    delay = int(0.011 * sr)
    right = np.roll(mono, delay)
    right[:delay] = 0
    left = mono
    stereo = np.column_stack([left, right]).astype(np.float32)
    return GeneratedArrangement(stereo=stereo, bpm=bpm, root_pc=root)


def write_arrangement(path: str | Path, arrangement: GeneratedArrangement, sr: int = SR) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sf.write(target, arrangement.stereo, sr, subtype="PCM_24")
    return target
