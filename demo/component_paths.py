"""Locate independently installed component SDKs; never copy their implementations."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def sdk_roots():
    roots = []
    for variable, name, module, library in [
        ('AUDIO8_SDK_ROOT', 'audio8-asr-infinite-demo', 'audio8_asr.py', 'libaudio8_asr.so'),
        ('HY_MT2_SDK_ROOT', 'hy-mt2-1.8b-demo', 'hy_mt2.py', 'libhy_mt2.so'),
    ]:
        root = Path(os.environ.get(variable, ROOT.parent / name)).expanduser().resolve()
        if not (root/'sdk/python'/module).is_file() or not (root/'sdk/lib'/library).is_file():
            raise ValueError(f'Install {name} independently and set {variable} to its checkout root: {root}')
        roots.append(root)
    return tuple(roots)

def configure():
    roots = sdk_roots()
    for root in roots:
        directory = str(root/'sdk/python')
        if directory not in sys.path:
            sys.path.insert(0, directory)
    return roots
