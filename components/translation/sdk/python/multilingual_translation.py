"""Synchronous ctypes binding. Thread scheduling belongs to the application."""
import codecs
import ctypes as C
import json
import os
from pathlib import Path


class TranslationError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def resolve_model_dir(model_dir=None, *, default_container=None):
    """Resolve one manifest package; explicit paths never fall back elsewhere.

    Explicit relative paths are relative to the caller's working directory.
    Defaults are anchored to this checkout, including when called elsewhere.
    Discovery checks package structure, not cryptographic authenticity or SoC
    compatibility. Verify the downloaded checksum list before loading a model.
    """
    if model_dir is None and "MT01_MODELS" in os.environ:
        model_dir = os.environ["MT01_MODELS"]
    if model_dir is not None:
        if not os.fspath(model_dir).strip():
            raise TranslationError(-2, "Explicit model path is empty; specify the directory containing manifest.json")
        root = Path(model_dir).expanduser().resolve()
        if not (root / "manifest.json").is_file():
            raise TranslationError(-2, f"Model manifest not found: {root / 'manifest.json'}; explicit paths must name a package root")
    else:
        container = (Path(default_container) if default_container is not None else
                     Path(__file__).resolve().parents[2] / "models").resolve()
        if (container / "manifest.json").is_file():
            root = container
        else:
            candidates = sorted(p for p in container.iterdir()
                                if p.is_dir() and (p / "manifest.json").is_file()) if container.is_dir() else []
            if len(candidates) != 1:
                detail = "Multiple model packages: " + ", ".join(str(p) for p in candidates) if candidates else (
                    f"No model package in {container}/manifest.json or {container}/*/manifest.json")
                raise TranslationError(-2, detail + "; download your board's folder into models/, or select --models models/qcs8550 (SDK: model_dir=...)")
            root = candidates[0].resolve()
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        names = manifest["files"]
        config = manifest["config"]
        if manifest["schema_version"] != 1 or not isinstance(names, list) or not names or config not in names:
            raise ValueError("unsupported or incomplete manifest")
        for name in names:
            if not isinstance(name, str) or not name or "\\" in name or Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("unsafe manifest path")
            path = root / name
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"missing or empty package file: {path}")
        json.loads((root / config).read_text())
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise TranslationError(-2, f"Invalid model package {root}: {exc}") from exc
    return root


class Options(C.Structure):
    _fields_ = [("struct_size", C.c_uint32), ("max_input_tokens", C.c_uint32)]


class Stats(C.Structure):
    _fields_ = [("struct_size", C.c_uint32), ("state", C.c_uint32),
                ("prompt_tokens", C.c_uint64), ("generated_tokens", C.c_uint64),
                ("init_ms", C.c_double), ("first_token_ms", C.c_double),
                ("generation_ms", C.c_double), ("tokens_per_second", C.c_double)]


NOTIFY = C.CFUNCTYPE(None, C.c_void_p)


