from __future__ import annotations

from pathlib import Path
import subprocess

from .runtime import require_ffmpeg


_VOCAL_FILTERS = {
    "natural": (
        "aresample=44100,"
        "highpass=f=65,"
        "lowpass=f=18500,"
        "acompressor=threshold=-20dB:ratio=1.5:attack=15:release=120:makeup=1,"
        "alimiter=limit=0.98:attack=5:release=80"
    ),
    "polished": (
        "aresample=44100,"
        "highpass=f=75,"
        "afftdn=nf=-28,"
        "equalizer=f=250:t=q:w=1.2:g=-1.5,"
        "equalizer=f=3500:t=q:w=1.0:g=1.5,"
        "acompressor=threshold=-22dB:ratio=2.2:attack=8:release=100:makeup=2,"
        "alimiter=limit=0.97:attack=5:release=80"
    ),
    "flexible": (
        "aresample=44100,"
        "highpass=f=80,"
        "afftdn=nf=-24,"
        "equalizer=f=220:t=q:w=1.2:g=-2,"
        "equalizer=f=4200:t=q:w=1.0:g=2,"
        "dynaudnorm=f=150:g=9:p=0.80,"
        "acompressor=threshold=-24dB:ratio=2.8:attack=5:release=85:makeup=2.5,"
        "alimiter=limit=0.96:attack=5:release=70"
    ),
}


def process_vocal(
    source_path: str | Path,
    target_path: str | Path,
    mode: str = "Polished",
) -> Path:
    """Render a non-destructive vocal derivative.

    The source recording is never modified. These modes intentionally use
    cleanup/dynamics/tone processing only; they do not impersonate or replace
    the singer's vocal identity.
    """
    source = Path(source_path)
    target = Path(target_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)

    key = (mode or "Polished").strip().lower()
    filters = _VOCAL_FILTERS.get(key, _VOCAL_FILTERS["polished"])
    result = subprocess.run(
        [
            require_ffmpeg(),
            "-y",
            "-v", "error",
            "-i", str(source),
            "-vn",
            "-af", filters,
            "-c:a", "pcm_s24le",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:] or "Vocal processing failed.")
    return target
