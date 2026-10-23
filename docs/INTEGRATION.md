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

The qualified run.sh entry now starts a lightweight native-free supervisor. It owns OS stop signals and writes a stop byte to the model process. The model process ignores OS SIGTERM/SIGINT and receives stop/parent-EOF through that pipe, allowing native initialization to finish and acquire its handle before cancellation/destruction. Both term/int ASR-loading preflights subsequently passed with 30-second DMA return. A final complete workload and exit matrix is running for this boundary. Do not bypass the supervisor in a service configuration.
