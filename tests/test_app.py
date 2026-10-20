import io
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import pytest


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app, 'languages', lambda: [SimpleNamespace(code='ar', name='Arabic'), SimpleNamespace(code='en', name='English')])
    return app.app.test_client()


def test_gui_has_local_assets(client):
    page = client.get('/')
    assert page.status_code == 200
    assert b'Arabic' in page.data
    assert b'cloud services' in page.data
    assert b'fonts.googleapis' not in client.get('/static/style.css').data


def test_translation_request(client, monkeypatch):
    monkeypatch.setattr(app, 'translate', lambda text, source, target: 'Hello' if (text, source, target) == ('مرحبا', 'ar', 'en') else None)
    response = client.post('/api/translate', data={'text': 'مرحبا', 'source_language': 'ar', 'language': 'en'})
    assert response.status_code == 200
    assert response.json['translation'] == 'Hello'


def test_utf8_file(client, monkeypatch):
    monkeypatch.setattr(app, 'translate', lambda text, *_: text)
    response = client.post('/api/translate', data={'source_language': 'ar', 'language': 'en', 'file': (io.BytesIO('مرحبا'.encode()), 'arabic.txt')})
    assert response.json['source'] == 'مرحبا'


def test_bad_pdf_and_empty_input(client):
    for extra in [{}, {'file': (io.BytesIO(b'bad pdf'), 'bad.pdf')}]:
        response = client.post('/api/translate', data={'source_language': 'ar', 'language': 'en', **extra})
        assert response.status_code == 400


@pytest.mark.parametrize('filename', ['speech.wav', 'speech.opus', 'speech.OPUS'])
def test_audio_extract(monkeypatch, filename):
    monkeypatch.setattr(app, 'speech_model', lambda: SimpleNamespace(transcribe=lambda stream, **kwargs: ([SimpleNamespace(text='مرحبا')], None)))
    from werkzeug.datastructures import FileStorage
    assert app.extract_text(FileStorage(io.BytesIO(b'audio'), filename=filename), 'ar') == 'مرحبا'


def test_real_offline_arabic_translation(monkeypatch):
    import argostranslate.translate
    if not any(p.code == 'ar' for p in argostranslate.translate.get_installed_languages()):
        pytest.skip('Arabic model not installed')
    def denied(*args, **kwargs):
        raise AssertionError('Network access attempted during offline translation')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    text = app.translate('مرحبا بالعالم', 'ar', 'en')
    assert 'hello' in text.lower() and 'world' in text.lower()


