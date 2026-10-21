# Integration contract

The application uses two separately versioned component SDKs. Model loading,
feature/token processing, model execution and model state remain in the native
libraries. Python owns input selection, language records, phrase/paragraph
policies, queues, sessions and transport.

| Operation | Public interface |
| --- | --- |
| Create ASR | `Engine(model_dir, clock_ms=160, lang=...)` |
| Stream and finish audio | `reset`, `feed`, `finish`, `token_bytes` |
| Inspect/recover ASR | `info`, `stats`, `soft_reset` |
| Create translation | `Translator(model_dir)` |
| Check request budget | `count_prompt_tokens(text, source, target)` |
| Stream translation | `translate(text, source, target, on_chunk=...)` |
| Cancel obsolete work | `abort` from another thread |
| Release resources | `close` after draining or cancelling work |

Web and standalone Python flows use the same interfaces and native libraries.
Package discovery is shared through `demo/model_paths.py` and delegates validation
to the supplied public SDKs. Explicit invalid paths fail, flat layouts are accepted,
and ambiguous defaults require an explicit package root.

The application version does not change either component SDK version. Supported
language choices are documented in the main README. Model resource paths and
checksums are fixed in `resources/model-lock.json`.
