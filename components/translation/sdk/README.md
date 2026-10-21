# Translation SDK

The prebuilt Linux AArch64 library is `lib/libmultilingual_translation_01.so`. It links to the separately installed AidGen runtime. Public C interface: `include/multilingual_translation_01.h`; Python binding: `python/multilingual_translation.py`.

Calls are synchronous. The application supplies threads and transport. One engine instance is allowed per process. Create, start, generate, drain text and inspect statistics; repeat for another translation, then destroy. The generator callback notifies that UTF-8 bytes are queued; the Python binding decodes incrementally.

Only abort, output reads and statistics reads may run concurrently with generation. Abort must be called from another application thread, never from the generation callback. Wait for generation and readers before closing. Starting a request resets conversation history. Supported language codes: `zh en ja ko fr de es ar th`; source and target must differ.

The default prompt budget is 512 tokens for API compatibility. Pass `max_input_tokens=2048` to the Python constructor for larger single requests. The maximum supported prompt budget is 2048 tokens, including the SDK's instructions and control markers. `count_prompt_tokens` returns the exact full-prompt count while idle, without starting inference. Phrase segmentation and task scheduling are application policies outside this SDK.

`TranslationError.code` maps argument (-1), model (-2), runtime (-3), state (-4), internal (-5) and cancellation (-6) conditions. Generation cancellation returns partial text with `cancelled=True`. Read the header for the state machine and complete C ABI.

The library has no embedded runtime search path. Install the vendor runtime through AidLux; applications can use `LD_LIBRARY_PATH`, their own rpath or a system library installation to locate this SDK. See [the C header](include/multilingual_translation_01.h) for the ABI.

## Component and model pairing

This composite uses the unchanged native SDK 0.1.0 with the recorded compatible
model package. The application-level resource lock selects the complete package;
run `tools/download_models.py --verify-only` from the repository root before use.
The composite does not claim that a signature from the original translation
application covers this new Web application or its directory layout.

Original component signatures, compatibility evidence and detailed dependency
reviews remain with the internal release records. This repository includes the
runtime library, public interface, Python binding and required license files.
