from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib.util

from .lyrics import LyricCue


@dataclass
class TranscriptionResult:
    text: str
    cues: list[LyricCue]
    language: str = ""


class FasterWhisperTranscriber:
    id = "faster-whisper"
    name = "faster-whisper"

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("faster_whisper") is not None

    def transcribe(self, audio_path: str | Path, model_size: str = "small") -> TranscriptionResult:
        if not self.available():
            raise RuntimeError("faster-whisper is not installed. Install the optional transcription model pack first.")
        from faster_whisper import WhisperModel

        model = WhisperModel(model_size, device="auto", compute_type="auto")
        segments, info = model.transcribe(str(audio_path), word_timestamps=True, vad_filter=True)
        cues: list[LyricCue] = []
        text_parts = []
        for segment in segments:
            segment_text = (segment.text or "").strip()
            if segment_text:
                text_parts.append(segment_text)
            words = getattr(segment, "words", None) or []
            if words:
                for word in words:
                    token = (word.word or "").strip()
                    if token and word.start is not None and word.end is not None:
                        cues.append(LyricCue(float(word.start), float(word.end), token))
            elif segment_text:
                cues.append(LyricCue(float(segment.start), float(segment.end), segment_text))
        return TranscriptionResult("\n".join(text_parts), cues, getattr(info, "language", "") or "")
