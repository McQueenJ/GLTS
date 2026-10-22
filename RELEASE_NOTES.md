# Global Language Translation Service (GLTS) v0.1.2

Removes the optional Sana’ani/Yemeni speech pack, download controls, installer, runtime selection, and its Transformers conversion dependency. All audio now uses standard Whisper. Sana’ani text and transcript translation through Ollama, experimental dialect suggestions, and transcription-only mode remain available.

Validated with 45 passing automated tests (one Arabic-pack test skipped), including actual standard Whisper inference with network connections blocked. Browser checks confirmed removal of speech-pack controls, functioning Ollama Settings and the transcription task; the browser transcription response was mocked.

Update source files while preserving `.venv`, `.local`, and `models`. Include all new source/assets, then restart GLTS and refresh with Ctrl+F5. The old `prepare_sanaani.py` and `speech_packs.py` files are retired and may be removed from an existing installation. Previously downloaded `models/whisper-yemeni` files are not used and may be deleted manually to reclaim space. Keep `models/whisper-tiny` for normal transcription. No new dependencies are needed, and existing installed Transformers libraries do not need to be uninstalled.

Earlier release notes below describe historical behavior, not the current release.

---

# Global Language Translation Service (GLTS) v0.1.1

Adds a **Transcribe audio only** task. Original-language transcripts can be copied or saved as UTF-8 notes or PDF files, without invoking a translation engine. It uses the existing Whisper model and optional Sana’ani/Yemeni speech pack. Translation remains the default task.

Validated with 44 passing automated tests (one model-dependent Arabic-pack test skipped) and browser checks for switching tasks, displaying a transcript, downloading a text note and PDF, and returning to translation. The browser speech response was mocked; the PDF request used the real export endpoint. Previously installed speech inference is covered by the existing offline model test. Windows and CUDA behavior have not been independently validated here.

This update adds no new dependencies. To install or update, follow the Windows instructions below, preserving `.venv`, `.local`, and `models`.

---

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
