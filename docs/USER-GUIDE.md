# Drellion Nexus 2.0 User Guide

## Start a project

Choose **Create From Vocal**, **Rework a Song**, or **Open Studio**. Set the project name, artist, save location, start mode, import policy, and autosave interval. Drellion creates the complete project folder immediately.

## 1. Sources

Add up to six sources in Auto. Assign each a role such as Lead Vocal, Backing Vocal, Drums, Bass, Music, Instrument, Other, or Full Song. Use **Preserve** for material that must remain and **Rebuild** for a part you want replaced. WAV lead vocals are analysed for phrases, voiced activity, duration, level, and pitch range/median.

Full-song sources can be separated when an optional Open-Unmix or Spleeter integration is installed. The original file is never changed.

## 2. References

Add up to six references. Local audio can be analysed for tempo estimate, low-end balance, energy, dynamics, and stereo character. A YouTube URL loads public oEmbed metadata and can be played in an embedded YouTube player; Drellion does not download the media stream.

Set each reference's overall weight and whether it influences drums, bass, energy, arrangement, tone, stereo character, and mastering direction.

## 3. Direction

Set reference influence from Original to Strong Reference, then optionally choose Cinematic, Harder, Cleaner, Darker and add production notes. The generated prompt explicitly instructs engines not to reproduce exact melodies, hooks, samples or beat sequences.

## 4. Previews

Click **Generate 3 Previews**. Drellion chooses a representative vocal-heavy region when possible and requests three different seeds. Each candidate is quality checked before it becomes selectable. Audition vocal-only, instrumental-only, or the combined preview.

If no production engine is ready, Drellion stops and tells you to configure ACE-Step or DiffRhythm. It will not silently use the Basic Test Engine.

## 5. Build

Select a QC-passed preview and build the full arrangement using the same seed and direction. If a stem separator is installed, Drellion can create editable generated stems automatically; otherwise the generated instrumental remains a nondestructive stem and can be separated later.

## 6. Master

Choose target loudness and true peak. Windows builds bundle FFmpeg, which Drellion uses for EBU R128 loudness normalization. A conservative PCM peak-normalization fallback exists for environments where FFmpeg is unavailable.

## Studio

Studio provides a library, multitrack timeline, inspector and mixer. Clips can be moved by dragging or with numeric/button alternatives; split, trim, duplicate, source offset, clip gain, fade-in, fade-out and crossfade are nondestructive project instructions. Tracks expose volume, pan, mute and solo.

## Lyrics & Timing

Paste/edit lyrics, then align lyric lines to the vocal duration or install the optional faster-whisper extra for transcription workflows. Timed lyrics can be exported as LRC and SRT.

## Versions and recovery

**Save** updates the current project. **Save As** creates another project location and switches to it. **Save Copy** creates a backup without switching. **Snapshot** stores a named project state. If Drellion finds a newer autosave whose content actually differs from the manual save, it offers recovery on open.

## Export

Export master WAV plus optional MP3, FLAC, M4A, stems, timed lyrics, metadata, premaster and project archive from one screen.

## Accessibility

The Accessibility button is always in the top bar. UI scale and text scale are separate. Dark, Light and High Contrast themes are available. Primary workflows are keyboard operable, controls expose values, and every drag-based Studio operation also has a non-drag alternative.