def test_pdf_text_extraction():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    from werkzeug.datastructures import FileStorage
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(b'BT /F1 12 Tf 20 200 Td (Hello world) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(content)
    stream = io.BytesIO()
    writer.write(stream)
    stream.seek(0)
    assert 'Hello world' in app.extract_text(FileStorage(stream, filename='test.pdf'), 'en')


@pytest.fixture
def settings_client(monkeypatch, tmp_path):
    monkeypatch.setattr(app, 'SETTINGS_PATH', tmp_path / 'settings.json')
    monkeypatch.setitem(app.app.config, 'MAX_CONTENT_LENGTH', 25 * 1024 * 1024)
    monkeypatch.setitem(app.app.config, 'COMPUTE_MODE', 'cpu')
    monkeypatch.setattr(app, 'cuda_available', lambda: False)
    return app.app.test_client()


def test_settings_persist_and_enforce_upload_limit(settings_client):
    assert settings_client.post('/api/settings', json={'max_upload_mb': 1}).status_code == 200
    assert app.saved_upload_limit() == 1
    response = settings_client.post('/api/translate', data={'file': (io.BytesIO(b'x' * (1024 * 1024 + 1)), 'large.txt')})
    assert response.status_code == 413
    assert '1 MB' in response.json['error']
    for bad in [0, 1025, 1.5, True, '25']:
        assert settings_client.post('/api/settings', json={'max_upload_mb': bad}).status_code == 400
    assert app.saved_upload_limit() == 1


def test_cuda_mode_validation(settings_client, monkeypatch):
    assert settings_client.post('/api/settings', json={'compute_mode': 'cuda'}).status_code == 400
    assert app.app.config['COMPUTE_MODE'] == 'cpu'
    monkeypatch.setattr(app, 'cuda_available', lambda: True)
    response = settings_client.post('/api/settings', json={'compute_mode': 'cuda'})
    assert response.status_code == 200
    import json
    assert json.loads(app.SETTINGS_PATH.read_text())['compute_mode'] == 'cuda'
    assert app.compute_mode() == 'cuda'
    assert settings_client.post('/api/settings', json={'max_upload_mb': 100}).json['compute_mode'] == 'cuda'
    monkeypatch.setattr(app, 'cuda_available', lambda: False)
    with pytest.raises(ValueError, match='CUDA is unavailable'):
        app.compute_mode()
    assert settings_client.post('/api/settings', json={'compute_mode': 'cpu'}).status_code == 200


def test_pack_catalog_offline_and_install(client, monkeypatch, tmp_path):
    from argostranslate import settings
    index = tmp_path / 'index.json'
    monkeypatch.setattr(settings, 'local_package_index', index)
    installed = []
    events = []
    pack = SimpleNamespace(type='translate', from_code='ar', to_code='en', from_name='Arabic', to_name='English', download=lambda: events.append('download') or 'pack.argosmodel')
    def get_available():
        assert index.exists(), 'Offline catalog must not trigger an index download'
        return [pack]
    def refresh():
        events.append('refresh')
        index.write_text('[]')
    def install(path):
        assert path == 'pack.argosmodel'
        events.append('install')
        installed.append(pack)
    manager = SimpleNamespace(get_installed_packages=lambda: installed, get_available_packages=get_available, update_package_index=refresh, install_from_path=install)
    monkeypatch.setattr(app, 'package_manager', lambda: manager)
    assert client.get('/api/packs').json['packs'] == []
    assert events == []
    assert client.post('/api/packs/refresh', json={}).status_code == 200
    assert client.post('/api/packs/install', json={'id': 'ar:en'}).json['packs'][0]['installed']
    assert events == ['refresh', 'download', 'install']
    assert client.post('/api/packs/install', json={'id': 'ar:en'}).status_code == 200
    assert events == ['refresh', 'download', 'install']
    assert client.post('/api/packs/install', json={'id': 'fake'}).status_code == 400


def test_pack_network_failure_preserves_existing(client, monkeypatch):
    def failed():
        raise OSError('Offline')
    monkeypatch.setattr(app, 'package_manager', lambda: SimpleNamespace(update_package_index=failed))
    response = client.post('/api/packs/refresh', json={})
    assert response.status_code == 502
    assert 'Existing packs remain available offline' in response.json['error']
    assert not app.pack_lock.locked()
    assert client.post('/api/packs/install', data={'id': 'ar:en'}).status_code == 400
    assert client.post('/api/packs/refresh', json={}, headers={'Origin': 'https://example.com'}).status_code == 403


def test_gui_settings(client):
    page = client.get('/').data
    assert b'WORDS WITHOUT BORDERS' not in page
    for control in [b'dark-mode', b'pack-search', b'max-upload', b'compute-mode']:
        assert control in page


@pytest.mark.parametrize('model', ['qwen2.5:7b', 'qwen2.5:14b'])
def test_sanaani_text_uses_local_language_model(client, monkeypatch, model):
    calls = []
    monkeypatch.setattr(app, 'translate_local', lambda *args: calls.append(args) or 'I want to go home.')
    response = client.post('/api/translate', data={'text': 'اشتي اروح البيت', 'source_language': 'ar-sanaa', 'language': 'en', 'engine': 'ollama', 'llm_model': model})
    assert response.status_code == 200
    assert response.json['translation'] == 'I want to go home.'
    assert calls[0][1:] == ('ar-sanaa', 'English', model)
    response = client.post('/api/translate', data={'text': 'اشتي', 'source_language': 'ar-sanaa', 'language': 'en'})
    assert response.status_code == 400
    assert 'not dialect-specific' in response.json['error']


def test_sanaani_audio_routes_to_dedicated_model(client, monkeypatch):
    calls = []
    class Speech:
        def transcribe(self, audio, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(text='اشتي اروح البيت')], None
    monkeypatch.setattr(app, 'load_speech_model', lambda mode, pack: calls.append((mode, pack)) or Speech())
    monkeypatch.setattr(app, 'translate', lambda text, source, target: 'I want to go home.' if source == 'ar' else None)
    response = client.post('/api/translate', data={'source_language': 'ar-sanaa', 'language': 'en', 'file': (io.BytesIO(b'audio'), 'sanaa.opus')})
    assert response.status_code == 200
    assert calls[0] == ('cpu', app.SANAANI_ID)
    assert calls[1]['language'] == 'ar'
    assert response.json['source'] == 'اشتي اروح البيت'


def test_optional_models_require_license_and_known_names(client, monkeypatch):
    monkeypatch.setattr(app, 'sanaani_installed', lambda: False)
    monkeypatch.setattr(app, 'installed_models', lambda: [])
    assert client.post('/api/local-models/install', json={'kind': 'speech'}).status_code == 400
    assert client.post('/api/local-models/install', json={'kind': 'llm', 'model': 'untrusted/model'}).status_code == 400
    assert client.post('/api/local-models/install', json={'kind': 'speech', 'accept_license': True}, headers={'Origin': 'https://example.com'}).status_code == 403
    monkeypatch.setitem(app.model_job, 'state', 'running')
    assert client.post('/api/local-models/install', json={'kind': 'speech', 'accept_license': True}).status_code == 409
    status = client.get('/api/local-models')
    assert status.status_code == 200
    assert status.json['job']['state'] == 'running'


@pytest.mark.parametrize('model', ['qwen2.5:7b', 'qwen2.5:14b'])
def test_background_model_download_updates_status(monkeypatch, tmp_path, model):
    monkeypatch.setattr(app, 'installed_models', lambda: [model])
    calls = []
    monkeypatch.setattr(app, 'ollama_request', lambda *args, **kwargs: calls.append(args) or {})
    monkeypatch.setattr(app, 'model_job', {'state': 'running'})
    app.run_model_install('llm', model)
    assert calls[0] == ('/api/pull', {'model': model, 'stream': False})
    assert app.model_job['state'] == 'complete'
    def failed(*args, **kwargs):
        raise ValueError('Connection refused')
    monkeypatch.setattr(app, 'ollama_request', failed)
    app.run_model_install('llm', model)
    assert app.model_job['state'] == 'failed'
    assert 'Connection refused' in app.model_job['message']


@pytest.mark.parametrize('model', ['qwen2.5:7b', 'qwen2.5:14b'])
def test_local_llm_chunking_and_truncation(monkeypatch, model):
    import local_models
    monkeypatch.setattr(local_models, 'installed_models', lambda: [model])
    calls = []
    def chat(path, payload, **kwargs):
        calls.append(payload)
        return {'message': {'content': 'translated'}, 'done_reason': 'stop'}
    monkeypatch.setattr(local_models, 'ollama_request', chat)
    result = local_models.translate_local('a' * 3000, 'ar-sanaa', 'English', model)
    assert result == 'translated\ntranslated'
    assert 'Sana’ani' in calls[0]['messages'][0]['content']
    assert ''.join(p['messages'][1]['content'] for p in calls) == 'a' * 3000
    monkeypatch.setattr(local_models, 'ollama_request', lambda *args, **kwargs: {'message': {'content': 'cut off'}, 'done_reason': 'length'})
    with pytest.raises(ValueError, match='incomplete'):
        local_models.translate_local('text', 'ar-sanaa', 'English', model)


def test_real_sanaani_speech_inference_offline(monkeypatch):
    if not app.sanaani_installed():
        pytest.skip('Optional Sana’ani speech pack is not installed')
    import wave
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b'\0\0' * 16000)
    buffer.seek(0)
    def denied(*args, **kwargs):
        raise AssertionError('Network attempted during speech inference')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    model = app.load_speech_model('cpu', app.SANAANI_ID)
    segments, info = model.transcribe(buffer, language='ar', beam_size=1)
    assert isinstance(list(segments), list)
    assert info.language == 'ar'


