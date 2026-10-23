# Independent resource reuse

Install the component SDKs and model packages once, using their own GitHub/ModelFarm instructions. This composite has no model repository, bundled SDK or model download step. Pass the existing package roots through --models and --translation-models; SDK paths use AUDIO8_SDK_ROOT and HY_MT2_SDK_ROOT. Refer to the main README for component release versions.

model-lock.json retains the exact original QCS8550/160 ms model-file identities used for this integration. Its current backing repositories preserve those same file identities; no duplicate model download is needed for existing verified installations. Runtime data are unchanged; preserve manifests, hashes and all package licenses. Other chip packages belong to their component projects and do not constitute composite inference qualification.

## Preparing an existing HY raw package

The raw `qnn236_*_cl4096` resources contain original graph shards, configuration and prefix cache; they do not include the SDK loading manifest. Follow the independent [HY model guide](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/main/models/README.md), using its own `demo/prepare_models.py` on that existing package. It verifies fixed resource identities and adds local loading metadata/licenses in place. Do not copy its installer into this application or download a second model. Already prepared packages can be reused directly.

For Audio8, use the existing [160ms package guide](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/main/models/README.md).
