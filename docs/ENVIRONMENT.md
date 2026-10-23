# Application environment and component pairing

Use an independent project `.venv`, created on the board with Python 3.10. The qualified QCS8550 snapshot uses Ubuntu 22.04, AidLite 2.5.0.284, AidGen 2.4.4 and QNN 2.48. `ffmpeg` and `ffprobe` are system media prerequisites, separate from the Python requirements and native SDK dependencies. Install the platform vendor packages through the independent component guides; do not replace a shared board runtime for this application.

The launcher resolves this project's `.venv/bin/python` from its absolute checkout location. No shell activation or global Python fallback is used. The file example runs through that same interpreter. Set `AUDIO8_SDK_ROOT` and `HY_MT2_SDK_ROOT` to the separately installed component repositories, not their venvs.

`demo/component-versions.json` records the qualified component versions, binding/library SHA256 and canonical repositories. Both Web and file entry points verify those files before SDK import. Current native identities:

- Audio8 SDK 0.6.1: `7b1dfc1d1cf1b2959dfd7c013c73eb89665f720f3c927c6b89afe92b022e1e40`.
- HY-MT2 SDK 0.2.1: `695f6846507c51ff20b61430cb17c26b176edf8edf1f79319662f3298128922a`.

Leave `AUDIO8_ASR_LIB` unset, or point it to the selected Audio8 checkout's own library. An unrelated override is rejected. `--translation-library` is a diagnostic override and must have the same qualified native hash; it does not authorize a new SDK candidate. Component documentation/example-only updates are compatible when these runtime bytes still match. A native/binding change requires separate composition qualification and a deliberate contract update.

## Same owned SDK files across Ubuntu versions

| System / architecture | Existing component evidence | Hardware scope |
|---|---|---|
| Ubuntu 22.04 arm64 | Same-file ABI/userspace and QCS8550 inference/lifecycle | Recorded QCS8550 only |
| Ubuntu 24.04 arm64 | Same-file ABI/userspace/loader checks | Separate BSP/NPU untested |
| Ubuntu 26.04 arm64 | Same-file ABI/userspace/loader checks | Separate BSP/NPU untested |

This application adds no native inference SDK. Audio8 embeds ICU 70.1 code/data; HY tokenization uses the independently installed AidGen runtime. See the [Audio8 environment](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/main/sdk/README.md) and [HY environment](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/main/sdk/environment.md). These component checks do not guarantee every external BSP/vendor runtime on every Ubuntu release. No per-system SDK build or obsolete system ICU installation is needed by this application.
