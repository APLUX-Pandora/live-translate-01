# Live Translate · APLUX Pandora

Live transcription with Audio8-ASR-Infinite-160ms and streaming translation with Hy-MT2-1.8B. This application reuses the two fixed component submodules and model packages.

https://github.com/user-attachments/assets/e6dbe78c-361a-4c53-a936-f45483d19137

[One-minute English-to-Chinese recording](docs/demo.mp4) · [Media credits](docs/MEDIA_ATTRIBUTION.md).

## 1. Install

Use Python 3.10, 3.11 or 3.12 on a supported AidLux Linux AArch64 image with AidLite, AidGen and QNN 2.48 installed. The pinned components are [Audio8 SDK 0.7.0](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo) and [HY-MT2 SDK 0.3.0](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo).

```bash
git clone --recurse-submodules https://github.com/APLUX-Pandora/live-translate-01.git
cd live-translate-01
sudo apt install python3-venv ffmpeg libsndfile1
python3.10 -m venv .venv  # or python3.11 / python3.12
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

For an existing checkout, run `git submodule update --init --recursive`. Component versions are fixed by this repository; installation never follows their latest main. See [environment and validated scope](docs/ENVIRONMENT.md). Startup verifies component commits and runtime files before importing them.

## 2. Reuse the model packages

Reuse the existing Audio8 **160ms QCS8550** and HY-MT2 **QCS8550** packages directly. For initial provisioning, follow the components' [ASR model guide](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/main/models/README.md) and [translation model/preparation guide](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/main/models/README.md).

Set the paths to their prepared package roots, each containing `manifest.json`:

```bash
export ASR_MODELS=/path/to/existing/audio8-package
export TRANSLATION_MODELS=/path/to/existing/hy-mt2-package
```

Keep one installation of each package. [Resource layout and local preparation](resources/README.md) explain raw downloads and other platforms.

## 3. Run the Web Demo

```bash
bash demo/run.sh --port 8766 \
  --models "$ASR_MODELS" --translation-models "$TRANSLATION_MODELS"
```

Open `http://<board-ip>:8766/`, upload your authorized video, choose its spoken language and a different translation target, then select **Start**. **Stop** drains accepted work. An existing media directory can be reused with `--media-dir /path/to/media`; see [Web controls](docs/WEB.md).

## 4. Run a Python example

```bash
.venv/bin/python examples/python/translate_audio.py /path/to/authorized-audio.wav \
  --source en --target zh --models "$ASR_MODELS" \
  --translation-models "$TRANSLATION_MODELS"
```

See [file input, output and stopping](examples/README.md).

## API reference and license

[Python SDK and C ABI/C++ references](docs/INTEGRATION.md) · [Environment](docs/ENVIRONMENT.md) · [Licensing](LICENSING.md).
