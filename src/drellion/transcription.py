from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class WordStamp:
    start: float
    end: float
    word: str


@dataclass
class Transcript:
    text: str
    language: str = ""
    words: list[WordStamp] | None = None


def transcribe_faster_whisper(
    source: str | Path,
    *,
    model_size: str = "small",
    device: str = "auto",
) -> Transcript:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Install the optional transcription pack."
        ) from exc

    compute_type = "int8" if device in {"auto", "cpu"} else "float16"
    actual_device = "cpu" if device == "auto" else device
    model = WhisperModel(model_size, device=actual_device, compute_type=compute_type)
    segments, info = model.transcribe(
        str(source),
        word_timestamps=True,
        vad_filter=True,
    )
    lines: list[str] = []
    words: list[WordStamp] = []
    for segment in segments:
        text = str(segment.text or "").strip()
        if text:
            lines.append(text)
        for word in segment.words or []:
            if word.start is None or word.end is None:
                continue
            words.append(WordStamp(float(word.start), float(word.end), str(word.word or "").strip()))
    return Transcript(
        text="\n".join(lines),
        language=str(getattr(info, "language", "") or ""),
        words=words,
    )


def words_to_lrc(words: Iterable[WordStamp]) -> str:
    lines = []
    for item in words:
        minutes = int(item.start // 60)
        seconds = item.start - minutes * 60
        lines.append(f"[{minutes:02d}:{seconds:05.2f}]{item.word}")
    return "\n".join(lines) + ("\n" if lines else "")
