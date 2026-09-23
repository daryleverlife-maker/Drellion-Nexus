from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass
class TrackMetadata:
    title:str=''
    artist:str=''
    album:str=''
    lyrics:str=''
    comment:str='Created with Drellion Nexus'

def sidecar_lyrics(audio_path:str|Path,lyrics:str)->Path:
    target=Path(audio_path).with_suffix('.txt')
    target.write_text(lyrics,encoding='utf-8')
    return target

def timed_lyrics_path(audio_path:str|Path)->Path:
    return Path(audio_path).with_suffix('.lrc')
