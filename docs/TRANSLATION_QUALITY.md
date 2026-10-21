# Translation quality and causal checks

The previous seven-language 10-minute result was a transport/completion test, not linguistic acceptance. A subsequent semantic review inspected all 602 final bilingual display pairs (86 per target language). It found material terminology errors, lost sentence relationships, occasional mixed-language tokens and grammar problems. This was an AI-assisted source/target review, not a professional native-speaker accuracy certification. Source truth for this review is the ASR text actually submitted; suspected speech-recognition errors were not silently corrected or presented as verified audio transcriptions.

## Controlled experiments

46 diagnostic cases cover all seven target languages. Tests compare the exact recorded phrase inputs, their original complete source sentence/block, and (where applicable) a version normalizing technical names such as README. No model weights were changed.

- The old SDK ran 157 translations. All 93 exact recorded-phrase replays reproduced the Web demo output byte for byte.
- The corrected SDK ran 177 translations, including three repetitions of ten selected complete inputs. It preserves sampler settings supplied by the model package.
- Every callback stream joined exactly to its SDK final text in all 334 board executions.
- An independent original-weight reference ran 18 complete/normalized inputs, using the exact chat prompt, greedy decoding and repetition penalty 1.0. Prompt token counts matched in all 18 checks. Counts alone are not a token-ID parity proof. GPU execution was unavailable; reference weights were expanded to FP32 for CPU computation. No timing comparison is claimed.

## Confirmed attribution

| Observation | Controlled result | What it establishes |
|---|---|---|
| Korean Wireshark sentence contained Chinese `上的` | Same recorded phrase, old sampler: reproduced. Package sampler: normal Korean, including three complete-input repetitions. | The old decoding override interacts badly with this deployed package; queueing, display and sentence splitting are not the cause of this case. |
| Thai GitHub-history translation contained `saya` | Same second phrase with package sampling no longer contains this foreign-language word. Whole-source input also removes it under old decoding. | Both decoding and available context affect this case. |
| Long README is as problematic as a short one | The demo split the comparison across three independently reset requests. Package sampling alone still loses the relation. A complete input restores it under both old and package decoding. | Confirmed segmentation/context loss, not an inability to translate the comparison. |
| Long sentence changes an instruction to “I try” | German, Spanish and Arabic complete-input results restore the subject relationship even with old decoding. | The independent phrase requests contribute to the pronoun error. |
| `read me` becomes ordinary reading | Similar ambiguity occurs with the original-weight reference. `README` normalization improves selected Japanese and Thai inputs. | ASR spelling/technical terminology is a contributor; normalization is helpful but is not a universal fix. |
| Markdown/markup, French negation and document-folder wording | Some errors remain with a complete input and package sampling. Original-weight reference results are mixed; e.g. German folder wording is also awkward there. | Residual quality is not explained entirely by our segmentation. More evidence is needed to separate model, prompt, numeric precision, conversion and runtime effects. |

The original-weight reference does not independently establish the source revision used to convert the encrypted package. Therefore a difference is described as a deployed-path difference, not proof that quantization alone caused it. Conversely, an error reproduced by both paths is evidence of a shared limitation under that input/prompt, not a general judgment about every use of the model.

## Sampling correction

SDK 0.1.0 explicitly overrode sampling with top-k 1, top-p 1.0, temperature 1.0 and repetition penalty 1.0. The corrected SDK deletes those overrides. The fixed supplied package reports:

```json
{"top-k":20,"top-p":0.6,"temp":0.7,"repetition-penalty":1.05,"frequency-penalty":0.0,"presence-penalty":0.0,"penalize-last-n":-1}
```

SDK info now identifies `model-package` decoding and returns the effective properties captured after generator initialization. The local original-weight generation configuration has top-p 0.8, while the encrypted package initializes 0.6. This change deliberately follows the supplied package, as authorized, rather than imposing either value on all packages. No new conversion or model-package modification was performed.

The 0.1.1 native SDK is a signed **candidate**, built from a clean candidate source tag and validated on QCS8550. It is explicitly selected by `--translation-library` in the board Web test. Existing formally released native libraries, signed component inventories and HF model revisions remain intact; this diagnostic override does not silently replace a released component. The previous seven-language 70-minute result remains scoped to SDK 0.1.0. It is not a fresh long-run test of the new sampler.

The stripped candidate also passed a direct native C ABI smoke check and a 128.3-second actual browser English-to-Korean run: 23/23 translation tasks completed, no transport errors, no source loss, and the Wireshark sentence no longer contained Chinese text. All 78 SDK and 48 application unit tests passed. This is targeted regression evidence, not a repeat of the seven-language 70-minute test.

The remaining quality work is to preserve comparisons/unfinished syntax across phrase boundaries and introduce context-sensitive technical-name handling. Those policy changes are separate from this sampler correction and need their own quality/latency checks.
