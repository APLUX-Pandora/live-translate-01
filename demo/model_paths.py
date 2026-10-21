"""Shared package resolution for Web and standalone business applications."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def resolve_packages(asr=None, translation=None):
    from live_transcribe_01 import resolve_model_dir as resolve_asr
    from multilingual_translation import resolve_model_dir as resolve_translation
    return (resolve_asr(asr, models_root=ROOT/'models/asr'),
            resolve_translation(translation, default_container=ROOT/'models/translation'))
