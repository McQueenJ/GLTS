import io
import json
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from threading import Lock, RLock, Thread

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('XDG_DATA_HOME', str(ROOT / '.local/share'))
os.environ.setdefault('XDG_CACHE_HOME', str(ROOT / '.local/cache'))
os.environ.setdefault('XDG_CONFIG_HOME', str(ROOT / '.local/config'))
os.environ.setdefault('ARGOS_CHUNK_TYPE', 'MINISBD')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ['ARGOS_MODEL_PROVIDER'] = 'OPENNMT'

from flask import Flask, jsonify, render_template, request
from pypdf import PdfReader
from speech_packs import SANAANI_ID, SANAANI_PATH, sanaani_installed
from local_models import MODELS, installed_models, ollama_request, translate_local

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
AUDIO = {'.mp3', '.wav', '.m4a', '.mp4', '.mpeg', '.mpga', '.webm', '.opus'}


def languages():
    import argostranslate.translate
    return argostranslate.translate.get_installed_languages()


def speech_model():
    return load_speech_model(compute_mode())


@lru_cache(maxsize=2)
def load_speech_model(mode, pack='default'):
    from faster_whisper import WhisperModel
    path = SANAANI_PATH if pack == SANAANI_ID else ROOT / 'models/whisper-tiny'
    if not (path / 'model.bin').exists():
        raise ValueError('Download the Sana’ani speech pack in Settings first.' if pack == SANAANI_ID else 'Install the local speech model using prepare_models.py before translating audio.')
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
            model = load_speech_model(compute_mode(), SANAANI_ID) if source == 'ar-sanaa' else speech_model()
            segments, _ = model.transcribe(io.BytesIO(data), language='ar' if source == 'ar-sanaa' else source, beam_size=1)
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


def ui_languages():
    from types import SimpleNamespace
    installed = {p.code: p for p in languages()}
    for code, name in [('ar', 'Arabic'), ('en', 'English')]:
        installed.setdefault(code, SimpleNamespace(code=code, name=name))
    return list(installed.values())


@app.get('/')
def index():
    installed = ui_languages()
    return render_template('index.html', languages=installed, configured=bool(languages()))


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
    engine = request.form.get('engine', 'argos')
    available = {language.code for language in ui_languages()}
    if source not in available | {'ar-sanaa'} or target not in available:
        raise ValueError('Choose installed source and target languages.')
    upload = request.files.get('file')
    text = extract_text(upload, source) if upload else request.form.get('text', '')
    if not text.strip():
        raise ValueError('Enter text or upload a readable file. Scanned PDFs require OCR and are not supported yet.')
    if len(text) > 100000:
        raise ValueError('Please use a document with fewer than 100,000 characters.')
    if engine == 'ollama':
        names = {p.code: p.name for p in ui_languages()}
        result = translate_local(text, source if source == 'ar-sanaa' else names[source], names[target], request.form.get('llm_model', 'qwen2.5:7b'))
    elif engine == 'argos':
        if source == 'ar-sanaa' and not (upload and Path(upload.filename or '').suffix.lower() in AUDIO):
            raise ValueError('Select Local language model for Sana’ani text translation. The standard Arabic pack is not dialect-specific.')
        result = translate(text, 'ar' if source == 'ar-sanaa' else source, target)
    else:
        raise ValueError('Choose a supported translation engine.')
    return jsonify(translation=result, source=text, language=target)


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
        return jsonify(packs=pack_catalog(), languages=[dict(code=p.code, name=p.name) for p in ui_languages()])
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
        return jsonify(packs=pack_catalog(), languages=[dict(code=p.code, name=p.name) for p in ui_languages()])
    except Exception:
        app.logger.exception('Language pack operation failed')
        return jsonify(error='Could not download the catalog or language pack. Check your internet connection and try again. Existing packs remain available offline.'), 502
    finally:
        pack_lock.release()


model_job_lock = Lock()
model_job = dict(state='idle', message='', kind='')


def run_model_install(kind, model):
    try:
        if kind == 'speech':
            with (ROOT / '.local/sanaani-install.log').open('w', encoding='utf-8') as log:
                process = subprocess.Popen([sys.executable, str(ROOT / 'prepare_sanaani.py'), '--accept-noncommercial-license'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                code = process.wait()
            if code or not sanaani_installed():
                raise ValueError('Speech installation failed. Check internet access, free disk space, and .local/sanaani-install.log. Run pip install -r requirements.txt if dependencies are missing.')
        else:
            ollama_request('/api/pull', {'model': model, 'stream': False}, timeout=3600)
            if model not in installed_models():
                raise ValueError('Ollama did not finish installing the selected model.')
        with model_job_lock:
            model_job.update(state='complete', message='Model installed and ready for offline use.')
    except Exception as exc:
        app.logger.exception('Optional model installation failed')
        with model_job_lock:
            model_job.update(state='failed', message=str(exc))


@app.get('/api/local-models')
def local_model_status():
    with model_job_lock:
        job = dict(model_job)
    try:
        installed = installed_models()
        connected = True
    except ValueError:
        installed = []
        connected = False
    return jsonify(speech_installed=sanaani_installed(), ollama_connected=connected, installed_models=installed, job=job)


@app.post('/api/local-models/install')
def install_local_model():
    if not request.is_json:
        return jsonify(error='A JSON request is required.'), 400
    if request.headers.get('Origin') and request.headers['Origin'] != request.host_url.rstrip('/'):
        return jsonify(error='Use the local GLTS interface to download models.'), 403
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(error='Choose a supported model.'), 400
    kind = data.get('kind')
    model = data.get('model')
    if kind == 'speech':
        if data.get('accept_license') is not True:
            return jsonify(error='Accept the noncommercial speech-model license before downloading.'), 400
        if sanaani_installed():
            return jsonify(message='Speech model already installed.'), 200
    elif kind == 'llm' and model in MODELS:
        try:
            installed_models()
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
    else:
        return jsonify(error='Choose a supported model.'), 400
    with model_job_lock:
        if model_job['state'] == 'running':
            return jsonify(error='A model download is already running. Please wait.'), 409
        (ROOT / '.local').mkdir(parents=True, exist_ok=True)
        model_job.update(state='running', kind=kind, message='Downloading and preparing the model. This may take several minutes. Keep GLTS running.')
        Thread(target=run_model_install, args=(kind, model), daemon=True).start()
    return jsonify(message='Download started.'), 202


@app.errorhandler(413)
def too_large(error):
    return jsonify(error=f'Files must be smaller than {app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)} MB.'), 413


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')))