def test_opus_decoding():
    from faster_whisper.audio import decode_audio
    path = Path(__file__).parent / 'fixtures/tone.opus'
    audio = decode_audio(str(path), sampling_rate=16000)
    assert 15000 <= len(audio) <= 17000
    assert abs(audio).max() > 0.01


def test_opus_upload_available_in_gui(client):
    page = client.get('/').get_data(as_text=True)
    assert '.opus' in page
    assert 'OPUS' in page


@pytest.mark.parametrize('text,code', [
    ('This is a longer English passage about translating documents offline.', 'en'),
    ('مرحبا بكم في هذا البرنامج لترجمة النصوص والوثائق إلى اللغة الإنجليزية.', 'ar'),
    ('Bonjour, ce programme permet de traduire des documents sans connexion Internet.', 'fr'),
])
def test_text_detection_offline(monkeypatch, text, code):
    from detection import detect_text
    def denied(*args, **kwargs):
        raise AssertionError('Network attempted during text detection')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    assert detect_text(text)[0] == code


def test_detection_requires_review_and_handles_short_text(client, monkeypatch):
    def unexpected(*args):
        raise AssertionError('Detection must not translate')
    monkeypatch.setattr(app, 'translate', unexpected)
    response = client.post('/api/detect', data={'text': 'This English document explains how local translation works.'})
    assert response.status_code == 200
    assert response.json['language'] == 'en'
    assert 'translation' not in response.json
    assert 'Review' in response.json['warning']
    assert client.post('/api/detect', data={'text': 'hi'}).status_code == 400
    response = client.post('/api/translate', data={'source_language': 'auto', 'language': 'en', 'text': 'test'})
    assert response.status_code == 400
    assert 'confirm' in response.json['error']


