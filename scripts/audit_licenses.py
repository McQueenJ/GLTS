"""Capture installed runtime dependency metadata and upstream notice files.

Run with GLTS's venv. This is evidence for the installed platform, not a legal
clearance or a substitute for reviewing platform-specific binary licenses.
"""
import hashlib
import json
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def main():
    generated = ROOT / 'licenses/python'
    if generated.exists():
        shutil.rmtree(generated)  # Only generated copies; upstream notices are separate.
    roots = [Requirement(line).name for line in (ROOT / 'requirements.txt').read_text().splitlines() if line.strip() and not line.startswith('#')]
    roots.append('torch')  # CPU-only installer prerequisite.
    pending = list(roots)
    visited = set()
    packages = []
    while pending:
        name = canonicalize_name(pending.pop())
        if name in visited:
            continue
        visited.add(name)
        dist = metadata.distribution(name)
        meta = dist.metadata
        for spec in dist.requires or []:
            req = Requirement(spec)
            if req.marker is None or req.marker.evaluate({'extra': ''}):
                pending.append(req.name)
        notices = []
        for path in dist.files or []:
            filename = Path(str(path)).name
            if not re.match(r'^(licen[cs]e|copying|copyright|notice)([._-]|$)', filename, re.I):
                continue
            if Path(filename).suffix in ('.py', '.pyc'):
                continue
            original = dist.locate_file(path)
            if not original.is_file():
                continue
            relative = Path(str(path))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            destination = ROOT / 'licenses/python' / name / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = original.read_bytes()
            destination.write_bytes(data)
            notices.append({'path': str(destination.relative_to(ROOT)), 'sha256': hashlib.sha256(data).hexdigest()})
        supplemental = {
            'langid': 'langid-LICENSE', 'flatbuffers': 'flatbuffers-LICENSE',
            'tokenizers': 'tokenizers-LICENSE', 'ctranslate2': 'CTranslate2-LICENSE',
            'sentencepiece': 'sentencepiece-LICENSE',
        }.get(name)
        if supplemental:
            notice = ROOT / 'licenses/upstream' / supplemental
            if notice.is_file():
                notices.append({'path': str(notice.relative_to(ROOT)), 'sha256': hashlib.sha256(notice.read_bytes()).hexdigest()})
        packages.append({
            'name': meta['Name'], 'version': dist.version,
            'declared_license': meta.get('License-Expression') or meta.get('License') or '',
            'license_classifiers': [value for value in meta.get_all('Classifier', []) if 'License ::' in value],
            'project_urls': meta.get_all('Project-URL', []),
            'homepage': meta.get('Home-page', ''), 'notice_files': notices,
        })
    result = {'scope': 'Installed Python dependency closure including CPU torch; current platform markers only. Not a Windows binary audit or legal clearance.', 'platform': sys.platform, 'python': sys.version.split()[0], 'packages': sorted(packages, key=lambda p: p['name'].lower())}
    (ROOT / 'licenses/dependency-inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    rows = ['# Installed Python dependency inventory', '', 'Generated from the tested environment. See dependency-inventory.json for exact metadata and retained notices. Platform-specific wheels and future resolver choices may differ.', '', '| Package | Version | Declared license / classifier |', '| --- | --- | --- |']
    for package in result['packages']:
        label = package['declared_license']
        if not label or label == 'UNKNOWN' or len(label) > 150:
            label = '; '.join(package['license_classifiers']) or 'See upstream notices'
        rows.append(f"| {package['name']} | {package['version']} | {label.replace('|', '/').replace(chr(10), ' ')} |")
    (ROOT / 'licenses/DEPENDENCIES.md').write_text('\n'.join(rows) + '\n')
    missing = [p['name'] for p in packages if not p['notice_files']]
    print(f'Recorded {len(packages)} dependency versions and {sum(len(p["notice_files"]) for p in packages)} notice files.')
    print('Packages with no captured notice file:', ', '.join(missing) or 'none')


if __name__ == '__main__':
    main()
