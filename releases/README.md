# GLTS v0.1.0 Windows source release

- `GLTS-v0.1.0-Windows.zip`: versioned source package.
- `GLTS-Windows.zip`: the same package under the existing download filename.
- `SHA256SUMS`: checksums for both ZIP filenames.

The package includes all application source, the GLTS logo, the PDF font and license, Windows install/launch scripts, release notes, documentation and tests. It excludes local environments, settings, credentials and downloaded model weights. This is not a standalone EXE.

Read `RELEASE_NOTES.md` and `README.md` inside the extracted GLTS folder for installation and upgrade instructions. Keep `.venv`, `.local`, and `models` when updating, and run the dependency installation command before restarting. Ollama is installed separately for local language-model translation.

The release tag is `v0.1.0`. The tag `glts-before-auto-detect` retains the earlier version without experimental source detection.

To verify a downloaded archive in Windows PowerShell, use `Get-FileHash .\GLTS-v0.1.0-Windows.zip -Algorithm SHA256` and compare it to `SHA256SUMS`.
