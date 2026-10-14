import io
import os
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('XDG_DATA_HOME', str(ROOT / '.local/share'))
os.environ.setdefault('XDG_CACHE_HOME', str(ROOT / '.local/cache'))
os.environ.setdefault('XDG_CONFIG_HOME', str(ROOT / '.local/config'))
os.environ.setdefault('ARGOS_CHUNK_TYPE', 'MINISBD')
os.environ.setdefault('HF_HUB_OFFLINE', '1')

from flask import Flask, jsonify, render_template, request
from pypdf import PdfReader

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
AUDIO = {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg', '.mpga', '.webm'}


def languages():
    import argostranslate.translate
    return argostranslate.translate.get_installed_languages()


@lru_cache(maxsize=1)
def speech_model():
    from faster_whisper import WhisperModel
    path = ROOT / 'models/whisper-tiny'
    if not (path / 'model.bin').exists():
        raise ValueError('Install the local speech model using prepare_models.py before translating audio.')
    return WhisperModel(str(path), device='cpu', compute_type='int8', local_files_only=True, cpu_threads=2)


def extract_text(upload, source):
    suffix = Path(upload.filename or '').suffix.lower()
    data = upload.read()
    if not data:
        raise ValueError('The uploaded file is empty.')
    if suffix == '.txt':
        try:
            return data.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValueError('Please save your text file using UTF-8 encoding.')
    if suffix == '.pdf':
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError('Please upload an unencrypted PDF.')
            return '\n\n'.join(page.extract_text() or '' for page in reader.pages)
        except ValueError:
            raise
        except Exception:
            raise ValueError('This PDF could not be read. Please upload a valid PDF.')
    if suffix in AUDIO:
        try:
            segments, _ = speech_model().transcribe(io.BytesIO(data), language=source, beam_size=1)
            return ' '.join(segment.text.strip() for segment in segments)
        except ValueError:
            raise
        except Exception:
            raise ValueError('Audio could not be transcribed. Check the format and local speech model.')
    raise ValueError('Choose a supported text, PDF, or audio file.')


class LocalSentenceSplitter:
    """No downloadable sentence-boundary model is needed at runtime."""
    def split_sentences(self, text):
        return [part for part in re.split(r'(?<=[.!?؟。！])\s+', text) if part.strip()]


def use_local_splitter(translation):
    if hasattr(translation, 'sentencizer'):
        translation.sentencizer = LocalSentenceSplitter()
    for name in ('underlying', 't1', 't2'):
        child = getattr(translation, name, None)
        if child is not None:
            use_local_splitter(child)


def translate(text, source, target):
    available = {language.code: language for language in languages()}
    if source not in available or target not in available:
        raise ValueError('Install language packs for the selected languages first.')
    if source == target:
        return text
    translation = available[source].get_translation(available[target])
    if translation is None:
        raise ValueError('No offline translation pack is installed for this language pair.')
    use_local_splitter(translation)
    return translation.translate(text)


@app.get('/')
def index():
    installed = languages()
    return render_template('index.html', languages=installed, configured=bool(installed))


@app.post('/api/translate')
def translation():
    source = request.form.get('source_language', '')
    target = request.form.get('language', '')
    try:
        available = {language.code for language in languages()}
        if source not in available or target not in available:
            raise ValueError('Choose installed source and target languages.')
        upload = request.files.get('file')
        text = extract_text(upload, source) if upload else request.form.get('text', '')
        if not text.strip():
            raise ValueError('Enter text or upload a readable file. Scanned PDFs require OCR and are not supported yet.')
        if len(text) > 100000:
            raise ValueError('Please use a document with fewer than 100,000 characters.')
        return jsonify(translation=translate(text, source, target), source=text, language=target)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception('Local translation failed')
        return jsonify(error='Local translation failed. Check the installed models and server log.'), 500


@app.errorhandler(413)
def too_large(error):
    return jsonify(error='Files must be smaller than 25 MB.'), 413


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')))
