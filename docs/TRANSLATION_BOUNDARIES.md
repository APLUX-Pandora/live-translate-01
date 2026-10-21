# Translation boundaries

English translation input favors complete sentences. ASR still streams immediately, retains its original text and paragraph boundaries, and the bilingual renderer pairs each source sentence with its translation. This policy only changes when text is submitted to the translation worker.

## Policy

- A comma alone does not submit a request. An early coordinate clause requires evidence of a standalone predicate on the left and a conjunction with an explicit subject on the right.
- Comparisons, dependent constructions, obvious unfinished noun phrases and incomplete conditional phrases are held for continuation. These are conservative English heuristics, not a grammatical parser.
- Semantic and speech pause thresholds are 1.2 and 1.6 seconds. The English fallback is 24 seconds or 512 characters, retaining an unfinished word where possible. A hard fallback can still split a very long sentence.
- Chinese thresholds and its 96-character/12-second fallback remain unchanged. Other source languages have not been newly validated by this English-specific change.

The earlier 3.5-second clause preference remains available only when the conservative independent-clause check succeeds. A long dependent sentence may therefore wait about 22 seconds before translation starts. Original ASR text continues during that wait. This is an explicit quality/latency tradeoff.

## Verification

54 application unit tests cover comparisons, subject relationships, unfinished noun phrases, conditional continuations, independent clauses, bounded fallback and existing paragraph behavior.

A policy simulation replayed the seven historical 10-minute English ASR streams. Each produced 84 translation requests (81 sentence, two clause, one finish), compared with about 133 historical requests. Maximum input length was 329 characters; none required a max-wait fallback. Source text was conserved per ASR paragraph, allowing only recorded trailing boundary whitespace. The snapshots do not retain every native token timestamp, so this is not an exact native-token replay or a latency benchmark.

63 direct native probes cover nine boundary cases across Japanese, Korean, French, German, Spanish, Arabic and Thai. All completed with nonempty output and exact callback/final-text equality. Semantic inspection found that complete inputs improve comparison relationships, noun-phrase continuity and subject relationships. These are targeted qualitative checks, not a linguistic acceptance score. Arabic and Thai still mistranslate README in selected inputs; French folder/render wording and some German terminology remain problematic. Sentence preservation cannot by itself fix these model/terminology errors.

The board uses the explicitly selected signed SDK 0.1.1 candidate with model-package sampling (top-k 20, top-p 0.6, temperature 0.7, repetition penalty 1.05). Model weights and ASR SDK are unchanged. The bundled formal SDK 0.1.0 and immutable release tags remain intact. See [quality attribution](TRANSLATION_QUALITY.md) for the separate decoding correction.

A fresh actual browser English-to-Japanese 10-minute run completed 84/84 tasks without errors or source loss (one trailing paragraph whitespace character excluded). Renderer replay preserved both ASR paragraphs and sentence pairs. ASR step median/p95 was 75.0/118.8 ms; observed ASR-first-character to first-translation-chunk median/p95 was 4.60/13.90 seconds, and final drain was 1.70 seconds. These measures include sentence collection and are not speech-end latency or browser-paint timing. The complete long concession and README comparison appeared as paired full inputs in the actual page. False ASR punctuation can still yield fragments such as “Do you want people to open?” followed by “Discussions on GitHub”; semantic boundary recovery is not comprehensive. This run is separate from the historical seven-language run. Final measurements are retained in the workflow evidence record. The previous performance report's clause-policy latency gains do not describe this policy.