def test_audio_autodetection(client, monkeypatch):
    calls = []
    def transcribe(data, source):
        calls.append(source)
        return 'مرحبا بكم في هذا البرنامج', SimpleNamespace(language='ar', language_probability=0.3)
    monkeypatch.setattr(app, 'transcribe_audio', transcribe)
    monkeypatch.setattr(app, 'suggest_dialect', lambda *_: 'ar-sanaa')
    response = client.post('/api/detect', data={'file': (io.BytesIO(b'opus'), 'audio.opus'), 'suggest_dialect': 'on'})
    assert response.status_code == 200
    assert calls == ['auto']
    assert response.json['dialect'] == 'ar-sanaa'
    assert 'unverified' in response.json['warning']
    assert 'uncertain' in response.json['warning']
    assert response.json['is_audio']


def test_missing_dialect_model_does_not_block_detection(client, monkeypatch):
    def missing(*args):
        raise ValueError('Ollama is unavailable')
    monkeypatch.setattr(app, 'suggest_dialect', missing)
    response = client.post('/api/detect', data={'text': 'مرحبا بكم في هذا البرنامج لترجمة النصوص والوثائق إلى اللغة الإنجليزية.', 'suggest_dialect': 'on'})
    assert response.status_code == 200
    assert response.json['language'] == 'ar'
    assert response.json['dialect'] is None
    assert 'unavailable' in response.json['warning']


@pytest.mark.parametrize('model', ['qwen2.5:7b', 'qwen2.5:14b'])
def test_dialect_suggestion_is_conservative(monkeypatch, model):
    import detection
    import local_models
    monkeypatch.setattr(local_models, 'installed_models', lambda: [model])
    for value, expected in [('unknown', None), ('other', None), ('sanaani', 'ar-sanaa')]:
        import json
        monkeypatch.setattr(local_models, 'ollama_request', lambda *args, value=value, **kwargs: {'message': {'content': json.dumps({'dialect': value})}})
        assert detection.suggest_dialect('مرحبا', model) == expected
    monkeypatch.setattr(local_models, 'ollama_request', lambda *args, **kwargs: {'message': {'content': 'not JSON'}})
    assert detection.suggest_dialect('مرحبا', model) is None


def test_ollama_http_error_details_reach_gui(client, monkeypatch):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import local_models
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({'models': [{'name': 'qwen2.5:14b'}]}).encode())
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'model requires more system memory than is available'}).encode())
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(local_models, 'OLLAMA_URL', f'http://127.0.0.1:{server.server_port}')
    try:
        response = client.post('/api/translate', data={'text': 'أنا حوثي من زمان يغالي', 'source_language': 'ar-sanaa', 'language': 'en', 'engine': 'ollama', 'llm_model': 'qwen2.5:14b'})
        assert response.status_code == 400
        assert 'model requires more system memory' in response.json['error']
        assert 'CUDA 12' not in response.json['error']
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_missing_dependency_actionable(client, monkeypatch):
    def missing(*args):
        raise ModuleNotFoundError('No module named pycountry')
    monkeypatch.setattr(app, 'translate_local', missing)
    response = client.post('/api/translate', data={'text': 'مرحبا', 'source_language': 'ar-sanaa', 'language': 'en', 'engine': 'ollama'})
    assert response.status_code == 500
    assert 'pip install -r requirements.txt' in response.json['error']


