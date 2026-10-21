# Bilingual output

The Web demo uses one text area. Each source sentence is immediately followed by its streamed translation. ASR paragraph breaks remain unchanged; internal translation clauses are combined within the corresponding sentence.

Choose the source and target languages before starting. Starting or seeking enables translation for the new session. Source ASR text continues to arrive while translation runs. Stop finishes accepted audio and pending translation. There are no output tabs or saved layout preferences.

Use Copy original, Export original or Copy translation to retrieve text. Arabic translations use automatic right-to-left direction independently of the English source.

For an explicitly selected native SDK validation build, start the server with `bash demo/run.sh --translation-library /absolute/path/to/libmultilingual_translation_01.so`. This is an opt-in diagnostic override; it does not replace or re-sign the bundled released SDK. The `/api/videos` response exposes `translation_sdk`, including any effective sampling properties reported by that library.
