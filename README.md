# Drellion Nexus 2.0

Drellion Nexus 2.0 is a vocal-first, reference-guided music production application for Windows. The 2.0 rebuild separates three concepts throughout the project model and UI:

- **Sources** — the user's vocal, stems, songs, instruments, and other owned project material.
- **References** — up to six production-direction references in Auto mode, with local audio analysis and YouTube identity/player support.
- **Generated** — new preview candidates, full builds, stems, mixes, masters, and versions created by Drellion.

## 2.0 workflow

**Source → Reference → Direction → 3 Previews + QC → Build → Master → Studio → Export**

The user's performance is the musical anchor. References provide high-level direction such as energy, drum character, low-end balance, arrangement shape, stereo character, and mastering direction. Drellion does not intentionally copy reference recordings, exact beat sequences, melodies/hooks, or samples.

## Generation engines

Drellion 2.0 uses an **Engine Broker** instead of silently switching to a procedural synth. Configure one or more of:

- ACE-Step HTTP/custom endpoint
- DiffRhythm HTTP endpoint
- DiffRhythm local checkout

The **Basic Test Engine** is developer/demo quality and requires explicit opt-in. It is never selected automatically.

## Preview quality gate

Auto always requests three different 20–30 second candidates first. Each is checked for clipping, low-end foundation, transient activity, silence, stereo phase, excessive repetition, and vocal/music balance where measurable. A rejected preview cannot be selected for the full Build stage.

## Project layout

Each project is self-contained:

    My Song/
      Project.drellion
      Sources/
      References/
      Stems/
      Generated/
      Previews/
      Masters/
      Exports/
      Lyrics/
      Autosaves/
      Versions/
      Cache/

Drellion supports Save, Save As, Save Copy, named snapshots, crash-recovery autosaves, media consolidation, relinking, and Project Health checks.

## Studio

Studio uses a conventional production hierarchy: transport, left library, central multitrack timeline, right inspector, and bottom mixer. The 2.0 data model supports nondestructive clip move, split, trim, duplicate, source offset, clip gain, fades, crossfades, track volume/pan, mute, and solo. Drag operations have button/value alternatives for keyboard and screen-reader users.

## Accessibility

The Accessibility Center includes UI scale, independent text scale, system/Atkinson/OpenDyslexic font preferences, dark/light/high-contrast themes, color-vision preferences, enhanced focus, reduced/no motion preferences, keyboard-only emphasis, large-control modes, waveform contrast, numeric meter mode, and spoken-feedback preference. Standard widgets receive programmatic accessible names, and editing functions have non-drag alternatives.

## Optional AI/audio packages

The base installer stays reasonably small. Heavier capabilities are optional:

    pip install -e ".[transcription]"
    pip install -e ".[separation-openunmix]"
    pip install -e ".[separation-spleeter]"

FFmpeg is bundled into Windows builds and is used for media conversion and EBU R128 loudness normalization when available.

## Development

    python -m pip install -e ".[dev]"
    pytest
    python -m drellion.app

The active clean-room rebuild branch is `v2.0-rebuild`.
