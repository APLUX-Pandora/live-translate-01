# Examples

## Overview

| Example | What it shows |
| --- | --- |
| [python/translate_audio.py](python/translate_audio.py) | Stream transcription of a local audio file and translate confirmed phrases. |

## Before you run

Complete [Install](../README.md#1-install) and [Get the model](../README.md#2-get-the-model). Run every command from the Demo root in the activated environment. Stop the Web Demo first; examples and the Web Demo share the NPU.

## Python examples

### translate_audio.py

Transcribe the English sample from the Audio8 component and translate it into Chinese.

```bash
python examples/python/translate_audio.py
```

Output (excerpt):

```text
{"type": "source", "piece": "Welcome"}
…
{"type": "translation", "kind": "done", …, "text": "欢迎来到这个语音识别演示。", …}
```

The example prints source and translation events as JSON lines. The final event contains the transcript, the translations and the transcription's finish reason.

| Option | Default | Purpose |
| --- | --- | --- |
| `audio` | `components/asr/examples/audio/speech.wav` | Path to the input audio file. |
| `--source` | `en` | Source language, `en` or `zh`. |
| `--target` | `zh` for English input, `en` for Chinese input | Target language. It must differ from the source. |
| `--models` | `models/asr` | Speech recognition model directory. |
| `--translation-models` | `models/translation` | Translation model directory. |
| `--seconds` | Full input | Read only the first specified number of seconds. |
| `--realtime` | Off | Feed audio at its original pace. |

See the [Python API](../sdk/PYTHON_API.md) for the interfaces used by the example.
