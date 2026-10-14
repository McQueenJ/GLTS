"""Explicitly online installer for the optional noncommercial Yemeni speech pack."""
import argparse
import json
import os
import shutil
import tempfile

from speech_packs import ROOT, SANAANI_PATH, SANAANI_REPO, SANAANI_REVISION, sanaani_installed

os.environ.setdefault('HF_HOME', str(ROOT / '.local/cache/huggingface'))
os.environ['HF_HUB_OFFLINE'] = '0'
os.environ['TRANSFORMERS_OFFLINE'] = '0'
os.environ.setdefault('OMP_NUM_THREADS', '2')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accept-noncommercial-license', action='store_true')
    args = parser.parse_args()
    if not args.accept_noncommercial_license:
        raise SystemExit('Read the CC BY-NC-SA 4.0 license on the model page and accept it before downloading.')
    if sanaani_installed():
        print('The Yemeni / Sana’ani speech pack is already installed.', flush=True)
        return
    if shutil.disk_usage(ROOT).free < 4 * 1024**3:
        raise SystemExit('At least 4 GB of free disk space is required for download and conversion.')
    from huggingface_hub import snapshot_download
    from ctranslate2.converters import TransformersConverter
    from transformers import AutoTokenizer
    import torch
    torch.set_num_threads(2)
    print('Downloading the Yemeni speech model (approximately 1 GB)…', flush=True)
    snapshot = snapshot_download(SANAANI_REPO, revision=SANAANI_REVISION, allow_patterns=['*.json', '*.txt', 'model.safetensors', 'README.md'])
    print('Preparing the local model. This can take several minutes…', flush=True)
    SANAANI_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.yemeni-setup-', dir=SANAANI_PATH.parent) as staging:
        converted = os.path.join(staging, 'converted')
        class LocalConverter(TransformersConverter):
            def load_model(self, model_class, model_name_or_path, **kwargs):
                # CTranslate2 4.8 uses dtype; Transformers 4.51 uses torch_dtype.
                if 'dtype' in kwargs:
                    kwargs['torch_dtype'] = kwargs.pop('dtype')
                return model_class.from_pretrained(model_name_or_path, local_files_only=True, use_safetensors=True, **kwargs)
        LocalConverter(snapshot).convert(converted, quantization='int8')
        AutoTokenizer.from_pretrained(snapshot, local_files_only=True).backend_tokenizer.save(os.path.join(converted, 'tokenizer.json'))
        shutil.copyfile(os.path.join(snapshot, 'README.md'), os.path.join(converted, 'MODEL_CARD.md'))
        from faster_whisper import WhisperModel
        print('Checking that the converted model can load locally…', flush=True)
        model = WhisperModel(converted, device='cpu', compute_type='int8', local_files_only=True, cpu_threads=2)
        del model
        with open(os.path.join(converted, 'glts-model.json'), 'w', encoding='utf-8') as f:
            json.dump(dict(repository=SANAANI_REPO, revision=SANAANI_REVISION, license='CC-BY-NC-SA-4.0'), f)
        if SANAANI_PATH.exists():
            raise SystemExit('An incomplete model folder exists. Rename models/whisper-yemeni and retry; existing files were preserved.')
        os.replace(converted, SANAANI_PATH)
    print('Speech pack installed. It is ready for offline use.', flush=True)


if __name__ == '__main__':
    main()
