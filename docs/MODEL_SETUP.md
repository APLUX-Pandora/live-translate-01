# Model setup

## Device requirements

- A compatible Linux device with Aidlux LMS (`sudo lms check` returns true), drivers, DSP firmware and BSP/FastRPC support.
- Python 3.10–3.12 in the Demo environment (see [Install](../README.md#1-install)).
- The SDK includes its QNN runtime libraries. Do not install QNN separately or set QNN paths.

Both component SDKs come from the Demo's Git submodules and use the shared Pandora Runtime.

## Targets

Pick the folder for your device's SoC in both repositories.

| SoC | Target folder |
| --- | --- |
| QCS8550 | `qcs8550_qnn248` |
| QCS9075 | `qcs9075_qnn248` |
| QCS8625 | `qcs8625_qnn248` |
| QCS8275 | `qcs8275_qnn248` |

## Download

Use the Audio8-ASR-Infinite 160 ms package for recognition. Replace `<target-folder>` in both download blocks with the entry for your device in the table above.

From the Demo root, in the activated environment, download the shared resources once and then one target:

```bash
hf download APLUX-Pandora/Audio8-ASR-Infinite-160ms --local-dir models/asr --exclude "targets/*" --exclude "media/*" --exclude README.md --exclude .gitattributes
hf download APLUX-Pandora/Audio8-ASR-Infinite-160ms --local-dir models/asr --include "targets/<target-folder>/*"
```

Run `hf auth login` first if the repository is private. Keep one target per model folder: to switch devices, move the old `targets/` folder out or download into a new folder.

Download the translation package into its own model folder using the same target.

```bash
hf download APLUX-Pandora/Hy-MT2-1.8B --local-dir models/translation --exclude "targets/*" --exclude "media/*" --exclude README.md --exclude .gitattributes
hf download APLUX-Pandora/Hy-MT2-1.8B --local-dir models/translation --include "targets/<target-folder>/*"
```

## Folder layout

After the download, `models/` looks like this:

```text
models/
  asr/
    models.json
    SHA256SUMS
    embedding.bin
    frontend/
    mel_filters.npy
    prefix/
    rotation.npy
    semantic_vad/
    token_bytes.json
    tokenizer.json
    targets/<target-folder>/    # encoder, adapter and two decoder graphs
  translation/
    models.json
    SHA256SUMS
    embedding/
    prefix/
    tokenizer.json
    targets/<target-folder>/    # two language model shards
```

The SDK reads `models.json`, checks that the shared resources and one complete target are present, and reports what is missing. `hf download` verifies each large file's checksum.

These checks apply to each model folder. Keep the accompanying license and notice files.

## Troubleshooting

| Message or symptom | What to do |
| --- | --- |
| Authentication required | Log in with an account that can read both repositories. |
| Target files missing | Check the SoC and download its target into both model directories. |
| Device authorization failed | Check LMS activation on the device. |
