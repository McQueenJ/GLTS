# GLTS v0.1.2 Windows source release

- `GLTS-v0.1.2-Windows.zip`: latest source package; removes the dedicated Sana’ani speech pack.
- `GLTS-v0.1.1-Windows.zip`: previous source package with transcription-only mode.
- `GLTS-v0.1.0-Windows.zip`: previous source release.
- `GLTS-Windows.zip`: latest source snapshot, including README corrections after the versioned release.
- `SHA256SUMS`: checksums for the versioned packages and latest ZIP.

The package includes all application source, the GLTS logo, the PDF font and license, Windows install/launch scripts, release notes, documentation and tests. It excludes local environments, settings, credentials and downloaded model weights. This is not a standalone EXE.

Read `RELEASE_NOTES.md` and `README.md` inside the extracted GLTS folder for installation and upgrade instructions. Keep `.venv`, `.local`, and `models` when updating, and run the dependency installation command before restarting. Ollama is installed separately for local language-model translation.

The latest release tag is `v0.1.2`. The tag `glts-before-auto-detect` retains the earlier version without experimental source detection.

To verify a downloaded archive in Windows PowerShell, use `Get-FileHash .\GLTS-v0.1.2-Windows.zip -Algorithm SHA256` and compare it to `SHA256SUMS`.
