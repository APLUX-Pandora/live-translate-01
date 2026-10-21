# Reused model resources

`model-lock.json` fixes the repository commit, package subtree, local destination
and SHA-256 for every file used by the QCS8550 composite. Model weights are not
stored in this application repository. The two existing model repositories keep
their visibility and licenses; no new conversion or weight upload is required.

```bash
# Set HF_TOKEN in the current shell using an account with repository access.
.venv/bin/python tools/download_models.py
.venv/bin/python tools/download_models.py --verify-only
```

Both repositories currently require access. Never write tokens into this project
or pass them in model URLs. The script reads `HF_TOKEN`, verifies existing files
before reusing them, checks every completed download, and omits authorization on
cross-host redirects. It downloads only the fixed packages in the lock. A network
or checksum failure is an error, not permission to use a different model revision.

The resulting layout is shared by the Web application and standalone example:

```
models/asr/qnn248_qcs8550/manifest.json
models/translation/qcs8550/manifest.json
```

The current lock and composite verification cover QCS8550 with the 160 ms ASR
clock. Other component variants are not composite qualification evidence.
Package-level LICENSE/NOTICE files remain with each package. Existing signed SDK
manifests apply only to their original component releases, not to this application.
