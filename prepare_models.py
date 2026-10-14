"""One-time ONLINE preparation. The application itself operates offline."""
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('XDG_DATA_HOME', str(ROOT / '.local/share'))
os.environ.setdefault('XDG_CACHE_HOME', str(ROOT / '.local/cache'))
os.environ.setdefault('XDG_CONFIG_HOME', str(ROOT / '.local/config'))
os.environ.setdefault('HF_HOME', str(ROOT / '.local/cache/huggingface'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--languages', nargs='+', default=['en', 'es', 'ar'])
    parser.add_argument('--skip-audio', action='store_true')
    args = parser.parse_args()
    import argostranslate.package as package
    installed = {(p.from_code, p.to_code) for p in package.get_installed_packages()}
    package.update_package_index()
    available = package.get_available_packages()
    failures = []
    for source in args.languages:
        for target in args.languages:
            if source == target or (source, target) in installed:
                continue
            match = next((p for p in available if p.from_code == source and p.to_code == target), None)
            if match is None:
                print(f'No direct pack available: {source} -> {target}')
                continue
            print(f'Installing {source} -> {target}', flush=True)
            try:
                package.install_from_path(match.download())
            except Exception as exc:
                failures.append(f'{source} -> {target}: {exc}')
    if not args.skip_audio:
        from huggingface_hub import snapshot_download
        snapshot_download('Systran/faster-whisper-tiny', local_dir=ROOT / 'models/whisper-tiny', allow_patterns=['model.bin', 'config.json', 'tokenizer.json', 'vocabulary.*'])
    if failures:
        raise SystemExit('Language packs remain unavailable:\n' + '\n'.join(failures))
    print('Model preparation complete. You can now disconnect from the internet.')


if __name__ == '__main__':
    main()
