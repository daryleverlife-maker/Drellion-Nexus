from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import random


SUPPORTED_AUDIO = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".aiff", ".aif", ".wma"}


@dataclass
class SoundItem:
    path: str
    name: str
    extension: str
    size: int
    fingerprint: str


@dataclass
class SoundPalette:
    kick: str = ""
    snare: str = ""
    hat: str = ""
    percussion: str = ""
    fx: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def sample_paths(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "kick": self.kick,
                "snare": self.snare,
                "hat": self.hat,
                "percussion": self.percussion,
            }.items()
            if value
        }


class SoundLibrary:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.items: list[SoundItem] = []

    def scan(self) -> list[SoundItem]:
        self.items = []
        if not self.root.exists():
            return self.items

        seen = set()
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_AUDIO:
                continue
            stat = path.stat()
            # This prevents duplicate catalogue rows for the exact same named file
            # while avoiding the cost of hashing multi-gigabyte libraries at startup.
            key = f"{stat.st_size}:{path.name.lower()}"
            fingerprint = hashlib.sha1(key.encode()).hexdigest()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            self.items.append(
                SoundItem(
                    str(path),
                    path.stem,
                    path.suffix.lower(),
                    stat.st_size,
                    fingerprint,
                )
            )
        return self.items

    def _matches(self, keywords: tuple[str, ...]) -> list[SoundItem]:
        matches = []
        for item in self.items:
            text = item.name.lower().replace("_", " ").replace("-", " ")
            if any(keyword in text for keyword in keywords):
                matches.append(item)
        return matches

    @staticmethod
    def _pick(candidates: list[SoundItem], rng: random.Random) -> str:
        if not candidates:
            return ""
        return rng.choice(candidates).path

    def pick_palette(self, variant: int = 0) -> SoundPalette:
        if not self.items:
            self.scan()
        rng = random.Random(94817 + int(variant) * 1709)

        kicks = self._matches(("kick", "bass drum", "bd "))
        snares = self._matches(("snare", "clap", "rimshot", "rim shot"))
        hats = self._matches(("hihat", "hi hat", "hi-hat", "hat closed", "hat open", "closed hat", "open hat"))
        percussion = self._matches(("perc", "shaker", "tamb", "snap", "rim", "conga", "bongo"))
        fx = self._matches(("riser", "impact", "whoosh", "sweep", "transition", "uplifter", "downlifter"))

        return SoundPalette(
            kick=self._pick(kicks, rng),
            snare=self._pick(snares, rng),
            hat=self._pick(hats, rng),
            percussion=self._pick(percussion, rng),
            fx=self._pick(fx, rng),
        )

    def save_catalog(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps([asdict(item) for item in self.items], indent=2),
            encoding="utf-8",
        )
        return target
