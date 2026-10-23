#!/usr/bin/env python3
"""Stream a local audio file through the delivered ASR and translation SDKs."""
import argparse
import codecs
import hashlib
import json
from math import gcd
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'demo'))
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')


def main():
    from languages import LANGUAGES, SOURCE_LANGUAGES, target_for
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('audio', type=Path)
    ap.add_argument('--source', choices=SOURCE_LANGUAGES, required=True)
    ap.add_argument('--target', choices=LANGUAGES)
    ap.add_argument('--models', help='ASR package root containing manifest.json')
    ap.add_argument('--translation-models', help='Translation package root containing manifest.json')
    ap.add_argument('--translation-library', help='Qualified independent HY-MT2 library override')
    ap.add_argument('--seconds', type=float, help='Limit input duration for a short sample')
    ap.add_argument('--realtime', action='store_true', help='Pace audio at its original speed')
    a = ap.parse_args()
    try:
        target = target_for(a.source, a.target)
        if a.seconds is not None and a.seconds <= 0:
            raise ValueError('--seconds must be positive')
        if not a.audio.is_file():
            raise ValueError(f'Audio file not found: {a.audio}')
    except ValueError as exc:
        ap.error(str(exc))
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    from component_paths import configure
    _, translation_root = configure()
    from audio8_asr import Engine, extra_file
    from model_paths import resolve_packages
    from paragraphs import ParagraphTracker
    from reset_policy import ResetPolicy
    from segmentation import Segmenter
    from translation_service import TranslationService
    from vad_gate import SileroGate

    paths = resolve_packages(a.models, a.translation_models)
    audio, rate = sf.read(a.audio, dtype='float32', always_2d=True)
    audio = audio.mean(axis=1)
    if a.seconds is not None:
        audio = audio[:round(a.seconds*rate)]
    if not len(audio):
        ap.error('Input contains no audio samples')
    if rate != 16000:
        divisor = gcd(rate, 16000)
        audio = resample_poly(audio, 16000//divisor, rate//divisor).astype(np.float32)
    output_lock = threading.Lock()
    def emit(event):
        with output_lock:
            print(json.dumps(event, ensure_ascii=False), flush=True)

    engine = service = None
    try:
        service = TranslationService(paths[1], translation_root/'sdk/python', emit,
                                     library=a.translation_library)
        engine = Engine(paths[0], clock_ms=160, lang=a.source)
        engine.reset()
        policy = ResetPolicy(engine)
        gate = SileroGate(extra_file(paths[0], 'silero_vad'))
        phrases = Segmenter(a.source, engine.info['num_delay_tokens'])
        paragraphs = ParagraphTracker(engine.info['num_delay_tokens'])
        decoder = codecs.getincrementaldecoder('utf-8')('replace')
        service.begin(1, a.source, target)
        paragraph_id = None
        count = 0
        source = []
        horizon = min(range(len(engine.info['eot_horizons_s'])), key=lambda i: abs(engine.info['eot_horizons_s'][i]-1.0))
        paragraph_horizon = min(range(len(engine.info['eot_horizons_s'])), key=lambda i: abs(engine.info['eot_horizons_s'][i]-2.0))
        def submit(segments):
            for segment in segments:
                service.submit(1, segment, paragraph_id)
        def accept(piece, timestamp, eot, paragraph_eot):
            nonlocal paragraph_id
            source.append(piece)
            parts = paragraphs.push(piece, count, paragraph_eot, len(policy.resets),
                                    max(0, timestamp-engine.info['num_delay_tokens']*engine.clock_s))
            emit(dict(type='source', piece=piece, parts=parts))
            for part in parts:
                if paragraph_id != part['id']:
                    submit(phrases.finish())
                    paragraph_id = part['id']
                submit(phrases.push(part['piece'], timestamp, eot))
            if not parts:
                submit(phrases.push('', timestamp, eot))
        def consume(tokens):
            nonlocal count
            for token in tokens:
                count += 1
                accept(decoder.decode(engine.token_bytes(token.id)), token.audio_t,
                       token.eot[horizon], token.eot[paragraph_horizon])
        emit(dict(type='input', source=a.source, target=target, seconds=len(audio)/16000,
                  sha256=hashlib.sha256(a.audio.read_bytes()).hexdigest(),
                  asr_models=str(paths[0]), translation_models=str(paths[1])))
        start = time.monotonic()
        size = engine.samples_per_token
        for i in range(0, len(audio), size):
            if a.realtime:
                time.sleep(max(0, start+min(i+size,len(audio))/16000-time.monotonic()))
            samples = gate.process(audio[i:i+size])
            if i+size >= len(audio):
                samples = np.concatenate([samples, gate.flush()])
            for j in range(0, len(samples), size):
                consume(policy.check(*gate.segment()))
                tokens = engine.feed(samples[j:j+size])
                policy.observe(tokens)
                consume(tokens)
            submit(phrases.tick(min(i+size,len(audio))/16000))
        consume(engine.finish())
        accept(decoder.decode(b'', final=True), len(audio)/16000, 0, None)
        submit(phrases.finish())
        deadline = time.monotonic()+300
        while service.snapshot()['pending']:
            if time.monotonic() >= deadline:
                raise TimeoutError('Translation did not drain within 300 seconds')
            time.sleep(.05)
        snapshot = service.snapshot()
        if any(row['status'] != 'done' for row in snapshot['segments']):
            raise RuntimeError('Translation failed; inspect the translation error events')
        if ''.join(source).strip() != ''.join(row['source_text'] for row in snapshot['segments']).strip():
            raise RuntimeError('Source text was lost or duplicated')
        emit(dict(type='complete', source_text=''.join(source), paragraphs=paragraphs.snapshot(),
                  translations=snapshot['segments'], source_conserved=True))
    finally:
        try:
            if service:
                service.close()
        finally:
            if engine:
                engine.close()


if __name__ == '__main__':
    main()
