from __future__ import annotations

from pathlib import Path
from .audio.analysis import analyze_vocal_file
from .lyrics import LyricCue, align_lyrics, to_lrc


def to_srt(cues: list[LyricCue]) -> str:
    def stamp(seconds: float) -> str:
        ms = max(0, round(float(seconds) * 1000))
        h, rem = divmod(ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    blocks = []
    for index, cue in enumerate(cues, 1):
        blocks.append(f"{index}\n{stamp(cue.start)} --> {stamp(cue.end)}\n{cue.text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def align_and_write(lyrics: str, vocal_path: str | Path, output_dir: str | Path) -> tuple[list[LyricCue], Path, Path]:
    vocal = analyze_vocal_file(vocal_path)
    cues = align_lyrics(lyrics, vocal.phrase_regions, vocal.duration)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    lrc = out / "lyrics.lrc"; lrc.write_text(to_lrc(cues), encoding="utf-8")
    srt = out / "lyrics.srt"; srt.write_text(to_srt(cues), encoding="utf-8")
    return cues, lrc, srt
