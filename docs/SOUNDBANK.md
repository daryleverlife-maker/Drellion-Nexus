# Drellion sound library packaging

The default Drellion soundbank is intentionally separate from Git history.

## Versioning

Application, sound library and offline model packs use independent versions. Example:

- App: 1.0.0
- Sound library: 1.0
- Offline models: 1.0

## Release layout

Recommended GitHub Release assets:

- Drellion-Nexus-Setup.exe
- Drellion-Nexus-Portable.zip
- Drellion-Soundbank-Part1.zip
- Drellion-Soundbank-Part2.zip
- Drellion-Soundbank-Part3.zip
- Drellion-Soundbank-Part4.zip
- checksums.sha256

At install/import time Nexus should validate each package checksum before indexing the audio library.
