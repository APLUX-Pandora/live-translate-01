# Historical application performance notes

These measurements describe the earlier aggressive-clause policy and SDK 0.1.0. The active English boundary policy now prioritizes sentence context; see [translation boundaries](TRANSLATION_BOUNDARIES.md). Do not apply the latency improvement below to the revised policy. The incremental renderer remains in use.

This application patch keeps the existing 160 ms transcription package, native SDKs and model files. Each original sentence still owns its streamed translation; ASR paragraph breaks are unchanged.

Long speech can submit a sufficiently complete clause after 3.5 seconds rather than waiting six seconds. Earlier English clauses require eight words; Chinese clauses require twelve word characters. Incomplete relative-clause endings are held. Shorter suitable clauses retain a submission opportunity after six seconds; the twelve-second unpunctuated fallback remains unchanged. These are application heuristics, not a guarantee of grammatical completeness.

The renderer indexes jobs and sentence groups once, updates only changed groups and avoids rewriting unchanged text. Original-only export is constructed when requested, and word/character totals are updated from the changed paragraph instead of rescanning the full transcript.

## Same-audio board comparison

One 90-second English-to-Chinese comparison used the same authorized FOSDEM lecture excerpt, mono 16 kHz PCM16 audio, 1x API ingestion and QCS8550. ASR output was identical in both runs; all 17 translation tasks completed without errors. The table uses server-side SSE receipt timestamps. Source-sentence timing starts when its first ASR character was observed, not when speech began.

| Metric | Before | After |
| --- | ---: | ---: |
| First ASR sentence character to first translated chunk, median | 5.99 s | 4.28 s |
| Same metric, P95 | 8.86 s | 8.86 s |
| Translation completion after ASR sentence-end text, median | 719 ms | 612 ms |
| ASR step time, median | 74.8 ms | 75.1 ms |
| ASR step time, P95 | 109.9 ms | 108.8 ms |
| Translation tasks | 17 | 17 |
| Maximum pending translation tasks, including active generation | 2 | 1 |

Typical first-translation waiting improved by about 29% in this sample; tail latency did not improve. This is one paired recording with eleven complete punctuated source sentences, not a multi-corpus or multi-language benchmark. It does not measure ground-truth spoken-sentence endpoints, network-to-browser paint time or demonstrate faster native model inference. Translation quality was spot-checked; no independent quality score is claimed. Twelve seconds remains the fallback threshold for unpunctuated input.

## Renderer stress check

A synthetic Node mock-DOM replay retained 1,500 historical sentences and delivered 100 further translation chunks. Text setter writes fell from 600,100 to 100. This verifies that completed history is no longer rewritten; it is not a browser frame-rate or end-to-end speedup claim. History remains available for copying and export; DOM virtualization is not part of this patch.

The existing demonstration recording captures the earlier v0.1.0 UI. See [media attribution](MEDIA_ATTRIBUTION.md) for the lecture source and license.
