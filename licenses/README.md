# License-review evidence

- `dependency-inventory.json`: installed runtime dependency closure plus pytest and CPU PyTorch; exact tested versions, publisher license metadata, project links, retained notice paths and hashes.
- `DEPENDENCIES.md`: readable summary of that inventory.
- `python/`: unmodified license/copyright/notice files found in the installed distributions.
- `upstream/`: supplemental license texts for supported models, Ollama, LGPL/GPL base texts, and distributions whose wheels omitted a notice file. SOURCES.txt records retrieval URLs.

Regenerate using GLTS's virtual environment: `python scripts/audit_licenses.py`. The script replaces only the generated `licenses/python` tree and inventory files; it leaves supplemental upstream files alone.

The snapshot reflects the cloud's Linux dependency resolution. Dependencies are not bundled into the GLTS source archive. A Windows installation, optional extras, future resolver changes, and different native binaries may add or change license obligations. FlatBuffers/langid supplemental notices came from default branches rather than matched release tags. Read THIRD_PARTY_NOTICES.md for review limits and the unresolved Argos model-weight verification. The notices are evidence and retained attribution, not a blanket legal certification.
