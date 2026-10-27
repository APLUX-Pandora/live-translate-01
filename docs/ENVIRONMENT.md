# Environment and fixed components

Use CPython3.10,3.11 or3.12 with a separate clean project venv for the selected interpreter. The updated composite was verified on QCS8550/Ubuntu22.04 with CPython3.10.12,3.11.18 and3.12.16 in separate clean project venvs. File examples, real streaming/Web requests and idle/active TERM/INT shutdown passed on each version. Earlier application qualification remains scoped to its old component pairing.

The target is supported AidLux Linux AArch64 with the components' AidLite/AidGen/QNN prerequisites. Existing QCS8550 qualification used Ubuntu22.04 and QNN2.48. Do not replace shared board runtimes. ffmpeg/ffprobe and libsndfile are system prerequisites; venv does not isolate NPU, drivers or native runtime libraries.

Audio8 SDK0.7.0 and HY-MT2 SDK0.3.0 are referenced by Git submodules under `components/asr` and `components/translation`. Exact commits, formal tags and runtime hashes are recorded in `demo/component-versions.json`. The pinned commits include post-release Python-version documentation; all recorded runtime files match the corresponding formal release tag byte-for-byte.

Clone with `--recurse-submodules`. For an existing checkout run `git submodule update --init --recursive`; do not use `--remote` during installation. No separate component venv or SDK-root environment variable is required. Unset obsolete `AUDIO8_SDK_ROOT`/`HY_MT2_SDK_ROOT` overrides; intentional overrides must match the fixed commit and runtime bytes. `AUDIO8_ASR_LIB` and the diagnostic `--translation-library` cannot substitute an unmatched binary.

README, example and Web launcher use this project's selected `.venv/bin/python`, with no system-Python fallback. requirements.txt is the single install entry for the actual composite dependencies; component Web-server dependencies are not required by this application.

Python-version support and Ubuntu/BSP/NPU qualification are separate. No new Ubuntu24/26 or other-chip qualification is claimed. Model packages remain separate; reuse matching prepared resources following each component's model guide.
