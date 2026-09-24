from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class LyricLine:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "text": self.text}


def _fmt_lrc(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    sec = seconds - minutes * 60
    return f"{minutes:02d}:{sec:05.2f}"


def _fmt_srt(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def export_lrc(lines: Iterable[LyricLine], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(f"[{_fmt_lrc(line.start)}]{line.text}" for line in lines) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def export_srt(lines: Iterable[LyricLine], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    chunks = []
    for i, line in enumerate(lines, 1):
        chunks.append(f"{i}\n{_fmt_srt(line.start)} --> {_fmt_srt(line.end)}\n{line.text}\n")
    path.write_text("\n".join(chunks), encoding="utf-8")
    return path


def align_plain_lyrics(text: str, duration_seconds: float) -> list[LyricLine]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    step = max(0.5, duration_seconds / len(lines))
    return [LyricLine(i * step, min(duration_seconds, (i + 1) * step), line) for i, line in enumerate(lines)]


class WhisperTranscriber:
    """Optional faster-whisper adapter; not required for the base installation."""

    def __init__(self, model_size: str = "small") -> None:
        self.model_size = model_size

    def available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except Exception:
            return False

    def transcribe(self, path: str | Path) -> tuple[str, list[LyricLine]]:
        if not self.available():
            raise RuntimeError("faster-whisper is not installed. Install Drellion with the transcription extra.")
        from faster_whisper import WhisperModel

        model = WhisperModel(self.model_size, device="auto", compute_type="auto")
        segments, _info = model.transcribe(str(path), word_timestamps=True)
        lines: list[LyricLine] = []
        plain: list[str] = []
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            lines.append(LyricLine(float(segment.start), float(segment.end), text))
            plain.append(text)
        return "\n".join(plain), lines
