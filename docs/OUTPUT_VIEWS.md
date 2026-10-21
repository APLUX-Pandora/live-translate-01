# Output views

The result area has three tabs:

- **ASR transcript** shows the original text with the ASR paragraph breaks and stops translation inference.
- **Translation only** shows translated text without the original sentences.
- **Bilingual** shows each source sentence followed by its streamed translation, retaining the ASR paragraph boundaries.

Entering ASR transcript clears pending translation execution and requests cancellation of the active generation. ASR and playback continue. The translation model remains loaded but idle after cancellation returns. Switching back to Translation only or Bilingual resumes translation and translates the source accumulated while paused. Completed translations are retained; an interrupted segment restarts with the same segment ID. Switching between Translation only and Bilingual only changes presentation.

Translation pause/resume applies to the shared board session and is synchronized across connected browsers. Opening or refreshing a browser does not change the backend mode. The selected layout is remembered locally; the backend translation mode takes precedence. Switching preserves playback, transcript, sentence alignment and ASR session ID. Original copy/export controls appear in the ASR and bilingual views; translation copy appears in the translation and bilingual views.

Use Left/Right arrows, Home or End while a tab is focused to switch views. Each view retains its scroll position while switching. The default is Bilingual.
