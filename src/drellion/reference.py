from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import requests
import numpy as np
from mutagen import File as MutagenFile

from .audio_core import read_wav, mono, rms, dbfs


YOUTUBE_RE = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,})")


@dataclass(frozen=True)
class ReferenceProfile:
    duration_seconds: float | None
    bpm_estimate: float | None
    low_end: str
    energy: str
    dynamics: str
    stereo: str
    source: str

    def to_dict(self) -> dict:
        return {
            "duration_seconds": self.duration_seconds,
            "bpm_estimate": self.bpm_estimate,
            "low_end": self.low_end,
            "energy": self.energy,
            "dynamics": self.dynamics,
            "stereo": self.stereo,
            "source": self.source,
        }


def youtube_video_id(url: str) -> str | None:
    match = YOUTUBE_RE.search(url or "")
    return match.group(1) if match else None


def media_duration(path: str | Path) -> float | None:
    try:
        obj = MutagenFile(str(path))
        return float(obj.info.length) if obj and obj.info else None
    except Exception:
        return None


def _estimate_bpm(envelope: np.ndarray, sample_rate: int) -> float | None:
    if len(envelope) < sample_rate * 4:
        return None
    hop = max(1, sample_rate // 100)
    frames = len(envelope) // hop
    env = np.array([np.mean(np.abs(envelope[i * hop:(i + 1) * hop])) for i in range(frames)], dtype=np.float64)
    env = np.diff(env, prepend=env[0])
    env = np.maximum(env, 0)
    env -= env.mean()
    if np.max(np.abs(env)) < 1e-8:
        return None
    min_lag = int(100 * 60 / 200)
    max_lag = int(100 * 60 / 55)
    corr = np.correlate(env, env, mode="full")[len(env) - 1:]
    window = corr[min_lag:min(max_lag, len(corr))]
    if not len(window):
        return None
    lag = int(np.argmax(window)) + min_lag
    bpm = 60.0 * 100.0 / lag
    if bpm < 70:
        bpm *= 2
    if bpm > 180:
        bpm /= 2
    return round(float(bpm), 1)


def analyze_reference(path: str | Path) -> ReferenceProfile:
    p = Path(path)
    duration = media_duration(p)
    if p.suffix.lower() != ".wav":
        return ReferenceProfile(duration, None, "unknown", "unknown", "unknown", "unknown", "metadata-only")
    audio = read_wav(p)
    x = mono(audio.samples)
    duration = audio.duration
    n = min(len(x), audio.sample_rate * 90)
    y = x[:n]
    if len(y) < 256:
        return ReferenceProfile(duration, None, "unknown", "very low", "unknown", "mono", "wav-analysis")
    fft = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
    freqs = np.fft.rfftfreq(len(y), 1.0 / audio.sample_rate)
    total = float(fft.sum()) + 1e-12
    low_ratio = float(fft[freqs < 180].sum() / total)
    level_db = dbfs(rms(y))
    crest = dbfs(float(np.max(np.abs(y))) + 1e-12) - level_db
    stereo = "mono"
    if audio.channels > 1:
        l = audio.samples[:n, 0]
        r = audio.samples[:n, 1]
        corr = float(np.corrcoef(l, r)[0, 1]) if np.std(l) > 1e-8 and np.std(r) > 1e-8 else 1.0
        stereo = "wide" if corr < 0.45 else "moderate" if corr < 0.85 else "narrow"
    low = "heavy" if low_ratio >= 0.25 else "balanced" if low_ratio >= 0.12 else "light"
    energy = "high" if level_db > -16 else "medium" if level_db > -24 else "low"
    dynamics = "open" if crest > 13 else "moderate" if crest > 8 else "controlled"
    return ReferenceProfile(duration, _estimate_bpm(y, audio.sample_rate), low, energy, dynamics, stereo, "wav-analysis")


def fetch_youtube_metadata(url: str, timeout: int = 8) -> dict[str, str]:
    """Fetch public oEmbed metadata without downloading the media stream."""
    if not youtube_video_id(url):
        raise ValueError("Invalid YouTube URL")
    response = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return {
        "title": str(payload.get("title") or "YouTube reference"),
        "artist": str(payload.get("author_name") or ""),
        "channel": str(payload.get("author_name") or ""),
        "thumbnail_url": str(payload.get("thumbnail_url") or ""),
    }
