# GLTS third-party software and model notices

The root MIT LICENSE applies to GLTS's original application code and documentation. It does not replace the licenses for dependencies, model weights, the bundled font, or optional GPU software. Free of charge does not mean free of license obligations.

## What this source package contains

The application source, original logo, DejaVu Sans font, font license, dependency/model notice copies, and license-review records are included. Python libraries, model weights, Ollama binaries, NVIDIA libraries and personal settings are not bundled. Installation downloads dependencies and user-selected models from their publishers.

Retain LICENSE, this file, licenses/, and assets/fonts/LICENSE.txt when redistributing this source package. Modifications and redistribution of third-party components must follow their own terms.

## Core components

| Component | Publisher / license | Retained text or reference |
| --- | --- | --- |
| Argos Translate 1.10.0 | Argos Open Technologies; MIT (also offered under CC0 upstream) | licenses/python/argostranslate/ and https://github.com/argosopentech/argos-translate |
| faster-whisper | SYSTRAN; MIT | licenses/upstream/faster-whisper-LICENSE |
| Whisper model | OpenAI; MIT; converted tiny model distributed by SYSTRAN | licenses/upstream/Whisper-LICENSE and https://huggingface.co/Systran/faster-whisper-tiny |
| Qwen2.5 7B Instruct | Alibaba Cloud / Qwen team; Apache 2.0 | licenses/upstream/Qwen2.5-7B-Instruct-LICENSE and https://huggingface.co/Qwen/Qwen2.5-7B-Instruct |
| Qwen2.5 14B Instruct | Alibaba Cloud / Qwen team; Apache 2.0 | licenses/upstream/Qwen2.5-14B-Instruct-LICENSE and https://huggingface.co/Qwen/Qwen2.5-14B-Instruct |
| Ollama | Ollama contributors; MIT | licenses/upstream/Ollama-LICENSE and https://github.com/ollama/ollama |
| fpdf2 | LGPL 3.0 or later | licenses/python/fpdf2/ and licenses/upstream/LGPL-3.0.txt, GPL-3.0.txt |
| pycountry | LGPL 2.1; includes separately credited ISO data | licenses/python/pycountry/ and licenses/upstream/LGPL-2.1.txt |
| PyAV | BSD 3-Clause wrapper; linked FFmpeg has its own license | licenses/python/av/ and https://pyav.org/docs/stable/overview/installation.html |
| DejaVu Sans | Bitstream Vera font license / public-domain DejaVu changes | assets/fonts/LICENSE.txt |

The installed dependency closure, including PyTorch CPU, comprises 83 packages. See licenses/DEPENDENCIES.md and licenses/dependency-inventory.json for exact tested versions, declared licenses, source links, and retained notice hashes. The scan covers current-platform dependencies, not every optional extra or every future package resolver result. Notice files missing from installed wheels were supplemented from upstream; URLs are recorded in licenses/upstream/SOURCES.txt. FlatBuffers and langid supplemental notices were obtained from upstream default branches rather than a verified matching release tag.

The closure includes additional open-source licenses such as MPL 2.0, PSF and ISC. Read the retained texts; the application MIT license does not make those components MIT.

## LGPL and native components

LGPL libraries may be used in applications under other licenses, subject to their conditions. GLTS keeps them separately installed as ordinary Python packages; it does not modify, embed, statically link, or prevent replacement of those libraries. If redistributing their binaries or modified sources, meet the applicable license, notice, source-availability, modification and relinking/replacement requirements. This source ZIP does not contain those binaries.

The FFmpeg libraries linked to the tested Linux PyAV 15.1.0 wheel report LGPL version 3 or later and no --enable-gpl configuration flag. This observation does not establish the license of every Windows wheel, system FFmpeg build, optional codec or downstream executable. Audit the exact binaries if creating an EXE or bundled installer. Optional CUDA/cuDNN/NVIDIA drivers are governed by NVIDIA's own terms and are not covered by MIT or represented here as wholly open source.

## Argos model downloads remain available

Argos Translate's MIT software license is verified. Its public package-index repository also states MIT/CC0. However, the catalog entries examined contain no per-model license field, and the external model files could not be inspected in this environment because their download host returned 403. Do not treat the software/index license as proof that every external weight file has identical terms.

At the user's direction, existing and new Argos downloads remain available, including the normal setup language downloads. No model weights are redistributed in this source ZIP. Anyone redistributing model weights or using them in a context requiring specific permissions should verify the selected package's terms with its publisher. This is an unresolved model-specific verification item, not a finding that those models are prohibited or proprietary.

## Removed model and dependency

Qwen2.5 3B uses a custom research license rather than Apache 2.0. It is no longer offered, accepted by translation/detection endpoints, or listed as a supported installed model. An existing Ollama copy is not automatically deleted; users may remove it with `ollama rm qwen2.5:3b`.

Argos 1.11 depends on AGPL-licensed MiniSBD. GLTS pins the MIT-licensed Argos 1.10.0 release and uses its own sentence splitter via argos_runtime.py, avoiding MiniSBD and automatic spaCy model downloads. No installed Argos source is modified. The inherited Argos translation pipeline remains covered by Argos's MIT notice. Previously installed MiniSBD is not used by the new dependency closure; users updating an existing virtual environment may remove that unused package if no other application needs it.

Historical release archives and Git tags may contain earlier dependency/model options. These notices describe the current source release, not a retroactive relicensing of older materials.

## Review limits

This is a documented technical license inventory, not a certification that every possible deployment or redistribution satisfies all legal obligations. Unverified Argos model terms, platform-specific binary licenses, future dependency changes and optional GPU components must not be described as universally cleared, license-free or all MIT. The original GLTS source can be published under its MIT license while preserving applicable third-party terms and these qualifications.
