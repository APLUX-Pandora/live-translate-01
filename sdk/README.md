# Live Translate 01 SDK

Live Translate uses Audio8-ASR-Infinite to turn speech into text and Hy-MT2-1.8B to translate the confirmed phrases.

## What's included

The following paths are relative to the Audio8 component's `sdk/` directory.

| Path | Content |
| --- | --- |
| `python/pandora_audio8_asr_infinite/` | Python package (`from pandora_audio8_asr_infinite import ASRModel`) |
| `include/` | C header |
| `lib/` | Prebuilt native library with its QNN runtime |
| `SHA256SUMS` | Checksums of the shipped files |

The Hy-MT2 component has the same layout and provides `from pandora_hy_mt2_1_8b import LanguageModel`. The Audio8 component also supplies the shared Runtime wheel used below.

## Install

Follow the [clone and device preparation steps](../README.md#1-install) and activate your application's Python 3.10–3.12 environment. From the Live Translate root, install the shared Runtime wheel once:

```bash
python -m pip install components/asr/sdk/wheels/pandora_runtime-*.whl
```

Run the install command below once in each component's Demo root, `components/asr` and `components/translation`, using the same environment.

In your application's activated Python 3.10–3.12 environment, from the Demo root:

```bash
python -m pip install ./sdk
```

The device must pass `sudo lms check`. The SDK does not install LMS or drivers and does not download models; see [Get the model](../README.md#2-get-the-model).

## Usage

To use the download commands in an SDK-only environment, install the Hugging Face CLI with `python -m pip install 'huggingface_hub>=1.0,<2'`.

After downloading the models, return to the Live Translate root and run the example:

```bash
python examples/python/translate_audio.py
```

## Documentation

- [Python API](PYTHON_API.md)
- [Runtime](RUNTIME_API.md)
- [Examples](../examples/README.md)
- [Licensing](../LICENSING.md)

| Component | Python API | Runtime | C ABI | Model card |
| --- | --- | --- | --- | --- |
| Audio8-ASR-Infinite | [Python API](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/v1.1.0/sdk/PYTHON_API.md) | [Runtime](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/v1.1.0/sdk/RUNTIME_API.md) | [C ABI](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/v1.1.0/docs/C_ABI.md) | [Audio8-ASR-Infinite-160ms](https://huggingface.co/APLUX-Pandora/Audio8-ASR-Infinite-160ms) |
| Hy-MT2-1.8B | [Python API](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/v1.1.0/sdk/PYTHON_API.md) | [Runtime](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/v1.1.0/sdk/RUNTIME_API.md) | [C ABI](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/v1.1.0/docs/C_ABI.md) | [Hy-MT2-1.8B](https://huggingface.co/APLUX-Pandora/Hy-MT2-1.8B) |
