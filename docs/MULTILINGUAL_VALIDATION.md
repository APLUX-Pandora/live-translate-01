# Multilingual Web validation

The Web demo uses a single sentence-aligned bilingual text area, without output tabs. Each original sentence is followed by its streamed translation; the ASR paragraph boundaries remain unchanged. Source and target language selectors remain available before a run. See [bilingual output](BILINGUAL_OUTPUT.md).

## Method

Seven separate 600-second runs played the licensed English lecture in the actual browser at 1x speed. The demo page decoded the original video, captured Web Audio, resampled and posted PCM to the board, received ASR and translation events, and displayed the bilingual output. A separate read-only SSE observer collected evidence; it did not feed audio or control inference. Only one run used the board at a time. The lecture and attribution are documented in [media attribution](MEDIA_ATTRIBUTION.md).

Tested device: QCS8550, Ubuntu 22.04.2. Native SDKs, model packages, audio clock and existing segmentation policy were unchanged. Browser audio chunk timing can produce small ASR/segmentation differences, so these runs are functional checks rather than a strict cross-language model benchmark.

## Results

| English to | Playback | Completed tasks | Errors | ASR step P95 | Translation completion P95 |
|---|---:|---:|---:|---:|---:|
| Japanese | 10:00 | 131/131 | 0 | 120.1 ms | 1.66 s |
| Korean | 10:00 | 133/133 | 0 | 120.5 ms | 1.52 s |
| French | 10:00 | 133/133 | 0 | 119.4 ms | 1.46 s |
| German | 10:00 | 133/133 | 0 | 120.7 ms | 1.61 s |
| Spanish | 10:00 | 133/133 | 0 | 119.6 ms | 1.39 s |
| Arabic | 10:00 | 133/133 | 0 | 120.7 ms | 1.80 s |
| Thai | 10:00 | 133/133 | 0 | 121.4 ms | 2.12 s |

All 929 tasks completed with nonempty translations in the selected target language. Pending task count returned to zero in every run; at most two were pending during playback. Translation inputs covered the original ASR paragraph content. Closed-paragraph boundary whitespace is accounted for separately and is not a lost word. Original export and sentence grouping passed replay against all seven complete event streams.

ASR step medians were approximately 75 ms with a 160 ms audio clock. Across runs, first translation from the first observed ASR character had a median around 3.56 seconds and P95 around 7.42–8.14 seconds; this includes collecting a useful source phrase and is not native decode latency or speech-end latency. Translation completion above is measured from task submission, including queueing. Final translation drain after ASR completion was under 0.9 seconds. Board DRAM stayed approximately 6.15–6.17 GiB; this short test does not establish an indefinite leak-free runtime.

The actual browser reached video time 600 seconds and Done/Up to date in every run. Japanese, Korean and Thai characters displayed correctly. Arabic target blocks used right-to-left direction independently of left-to-right English source blocks, without horizontal overflow. There were no browser warning/error logs in the final inspection. All 48 Python tests and the incremental-render regression passed.

## Translation quality limits

These checks establish playback, inference completion and rendering behavior, not professional translation accuracy. Spot checks found terminology and short-context issues:

- When ASR writes README as “read me”, the translation can interpret it as an ordinary phrase. This was visible in Korean.
- A French negative sentence had an awkward repeated negation.
- A source pause splitting “code specialist” caused less natural independently translated German fragments.
- Some repeated spoken phrases were simplified in Spanish.

The complete source is submitted, but a nonempty completed result does not prove that every semantic detail is translated accurately. Terminology normalization and a better context policy are possible future quality improvements; they were not introduced during this compatibility test.
