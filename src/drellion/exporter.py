from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .audio.runtime import require_ffmpeg


@dataclass(frozen=True)
class ExportPreset:
    name: str
    extension: str
    codec_args: tuple[str, ...]
    kind: str = "audio"


PRESETS = {
    "WAV 24-bit": ExportPreset("WAV 24-bit", ".wav", ("-c:a", "pcm_s24le")),
    "WAV 16-bit": ExportPreset("WAV 16-bit", ".wav", ("-c:a", "pcm_s16le")),
    "FLAC": ExportPreset("FLAC", ".flac", ("-c:a", "flac")),
    "MP3 320k": ExportPreset("MP3 320k", ".mp3", ("-c:a", "libmp3lame", "-b:a", "320k")),
    "AAC/M4A": ExportPreset("AAC/M4A", ".m4a", ("-c:a", "aac", "-b:a", "256k")),
    "ALAC": ExportPreset("ALAC", ".m4a", ("-c:a", "alac")),
    "AIFF": ExportPreset("AIFF", ".aiff", ("-c:a", "pcm_s24be")),
    "OGG Vorbis": ExportPreset("OGG Vorbis", ".ogg", ("-c:a", "libvorbis", "-q:a", "7")),
    "Opus": ExportPreset("Opus", ".opus", ("-c:a", "libopus", "-b:a", "192k")),
    "WMA": ExportPreset("WMA", ".wma", ("-c:a", "wmav2", "-b:a", "256k")),
    "MP4 Waveform Video": ExportPreset(
        "MP4 Waveform Video",
        ".mp4",
        ("-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "256k"),
        "video",
    ),
    "MOV Waveform Video": ExportPreset(
        "MOV Waveform Video",
        ".mov",
        ("-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "256k"),
        "video",
    ),
    "MKV Waveform Video": ExportPreset(
        "MKV Waveform Video",
        ".mkv",
        ("-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "256k"),
        "video",
    ),
    "WebM Waveform Video": ExportPreset(
        "WebM Waveform Video",
        ".webm",
        ("-c:v", "libvpx-vp9", "-crf", "31", "-b:v", "0", "-c:a", "libopus", "-b:a", "192k"),
        "video",
    ),
}


def export_audio(source: str | Path, target: str | Path, preset_name: str) -> Path:
    """Export audio or a waveform-video delivery preset.

    Kept under the historical export_audio name so existing callers and projects
    remain compatible.
    """
    preset = PRESETS[preset_name]
    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    output = Path(target)
    if output.suffix.lower() != preset.extension:
        output = output.with_suffix(preset.extension)
    output.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = require_ffmpeg()
    if preset.kind == "audio":
        command = [
            ffmpeg,
            "-y",
            "-v", "error",
            "-i", str(source_path),
            "-vn",
            *preset.codec_args,
            str(output),
        ]
    else:
        # Generate a clean waveform video directly from the finished audio.
        # The audio stream remains the user's rendered Drellion output.
        filter_graph = (
            "[0:a]aformat=channel_layouts=stereo,"
            "showwaves=s=1280x720:mode=p2p:rate=30,"
            "format=yuv420p[v]"
        )
        command = [
            ffmpeg,
            "-y",
            "-v", "error",
            "-i", str(source_path),
            "-filter_complex", filter_graph,
            "-map", "[v]",
            "-map", "0:a:0",
            *preset.codec_args,
            "-shortest",
            str(output),
        ]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:] or "Export failed.")
    return output
