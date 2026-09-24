# Drellion Nexus release assets

A user-facing Drellion Nexus release is considered complete when these three primary downloads exist:

1. **Drellion-Nexus-Setup.exe** — normal Windows installer.
2. **Drellion-Nexus-Portable.zip** — portable Windows build.
3. **Drellion-Soundbank-Pack.zip** — the extracted, indexed-ready Drellion sound library.

A small **checksums.sha256** file may also be published for verification.

## Soundbank pack

Do not commit the soundbank or multipart RAR files to Git history.

On a Windows machine with the four multipart source archives together, run:

```powershell
.\tools\build_soundbank_pack.ps1 -Part1 "C:\path\to\soundbank.part1.rar"
```

The script:

- verifies parts 1–4 are present;
- extracts the multipart archive with 7-Zip;
- confirms supported audio is present;
- writes `drellion-soundbank.json`;
- produces `Drellion-Soundbank-Pack.zip`;
- prints the SHA-256 checksum.

Only publish sound samples for which redistribution rights are confirmed.
