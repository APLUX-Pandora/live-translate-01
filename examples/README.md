# Standalone Python audio translation

Use the same project `.venv` as the Web demo, but no HTTP server is needed.
Provide an authorized WAV/FLAC supported by soundfile. Stereo channels are averaged
and audio is resampled to 16 kHz using scipy.

```bash
.venv/bin/python examples/python/translate_audio.py path/to/audio.wav \
  --source en --target fr --seconds 25 --realtime
```

Source choices are `zh en`; target choices are `zh en ja ko fr de es ar th`.
Source and target must differ. Omit `--target` for English → Chinese or Chinese →
English. Omit `--realtime` to process a file as fast as the runtime permits.

Default package discovery uses this checkout's model directories, independent of
working directory. To select explicitly:

```bash
.venv/bin/python examples/python/translate_audio.py path/to/audio.wav \
  --source zh --target ja --models models/asr/qnn248_qcs8550 \
  --translation-models models/translation/qcs8550
```

Output is a JSON event stream: input metadata, source updates, translation
queued/started/chunk/done events and a final complete record. The final record
contains source text, paragraphs, completed translations and source conservation.
Runtime diagnostics may be emitted separately by the installed vendor runtime.
Both default and explicit paths use the same public SDKs and native libraries.
