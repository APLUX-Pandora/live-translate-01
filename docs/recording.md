# Live Translate 01 recording

- Application: 0.1.1; released Audio8 0.6.1 and HY-MT2 0.2.1 SDKs, directly reused.
- Models: existing independent model packages; no copies or changes.
- Source: the attributed built-in FOSDEM lecture; English speech to Chinese.
- Initial state: empty transcript/translation, English source and Chinese target.
- Actions: Start, normal-speed playback, Stop after approximately 55.76 seconds
  of source playback, then display the completed translations.
- Length: 60 seconds; page-only background recording on Mac, inference on board.
- Audio: actual browser video captureStream audio with a continuous silent clock;
  no desktop audio or replacement source track. Attenuated 3 dB for headroom.
- Credits: continuously visible below the viewport; see MEDIA_ATTRIBUTION.md.
- QA: full audio/video decode, duration/codec checks, audio alignment check and
  visual samples at 0, 10, 30, 48 and 59 seconds passed.
- Input lecture media and model weights are not included in this repository.

The README poster links to the compact recording. Use demo-original.mp4 for the
higher-quality encode. This media update changes no inference code or SDK/model
release and includes no Pandora production deployment.
