from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from .runtime import require_ffmpeg


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:] or "Audio render failed.")


def mix_vocal_and_instrumental(
    vocal_path: str | Path,
    instrumental_path: str | Path,
    target_path: str | Path,
    *,
    vocal_gain_db: float = 0.0,
    instrumental_gain_db: float = -4.0,
    vocal_start: float = 0.0,
    duration: float | None = None,
) -> Path:
    vocal = Path(vocal_path)
    instrumental = Path(instrumental_path)
    target = Path(target_path)
    if not vocal.is_file():
        raise FileNotFoundError(vocal)
    if not instrumental.is_file():
        raise FileNotFoundError(instrumental)
    target.parent.mkdir(parents=True, exist_ok=True)

    command = [require_ffmpeg(), "-y", "-v", "error"]
    if vocal_start > 0:
        command += ["-ss", f"{vocal_start:.6f}"]
    command += ["-i", str(vocal), "-i", str(instrumental)]
    if duration is not None:
        command += ["-t", f"{max(0.1, duration):.6f}"]

    filter_graph = (
        f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,"
        f"volume={vocal_gain_db}dB[v];"
        f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
        f"volume={instrumental_gain_db}dB[i];"
        "[v][i]amix=inputs=2:duration=longest:dropout_transition=1.5,"
        "alimiter=limit=0.96:attack=5:release=80[out]"
    )
    command += [
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-c:a", "pcm_s24le",
        str(target),
    ]
    _run(command)
    return target


def mix_sfx_events(
    instrumental_path: str | Path,
    events: list[dict],
    target_path: str | Path,
) -> Path:
    """Mix selected user-library SFX onto an instrumental at timestamped moments."""
    source = Path(instrumental_path)
    target = Path(target_path)
    if not source.is_file():
        raise FileNotFoundError(source)

    clean = []
    for event in events[:24]:
        path = Path(str(event.get("path", "")))
        if path.is_file():
            clean.append({
                "path": path,
                "time": max(0.0, float(event.get("time", 0.0))),
                "gain_db": min(3.0, max(-30.0, float(event.get("gain_db", -10.0)))),
            })
    if not clean:
        return copy_audio(source, target)

    target.parent.mkdir(parents=True, exist_ok=True)
    command = [require_ffmpeg(), "-y", "-v", "error", "-i", str(source)]
    for event in clean:
        command += ["-i", str(event["path"])]

    filters = ["[0:a]aformat=sample_rates=44100:channel_layouts=stereo[base]"]
    mix_inputs = ["[base]"]
    for index, event in enumerate(clean, start=1):
        delay = round(event["time"] * 1000.0)
        label = f"s{index}"
        filters.append(
            f"[{index}:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"volume={event['gain_db']}dB,adelay={delay}|{delay}[{label}]"
        )
        mix_inputs.append(f"[{label}]")

    filters.append(
        "".join(mix_inputs)
        + f"amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0,"
        + "alimiter=limit=0.96:attack=5:release=80[out]"
    )

    command += [
        "-filter_complex", ";".join(filters),
        "-map", "[out]",
        "-c:a", "pcm_s24le",
        str(target),
    ]
    _run(command)
    return target


def master_audio(
    source_path: str | Path,
    target_path: str | Path,
    *,
    target_lufs: float = -14.0,
    true_peak: float = -1.0,
) -> Path:
    source = Path(source_path)
    target = Path(target_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)

    target_lufs = min(-7.0, max(-24.0, float(target_lufs)))
    true_peak = min(-0.2, max(-3.0, float(true_peak)))
    filters = (
        "highpass=f=25,"
        "acompressor=threshold=-16dB:ratio=1.6:attack=18:release=140:makeup=1,"
        f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11,"
        "alimiter=limit=0.97:attack=5:release=80"
    )
    _run([
        require_ffmpeg(), "-y", "-v", "error",
        "-i", str(source),
        "-vn",
        "-af", filters,
        "-c:a", "pcm_s24le",
        str(target),
    ])
    return target


def copy_audio(source_path: str | Path, target_path: str | Path) -> Path:
    source = Path(source_path)
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target
