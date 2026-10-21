# sdk

Prebuilt `liblive_transcribe_01.so` (`lib/`) and its public interface
[include/live_transcribe_01.h](include/live_transcribe_01.h).

The library is built for aarch64 Linux (AidLux); it needs the AidLite runtime with the QNN 2.48 backend (see the main
README's setup).

For signature verification, refer to the separately signed component SDK release for authenticity evidence. The signed SDK manifest records its
version, compatible model revision and release/candidate channel.

| | |
|---|---|
| Version | 0.5.1 (`LT01_VERSION`) |
| Compatible model package | HF v0.5.0 (`7c7f9bf118e19f596c611202bd065c1af0997cb9`) |
| Built with | Ubuntu 22.04 aarch64, g++ 11.4, aidlite-sdk 2.5.0, aidlite-qnn248 2.5.0, QNN / QAIRT 2.48 |
| sha256 | `78d324892c344177ff581575f78a8f17d88d6a7edfb4afc1d5822ae1e2aabc99` |

## C API

```c
lt01_options o; lt01_default_options(&o); o.clock_ms = 160; o.lang = LT01_LANG_ZH;   // also roll_s, semantic_vad, replay_max_s
lt01_engine *e = lt01_create("models", &o);       // NULL on failure: lt01_create_error()
lt01_reset(e);                                   // new session
lt01_feed(e, pcm, n);                            // returns the number of new tokens
lt01_read_tokens(e, toks, cap);                  // id / is_text / audio_t / eot[4]
lt01_token_bytes(e, id, buf, cap);               // UTF-8 bytes (decode incrementally)
lt01_soft_reset(e, replay_from_s);               // mechanism: LM back to the prefix + replay of cached audio rows
lt01_finish(e, -1);                              // end of input: default silent tail (5 clocks at 160 ms, 7 at 80 ms)
lt01_eot_probs / lt01_get_info / lt01_get_stats / lt01_last_error / lt01_destroy
```

Return codes: `>= 0` success or a count, `< 0` an `LT01_ERR_*` code with the message in `lt01_last_error`.

## Python binding

`python/live_transcribe_01.py` (ctypes, used by the business layer):

```python
from live_transcribe_01 import Engine
eng = Engine(clock_ms=160, lang="zh")
eng.reset()
toks = eng.feed(pcm_f32)               # [Token(id, is_text, audio_t, eot), ...]
text = eng.text_of([t.id for t in toks])
toks += eng.finish()
eng.soft_reset(replay_from_s); eng.stats(); eng.info; eng.close()
```

Library lookup order: `$LIVE_TRANSCRIBE_01_LIB`, `sdk/lib/`, `sdk/build/`, then the system loader path.

## Design notes

- **Passive engine.** No threads, timers or IO in the .so. `lt01_feed` synchronously runs every clock the audio
  completes; how much to feed and when is the caller's choice.
- **Chunk invariance.** The same audio gives the same tokens however it is chunked.
- **Outputs through a queue.** `lt01_feed` / `lt01_finish` / `lt01_soft_reset` return how many tokens were added; the caller
  drains them with `lt01_read_tokens`, so it never has to guess buffer sizes.
- **Text as bytes.** `lt01_token_bytes` returns UTF-8 bytes; a token can be part of a character, so decode incrementally.
- **No file names in the library.** The model directory's `manifest.json` lists the files of each audio clock; the
  library loads exactly these and fails with a message naming the missing or mismatching file (format, clock, key,
  path; shapes and tensor interfaces are checked against the model).
- **Audio clock and language at create time.** The clock (160 or 80 ms) selects the model
  package, the language only selects the LM prefix KV (language token). To switch, destroy and create again. A clock
  whose package is not installed fails with a clear message.
- **Soft reset: mechanism in the .so, policy in the caller.** The .so resets the LM to its prefix and replays the
  cached audio rows; when to do it (Silero onset, time without output, backoff) is decided by the business layer
  (`demo/reset_policy.py`). Valid once the first token is out.
- **Semantic VAD.** Every token carries P(no speech within 0.5 / 1 / 2 / 3 s) (`lt01_token.eot`); the full [4][8]
  distribution is available through `lt01_eot_probs`.
- **One engine = one thread at a time.**

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `LT01_KEEP_STDOUT` | unset | `lt01_create` / `lt01_destroy` send the process's stdout to stderr while the runtime loads and releases the graphs (its license and fastrpc notices); set it (e.g. `1`) to keep them on stdout |
| `LT01_AIDLITE_LOG` | `warning` | aidlite's log level; `info` shows everything |

## Python package discovery

The current main-branch Python binding exposes `resolve_model_dir()` and allows `Engine()` without a path.
It discovers this checkout's `models/manifest.json` first, otherwise a unique immediate child package. Multiple
packages require an explicit root, for example `Engine("models/qnn248_qcs8550", lang="en")`. An explicit invalid or
empty path raises the MODEL error before native loading; it never selects a different package. `engine.model_dir`
reports the resolved root. Explicit relative paths use the caller's working directory. Standalone integrations
should pass their package root explicitly. Native C callers continue to supply the exact root to the C API.

Discovery is packaging/interface glue: it neither checks all payload hashes nor proves chip compatibility.
The Web application's preflight validates its required files; native model loading remains authoritative.
These main-branch Python and deployment improvements do not change the prebuilt native .so v0.5.1 or HF v0.5.0;
older release tags retain their original binding code.


## Licensing / 许可

The APLUX proprietary portions of the prebuilt `.so` libraries are covered by the
Pandora Model and SDK License, not by the Apache-2.0 license of the business layer.
The C headers and Python bindings authored by APLUX remain Apache-2.0. Third-party
portions keep their own terms. See [licensing scope](../LICENSING.md),
[中文协议](../LICENSES/Pandora-Model-SDK.zh-CN.txt),
[English agreement](../LICENSES/Pandora-Model-SDK.en.txt) and the notices in `lib/`.

预编译 `.so` 中阿加犀专有部分采用 Pandora 自有许可，业务层 Apache-2.0 不覆盖这些专有部分；
阿加犀的 C 头文件、Python 绑定仍为 Apache-2.0，第三方部分保留各自许可。
