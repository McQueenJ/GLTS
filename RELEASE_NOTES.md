# Global Language Translation Service (GLTS) v0.1.0

This source release includes the GLTS logo in the application header, with readable presentation in light and dark mode and a layout that adapts to narrow screens.

## Included capabilities

- Text, selectable-text PDF and audio translation, including OPUS uploads and drag-and-drop.
- Offline Argos translation and local Ollama translation using Qwen2.5 3B, 7B or 14B.
- Optional noncommercial Yemeni/Sana’ani speech-model download and local transcription.
- Experimental language detection and tentative Sana’ani suggestions, with review before translation and a manual override.
- Dark mode, configurable upload size, CPU/CUDA selection for speech and Argos, loading indicator, and Clear button.
- Copy, UTF-8 note and PDF exports, including shaped Arabic PDF text.

## Windows installation

Install Python 3.12 (64-bit), extract the source ZIP, and run `install-windows.cmd` while online. After setup completes, run `launch-windows.cmd` and open `http://127.0.0.1:5000`. For local language models, install/start Ollama for Windows separately and download a model through GLTS Settings.

For an existing installation, stop every running GLTS instance, copy the updated source files into the existing folder, and preserve `.venv`, `.local` and `models`. Include the complete `assets` folder. Open PowerShell in the GLTS folder and run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Restart GLTS from that folder and refresh the browser with Ctrl+F5. The logo is served locally; no external image service is needed.

## Validation and limits

The automated suite passed 39 tests; one real Arabic-pack test was skipped because that pack is unavailable in the cloud test environment. Local optional Sana’ani speech inference and English/Arabic PDF export were exercised. Browser checks cover the logo in light/dark mode and at mobile width. Windows installation, GPU inference and real Qwen translation accuracy were not independently validated here. Review dialect translations for accuracy.

This is a source package, not a standalone EXE. Dependencies, downloaded model weights, credentials, personal settings and local environments are excluded. Initial model/dependency downloads require internet; prepared translation workflows run locally afterward. The optional Yemeni speech model has a noncommercial license; its download requires acceptance. See README.md and bundled third-party font license for details.
