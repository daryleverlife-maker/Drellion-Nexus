# Drellion Nexus 2.0 Release Gate

The rebuild is structured around the strict 2.0 gate rather than trying to ship every backlog idea at once.

- [x] Proper permanent project storage and predictable project folders
- [x] Up to six source uploads in Auto; unlimited Studio track model
- [x] Up to six references in Auto with per-category influence controls
- [x] ACE-Step / DiffRhythm Engine Broker with no silent Basic fallback
- [x] Vocal phrase/pitch/activity analysis and timed-lyrics foundation
- [x] Three genuinely separate preview requests with distinct seeds
- [x] Automatic preview QC before selection/Build
- [x] Generated-stem model plus optional automatic separation path
- [x] Redesigned Studio hierarchy with nondestructive clip and mixer editing
- [x] Reliable FFmpeg loudness-normalization mastering path plus safe fallback
- [x] Accessibility Center, scalable controls/text, semantic names and non-drag editing alternatives
- [x] Central Export Center
- [x] Save / Save As / Save Copy / snapshots / autosave recovery
- [x] Project Files, Storage, Engine Status and Project Health screens

## Mandatory listening test before declaring an audio-quality release

Use the same vocal and reference direction that exposed the v1 procedural failure. Generate three previews through a real configured ACE-Step or DiffRhythm engine. All user-selectable candidates must pass Drellion QC and must be reviewed by ear before a release build is promoted.

The repository can verify architecture, serialization, QC rules, editing behavior, and packaging automatically. It cannot truthfully certify the musical quality of an external model without running that model on the real test material.
