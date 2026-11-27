# Live Translate 01

Live Translate 01 transcribes audio and video and streams the translation
into the same subtitle view. It runs
[Audio8-ASR-Infinite-160ms](https://huggingface.co/APLUX-Pandora/Audio8-ASR-Infinite-160ms)
and [Hy-MT2-1.8B](https://huggingface.co/APLUX-Pandora/Hy-MT2-1.8B) on the device.

**Demo recording**

https://github.com/user-attachments/assets/83f3673e-8860-4455-871f-d772f0678bb6

English speech to Chinese subtitles on QCS8550 (31 seconds). Live transcription and translation of the built-in FOSDEM lecture · [Media credits](docs/MEDIA_ATTRIBUTION.md).

## 1. Install

Clone the Demo and enter its root directory:

```bash
git clone --recurse-submodules https://github.com/APLUX-Pandora/live-translate-01.git
cd live-translate-01
```

### Prepare the device

Use a compatible Linux device with Aidlux LMS and the required drivers, DSP firmware and BSP/FastRPC support. The SDK includes its QNN runtime libraries; no separate QNN installation or path configuration is required.

Check the activation:

```bash
sudo lms check
```

Continue only when it returns true.

Install the system packages the Demo needs:

```bash
sudo apt install python3-venv ffmpeg libsndfile1 git-lfs
```

Fetch the built-in lecture video from the cloned repository:

```bash
git lfs install --local
git lfs pull
```

### Install the Demo and SDK

The submodules provide the v1.1.0 SDK releases of [Audio8-ASR-Infinite](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/releases/tag/v1.1.0) and [Hy-MT2-1.8B](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/releases/tag/v1.1.0).

Use Python 3.10–3.12. Create and activate the Demo environment, then install:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

This installs the SDK, the Web Demo and the Hugging Face CLI. To use only the SDK in your own application, see the [SDK installation](sdk/README.md#install).

## 2. Get the model

Download the shared files and one device target. The commands below use QCS8550; for another device, use the folder in the [targets table](docs/MODEL_SETUP.md#targets).
Download both model packages into separate directories. Use the 160 ms profile for speech recognition.

For a private model, run `hf auth login` first.

```bash
hf download APLUX-Pandora/Audio8-ASR-Infinite-160ms --local-dir models/asr --exclude "targets/*" --exclude "media/*" --exclude README.md --exclude .gitattributes
hf download APLUX-Pandora/Audio8-ASR-Infinite-160ms --local-dir models/asr --include "targets/qcs8550_qnn248/*"
```

Download the translation model for the same target.

```bash
hf download APLUX-Pandora/Hy-MT2-1.8B --local-dir models/translation --exclude "targets/*" --exclude "media/*" --exclude README.md --exclude .gitattributes
hf download APLUX-Pandora/Hy-MT2-1.8B --local-dir models/translation --include "targets/qcs8550_qnn248/*"
```

## 3. Run the Web Demo

```bash
bash demo/run.sh --port 8766
```

Open `http://<device-ip>:8766/` and select **Start** to play the built-in
10-minute lecture with English and Chinese subtitles. Use **Upload file**
to add your own video with sound or an MP3, WAV or M4A (AAC) file. Use the
media list to switch back to the lecture. Stop the server with Ctrl+C.
See the [Web Demo guide](demo/README.md) and [media credits](docs/MEDIA_ATTRIBUTION.md#built-in-lecture).

## 4. Python Usage

In the same environment, from the Demo root:

```bash
python examples/python/translate_audio.py
```

More in the [Python API](sdk/PYTHON_API.md) and [examples](examples/README.md).

## Documentation

- [Model setup](docs/MODEL_SETUP.md) covers device requirements, targets, downloads and folder layout.
- [SDK installation](sdk/README.md) covers installing the two component SDKs on their own and links to their native interfaces.
- [Python API](sdk/PYTHON_API.md) describes the component APIs used by Live Translate.
- [Runtime](sdk/RUNTIME_API.md) covers hardware settings for native inference.
- [Examples](examples/README.md) shows how to translate an audio file.
- [Web Demo](demo/README.md) explains playback, cancellation and reconnecting.
- [Media credits](docs/MEDIA_ATTRIBUTION.md) lists sources and licenses for the built-in lecture, demo recording, poster and upload example.

## License

See [LICENSING.md](LICENSING.md), [NOTICE](NOTICE) and [LICENSES](LICENSES/).
