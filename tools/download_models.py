#!/usr/bin/env python3
"""Download or verify the exact reusable component packages in the model lock."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class ScopedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != 'https' or not target.hostname or not target.hostname.isascii() or target.username or target.password:
            raise ValueError('Model download redirect must use an ASCII HTTPS host without URL credentials')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            redirected.remove_header('Authorization')
        return redirected


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--models-root', type=Path, default=ROOT/'models')
    ap.add_argument('--component', choices=['asr','translation','all'], default='all')
    ap.add_argument('--verify-only', action='store_true', help='Verify local files without network access or writes')
    a = ap.parse_args()
    lock=json.loads((ROOT/'resources/model-lock.json').read_text())
    opener=urllib.request.build_opener(ScopedRedirect())
    total=0
    for role, item in lock['components'].items():
        if a.component not in ('all',role):continue
        package=a.models_root/item['local_directory']
        for name, expected in item['files'].items():
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe path in model lock')
            path=package/relative
            if path.is_file() and digest(path)==expected:
                total+=1
                continue
            if a.verify_only:
                raise RuntimeError(f'Missing or mismatched file: {path}')
            path.parent.mkdir(parents=True,exist_ok=True)
            bundled = item.get('bundled_files', {}).get(name)
            if bundled is not None:
                source_relative = Path(bundled)
                if source_relative.is_absolute() or '..' in source_relative.parts:
                    raise ValueError('Unsafe bundled metadata path in model lock')
                source = ROOT / source_relative
                if digest(source) != expected:
                    raise RuntimeError(f'Bundled metadata checksum mismatch: {name}')
                shutil.copyfile(source, path)
                total += 1
                continue
            remote_name = item.get('remote_files', {}).get(name, name)
            remote_relative = Path(remote_name)
            if remote_relative.is_absolute() or '..' in remote_relative.parts:
                raise ValueError('Unsafe remote path in model lock')
            url=f"https://huggingface.co/{item['repository']}/resolve/{item['revision']}/{item['remote_prefix']}/{remote_name}"
            headers={}
            if os.environ.get('HF_TOKEN'):
                headers['Authorization']='Bearer '+os.environ['HF_TOKEN']
            temporary=path.with_name(path.name+'.download')
            try:
                with opener.open(urllib.request.Request(url,headers=headers),timeout=120) as response, temporary.open('wb') as f:
                    for block in iter(lambda:response.read(4*1024*1024),b''):f.write(block)
                if digest(temporary)!=expected:
                    raise RuntimeError(f'Download checksum mismatch: {path}')
                temporary.replace(path)
            finally:
                if temporary.exists():temporary.unlink()
            total+=1
        print(f"{role}: verified {len(item['files'])} files at {package}",flush=True)
    print(f'Verified {total} pinned package files',flush=True)


if __name__=='__main__':main()
