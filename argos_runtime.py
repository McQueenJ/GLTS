"""MIT Argos 1.10 adapter using GLTS's local, model-free sentence splitter.

Avoids MiniSBD (an AGPL dependency of Argos 1.11) and prevents Argos 1.10's
import-time spaCy model download. No third-party installed files are modified.
"""
import re
from importlib.metadata import version
from threading import Lock

_module = None
_lock = Lock()


class LocalSentenceSplitter:
    def split_sentences(self, text):
        return [part for part in re.split(r'(?<=[.!?؟。！])\s+', text) if part.strip()]


def initialize_argos():
    global _module
    with _lock:
        if _module is not None:
            return _module
        if version('argostranslate') != '1.10.0':
            raise RuntimeError('GLTS requires Argos Translate 1.10.0. Install the updated requirements.txt in the GLTS virtual environment and restart.')
        from argostranslate import networking
        original_cache = networking.cache_spacy
        try:
            # This cache is not used: our adapter supplies sentence splitting.
            networking.cache_spacy = lambda: None
            from argostranslate import translate
        finally:
            networking.cache_spacy = original_cache
        class OfflinePackageTranslation(translate.PackageTranslation):
            def __init__(self, from_lang, to_lang, pkg):
                self.from_lang = from_lang
                self.to_lang = to_lang
                self.pkg = pkg
                self.translator = None
                self.sentencizer = LocalSentenceSplitter()
        translate.PackageTranslation = OfflinePackageTranslation
        _module = translate
        return _module
