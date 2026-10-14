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


def test_audio_extract(monkeypatch):
    monkeypatch.setattr(app, 'speech_model', lambda: SimpleNamespace(transcribe=lambda stream, **kwargs: ([SimpleNamespace(text='مرحبا')], None)))
    from werkzeug.datastructures import FileStorage
    assert app.extract_text(FileStorage(io.BytesIO(b'audio'), filename='speech.wav'), 'ar') == 'مرحبا'


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