class Translator:
    """One instance per process; close only after generation and readers finish.

    translate is blocking. abort is allowed from a separate application thread,
    never from on_chunk. on_chunk receives complete UTF-8 strings. When stopped,
    translate returns the partial result with cancelled=True.
    """
    def __init__(self, model_dir=None, library=None, max_input_tokens=512):
        self.model_dir = resolve_model_dir(model_dir)
        sdk = Path(__file__).resolve().parents[1]
        candidates = [Path(library)] if library else [
            sdk / "lib/libmultilingual_translation_01.so",
            sdk / "build/libmultilingual_translation_01.so"]
        selected = next((p for p in candidates if p.is_file()), None)
        if selected is None:
            raise FileNotFoundError("Translation SDK library not found; build sdk/ first")
        self.lib = C.CDLL(str(selected))
        signatures = {
            "mt01_create": ([C.c_char_p, C.POINTER(Options)], C.c_void_p),
            "mt01_destroy": ([C.c_void_p], None),
            "mt01_create_error": ([], C.c_char_p),
            "mt01_create_error_code": ([], C.c_int),
            "mt01_last_error": ([C.c_void_p], C.c_char_p),
            "mt01_count_prompt_tokens": ([C.c_void_p, C.c_char_p, C.c_char_p, C.c_char_p], C.c_int),
            "mt01_start": ([C.c_void_p, C.c_char_p, C.c_char_p, C.c_char_p], C.c_int),
            "mt01_generate": ([C.c_void_p, NOTIFY, C.c_void_p], C.c_int),
            "mt01_read_text": ([C.c_void_p, C.c_void_p, C.c_size_t], C.c_int),
            "mt01_abort": ([C.c_void_p], C.c_int),
            "mt01_get_stats": ([C.c_void_p, C.POINTER(Stats)], C.c_int),
            "mt01_get_info": ([C.c_void_p, C.c_void_p, C.c_size_t], C.c_int),
        }
        for name, (args, result) in signatures.items():
            f = getattr(self.lib, name)
            f.argtypes, f.restype = args, result
        options = Options(C.sizeof(Options), max_input_tokens)
        self.handle = self.lib.mt01_create(str(self.model_dir).encode(), C.byref(options))
        if not self.handle:
            raise TranslationError(self.lib.mt01_create_error_code(), self.lib.mt01_create_error().decode("utf-8", "replace"))
        self._translating = False

    def _check(self, result):
        if result < 0:
            raise TranslationError(result, self.lib.mt01_last_error(self.handle).decode("utf-8", "replace"))
        return result

    @property
    def info(self):
        size = self._check(self.lib.mt01_get_info(self.handle, None, 0))
        buf = C.create_string_buffer(size)
        self._check(self.lib.mt01_get_info(self.handle, buf, size))
        return json.loads(buf.value)

    @property
    def stats(self):
        stats = Stats()
        stats.struct_size = C.sizeof(Stats)
        self._check(self.lib.mt01_get_stats(self.handle, C.byref(stats)))
        return {name: getattr(stats, name) for name, _ in Stats._fields_ if name != "struct_size"}

    def count_prompt_tokens(self, text, source, target):
        """Count the SDK's full prompt without preparing or running inference."""
        if not self.handle or self._translating:
            raise TranslationError(-4, "Translator must be open and idle")
        if not all(isinstance(s, str) and "\x00" not in s for s in (text, source, target)):
            raise TranslationError(-1, "Text and language codes must be strings without NUL")
        return self._check(self.lib.mt01_count_prompt_tokens(self.handle, text.encode(), source.encode(), target.encode()))

    def translate(self, text, source, target, on_chunk=None):
        if not self.handle:
            raise TranslationError(-4, "Translator is closed")
        if self._translating:
            raise TranslationError(-4, "Translation already active")
        if not all(isinstance(s, str) and "\x00" not in s for s in (text, source, target)):
            raise TranslationError(-1, "Text and language codes must be strings without NUL")
        self._translating = True
        try:
            self._check(self.lib.mt01_start(self.handle, text.encode(), source.encode(), target.encode()))
            decoder = codecs.getincrementaldecoder("utf-8")("strict")
            chunks, errors = [], []
            buf = C.create_string_buffer(257)

            def drain(_):
                try:
                    while True:
                        n = self._check(self.lib.mt01_read_text(self.handle, buf, len(buf)))
                        if not n:
                            break
                        chunk = decoder.decode(buf.raw[:n])
                        if chunk:
                            chunks.append(chunk)
                            if on_chunk and not errors:
                                on_chunk(chunk)
                except Exception as exc:
                    errors.append(exc)

            callback = NOTIFY(drain)
            result = self.lib.mt01_generate(self.handle, callback, None)
            drain(None)
            tail = decoder.decode(b"", final=result != -6)
            if tail:
                chunks.append(tail)
                if on_chunk:
                    on_chunk(tail)
            if errors:
                raise errors[0]
            if result != -6:
                self._check(result)
            return {"text": "".join(chunks), "cancelled": result == -6, "stats": self.stats}
        finally:
            self._translating = False

    def abort(self):
        if self.handle:
            self._check(self.lib.mt01_abort(self.handle))

    def close(self):
        if self._translating:
            raise TranslationError(-4, "Wait for translate to finish before close")
        if self.handle:
            self.lib.mt01_destroy(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
