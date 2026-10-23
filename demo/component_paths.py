"""Locate independently installed component SDKs; never copy their implementations."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def verify_file(path, expected):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError(f'Unqualified SDK file: {path}; reuse the release in demo/component-versions.json')


def sdk_roots(translation_library=None):
    roots = []
    contract = json.loads((ROOT/'demo/component-versions.json').read_text())['components']
    for variable, name, module, library in [
        ('AUDIO8_SDK_ROOT', 'audio8-asr-infinite-demo', 'audio8_asr.py', 'libaudio8_asr.so'),
        ('HY_MT2_SDK_ROOT', 'hy-mt2-1.8b-demo', 'hy_mt2.py', 'libhy_mt2.so'),
    ]:
        root = Path(os.environ.get(variable, ROOT.parent / name)).expanduser().resolve()
        if not (root/'sdk/python'/module).is_file() or not (root/'sdk/lib'/library).is_file():
            raise ValueError(f'Install {name} independently and set {variable} to its checkout root: {root}')
        role = 'asr' if variable == 'AUDIO8_SDK_ROOT' else 'translation'
        expected = contract[role]
        verify_file(root/'sdk/python'/module, expected['binding_sha256'])
        verify_file(root/'sdk/lib'/library, expected['library_sha256'])
        if role == 'asr' and os.environ.get('AUDIO8_ASR_LIB'):
            if Path(os.environ['AUDIO8_ASR_LIB']).expanduser().resolve() != root/'sdk/lib'/library:
                raise ValueError('Unset AUDIO8_ASR_LIB; use the independently qualified AUDIO8_SDK_ROOT library')
        if role == 'translation' and translation_library:
            verify_file(Path(translation_library).expanduser().resolve(strict=True), expected['library_sha256'])
        roots.append(root)
    return tuple(roots)

def configure(translation_library=None):
    roots = sdk_roots(translation_library)
    for root in roots:
        directory = str(root/'sdk/python')
        if directory not in sys.path:
            sys.path.insert(0, directory)
    return roots
