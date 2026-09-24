# Drellion Nexus 2.0 Architecture

## Product boundary

Drellion's 2.0 product lane is: **keep the human performance, use references as production direction, generate an original editable backing, then let the user change everything in Studio.**

## Layers

1. **Project layer** (`project.py`, `autosave.py`, `versions.py`)
   - schema-versioned `.drellion` JSON
   - self-contained project folders
   - six Auto sources and six Auto references
   - nondestructive import/consolidation/relinking
   - builds, stems, masters, Studio tracks/clips, versions
2. **Analysis layer** (`vocal_analysis.py`, `reference.py`, `lyrics_v2.py`)
   - phrase/activity detection
   - pitch contour summary and confidence
   - reference duration/BPM/low-end/energy/dynamics/stereo profile
   - optional faster-whisper transcription and timed-lyrics export
3. **Generation layer** (`providers.py`, `production_v2.py`)
   - Engine Broker
   - ACE-Step HTTP provider
   - DiffRhythm HTTP/local providers
   - explicit-only Basic Test Engine
   - three-preview workflow and seed preservation into Build
4. **Quality layer** (`quality.py`)
   - QC before Build
   - clipping, silence, low-end, transient activity, stereo phase, repetition, vocal/music balance
5. **Stem layer** (`stems.py`)
   - optional Open-Unmix/Spleeter integration
   - originals remain untouched
6. **Mix/master/export layer** (`audio_core.py`, `master_v2.py`, `export_v2.py`)
   - PCM-safe internal operations
   - FFmpeg EBU R128 loudnorm when available
   - WAV/MP3/FLAC/M4A, stems, lyrics, metadata, archive
7. **UI layer** (`ui/`)
   - progressive Auto pages
   - full Studio shell and nondestructive clip editor
   - project dashboard, files, versions, storage, engines, health
   - persistent Accessibility entry point

## Engine policy

A production engine must report Ready before generation. If ACE-Step and DiffRhythm are unavailable, Auto stops with an explicit error. The Basic Test Engine is not a production fallback and requires deliberate opt-in and explicit selection.

## Reference policy

References guide high-level production characteristics. YouTube references use metadata and supported embedded playback; Drellion does not silently rip YouTube audio. Deep audio analysis is performed on local/authorized reference audio.

## Nondestructive policy

Imported originals are never modified. Studio edits are stored as source path + offset + timeline position + duration + gain/fades. Generated versions are appended rather than overwritten. Manual saves and recovery autosaves are distinct.
