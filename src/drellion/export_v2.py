from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import zipfile

from .exporter import export_audio
from .project import ProjectState


FORMAT_PRESETS = {
    "wav": "WAV 24-bit",
    "mp3": "MP3 320k",
    "flac": "FLAC",
    "m4a": "AAC/M4A",
    "mp4": "MP4 Waveform Video",
}


@dataclass
class ExportPlan:
    formats: list[str] = field(default_factory=lambda: ["wav", "mp3"])
    export_stems: bool = True
    lyrics_lrc: bool = True
    lyrics_srt: bool = False
    project_archive: bool = False


def export_project(project: ProjectState, destination: str | Path, plan: ExportPlan) -> list[Path]:
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    source = project.master_path or project.build_path or project.finished_song.path
    if not source or not Path(source).is_file():
        raise ValueError("A master, build, or finished song is required before export.")

    safe_name = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in (project.name or "Drellion Export")).strip()
    outputs: list[Path] = []
    for fmt in plan.formats:
        preset = FORMAT_PRESETS.get(fmt.lower())
        if not preset:
            continue
        outputs.append(export_audio(source, target / safe_name, preset))

    if plan.export_stems:
        stems = dict(project.settings.get("generated_stems", {}) or {})
        source_dir = target / "Stems"
        source_dir.mkdir(exist_ok=True)
        for role, raw in stems.items():
            path = Path(str(raw))
            if path.is_file():
                out = source_dir / f"{role}{path.suffix.lower()}"
                shutil.copy2(path, out)
                outputs.append(out)
        # Always make the user's preserved source materials available in the stem package.
        for index, item in enumerate(project.sources, 1):
            if item.enabled and item.path and Path(item.path).is_file() and item.preserve:
                path = Path(item.path)
                label = item.role.replace(" ", "-") or f"source-{index}"
                out = source_dir / f"{label}-{index}{path.suffix.lower()}"
                shutil.copy2(path, out)
                outputs.append(out)

    lrc_path = Path(str(project.settings.get("lyrics_lrc_path", "")))
    if plan.lyrics_lrc and lrc_path.is_file():
        out = target / f"{safe_name}.lrc"; shutil.copy2(lrc_path, out); outputs.append(out)

    srt_path = Path(str(project.settings.get("lyrics_srt_path", "")))
    if plan.lyrics_srt and srt_path.is_file():
        out = target / f"{safe_name}.srt"; shutil.copy2(srt_path, out); outputs.append(out)

    if plan.project_archive and project.project_root and Path(project.project_root).is_dir():
        archive = target / f"{safe_name}-Project.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            root = Path(project.project_root)
            for path in root.rglob("*"):
                if path.is_file() and target not in path.parents:
                    z.write(path, path.relative_to(root))
        outputs.append(archive)
    return outputs
