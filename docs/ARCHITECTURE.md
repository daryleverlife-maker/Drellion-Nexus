# Drellion Nexus architecture

## Product modes

### AI Auto
Guided workflow:

1. Vocal & Lyrics
2. Reference
3. Sounds
4. Arrangement Preview
5. Build
6. Master

The vocal is the musical anchor. The reference supplies production direction, not copied audio or an exact composition.

### Custom Studio
The Studio workspace shares the same project state and engine. Auto-created material must remain editable and non-destructive in the timeline.

## Core rules

- Finished-song input is optional.
- Vocal-only is a first-class workflow.
- Original imported files are never overwritten.
- Generation operations create new versions and history entries.
- Reference audio never enters rendered output directly.
- Exact reference onset sequences, melody, bassline, hooks and samples are not reused.
- Preview before full generation.
- Mastering occurs after arrangement and mix decisions.
- Large models and the default sound library are versioned outside normal Git history.

## Distribution

Source lives in GitHub. Windows builds are produced by GitHub Actions. Large sound/model packages are distributed separately through versioned release assets.
