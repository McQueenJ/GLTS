import io
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from threading import Lock, RLock

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('XDG_DATA_HOME', str(ROOT / '.local/share'))
os.environ.setdefault('XDG_CACHE_HOME', str(ROOT / '.local/cache'))
os.environ.setdefault('XDG_CONFIG_HOME', str(ROOT / '.local/config'))
os.environ.setdefault('ARGOS_CHUNK_TYPE', 'MINISBD')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ['ARGOS_MODEL_PROVIDER'] = 'OPENNMT'

from flask import Flask, jsonify, render_template, request
from pypdf import PdfReader

app = Flask(__name__)
SETTINGS_PATH = ROOT / '.local/settings.json'


def saved_upload_limit():
    try:
        value = json.loads(SETTINGS_PATH.read_text(encoding='utf-8')).get('max_upload_mb', 25)
        return value if type(value) is int and 1 <= value <= 1024 else 25
    except (OSError, ValueError, AttributeError):
        return 25


app.config['MAX_CONTENT_LENGTH'] = saved_upload_limit() * 1024 * 1024
try:
    saved_mode = json.loads(SETTINGS_PATH.read_text(encoding='utf-8')).get('compute_mode', 'cpu')
except (OSError, ValueError, AttributeError):
    saved_mode = 'cpu'
app.config['COMPUTE_MODE'] = saved_mode if saved_mode in ('cpu', 'cuda') else 'cpu'
inference_lock = RLock()


def cuda_available():
    import ctranslate2
    try:
        return ctranslate2.get_cuda_device_count() > 0
    except RuntimeError:
        return False


def compute_mode():
    mode = app.config['COMPUTE_MODE']
    if mode == 'cuda' and not cuda_available():
        raise ValueError('CUDA is unavailable. Switch to CPU in Settings or install compatible NVIDIA drivers, CUDA 12, and cuDNN 9.')
    return mode
AUDIO = {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg', '.mpga', '.webm'}


def languages():
    import argostranslate.translate
    return argostranslate.translate.get_installed_languages()


def speech_model():
    return load_speech_model(compute_mode())


@lru_cache(maxsize=2)
def load_speech_model(mode):
    from faster_whisper import WhisperModel
    path = ROOT / 'models/whisper-tiny'
    if not (path / 'model.bin').exists():
        raise ValueError('Install the local speech model using prepare_models.py before translating audio.')
    return WhisperModel(str(path), device=mode, compute_type='float16' if mode == 'cuda' else 'int8', local_files_only=True, cpu_threads=2)


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
            raise ValueError('Audio could not be transcribed. Check the file and local speech model. In CUDA mode, verify CUDA 12 and cuDNN 9 are installed, or switch to CPU in Settings.')
    raise ValueError('Choose a supported text, PDF, or audio file.')


class LocalSentenceSplitter:
    """No downloadable sentence-boundary model is needed at runtime."""
    def split_sentences(self, text):
        return [part for part in re.split(r'(?<=[.!?؟。！])\s+', text) if part.strip()]


def use_local_splitter(translation, mode):
    if hasattr(translation, 'translator') and getattr(translation, '_glts_device', None) != mode:
        translation.translator = None
        translation._glts_device = mode
    if hasattr(translation, 'sentencizer'):
        translation.sentencizer = LocalSentenceSplitter()
    for name in ('underlying', 't1', 't2'):
        child = getattr(translation, name, None)
        if child is not None:
            use_local_splitter(child, mode)


def translate(text, source, target):
    available = {language.code: language for language in languages()}
    if source not in available or target not in available:
        raise ValueError('Install language packs for the selected languages first.')
    if source == target:
        return text
    translation = available[source].get_translation(available[target])
    if translation is None:
        raise ValueError('No offline translation pack is installed for this language pair.')
    from argostranslate import settings
    mode = compute_mode()
    settings.device = mode
    settings.compute_type = 'float16' if mode == 'cuda' else 'int8'
    use_local_splitter(translation, mode)
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
        with inference_lock:
            return run_translation(source, target)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception('Local translation failed')
        return jsonify(error='Local translation failed. Check the models. For CUDA, verify CUDA 12 and cuDNN 9, or switch to CPU in Settings.'), 500


def run_translation(source, target):
    compute_mode()
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


# Catalog access is opt-in: opening Settings only reads local metadata.
pack_lock = Lock()


def package_manager():
    import argostranslate.package
    return argostranslate.package


def pack_catalog():
    from argostranslate import settings
    manager = package_manager()
    installed = {(p.from_code, p.to_code) for p in manager.get_installed_packages() if p.type == 'translate'}
    catalog = manager.get_available_packages() if settings.local_package_index.exists() else []
    packs = {}
    for p in [*catalog, *manager.get_installed_packages()]:
        if p.type == 'translate':
            key = f'{p.from_code}:{p.to_code}'
            packs[key] = dict(id=key, source=p.from_name, target=p.to_name, installed=(p.from_code, p.to_code) in installed)
    return sorted(packs.values(), key=lambda p: (p['source'], p['target']))


@app.route('/api/settings', methods=['GET', 'POST'])
def upload_settings():
    if request.method == 'POST':
        if not request.is_json:
            return jsonify(error='A JSON request is required.'), 400
        if request.headers.get('Origin') and request.headers['Origin'] != request.host_url.rstrip('/'):
            return jsonify(error='Use the local GLTS interface to change settings.'), 403
        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify(error='Invalid settings.'), 400
        with inference_lock:
            value = data.get('max_upload_mb', app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024))
            mode = data.get('compute_mode', app.config['COMPUTE_MODE'])
            if type(value) is not int or not 1 <= value <= 1024:
                return jsonify(error='Choose a whole number from 1 to 1024 MB.'), 400
            if mode not in ('cpu', 'cuda'):
                return jsonify(error='Choose CPU or CUDA mode.'), 400
            if 'compute_mode' in data and mode == 'cuda' and not cuda_available():
                return jsonify(error='No CUDA GPU is available. Install compatible NVIDIA drivers, CUDA 12 and cuDNN 9, or use CPU.'), 400
            try:
                SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
                temporary = SETTINGS_PATH.with_suffix('.tmp')
                temporary.write_text(json.dumps(dict(max_upload_mb=value, compute_mode=mode)), encoding='utf-8')
                temporary.replace(SETTINGS_PATH)
            except OSError:
                return jsonify(error='Could not save settings. Check that the GLTS folder is writable.'), 500
            app.config['MAX_CONTENT_LENGTH'] = value * 1024 * 1024
            app.config['COMPUTE_MODE'] = mode
    return jsonify(max_upload_mb=app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024), compute_mode=app.config['COMPUTE_MODE'], cuda_available=cuda_available())


