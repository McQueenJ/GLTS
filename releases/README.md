# GLTS Windows source package

`GLTS-Windows.zip` packages the application source at commit `4a91740959b20112378e61adf4ed4bb5d3bb962b`, including Windows install/launch scripts, local language-model integration, Sana’ani speech-model installation, OPUS support, and drag-and-drop uploads.

Extract the ZIP and follow `GLTS/README.md`. This is a source distribution, not a standalone executable. Python 3.12 is required. Initial setup downloads dependencies and models. Local environments, settings, credentials, and downloaded models are excluded.

For an existing installation, stop GLTS and copy the source files into its existing folder while retaining `.venv`, `.local`, and `models`. Update dependencies with `.venv\Scripts\python.exe -m pip install -r requirements.txt`, restart, and refresh the browser with Ctrl+F5. Ollama must be installed separately for local language-model translation.
