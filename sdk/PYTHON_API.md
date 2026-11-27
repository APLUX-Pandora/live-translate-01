# Python API

Live Translate uses the Python interfaces of `pandora_audio8_asr_infinite` and `pandora_hy_mt2_1_8b`.

## Quick start

Complete [installation](README.md#install) and [model setup](../docs/MODEL_SETUP.md), then run from the Live Translate root:

```bash
python examples/python/translate_audio.py
```

## API overview

| Name | Signature | Returns | Purpose |
| --- | --- | --- | --- |
| `ASRModel.from_pretrained` | `(model_dir, *, clock_ms=None, roll_s=28.8, stable_rows=-1, semantic_vad=True, replay_max_s=10.0, runtime=None)` | `ASRModel` | Load the speech recognition model. |
| `ASRModel.create_stream` | `(*, sample_rate, channels=1, channel=None, language, prompt=None, hotwords=None, max_new_tokens=None)` | `ASRStream` | Open a recording stream for PCM samples. |
| `ASRStream.feed` | `(pcm)` | `TranscriptionUpdate` | Send more audio and read the latest text. |
| `ASRStream.finish` | `(*, right_pad_text_tokens=0)` | `TranscriptionResult` | Flush the last text when input ends. |
| `LanguageModel.from_pretrained` | `(model_dir, *, runtime=None)` | `LanguageModel` | Load the translation model. |
| `LanguageModel.generate_stream` | `(messages, *, max_new_tokens=None, do_sample=None, temperature=None, top_p=None, top_k=None, repetition_penalty=None, return_audio=False)` | `GenerationStream` | Stream translated text for a confirmed phrase. |
| `close` | `()` | `None` | Release a stream or model. Its context manager calls this on exit. |

See the [component documentation](README.md#documentation) for the complete public signatures and types.

## Parameters

| Input | Value in Live Translate |
| --- | --- |
| Speech recognition `model_dir`, `clock_ms` | `models/asr`, with `clock_ms=160` for the Audio8 160 ms model. |
| Recording stream `sample_rate`, `language` | The input PCM rate in Hz and the selected source language (`en` or `zh`). The example sends mono PCM. |
| Translation `model_dir` | `models/translation`. |
| Translation `messages` | A list with a user message containing the confirmed source text and an instruction for the target language. |
| Model loading `runtime` | Omitted by the example and Web Demo. Each model owns its default Runtime. |

## Results and cleanup

| Result | Fields used |
| --- | --- |
| `TranscriptionUpdate` | `text` is the accumulated recognition text. `is_final` marks a final update. |
| `TranscriptionResult` | `text` contains the final transcript and `finish_reason` gives the reason for ending. |
| `GenerationUpdate` | `delta` contains the newly generated text. |
| `GenerationResult` (`stream.result`) | `text` is the accumulated translation and `finish_reason` gives the reason for ending. |

### Errors

A missing or incomplete model package surfaces during model loading. Start with [model setup](../docs/MODEL_SETUP.md#troubleshooting) for file and activation errors. The file example exits with an error if any phrase fails to finish translating.

### Lifecycle

Load each NPU model in its own process. Finish the recording stream and drain pending translations before closing the models for a completed run. Use a context manager for each model and stream so an early exit closes the stream before its model. A final source update can contain the last phrase, so pass it to translation before draining the queue.

## Advanced

Use [Runtime](RUNTIME_API.md) when configuring hardware in your own integration. See [examples](../examples/README.md) for the audio-file options.
