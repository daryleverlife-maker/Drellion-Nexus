from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import struct
import wave

import numpy as np


@dataclass(frozen=True)
class AudioData:
    samples: np.ndarray  # float32, shape=(frames, channels)
    sample_rate: int

    @property
    def channels(self) -> int:
        return int(self.samples.shape[1]) if self.samples.ndim == 2 else 1

    @property
    def duration(self) -> float:
        return float(len(self.samples) / self.sample_rate) if self.sample_rate else 0.0


def _pcm_to_float(raw: bytes, sample_width: int, channels: int) -> np.ndarray:
    if sample_width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        x = b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16)
        x = np.where(x & 0x800000, x | ~0xFFFFFF, x)
        data = x.astype(np.float32) / 8388608.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported PCM sample width: {sample_width}")
    if channels > 1:
        data = data.reshape(-1, channels)
    else:
        data = data.reshape(-1, 1)
    return np.clip(data, -1.0, 1.0).astype(np.float32)


def read_wav(path: str | Path) -> AudioData:
    """Read PCM or IEEE-float RIFF/WAVE audio into float32 samples.

    Python's standard :mod:`wave` reader rejects WAVE_FORMAT_IEEE_FLOAT
    (format tag 3), which is a common output format from AI audio engines.
    Drellion parses the small RIFF header itself so generated float WAVs and
    ordinary PCM WAVs follow the same internal audio path.
    """
    path = Path(path)
    blob = path.read_bytes()
    if len(blob) < 12 or blob[:4] != b"RIFF" or blob[8:12] != b"WAVE":
        raise ValueError(f"Unsupported or invalid WAV file: {path}")

    fmt: bytes | None = None
    data_chunks: list[bytes] = []
    offset = 12
    while offset + 8 <= len(blob):
        chunk_id = blob[offset:offset + 4]
        chunk_size = struct.unpack_from("<I", blob, offset + 4)[0]
        start = offset + 8
        end = start + chunk_size
        if end > len(blob):
            raise ValueError(f"Truncated WAV chunk {chunk_id!r} in {path}")
        payload = blob[start:end]
        if chunk_id == b"fmt ":
            fmt = payload
        elif chunk_id == b"data":
            data_chunks.append(payload)
        offset = end + (chunk_size & 1)

    if fmt is None or len(fmt) < 16:
        raise ValueError(f"WAV format chunk is missing or invalid: {path}")
    if not data_chunks:
        raise ValueError(f"WAV data chunk is missing: {path}")

    format_tag, channels, sample_rate, _byte_rate, block_align, bits_per_sample = struct.unpack_from(
        "<HHIIHH", fmt, 0
    )
    # WAVE_FORMAT_EXTENSIBLE stores the real codec tag in the sub-format GUID.
    if format_tag == 0xFFFE and len(fmt) >= 40:
        format_tag = struct.unpack_from("<H", fmt, 24)[0]

    if channels < 1 or sample_rate < 1 or bits_per_sample < 1:
        raise ValueError(f"Invalid WAV format values in {path}")

    sample_width = (bits_per_sample + 7) // 8
    expected_align = channels * sample_width
    if block_align and block_align < expected_align:
        raise ValueError(f"Invalid WAV block alignment in {path}")

    raw = b"".join(data_chunks)
    frame_bytes = block_align or expected_align
    if frame_bytes <= 0:
        raise ValueError(f"Invalid WAV frame size in {path}")
    raw = raw[: len(raw) - (len(raw) % frame_bytes)]

    if format_tag == 1:  # WAVE_FORMAT_PCM
        return AudioData(_pcm_to_float(raw, sample_width, channels), sample_rate)

    if format_tag == 3:  # WAVE_FORMAT_IEEE_FLOAT
        if bits_per_sample == 32:
            samples = np.frombuffer(raw, dtype="<f4").astype(np.float32, copy=False)
        elif bits_per_sample == 64:
            samples = np.frombuffer(raw, dtype="<f8").astype(np.float32)
        else:
            raise ValueError(f"Unsupported IEEE-float WAV width: {bits_per_sample} bits")
        if channels > 1:
            samples = samples.reshape(-1, channels)
        else:
            samples = samples.reshape(-1, 1)
        samples = np.nan_to_num(samples, nan=0.0, posinf=1.0, neginf=-1.0)
        return AudioData(np.clip(samples, -1.0, 1.0).astype(np.float32, copy=False), sample_rate)

    raise ValueError(f"Unsupported WAV format tag: {format_tag}")


def write_wav(path: str | Path, samples: np.ndarray, sample_rate: int) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    x = np.nan_to_num(x, nan=0.0, posinf=1.0, neginf=-1.0)
    x = np.clip(x, -1.0, 1.0)
    pcm = (x * 32767.0).round().astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(int(x.shape[1]))
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())
    return path


def mono(samples: np.ndarray) -> np.ndarray:
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim == 1:
        return x
    return x.mean(axis=1)


def peak(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.max(np.abs(samples)))


def rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))


def dbfs(value: float) -> float:
    return -120.0 if value <= 1e-12 else float(20.0 * math.log10(value))


def seconds_to_frames(seconds: float, sample_rate: int) -> int:
    return max(0, int(round(seconds * sample_rate)))


def crop(audio: AudioData, start_seconds: float, duration_seconds: float) -> AudioData:
    start = seconds_to_frames(max(0.0, start_seconds), audio.sample_rate)
    end = min(len(audio.samples), start + seconds_to_frames(max(0.0, duration_seconds), audio.sample_rate))
    return AudioData(audio.samples[start:end].copy(), audio.sample_rate)


def match_channels(a: np.ndarray, channels: int) -> np.ndarray:
    x = np.asarray(a, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] == channels:
        return x
    if channels == 1:
        return x.mean(axis=1, keepdims=True)
    if x.shape[1] == 1:
        return np.repeat(x, channels, axis=1)
    return x[:, :channels]


def resample_linear(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    x = np.asarray(samples, dtype=np.float32)
    if src_rate == dst_rate or len(x) == 0:
        return x.copy()
    if x.ndim == 1:
        x = x[:, None]
    out_len = max(1, int(round(len(x) * dst_rate / src_rate)))
    src_pos = np.linspace(0.0, len(x) - 1, out_len)
    base = np.arange(len(x))
    out = np.stack([np.interp(src_pos, base, x[:, c]) for c in range(x.shape[1])], axis=1)
    return out.astype(np.float32)


def mix_tracks(tracks: list[tuple[AudioData, float]], headroom_db: float = 1.0) -> AudioData:
    if not tracks:
        raise ValueError("No tracks to mix")
    sr = max(t.sample_rate for t, _ in tracks)
    channels = max(t.channels for t, _ in tracks)
    prepared: list[tuple[np.ndarray, float]] = []
    max_len = 0
    for audio, gain_db in tracks:
        x = resample_linear(audio.samples, audio.sample_rate, sr)
        x = match_channels(x, channels)
        gain = 10.0 ** (gain_db / 20.0)
        prepared.append((x, gain))
        max_len = max(max_len, len(x))
    out = np.zeros((max_len, channels), dtype=np.float32)
    for x, gain in prepared:
        out[: len(x)] += x * gain
    p = peak(out)
    target = 10.0 ** (-abs(headroom_db) / 20.0)
    if p > target and p > 0:
        out *= target / p
    return AudioData(out, sr)
