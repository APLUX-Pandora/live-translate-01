# Independent resource reuse

Install the component SDKs and model packages once, using their own GitHub/ModelFarm instructions. This composite has no model repository, bundled SDK or model download step. Pass the existing package roots through --models and --translation-models; SDK paths use AUDIO8_SDK_ROOT and HY_MT2_SDK_ROOT. Refer to the main README for component release versions.

model-lock.json retains the exact original QCS8550/160 ms model-file identities used for this integration. Its current backing repositories preserve those same file identities; no duplicate model download is needed for existing verified installations. Runtime data are unchanged; preserve manifests, hashes and all package licenses. Other chip packages belong to their component projects and do not constitute composite inference qualification.

## Backing-store migration


The fixed model lock now downloads unchanged inference bytes from the real-name private ModelFarm repositories. Local package paths and all 33 original runtime-file hashes remain unchanged. The downloader maps renamed remote files to their existing local names. Small original manifest/runtime/license/checksum files are retained under `resources/compatibility/`; they describe this existing SDK layout and are checked against the same lock. No weights or SDK binaries are added or updated.

Normal model provisioning follows the independent Audio8 and HY-MT2 GitHub/MMS instructions. The fixed backing-store downloader is an optional authorized migration/verification tool; it requires private repository access. This metadata migration does not change the independent SDK release status or claim MMS availability.