@app.get('/api/packs')
def list_packs():
    try:
        return jsonify(packs=pack_catalog(), languages=[dict(code=p.code, name=p.name) for p in languages()])
    except Exception:
        return jsonify(error='Could not read local language packs.'), 500


@app.post('/api/packs/refresh')
@app.post('/api/packs/install')
def manage_packs():
    # JSON prevents cross-site HTML forms from initiating model downloads.
    if not request.is_json:
        return jsonify(error='A JSON request is required.'), 400
    if request.headers.get('Origin') and request.headers['Origin'] != request.host_url.rstrip('/'):
        return jsonify(error='Use the local GLTS interface to manage packs.'), 403
    if not pack_lock.acquire(blocking=False):
        return jsonify(error='Another pack operation is in progress. Please wait.'), 409
    try:
        manager = package_manager()
        if request.path.endswith('/refresh'):
            manager.update_package_index()
        else:
            from argostranslate import settings
            if not settings.local_package_index.exists():
                return jsonify(error='Refresh the catalog before downloading a pack.'), 400
            data = request.get_json()
            if not isinstance(data, dict):
                return jsonify(error='Choose a language pack from the catalog.'), 400
            pack_id = data.get('id')
            selected = next((p for p in manager.get_available_packages() if p.type == 'translate' and f'{p.from_code}:{p.to_code}' == pack_id), None)
            if selected is None:
                return jsonify(error='Choose a language pack from the catalog.'), 400
            if not any(p.from_code == selected.from_code and p.to_code == selected.to_code for p in manager.get_installed_packages()):
                downloaded = selected.download()
                with inference_lock:
                    manager.install_from_path(downloaded)
        return jsonify(packs=pack_catalog(), languages=[dict(code=p.code, name=p.name) for p in languages()])
    except Exception:
        app.logger.exception('Language pack operation failed')
        return jsonify(error='Could not download the catalog or language pack. Check your internet connection and try again. Existing packs remain available offline.'), 502
    finally:
        pack_lock.release()


@app.errorhandler(413)
def too_large(error):
    return jsonify(error=f'Files must be smaller than {app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)} MB.'), 413


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')))
