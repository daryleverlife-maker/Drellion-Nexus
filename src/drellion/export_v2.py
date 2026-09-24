from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import shutil
import subprocess
import zipfile

from .lyrics_v2 import LyricLine, export_lrc, export_srt
from .master_v2 import ffmpeg_path
from .project import ProjectState


@dataclass
class ExportOptions:
    wav: bool = True
    mp3: bool = True
    flac: bool = False
    m4a: bool = False
    stems: bool = True
    lyrics_lrc: bool = True
    lyrics_srt: bool = True
    metadata: bool = True
    project_archive: bool = False
    premaster: bool = False


@dataclass
class ExportResult:
    output_dir: Path
    files: list[Path]


def _convert(source: Path, destination: Path) -> bool:
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), str(destination)], capture_output=True)
    return proc.returncode == 0 and destination.exists()


def export_project(project: ProjectState, destination: str | Path | None = None, options: ExportOptions | None = None) -> ExportResult:
    options = options or ExportOptions()
    out = Path(destination) if destination else project.folder("Exports")
    out.mkdir(parents=True, exist_ok=True)
    master = project.selected_master()
    build = project.selected_build()
    source = Path(master.path) if master and Path(master.path).exists() else Path(build.mix_path) if build and Path(build.mix_path).exists() else None
    if source is None:
        raise RuntimeError("Nothing is ready to export")
    stem = "".join(c if c.isalnum() or c in " .-_" else "_" for c in project.title).strip() or "Drellion Export"
    files: list[Path] = []
    if options.wav:
        target = out / f"{stem}.wav"
        shutil.copy2(source, target)
        files.append(target)
    for enabled, ext in ((options.mp3, "mp3"), (options.flac, "flac"), (options.m4a, "m4a")):
        if enabled:
            target = out / f"{stem}.{ext}"
            if _convert(source, target):
                files.append(target)
    if options.premaster and build and Path(build.mix_path).exists():
        target = out / f"{stem}-Premaster{Path(build.mix_path).suffix}"
        shutil.copy2(build.mix_path, target)
        files.append(target)
    if options.stems and build:
        stem_dir = out / "Stems"
        stem_dir.mkdir(exist_ok=True)
        for item in build.stems:
            src = Path(item.path)
            if src.exists():
                target = stem_dir / f"{item.role}{src.suffix}"
                shutil.copy2(src, target)
                files.append(target)
        for source_asset in project.sources:
            if source_asset.enabled and source_asset.preserve and Path(source_asset.path).exists():
                src = Path(source_asset.path)
                target = stem_dir / f"Source-{source_asset.role}-{source_asset.label}{src.suffix}"
                shutil.copy2(src, target)
                files.append(target)
    timed = [LyricLine(float(x.get("start", 0)), float(x.get("end", 0)), str(x.get("text", ""))) for x in project.lyrics_timed]
    if timed and options.lyrics_lrc:
        files.append(export_lrc(timed, out / f"{stem}.lrc"))
    if timed and options.lyrics_srt:
        files.append(export_srt(timed, out / f"{stem}.srt"))
    if options.metadata:
        meta = out / f"{stem}-metadata.json"
        meta.write_text(json.dumps({
            "title": project.title,
            "artist": project.artist,
            "build": build.label if build else "",
            "engine": build.engine if build else "",
            "master": master.measurements if master else {},
        }, indent=2), encoding="utf-8")
        files.append(meta)
    if options.project_archive:
        archive = out / f"{stem}-project.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder in ("Sources", "References", "Stems", "Generated", "Masters", "Lyrics"):
                root = project.folder(folder)
                for item in root.rglob("*"):
                    if item.is_file():
                        zf.write(item, item.relative_to(project.root_path))
            if project.project_file.exists():
                zf.write(project.project_file, project.project_file.name)
        files.append(archive)
    return ExportResult(out, files)
