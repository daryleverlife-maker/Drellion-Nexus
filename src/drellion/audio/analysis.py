from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
import math
import subprocess

from .contracts import ReferenceAnalysis, VocalAnalysis
from .runtime import require_ffmpeg


@dataclass(frozen=True)
class DecodedMono:
    sample_rate: int
    samples: array

    @property
    def duration(self) -> float:
        return len(self.samples) / float(self.sample_rate or 1)


def decode_mono(path: str | Path, sample_rate: int = 16000) -> DecodedMono:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)

    command = [
        require_ffmpeg(),
        "-v", "error",
        "-i", str(source),
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "s16le",
        "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace")[-4000:]
        raise RuntimeError(message or f"Could not decode {source.name}")

    pcm = array("h")
    pcm.frombytes(result.stdout)
    if not pcm:
        raise ValueError("Audio contains no decodable samples.")
    return DecodedMono(sample_rate, pcm)


def _frame_rms(decoded: DecodedMono, frame_seconds: float = 0.05) -> list[float]:
    size = max(64, int(decoded.sample_rate * frame_seconds))
    values: list[float] = []
    samples = decoded.samples
    for start in range(0, len(samples), size):
        block = samples[start:start + size]
        if not block:
            break
        power = sum(float(x) * float(x) for x in block) / len(block)
        values.append(math.sqrt(power) / 32768.0)
    return values


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    peak = max(values)
    if peak <= 1e-12:
        return [0.0 for _ in values]
    return [min(1.0, max(0.0, x / peak)) for x in values]


def _energy_curve(values: list[float], parts: int = 12) -> list[float]:
    if not values:
        return [0.0] * parts
    output: list[float] = []
    for index in range(parts):
        a = round(index * len(values) / parts)
        b = round((index + 1) * len(values) / parts)
        chunk = values[a:max(a + 1, b)]
        output.append(sum(chunk) / len(chunk))
    return _normalize(output)


def _onset_envelope(rms: list[float]) -> list[float]:
    if not rms:
        return []
    result = [0.0]
    previous = rms[0]
    for current in rms[1:]:
        result.append(max(0.0, current - previous))
        previous = current
    return _normalize(result)


def estimate_bpm(rms: list[float], frame_seconds: float = 0.05) -> float:
    onset = _onset_envelope(rms)
    if not onset or max(onset, default=0.0) < 0.03:
        return 0.0

    mean = sum(onset) / len(onset)
    centered = [x - mean for x in onset]
    best_score = float("-inf")
    best_bpm = 0.0

    for bpm in range(60, 181):
        lag = max(1, round((60.0 / bpm) / frame_seconds))
        if lag >= len(centered):
            continue
        score = sum(centered[i] * centered[i - lag] for i in range(lag, len(centered)))
        # Prefer a musically useful middle range if harmonics tie.
        score *= 1.0 - min(0.25, abs(bpm - 100) / 800.0)
        if score > best_score:
            best_score = score
            best_bpm = float(bpm)
    return best_bpm


def _phrase_regions(rms: list[float], frame_seconds: float = 0.05) -> list[tuple[float, float]]:
    if not rms:
        return []
    ordered = sorted(rms)
    noise = ordered[max(0, int(len(ordered) * 0.25) - 1)]
    active_peak = ordered[-1]
    threshold = max(0.006, noise * 2.2, active_peak * 0.06)
    min_frames = max(2, round(0.18 / frame_seconds))
    gap_frames = max(2, round(0.22 / frame_seconds))

    regions: list[tuple[float, float]] = []
    start: int | None = None
    quiet = 0

    for i, value in enumerate(rms):
        if value >= threshold:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet >= gap_frames:
                end = i - quiet + 1
                if end - start >= min_frames:
                    regions.append((start * frame_seconds, end * frame_seconds))
                start = None
                quiet = 0

    if start is not None:
        end = len(rms)
        if end - start >= min_frames:
            regions.append((start * frame_seconds, end * frame_seconds))
    return regions


def _coarse_pitch_track(decoded: DecodedMono, rms: list[float], frame_seconds: float = 0.05) -> list[tuple[float, float]]:
    """Estimate a lightweight monophonic pitch contour from an isolated vocal.

    This deliberately favors speed and robustness over note-level transcription.
    A heavier Basic Pitch/pYIN backend can replace it without changing the engine contract.
    """
    samples = decoded.samples
    frame_size = max(128, int(decoded.sample_rate * frame_seconds))
    ordered = sorted(rms)
    activity_threshold = max(
        0.008,
        ordered[max(0, int(len(ordered) * 0.35) - 1)] * 1.8 if ordered else 0.008,
    )
    track: list[tuple[float, float]] = []

    # Analyze at 10 Hz rather than every sample frame.
    stride_frames = max(1, round(0.10 / frame_seconds))
    for rms_index in range(0, len(rms), stride_frames):
        if rms[rms_index] < activity_threshold:
            continue
        start = rms_index * frame_size
        block = samples[start:start + frame_size]
        if len(block) < frame_size // 2:
            continue

        # Remove a simple DC estimate before counting zero crossings.
        mean = sum(block) / len(block)
        crossings = 0
        previous = block[0] - mean
        for sample in block[1:]:
            current = sample - mean
            if (previous <= 0 < current) or (previous >= 0 > current):
                crossings += 1
            previous = current

        hz = crossings / (2.0 * (len(block) / decoded.sample_rate))
        if 70.0 <= hz <= 700.0:
            track.append((rms_index * frame_seconds, hz))
    return track


def dominant_vocal_pitch_class(track: list[tuple[float, float]]) -> int | None:
    if not track:
        return None
    histogram = [0] * 12
    for _, hz in track:
        if hz <= 0:
            continue
        midi = round(69 + 12 * math.log2(hz / 440.0))
        histogram[midi % 12] += 1
    if not any(histogram):
        return None
    return max(range(12), key=histogram.__getitem__)


def analyze_vocal_file(path: str | Path) -> VocalAnalysis:
    decoded = decode_mono(path)
    rms = _frame_rms(decoded)
    return VocalAnalysis(
        duration=decoded.duration,
        phrase_regions=_phrase_regions(rms),
        pitch_track=_coarse_pitch_track(decoded, rms),
    )


def analyze_reference_file(path: str | Path) -> ReferenceAnalysis:
    decoded = decode_mono(path)
    rms = _frame_rms(decoded)
    onset = _onset_envelope(rms)
    active = sum(1 for x in onset if x > 0.18)
    onset_density = active / max(decoded.duration, 0.001)

    return ReferenceAnalysis(
        bpm=estimate_bpm(rms),
        duration=decoded.duration,
        energy_curve=_energy_curve(rms),
        groove={
            "onset_density": onset_density,
            "pulse_strength": max(onset, default=0.0),
        },
        tone={},
        stereo={},
        dynamics={
            "rms_peak": max(rms, default=0.0),
            "rms_mean": sum(rms) / max(1, len(rms)),
        },
    )
