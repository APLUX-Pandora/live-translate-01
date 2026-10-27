# Finite-file Python integration

Run the file example through this application's `.venv/bin/python`, with the initialized component submodules and prepared model roots from the main README. No HTTP service or browser is involved; the same ASR/translation SDKs and business segmentation are reused.

```bash
.venv/bin/python examples/python/translate_audio.py /path/to/audio.wav \
  --source en --target zh --models "$ASR_MODELS" \
  --translation-models "$TRANSLATION_MODELS"
```

Soundfile reads mono/stereo WAV/FLAC; channels are averaged and scipy resamples to16kHz. Source choices: `zh en`; targets: `zh en ja ko fr de es ar th`. Equal source/target is rejected; omitted target selects English for Chinese source and Chinese for English source. `--seconds 25` limits input. `--realtime` paces capture; default file processing runs as fast as the runtime permits and is not a latency benchmark. Explicit relative paths use the invoking directory; default discovery is anchored to this application.

Output is JSON events: `input`, `source`, translation reset/queued/started/chunk/done and final `complete`. Complete output contains `source_text`, `paragraphs`, ordered `translations` and `source_conserved`. Each translation retains original source, translation input, final text/status, timing/statistics and segment identity. Full finite-file results are accumulated independently of the256-row Web replay limit. Errors remain errors even after Web history would expire. Runtime diagnostics from external libraries may be written separately.

## Stop and release

The command starts a lightweight native-free supervisor using the same stop-pipe boundary as the Web launcher. TERM/INT to that PID or its process group records one stop request. The model process ignores asynchronous OS stops, checks the pipe between synchronous operations, stops submission, closes/joins the translation owner and closes the ASR recording before its model. Loading is allowed to return its owned handle before release; stop latency includes the current native operation. No SDK call occurs in an async signal handler. A stopped file emits `file_stopped` and the command returns130 for INT or143 for TERM. It does not claim a complete transcript when cancelled.

Use the foreground command or a dedicated process group so its supervisor can own cleanup; do not bypass it with an imported internal `main` function. Parent pipe EOF also requests ordinary model cleanup. SIGKILL cannot execute Python cleanup and is not an accepted graceful-stop path.

## Existing native clients

This composite defines no third SDK or C ABI. Use the independent [Audio8 C ABI/C++ guide](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/main/sdk/NATIVE_INTEGRATION.md) and [HY-MT2 C ABI guide](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/main/sdk/c-api.md), with their already delivered file clients and build commands. [API and ownership index](../docs/INTEGRATION.md).

Input recordings are supplied by you under their own rights. The approved60-second screen recording remains in `docs/` with its [credits](../docs/MEDIA_ATTRIBUTION.md); it does not redistribute the original input lecture here.
