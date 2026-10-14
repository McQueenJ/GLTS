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
