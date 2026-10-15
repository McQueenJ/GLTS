# Global Language Translation Service (GLTS)

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

Use your local browser on port 5000. Select the source and target languages, type text, choose a file, or drag a text/PDF/audio file into the upload area, then translate. Upload one file at a time; click Remove file to return to typed text. The Clear button above the text box clears the input, translation, transcript, detection preview and selected file, then focuses the text box for your next paste. Language and model settings are retained. Results can be copied or downloaded as UTF-8 TXT. Arabic → English is included by the setup command. Language packs may support indirect translation through English; quality varies.

`prepare_models.py` is an explicitly online setup utility, never invoked by the app. Models are stored under `models/` and `.local/` and should be retained for offline use. Additional packs can be downloaded using `--languages` or installed from local `.argosmodel` files with `argostranslate.package.install_from_path`. The runtime uses only installed packs and the local speech model.

## Settings

Click **Settings** in the GUI:

- **Dark mode** is saved in your browser and restored on your next visit.
- **Language packs** shows locally installed packs. Click **Refresh available packs** while online, search for a language, then click **Download** for the direction you need. Language selectors update after installation; documents are never sent during pack downloads. Installed packs remain usable offline.
- **Maximum upload size** accepts 1–1024 MB (25 MB by default). Changes apply immediately and persist in `.local/settings.json`. Larger uploads require more RAM and processing time. The extracted-text limit remains 100,000 characters.
- **Compute mode** offers CPU (default) or CUDA for NVIDIA GPUs. CUDA applies to both translation and speech recognition. On Windows, install a compatible NVIDIA driver, CUDA 12, and cuDNN 9, ensuring their DLL directories are on PATH, then restart GLTS. See the [faster-whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu). GPU detection alone does not verify all runtime libraries. If CUDA fails, return to CPU in Settings. CUDA inference has not been tested on a GPU in this environment.

### Updating an existing Windows installation

Stop GLTS, download the latest GitHub ZIP, and copy its source files into your existing GLTS folder. Keep `.venv`, `.local`, and `models` so your dependencies, settings, and language packs are retained. Launch GLTS again and refresh the browser (Ctrl+F5).

## Sana’ani Arabic and local language models

Choose **Sana’ani Arabic (Yemen)** as the source language.

### Audio

In Settings, accept the **CC BY-NC-SA 4.0** noncommercial model license and click **Download Sana’ani speech pack**. Keep GLTS running during preparation. The optional [Yemeni speech model by Mansoor Saleh](https://huggingface.co/mansoorSaleh/whisper-yemeni) covers several Yemeni dialects including Sana’ani. GLTS pins its revision, downloads safetensors (about 1 GB), converts locally to int8, and retains its attribution/model card in `models/whisper-yemeni`. Allow at least 4 GB free disk for preparation. It operates offline after installation, on CPU or CUDA.

The provider's model card and published model configuration disagree about the base-model size. Treat it as experimental; provider accuracy claims have not been independently verified. This implementation has been checked for model conversion, local loading and offline inference, not Sana’ani transcription accuracy on real recordings.

The speech pack transcribes audio, not written text. With **Standard language packs**, its Arabic transcript is translated using your Arabic → English pack. For dialect-sensitive translation of the transcript, select **Local language model (Ollama)**.

### Written text and transcripts

1. Install [Ollama for Windows](https://ollama.com/download/windows) and keep it running locally.
2. In GLTS Settings, click **Check models**, then download **Qwen2.5 7B** (about 5 GB). With 16 GB RAM or more, this is the recommended starting option. **Qwen2.5 3B** (about 2 GB) is a lighter alternative. **Qwen2.5 14B** (about 9 GB) is also available for comparison; 32 GB RAM is recommended for comfortable use. It may be slow with 16 GB, especially alongside speech recognition. Select 14B both in the Settings download menu and in the main translation model selector. It also works with optional dialect suggestions. A larger model does not guarantee better Sana’ani translations, and 14B translation quality has not been verified here.
3. Select **Local language model (Ollama)** as the translation engine, choose the installed model, and translate Sana’ani text, TXT/PDF documents, or an audio transcript.

GLTS communicates only with Ollama at `127.0.0.1:11434`, with proxy use disabled for this connection. Model downloads need internet, but translation stays local and requires no API key. Ollama chooses its own CPU/GPU resources; the GLTS CPU/CUDA setting controls Argos and speech inference. Make sure the selected model is installed before disconnecting. Translations of long documents are split into bounded chunks; context across chunks may be imperfect.

Qwen2.5 is a general multilingual model, not a validated Sana’ani translation pack. Results may omit, misinterpret or invent meanings and should be checked against known examples. End-to-end Qwen inference has not been validated in this cloud environment.

### Updating Windows for this feature

Stop GLTS and copy the latest source files from GitHub into your existing folder, keeping `.venv`, `.local`, and `models`. Open a terminal in that folder and run:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This installs the conversion dependency for the optional speech pack. Restart GLTS and press Ctrl+F5 in the browser. Model downloads run in the background, and Settings reports completion or errors. If speech preparation fails, see `.local/sanaani-install.log`.

## Experimental source auto-detection

Manual source selection remains the default. Choose **Auto-detect (experimental)** and click Translate. GLTS detects the language, displays a text/transcript preview and a review panel, and stops before translation. Correct the suggested source if necessary, click **Confirm source language**, then click Translate again.

- Text and selectable-text PDFs use a locally bundled `langid` detector. Very short input is rejected; short or mixed-language passages may be misidentified.
- Audio uses Whisper's language identification. After confirmation, the audio is transcribed again using your chosen source model; selecting Sana’ani uses the optional Yemeni model.
- Arabic input can optionally be checked by your installed Qwen model for a Sana’ani suggestion. This is an unverified text-based guess, including for an audio transcript, not a validated acoustic dialect classifier. Unknown/other results keep standard Arabic. If Ollama is missing, ordinary language detection still works.
- A detected language may need an additional translation pack or the local language-model engine. Sana’ani written translation still requires the local language model.
- Detection does not fetch models or send content outside your computer. Install dependencies before use with `.venv\Scripts\python.exe -m pip install -r requirements.txt` on Windows.

If auto-detection is not useful, choose a source manually to bypass it. The Git tag `glts-before-auto-detect` preserves the prior version for a full rollback; keep your local settings and downloaded models when replacing source files.

## Limits

- Uploaded files: up to the limit chosen in Settings (25 MB by default). Extracted text: up to 100,000 characters.
- PDF text extraction requires selectable text. Scanned PDFs, OCR, and PDF layout preservation are not included.
- Audio formats: MP3, WAV, M4A, MP4, MPEG, MPGA, WEBM, OPUS. Source language must match the speech. The transcript is displayed alongside the translation.
- The tiny speech model is economical on CPU; Arabic dialects and noisy recordings may need a larger model for reliable results.
- Files and results are processed in memory and are not saved by GLTS. Review important translations for accuracy.
- This is a local single-user app. The server binds to loopback; public deployment requires a production server and access controls.

## Validation

```sh
.venv/bin/pytest -q
```

Tests cover GUI rendering, upload handling, validation, transcription integration, and real Arabic translation with network connections blocked when its pack is installed.
