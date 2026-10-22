import io
import json
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock, RLock, Thread

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('XDG_DATA_HOME', str(ROOT / '.local/share'))
os.environ.setdefault('XDG_CACHE_HOME', str(ROOT / '.local/cache'))
os.environ.setdefault('XDG_CONFIG_HOME', str(ROOT / '.local/config'))
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ['ARGOS_MODEL_PROVIDER'] = 'OPENNMT'

from flask import Flask, jsonify, render_template, request, send_file
from pypdf import PdfReader
from local_models import MODELS, installed_models, ollama_request, translate_local
from detection import detect_text, language_name, suggest_dialect
from argos_runtime import LocalSentenceSplitter, initialize_argos

initialize_argos()

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
    return initialize_argos().get_installed_languages()


def speech_model():
    return load_speech_model(compute_mode())


@lru_cache(maxsize=2)
def load_speech_model(mode):
    from faster_whisper import WhisperModel
    path = ROOT / 'models/whisper-tiny'
    if not (path / 'model.bin').exists():
        raise ValueError('Install the local Whisper speech model using prepare_models.py before translating audio.')
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
        return transcribe_audio(data, source)[0]
    raise ValueError('Choose a supported text, PDF, or audio file.')


def transcribe_audio(data, source):
    try:
        model = speech_model()
        language = None if source == 'auto' else ('ar' if source == 'ar-sanaa' else source)
        segments, info = model.transcribe(io.BytesIO(data), language=language, beam_size=1)
        return ' '.join(segment.text.strip() for segment in segments), info
    except ValueError:
        raise
    except Exception:
        raise ValueError('Audio could not be transcribed. Check the file and local speech model. In CUDA mode, verify CUDA 12 and cuDNN 9 are installed, or switch to CPU in Settings.')


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


@app.get('/branding/glts-logo.png')
def branding_logo():
    return send_file(ROOT / 'assets/branding/glts-logo.png', mimetype='image/png')


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
    except ModuleNotFoundError:
        app.logger.exception('Missing translation dependency')
        return jsonify(error='A required Python dependency is missing. Stop GLTS, open PowerShell in its folder, run .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt, then restart GLTS.'), 500
    except Exception as exc:
        app.logger.exception('Local translation failed')
        return jsonify(error=f'Translation failed unexpectedly ({type(exc).__name__}). Copy the error traceback from the GLTS launch window so the cause can be diagnosed. Ollama manages its GPU independently of the GLTS CUDA setting.'), 500


def run_translation(source, target):
    engine = request.form.get('engine', 'argos')
    available = {language.code for language in ui_languages()}
    if source == 'auto':
        raise ValueError('Detect and confirm the source language before translating.')
    if (source != 'ar-sanaa' and not language_name(source)) or target not in available:
        raise ValueError('Choose installed source and target languages.')
    upload = request.files.get('file')
    text = extract_text(upload, source) if upload else request.form.get('text', '')
    if not text.strip():
        raise ValueError('Enter text or upload a readable file. Scanned PDFs require OCR and are not supported yet.')
    if len(text) > 100000:
        raise ValueError('Please use a document with fewer than 100,000 characters.')
    if engine == 'ollama':
        names = {p.code: p.name for p in ui_languages()}
        result = translate_local(text, source if source == 'ar-sanaa' else names.get(source, language_name(source)), names[target], request.form.get('llm_model', 'qwen2.5:7b'))
    elif engine == 'argos':
        if source == 'ar-sanaa' and not (upload and Path(upload.filename or '').suffix.lower() in AUDIO):
            raise ValueError('Select Local language model for Sana’ani text translation. The standard Arabic pack is not dialect-specific.')
        result = translate(text, 'ar' if source == 'ar-sanaa' else source, target)
    else:
        raise ValueError('Choose a supported translation engine.')
    return jsonify(translation=result, source=text, language=target)


