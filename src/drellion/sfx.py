from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import random

from .library import SoundLibrary
from .lyrics import LyricCue


@dataclass(frozen=True)
class SfxSuggestion:
    time: float
    lyric: str
    reason: str
    options: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["options"] = list(self.options)
        return data


_RULES: list[tuple[tuple[str, ...], tuple[str, ...], str]] = [
    (("rain", "storm", "thunder", "lightning"), ("rain", "storm", "thunder"), "weather image"),
    (("gun", "shot", "shoot", "bullet"), ("gunshot", "gun shot", "shot"), "lyric impact"),
    (("door", "knock", "knocking"), ("door", "knock"), "literal lyric cue"),
    (("car", "drive", "road", "engine"), ("car", "engine", "drive"), "motion cue"),
    (("phone", "call", "ring"), ("phone", "ring", "call"), "literal lyric cue"),
    (("heart", "heartbeat", "pulse"), ("heartbeat", "heart beat", "pulse"), "body/pulse cue"),
    (("fall", "drop", "down", "break", "crash", "hit"), ("impact", "crash", "hit", "drop"), "dramatic accent"),
    (("rise", "up", "higher", "fly", "lift"), ("riser", "whoosh", "uplifter", "sweep"), "lift/transition"),
    (("dark", "night", "ghost", "fear", "alone"), ("dark", "drone", "ambience", "atmosphere"), "atmosphere"),
]


def _keywords_for_line(text: str, index: int) -> tuple[tuple[str, ...], str]:
    lower = text.lower()
    for triggers, keywords, reason in _RULES:
        if any(trigger in lower for trigger in triggers):
            return keywords, reason
    if index % 4 == 3:
        return ("impact", "transition", "whoosh", "riser"), "phrase transition"
    return (), ""


def suggest_sfx(
    cues: list[LyricCue],
    library: SoundLibrary,
    *,
    max_moments: int = 12,
) -> list[SfxSuggestion]:
    if not library.items:
        library.scan()
    if not library.items or not cues:
        return []

    general = library.find_keywords(
        ("impact", "transition", "whoosh", "riser", "sweep", "fx"),
        limit=200,
    )
    suggestions: list[SfxSuggestion] = []

    for index, cue in enumerate(cues):
        keywords, reason = _keywords_for_line(cue.text, index)
        if not keywords:
            continue

        candidates = library.find_keywords(keywords, limit=120)
        pool = candidates + [item for item in general if item not in candidates]
        if not pool:
            continue

        seed_bytes = hashlib.sha1(f"{cue.start:.3f}:{cue.text}".encode("utf-8")).digest()
        rng = random.Random(int.from_bytes(seed_bytes[:8], "big"))
        unique: list[str] = []
        shuffled = list(pool)
        rng.shuffle(shuffled)
        for item in shuffled:
            if item.path not in unique:
                unique.append(item.path)
            if len(unique) == 3:
                break

        if unique:
            suggestions.append(
                SfxSuggestion(
                    time=cue.start,
                    lyric=cue.text,
                    reason=reason,
                    options=tuple(unique),
                )
            )
        if len(suggestions) >= max_moments:
            break

    return suggestions