def test_ollama_invalid_message_is_actionable(monkeypatch):
    import local_models
    monkeypatch.setattr(local_models, 'installed_models', lambda: ['qwen2.5:14b'])
    monkeypatch.setattr(local_models, 'ollama_request', lambda *args, **kwargs: {'message': None})
    with pytest.raises(ValueError, match='empty or incomplete'):
        local_models.translate_local('مرحبا', 'ar-sanaa', 'English', 'qwen2.5:14b')


def test_pdf_export_english_and_multipage(client):
    from pypdf import PdfReader
    text = 'Translation line with names and numbers 123.\n' * 90
    response = client.post('/api/export/pdf', json={'text': text})
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    assert 'attachment' in response.headers['Content-Disposition']
    reader = PdfReader(io.BytesIO(response.data))
    assert len(reader.pages) > 1
    extracted = '\n'.join(page.extract_text() for page in reader.pages)
    assert extracted.count('Translation line with names and numbers 123.') == 90


def test_pdf_export_arabic_offline(client, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('PDF export attempted network access')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    response = client.post('/api/export/pdf', json={'text': 'مرحبا بالعالم\nEnglish text 123'})
    assert response.status_code == 200
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(response.data))
    extracted = reader.pages[0].extract_text()
    assert 'English text 123' in extracted
    assert any('\u0600' <= char <= '\u06ff' for char in extracted)
    assert '/Font' in reader.pages[0]['/Resources']


def test_pdf_export_validation(client):
    for payload in [{}, {'text': ''}, {'text': 123}, {'text': 'x' * 500001}]:
        assert client.post('/api/export/pdf', json=payload).status_code == 400
    response = client.post('/api/export/pdf', json={'text': '翻译'})
    assert response.status_code == 400
    assert 'Save note' in response.json['error']
    assert client.post('/api/export/pdf', data={'text': 'hello'}).status_code == 400


def test_branding_logo_served_locally(client):
    page = client.get('/').get_data(as_text=True)
    assert '/branding/glts-logo.png' in page
    assert 'GLTS — Global Language Translation Service' in page
    response = client.get('/branding/glts-logo.png')
    assert response.status_code == 200
    assert response.mimetype == 'image/png'
    assert response.data.startswith(b'\x89PNG\r\n\x1a\n')


@pytest.mark.parametrize('source', ['ar', 'ar-sanaa', 'auto'])
def test_transcription_only_does_not_translate(client, monkeypatch, source):
    calls = []
    def transcribe(data, language):
        calls.append(language)
        return 'مرحبا بالعالم', SimpleNamespace(language='ar')
    def forbidden(*args):
        raise AssertionError('Transcription must not call a translation engine')
    monkeypatch.setattr(app, 'transcribe_audio', transcribe)
    monkeypatch.setattr(app, 'translate', forbidden)
    monkeypatch.setattr(app, 'translate_local', forbidden)
    response = client.post('/api/transcribe', data={'source_language': source, 'file': (io.BytesIO(b'audio'), 'speech.opus')})
    assert response.status_code == 200
    assert response.json['transcript'] == 'مرحبا بالعالم'
    assert 'translation' not in response.json
    assert calls == [source]


def test_transcription_requires_audio_and_speech(client, monkeypatch):
    assert client.post('/api/transcribe', data={'text': 'hello', 'source_language': 'en'}).status_code == 400
    assert client.post('/api/transcribe', data={'source_language': 'en', 'file': (io.BytesIO(b'hello'), 'notes.txt')}).status_code == 400
    monkeypatch.setattr(app, 'transcribe_audio', lambda *_: ('', SimpleNamespace(language='en')))
    response = client.post('/api/transcribe', data={'source_language': 'en', 'file': (io.BytesIO(b'audio'), 'silent.wav')})
    assert response.status_code == 400
    assert 'No speech' in response.json['error']


def test_transcript_pdf_filename_and_title(client):
    response = client.post('/api/export/pdf', json={'text': 'An original language transcript.', 'kind': 'transcript'})
    assert response.status_code == 200
    assert 'glts-transcript.pdf' in response.headers['Content-Disposition']
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(response.data))
    assert reader.metadata.title == 'GLTS transcript'
    assert 'original language transcript' in reader.pages[0].extract_text()
