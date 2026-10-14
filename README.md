# Global Language Translation Tool (GLTS)

An offline web GUI for translating text, selectable-text PDFs, and audio. Translation uses local Argos Translate language packs. Speech recognition uses a local multilingual Whisper model on CPU. Translation and transcription work offline. Settings can explicitly download additional language packs while online; no API key is needed. All fonts, scripts, and styles are local.

## Windows 11 installation

1. Install Python 3.12 (64-bit) from https://www.python.org/downloads/windows/, including the Python launcher.
2. Download this repository using GitHub **Code → Download ZIP**, then extract it to a folder you can write to.
3. Open the extracted folder and double-click `install-windows.cmd` while connected to the internet. It installs dependencies, English/Spanish/Arabic language packs, and the local speech model. Wait for the installation-complete message.
4. Double-click `launch-windows.cmd`, keep its window open, and visit `http://127.0.0.1:5000` in your browser.
5. Select Arabic as the source and English as the target to translate Arabic content. You can disconnect from the internet after installation completes. Press Ctrl+C in the launch window to stop the server.

Windows installation has not yet been validated on a Windows machine. If setup fails, keep the error message and rerun installation after correcting the reported issue. The initial downloads must be reachable from your workstation; this cloud environment's network policy does not apply to your personal computer.

## Setup

Requires Python 3.12. Initial installation downloads packages and models. After setup, disconnect from the internet and run normally. For an air-gapped machine, prepare and transfer compatible dependencies and the model directories from a connected machine.

```sh
python -m venv .venv
.venv/bin/pip install torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements.txt
.venv/bin/python prepare_models.py --languages en es ar
.venv/bin/python app.py
```

Use your local browser on port 5000. Select the source and target languages, type text or upload a file, then translate. Results can be copied or downloaded as UTF-8 TXT. Arabic → English is included by the setup command. Language packs may support indirect translation through English; quality varies.

`prepare_models.py` is an explicitly online setup utility, never invoked by the app. Models are stored under `models/` and `.local/` and should be retained for offline use. Additional packs can be downloaded using `--languages` or installed from local `.argosmodel` files with `argostranslate.package.install_from_path`. The runtime uses only installed packs and the local speech model.

## Settings

Click **Settings** in the GUI:

- **Dark mode** is saved in your browser and restored on your next visit.
- **Language packs** shows locally installed packs. Click **Refresh available packs** while online, search for a language, then click **Download** for the direction you need. Language selectors update after installation; documents are never sent during pack downloads. Installed packs remain usable offline.
- **Maximum upload size** accepts 1–1024 MB (25 MB by default). Changes apply immediately and persist in `.local/settings.json`. Larger uploads require more RAM and processing time. The extracted-text limit remains 100,000 characters.
- **Compute mode** offers CPU (default) or CUDA for NVIDIA GPUs. CUDA applies to both translation and speech recognition. On Windows, install a compatible NVIDIA driver, CUDA 12, and cuDNN 9, ensuring their DLL directories are on PATH, then restart GLTS. See the [faster-whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu). GPU detection alone does not verify all runtime libraries. If CUDA fails, return to CPU in Settings. CUDA inference has not been tested on a GPU in this environment.

### Updating an existing Windows installation

Stop GLTS, download the latest GitHub ZIP, and copy its source files into your existing GLTS folder. Keep `.venv`, `.local`, and `models` so your dependencies, settings, and language packs are retained. Launch GLTS again and refresh the browser (Ctrl+F5).

## Limits

- Uploaded files: up to the limit chosen in Settings (25 MB by default). Extracted text: up to 100,000 characters.
- PDF text extraction requires selectable text. Scanned PDFs, OCR, and PDF layout preservation are not included.
- Audio formats: MP3, WAV, M4A, MP4, MPEG, MPGA, WEBM. Source language must match the speech. The transcript is displayed alongside the translation.
- The tiny speech model is economical on CPU; Arabic dialects and noisy recordings may need a larger model for reliable results.
- Files and results are processed in memory and are not saved by GLTS. Review important translations for accuracy.
- This is a local single-user app. The server binds to loopback; public deployment requires a production server and access controls.

## Validation

```sh
.venv/bin/pytest -q
```

Tests cover GUI rendering, upload handling, validation, transcription integration, and real Arabic translation with network connections blocked when its pack is installed.
