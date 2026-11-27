# Web Demo

Complete [installation](../README.md#1-install) and [model setup](../docs/MODEL_SETUP.md).
In the activated environment, start the Web Demo from the repository root.

```bash
bash demo/run.sh --port 8766
```

Open the device address on port 8766. **Beyond the README**, a 10-minute
lecture excerpt, is selected by default. Select **Start** to play it with sound
and see live English and Chinese subtitles. The player lists the speaker, event,
source and license. [Media credits](../docs/MEDIA_ATTRIBUTION.md#built-in-lecture)

To use your own file, choose its language next to **Upload file**, then upload
a video with sound or an MP3, WAV or M4A (AAC) file. MP4 with H.264 video and AAC
audio works across common browsers. Files need a usable audio track.
The list marks audio files, including those with cover art, as **Audio**.
The audio player provides **Play**, **Pause** and a seek bar. Choose a target
language and select **Start** to transcribe and translate. Use the media list
to switch between uploads and the built-in lecture.

Original text updates during playback. The app submits confirmed phrases
for translation and displays translation updates until each phrase finishes.
**Stop** finishes captured audio and drains pending translations. **Cancel**
discards unfinished work. Seeking while transcribing starts a fresh session
from the new position. If less than one second remains, playback and transcription
restart from the beginning. Switching files cancels the active recording and clears
the displayed subtitles. After playback ends, wait for the final subtitles.
If playback pauses while buffered audio is sent, leave the page open.
If the connection drops, use **Retry connection** to recover the session.

One recording runs at a time. Stop the server with Ctrl+C.
