# Drellion Nexus — User Guide

## What Drellion Nexus is

Drellion Nexus is designed around a vocal-first workflow. A user can begin with a vocal stem and lyrics, choose a reference track for production direction, choose sounds, audition arrangement previews, build the song, and master/export it.

## AI Auto

### 1. Vocal & Lyrics
Load a vocal stem. A completed song is optional. Choose Natural, Polished, or Flexible vocal preservation. Paste lyrics when available so timing and later SFX suggestions can follow the performance.

### 2. Reference
Load a local reference song. Reference Influence controls how strongly broad production traits guide the new song. Originality Protection controls how aggressively the generator avoids identifiable reference patterns.

### 3. Sounds
Use the installed Drellion sound library or choose another folder. Refresh rescans supported audio files.

### 4. Preview
Generate three different vocal-matched arrangement previews. Audition the vocal with each proposed backing and select one before the full build.

### 5. Build
Build creates the full arrangement. The target architecture separates drums, bass, harmony/music, SFX, vocal, instrumental and premix so Studio mode can edit them non-destructively.

### 6. Master
Mastering is the final polish. It should not be used as a substitute for arrangement generation. Export supports delivery masters, instrumental/acapella/stems, lyric timestamp files and project archives.

## Custom Studio

Custom Studio is the detailed multitrack workspace. The alpha shell contains track, timeline, mixer and transport areas. The production target includes clip trim/split/duplicate/fades, automation, mixer sends, AI section tools, versioned alternatives, snap/grid and non-destructive history.

## Saving and recovery

Drellion projects use the `.drellion` extension. Autosave writes a recovery copy every 15 seconds. Undo and redo operate on project-state snapshots.

## Sound library packages

The main Git repository does not contain multi-gigabyte sound assets. Drellion sound libraries are versioned separately and can be installed or refreshed independently of the application.

## Copyright-aware reference workflow

Reference audio is used for analysis and production direction. Drellion is designed not to copy reference audio, exact beat/onset sequences, melody, bassline, hooks or samples into generated output. Users remain responsible for the rights to any source audio, lyrics, samples or other material they import.

## Export

The export subsystem is designed around FFmpeg-compatible outputs including WAV, FLAC, MP3, AAC/M4A, ALAC, AIFF, OGG and Opus, plus project/stem/timing exports. Available codecs depend on the FFmpeg build bundled with a release.
