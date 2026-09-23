from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mutagen.aiff import AIFF
from mutagen.asf import ASF
from mutagen.flac import FLAC
from mutagen.id3 import TALB, COMM, TIT2, TPE1, USLT
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE


@dataclass
class TrackMetadata:
    title: str = ""
    artist: str = ""
    album: str = ""
    lyrics: str = ""
    comment: str = "Created with Drellion Nexus"


def sidecar_lyrics(audio_path: str | Path, lyrics: str) -> Path:
    target = Path(audio_path).with_suffix(".txt")
    target.write_text(lyrics, encoding="utf-8")
    return target


def timed_lyrics_path(audio_path: str | Path) -> Path:
    return Path(audio_path).with_suffix(".lrc")


def _write_id3(audio, metadata: TrackMetadata) -> None:
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags
    for frame in ("TIT2", "TPE1", "TALB", "USLT", "COMM"):
        tags.delall(frame)
    if metadata.title:
        tags.add(TIT2(encoding=3, text=metadata.title))
    if metadata.artist:
        tags.add(TPE1(encoding=3, text=metadata.artist))
    if metadata.album:
        tags.add(TALB(encoding=3, text=metadata.album))
    if metadata.lyrics:
        tags.add(USLT(encoding=3, lang="eng", desc="", text=metadata.lyrics))
    if metadata.comment:
        tags.add(COMM(encoding=3, lang="eng", desc="", text=metadata.comment))
    audio.save()


def embed_metadata(audio_path: str | Path, metadata: TrackMetadata) -> list[str]:
    """Embed common tags/lyrics and return non-fatal warnings.

    Unsupported formats receive a UTF-8 lyric sidecar instead of silently
    discarding the user's lyrics.
    """
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    warnings: list[str] = []

    try:
        if suffix == ".mp3":
            _write_id3(MP3(path), metadata)
        elif suffix == ".wav":
            _write_id3(WAVE(path), metadata)
        elif suffix in {".aiff", ".aif"}:
            _write_id3(AIFF(path), metadata)
        elif suffix == ".flac":
            audio = FLAC(path)
            if metadata.title:
                audio["title"] = metadata.title
            if metadata.artist:
                audio["artist"] = metadata.artist
            if metadata.album:
                audio["album"] = metadata.album
            if metadata.lyrics:
                audio["lyrics"] = metadata.lyrics
            if metadata.comment:
                audio["comment"] = metadata.comment
            audio.save()
        elif suffix == ".ogg":
            audio = OggVorbis(path)
            if metadata.title:
                audio["title"] = metadata.title
            if metadata.artist:
                audio["artist"] = metadata.artist
            if metadata.album:
                audio["album"] = metadata.album
            if metadata.lyrics:
                audio["lyrics"] = metadata.lyrics
            if metadata.comment:
                audio["comment"] = metadata.comment
            audio.save()
        elif suffix == ".opus":
            audio = OggOpus(path)
            if metadata.title:
                audio["title"] = metadata.title
            if metadata.artist:
                audio["artist"] = metadata.artist
            if metadata.album:
                audio["album"] = metadata.album
            if metadata.lyrics:
                audio["lyrics"] = metadata.lyrics
            if metadata.comment:
                audio["comment"] = metadata.comment
            audio.save()
        elif suffix in {".m4a", ".mp4"}:
            audio = MP4(path)
            if audio.tags is None:
                audio.add_tags()
            if metadata.title:
                audio.tags["\xa9nam"] = [metadata.title]
            if metadata.artist:
                audio.tags["\xa9ART"] = [metadata.artist]
            if metadata.album:
                audio.tags["\xa9alb"] = [metadata.album]
            if metadata.lyrics:
                audio.tags["\xa9lyr"] = [metadata.lyrics]
            if metadata.comment:
                audio.tags["\xa9cmt"] = [metadata.comment]
            audio.save()
        elif suffix == ".wma":
            audio = ASF(path)
            if metadata.title:
                audio["Title"] = [metadata.title]
            if metadata.artist:
                audio["Author"] = [metadata.artist]
            if metadata.album:
                audio["WM/AlbumTitle"] = [metadata.album]
            if metadata.lyrics:
                audio["WM/Lyrics"] = [metadata.lyrics]
            if metadata.comment:
                audio["Description"] = [metadata.comment]
            audio.save()
        elif metadata.lyrics:
            sidecar = sidecar_lyrics(path, metadata.lyrics)
            warnings.append(
                f"{suffix or 'This format'} has no Drellion metadata writer; "
                f"lyrics were saved to {sidecar.name}."
            )
    except Exception as exc:
        if metadata.lyrics:
            sidecar = sidecar_lyrics(path, metadata.lyrics)
            warnings.append(
                f"Metadata embedding failed ({exc}); lyrics were saved to {sidecar.name}."
            )
        else:
            warnings.append(f"Metadata embedding failed: {exc}")

    return warnings
