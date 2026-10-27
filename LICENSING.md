# Licensing scope

Application/business code and new Python examples are under the root Apache-2.0
license. Existing component Python interfaces retain their supplied licenses.
The ASR and translation SDKs are referenced as fixed submodules and retain their original
licenses and release status. This application does not bundle their libraries,
headers or bindings, and does not relicense those components or vendor runtimes.
Historical SDK copies remain only in Git history. Existing attribution texts for
application code derived from the ASR demo are preserved in NOTICE and LICENSES/.

Model packages are separate resources and retain their package-level licenses and
notices. Access to a private repository is not a grant of additional model rights.
Reusing a fixed model revision does not change its terms. See `resources/README.md`.

The original ASR notice is retained in root NOTICE, including references to media
from the original component project. Those references do not mean that all those
files are bundled with this composite. Existing internal test media are not part
of the application git tree, and their external redistribution is not approved by
this project. Use your own authorized audio/video as input. The approved demonstration recording
and poster are separately attributed in docs/MEDIA_ATTRIBUTION.md and retain
the lecture's CC BY 2.0 BE terms.
