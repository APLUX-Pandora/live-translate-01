# Composite integration contract

This application reuses two separately versioned native SDKs. It does not define a
new model ABI or move model code into Python. Exact package and repository pins
are in the component repositories and the historical payload identities in `resources/model-lock.json`.

| Capability | Public SDK call | Application responsibility |
| --- | --- | --- |
| ASR creation and metadata | `Engine(..., clock_ms=160, lang=...)`, `info` | Select source language and matching package |
| Audio and text stream | `reset`, `feed`, `token_bytes`, `finish` | Capture/resample audio, decode UTF-8, preserve order |
| ASR recovery | `soft_reset`, `stats` | Silence gate and reset policy |
| Translation budget | `count_prompt_tokens` | Keep business phrases within the accepted request budget |
| Translation stream | `Translator.translate(..., on_chunk=...)` | Queue phrases, choose languages, stream results |
| Cancellation | `Translator.abort` | Abort from another thread and reject obsolete session events |
| Shutdown | `Engine.close`, `Translator.close` | Drain accepted work or cancel obsolete work before closing |

The Web service imports the independently installed audio8_asr and hy_mt2 SDKs; it does not call ctypes itself. The
standalone example calls the same ASR SDK and shares the translation worker that
calls the same translation SDK. HTTP, upload/playback, language records, paragraph
alignment, multiprocessing and inference scheduling are application logic.

Native binaries retain their component library names and licenses. A composite
application version does not silently retag or rebuild either component SDK.
Model weights stay in their existing repositories, and each component's package
root directly contains its manifest. Web and example share `demo/model_paths.py`,
which delegates discovery and strict path validation to the existing public SDKs.

Validation covers source/target selection, streaming conservation, stop/drain,
session replacement, default/explicit/ambiguous/missing paths and a standalone
file flow. It does not establish acoustic language identification, translation
quality scores for every language, hardware priority, or multi-chip qualification.

## Independently versioned components

Audio8 SDK 0.6.1 is reused unchanged. HY-MT2 SDK 0.2.1 removes the sampler override while preserving its 0.2.0 lifecycle fixes. Both SDKs are built and released independently; this application carries neither SDK payload. Both the Web worker and file example load the same independent bindings. No ctypes calls or model implementation are added to the application.

Engine creation is protected from asynchronous stop interruption by blocking stop signals before native pools start. The control thread receives signals; normal code coordinates cancellation, joins ASR/translation owners and explicitly destroys handles, including initialization and HTTP-bind failures. Translation uses a distinct process to respect the vendor context boundary.

## Supervisor boundary

ASR-loading SIGTERM reproduced a QNN open-session failure and a process that failed to exit within 180 seconds. That failed owned test process required SIGKILL after its evidence was saved; it is not counted as a passing graceful exit. The installed component SDK bytes were not changed to hide the failure.

The qualified run.sh entry now starts a lightweight native-free supervisor. It owns OS stop signals and writes a stop byte to the model process. The model process ignores OS SIGTERM/SIGINT and receives stop/parent-EOF through that pipe, allowing native initialization to finish and acquire its handle before cancellation/destruction. Both term/int ASR-loading preflights subsequently passed with 30-second DMA return. The released Web boundary completed the recorded600-second/81-job workload and nine shutdown cases with DMA return. Those historical results apply to the matched runtime; they do not substitute for verification of a changed file application. Do not bypass the supervisor in a service configuration.

## Canonical component references

| Component | Complete Python API | C ABI, build and existing C++ client |
|---|---|---|
| Audio8 | [Python API](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/main/sdk/PYTHON_API.md) | [Native guide](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/main/sdk/NATIVE_INTEGRATION.md), [file client/CMake](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/tree/main/examples/cpp) |
| HY-MT2 | [Python API](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/main/sdk/python-api.md) | [C ABI guide](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/main/sdk/c-api.md), [file client](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/main/examples/cpp/translate.cpp) |

These independent references define complete parameter/field units, errors, state and threading contracts. This application adds scheduling and JSON events, not another SDK. Retain those SDK installations, native headers/libraries, model licenses and build instructions together. Runtime identities are checked from `demo/component-versions.json`; see [environment](ENVIRONMENT.md).

## Finite-file ownership

The file command also uses the native-free supervisor/pipe. Its ordinary owner checks stop requests between calls, stops admission and waits for translation cancellation/callers before explicitly closing both engines. The pipe receiver never calls native methods. It is separate from Web HTTP/session ownership and returns130/143 when the command is stopped. See [file example](../examples/README.md). Complete finite-file results are stored separately from bounded Web replay; no new model logic is introduced.
