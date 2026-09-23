from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LyricCue:
    start: float
    end: float
    text: str


def align_lyrics(
    lyrics: str,
    phrase_regions: list[tuple[float, float]],
    duration: float,
) -> list[LyricCue]:
    """Align lyric lines to detected vocal phrase regions.

    This is a deterministic phrase-level fallback. Future word-level/phoneme
    aligners can replace it without changing the project/export contract.
    """
    lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
    if not lines:
        return []

    duration = max(0.1, float(duration))
    clean_regions = [
        (max(0.0, float(start)), min(duration, max(float(start), float(end))))
        for start, end in phrase_regions
        if float(end) > float(start)
    ]

    if not clean_regions:
        step = duration / len(lines)
        return [
            LyricCue(i * step, min(duration, (i + 1) * step), text)
            for i, text in enumerate(lines)
        ]

    if len(clean_regions) >= len(lines):
        if len(lines) == 1:
            indices = [0]
        else:
            indices = [
                round(i * (len(clean_regions) - 1) / (len(lines) - 1))
                for i in range(len(lines))
            ]
        return [
            LyricCue(clean_regions[index][0], clean_regions[index][1], text)
            for text, index in zip(lines, indices)
        ]

    # More lyric lines than detected phrases: preserve the detected vocal span
    # but subdivide it so every user-provided line receives an editable cue.
    start = clean_regions[0][0]
    end = clean_regions[-1][1]
    span = max(0.1, end - start)
    step = span / len(lines)
    return [
        LyricCue(start + i * step, min(end, start + (i + 1) * step), text)
        for i, text in enumerate(lines)
    ]


def _lrc_stamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"[{minutes:02d}:{remainder:05.2f}]"


def to_lrc(cues: list[LyricCue]) -> str:
    return "\n".join(f"{_lrc_stamp(cue.start)}{cue.text}" for cue in cues) + ("\n" if cues else "")
