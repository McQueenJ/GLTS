# GLTS Windows source package

`GLTS-Windows.zip` contains the latest application source, Windows install/launch scripts, documentation and tests. It includes experimental language detection with manual review, local language-model integration, optional Sana’ani speech recognition, OPUS support and drag-and-drop uploads.

Extract the ZIP and follow `GLTS/README.md`. This is a source distribution, not a standalone executable. Python 3.12 is required. Initial setup downloads dependencies and models. Local environments, settings, credentials, and downloaded models are excluded.

For an existing installation, stop GLTS and copy the source files into its existing folder while retaining `.venv`, `.local`, and `models`. Update dependencies with `.venv\Scripts\python.exe -m pip install -r requirements.txt`, restart, and refresh the browser with Ctrl+F5. Ollama must be installed separately for local language-model translation and dialect suggestions.

To bypass experimental detection, select the source language manually. For a full rollback, the GitHub tag `glts-before-auto-detect` retains the previously working source and package. Preserve local settings and models when reverting.
