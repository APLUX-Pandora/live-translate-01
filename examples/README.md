# Standalone Python integration

Run this example in the same project `.venv` used by the Web application. It calls
the independently installed Audio8 ASR Python SDK and the translation Python SDK through the independent
translation worker. It does not start an HTTP server, use browser state or import
the Web server. Segmentation, paragraph association and job management remain
business code outside the model SDKs.

Set AUDIO8_SDK_ROOT and HY_MT2_SDK_ROOT as in the main README. Use Audio8 SDK 0.6.1 and HY-MT2 SDK 0.2.1 from their independent installations; no library override is needed for these versions. Prepare a mono or stereo WAV/FLAC supported by soundfile, record its spoken
language, and download the model packages as described in `resources/README.md`.
The example averages channels and resamples audio to 16 kHz using scipy.

```bash
.venv/bin/python examples/python/translate_audio.py path/to/audio.wav \
  --source en --target fr --seconds 25 --realtime
# Optional strict package-root selection:
.venv/bin/python examples/python/translate_audio.py path/to/audio.wav \
  --source zh --target ja --models models/asr/qnn248_qcs8550 \
  --translation-models models/translation/qcs8550
```

Source choices are `zh en`; target choices are `zh en ja ko fr de es ar th`.
Identical source/target choices are rejected. Omitting `--target` chooses English
for Chinese input and Chinese for English input. Omitting `--realtime` processes
the file as fast as the runtime permits; it is not a realtime latency benchmark.
Explicit model paths are never silently replaced, and default discovery rejects
multiple candidate packages. Launching from another working directory is supported.

Output is a JSON event stream: `input`, `source`, translation reset/queued/started/
chunk/done events and a final `complete` record. `complete` contains the source
text, paragraphs, completed translations and `source_conserved: true`. Model
runtime diagnostics may be written separately by the installed vendor runtime.
For the English internal verification recording, the first complete phrase is
`In 2001, we introduced the first iPod.`; French output is `En 2001, nous avons lancé le premier iPod.` in the
QCS8550 file-example verification. Outputs depend on the supplied
recording, not a hard-coded transcript.

Internal verification uses the same original recordings as the Web tests, with
hashes and clip lengths in internal evidence. Those recordings are not bundled
here and are not approved for external redistribution by this example. Provide
your own authorized audio; external bundled experience media remain a release task.
