from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil,subprocess

@dataclass(frozen=True)
class ExportPreset:
    name:str
    extension:str
    codec_args:tuple[str,...]

PRESETS={
 'WAV':ExportPreset('WAV','.wav',('-c:a','pcm_s24le')),
 'FLAC':ExportPreset('FLAC','.flac',('-c:a','flac')),
 'MP3 320k':ExportPreset('MP3 320k','.mp3',('-c:a','libmp3lame','-b:a','320k')),
 'AAC/M4A':ExportPreset('AAC/M4A','.m4a',('-c:a','aac','-b:a','256k')),
 'ALAC':ExportPreset('ALAC','.m4a',('-c:a','alac')),
 'AIFF':ExportPreset('AIFF','.aiff',('-c:a','pcm_s24be')),
 'OGG Vorbis':ExportPreset('OGG Vorbis','.ogg',('-c:a','libvorbis','-q:a','7')),
 'Opus':ExportPreset('Opus','.opus',('-c:a','libopus','-b:a','192k')),
}

def ffmpeg_path()->str:
    return shutil.which('ffmpeg') or ''

def export_audio(source:str|Path,target:str|Path,preset_name:str)->Path:
    ff=ffmpeg_path()
    if not ff: raise RuntimeError('FFmpeg is required for this export format.')
    preset=PRESETS[preset_name]; out=Path(target)
    if out.suffix.lower()!=preset.extension: out=out.with_suffix(preset.extension)
    out.parent.mkdir(parents=True,exist_ok=True)
    cmd=[ff,'-y','-i',str(source),'-vn',*preset.codec_args,str(out)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    if result.returncode: raise RuntimeError(result.stderr[-4000:])
    return out