@app.post('/api/transcribe')
def transcription():
    try:
        with inference_lock:
            upload = request.files.get('file')
            if not upload or Path(upload.filename or '').suffix.lower() not in AUDIO:
                raise ValueError('Upload a supported audio file to transcribe, including OPUS, MP3, WAV, M4A or WEBM.')
            source = request.form.get('source_language', '')
            if source not in ('auto', 'ar-sanaa') and not language_name(source):
                raise ValueError('Choose the spoken language or Auto-detect.')
            data = upload.read()
            if not data:
                raise ValueError('The uploaded file is empty.')
            text, info = transcribe_audio(data, source)
            if not text.strip():
                raise ValueError('No speech was found. Try a clearer recording or choose the spoken language manually.')
            if len(text) > 500000:
                raise ValueError('The transcript is too long. Split the recording into smaller files.')
            code = info.language if source == 'auto' else ('ar' if source == 'ar-sanaa' else source)
            return jsonify(transcript=text, language=code)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except ModuleNotFoundError:
        return jsonify(error='A required dependency is missing. Install requirements.txt using the GLTS virtual environment, then restart.'), 500
    except Exception:
        app.logger.exception('Local transcription failed')
        return jsonify(error='Transcription failed. Check the speech model and GLTS launch window. Ollama is not needed for transcription.'), 500


@app.post('/api/detect')
def detect_source():
    try:
        with inference_lock:
            upload = request.files.get('file')
            is_audio = bool(upload and Path(upload.filename or '').suffix.lower() in AUDIO)
            if is_audio:
                data = upload.read()
                if not data:
                    raise ValueError('The uploaded file is empty.')
                text, info = transcribe_audio(data, 'auto')
                code = info.language
                if not text.strip():
                    raise ValueError('No speech was found. Choose a source language manually or try a clearer recording.')
                warning = 'Whisper identified the language, not the dialect. Review the transcript and language before translating.'
                if getattr(info, 'language_probability', 0) < 0.6:
                    warning += ' Language detection was uncertain.'
            else:
                text = extract_text(upload, 'auto') if upload else request.form.get('text', '')
                if len(text) > 100000:
                    raise ValueError('Please use a document with fewer than 100,000 characters.')
                code, warning = detect_text(text)
            name = language_name(code)
            if not name:
                raise ValueError('Could not identify a supported language. Choose the source manually.')
            dialect = None
            if code == 'ar' and request.form.get('suggest_dialect') == 'on':
                try:
                    dialect = suggest_dialect(text, request.form.get('llm_model', 'qwen2.5:7b'))
                    warning += ' Sana’ani is an unverified model suggestion, not a confirmed dialect.' if dialect else ' No reliable Sana’ani suggestion was found; you may select it manually.'
                except ValueError as exc:
                    warning += ' ' + str(exc)
            return jsonify(language=code, name=name, dialect=dialect, warning=warning, preview=text[:600], is_audio=is_audio)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception('Source detection failed')
        return jsonify(error='Detection failed. Choose the source language manually or check your local models.'), 500


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
    return jsonify(ollama_connected=connected, installed_models=installed, job=job)


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
    if kind == 'llm' and model in MODELS:
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


@app.post('/api/export/pdf')
def export_pdf():
    if not request.is_json:
        return jsonify(error='A JSON request is required.'), 400
    data = request.get_json()
    text = data.get('text') if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        return jsonify(error='Create a translation or transcript before saving a PDF.'), 400
    if len(text) > 500000:
        return jsonify(error='This translation is too long for PDF export. Use Save note (.txt).'), 400
    try:
        from pdf_export import translation_pdf
        kind = 'transcript' if data.get('kind') == 'transcript' else 'translation'
        return send_file(io.BytesIO(translation_pdf(text, kind=kind)), mimetype='application/pdf', as_attachment=True, download_name=f'glts-{kind}.pdf')
    except ModuleNotFoundError:
        return jsonify(error='PDF export needs updated dependencies. Run pip install -r requirements.txt using the GLTS virtual environment, then restart GLTS. You can still use Save note (.txt).'), 500
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception('PDF export failed')
        return jsonify(error='Could not create a PDF. Check the GLTS launch window, or use Save note (.txt).'), 500


@app.errorhandler(413)
def too_large(error):
    return jsonify(error=f'Files must be smaller than {app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)} MB.'), 413


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')))
