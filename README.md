# Live Translate · APLUX Pandora

Real-time transcription with Audio8-ASR-Infinite-160ms and streaming translation with HY-MT2-1.8B. This is a composite application, with no duplicate model SDK or model weights.

Application 0.1.1 independently reuses Audio8 SDK 0.6.1 and HY-MT2 SDK 0.2.1. HY-MT2 preserves the model-package sampler and explicit lifecycle cleanup.

## Install and reuse components

Install [Audio8 ASR](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo) and [HY-MT2](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo) independently. Keep their SDK files, model packages, checksums and licenses in those installations. These private repositories require authorized access. Audio8 SDK 0.6.1 is the formally released static-ICU portability fix (install the independent Audio8 project at tag v0.6.1); install or reuse the independent HY-MT2 project at tag v0.2.1. Both component SDKs are formally published. Supply your existing HY-MT2 installation through HY_MT2_SDK_ROOT. No SDK or weights should be copied into this application.

Use a separate project environment with Python 3.10 (tested). AidLite/QNN 2.48, AidGen and the board drivers are independent system prerequisites; video handling uses ffmpeg and ffprobe. Other Python minor versions are not execution-qualified by this check.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
export AUDIO8_SDK_ROOT=/path/to/audio8-asr-infinite-demo
export HY_MT2_SDK_ROOT=/path/to/hy-mt2-1.8b-demo
bash demo/run.sh --port 8766   --models /path/to/existing/audio8-package   --translation-models /path/to/existing/hy-mt2-package
```

Each explicit model path must directly contain manifest.json. The Web and example share the component SDKs' resolver; defaults search models/asr and models/translation relative to this application and require a flat package or one unique immediate child. Default SDK roots are independently installed sibling checkouts with the names above. The default HY-MT2 library comes from its independently installed SDK. --translation-library is available for an explicit compatible library override; model files are unchanged.

Provide authorized media under demo/media, optionally as links to an existing independent media directory. Preserve each video's language sidecar JSON. Open http://<board-address>:8766/, select its spoken language and a different target language, then Start. Browser playback feeds 16 kHz mono PCM; HTTP fallback remains available. Stop drains accepted audio and translation. Use demo/run.sh as the service command and send SIGTERM/SIGINT to its supervisor PID or process group. The supervisor notifies the model process over a pipe so vendor initialization is not interrupted. The model process stops admission, cancels obsolete translation, joins callers, explicitly closes both engines and closes HTTP owners. demo_server.py is the internal worker, not the qualified service entry point.

## One-minute demonstration

[![English-to-Chinese live demonstration](docs/poster.png)](docs/demo.mp4)

[Watch the one-minute recording](docs/demo.mp4) · [Original quality](docs/demo-original.mp4)

Recorded with application 0.1.1, Audio8 0.6.1 and HY-MT2 0.2.1: the built-in English video produces live transcription and Chinese translation on the board. Source: Lorna Mitchell, FOSDEM2025, *Beyond the README*, CC BY2.0 Belgium. See [attribution](docs/MEDIA_ATTRIBUTION.md).

## Streaming behavior

English phrases prefer complete sentences and preserve comparisons/subordinate clauses, with a bounded 24-second/512-character fallback. Chinese retains its 12-second/96-character policy. A conservative noun/file-context rule converts ASR `read me` to `README` only in the translation input; the original transcript is unchanged. Ordinary requests such as `Can you read me a story?` are preserved. False question punctuation after an unfinished transitive construction is held for its object, without deleting source text.

Runtime sampling follows the encrypted model package and is reported by the HY-MT2 SDK. The application does not implement decoding or post-edit translated output.

SSE readers have bounded queues and are disconnected when slow; reconnection uses a bounded replay snapshot. Completed translation replay history is expired above 256 records when possible; pending work is retained. The live client owns its displayed/exported full transcript. Timing windows retain 200 steps and 240 system samples.

See [standalone example](examples/README.md), [integration contract](docs/INTEGRATION.md), and [resource reuse](resources/README.md). Component SDK licenses and their separate release status remain applicable. No new HF repository or production website deployment is part of this release.
