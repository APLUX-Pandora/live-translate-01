# Independent resource reuse

Initialize the fixed component submodules and obtain their model packages using the corresponding component GitHub/ModelFarm instructions. This composite has no model repository, bundled SDK or model download step. Pass the existing package roots through --models and --translation-models; SDKs are discovered under components/asr and components/translation; no manual SDK-root variables are needed. Refer to the main README for component release versions.

model-lock.json and compatibility/ retain the original composition resource identities as historical provisioning evidence. They do not qualify the updated component pairing or override the fixed components' current model guides. Reuse matching existing weights without downloading duplicates, but verify the package manifest/configuration required by the pinned SDK. Preserve hashes and all package licenses. Other chip packages belong to their component projects and do not constitute composite inference qualification.

## Preparing an existing HY raw package

The raw `qnn236_*_cl4096` resources contain original graph shards, configuration and prefix cache; they do not include the SDK loading manifest. Follow the independent [HY model guide](https://github.com/APLUX-Pandora/hy-mt2-1.8b-demo/blob/main/models/README.md), using its own `demo/prepare_models.py` on that existing package. It verifies fixed resource identities and adds local loading metadata/licenses in place. Do not copy its installer into this application or download a second model. Already prepared packages can be reused directly.

For Audio8, use the existing [160ms package guide](https://github.com/APLUX-Pandora/audio8-asr-infinite-demo/blob/main/models/README.md).
