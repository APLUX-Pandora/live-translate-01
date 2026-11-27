# SPDX-License-Identifier: Apache-2.0
# Recovery policy adapted from the APLUX Audio8-ASR-Infinite Web Demo.
"""Bounded, per-recording audio recovery for the Web Demo."""

import numpy as np


class ResetPolicy:
    """After a quiet gap, give the current stream time to resume before replaying."""

    QUIET_S = 1.76
    NO_TEXT_S = 6.0
    WAIT_S = 1.28
    ACTIVE_POWER = 1e-5
    LEAD_POWER = 1e-7

    def __init__(self, rate, window, *, roll_s):
        self.rate = rate
        self.window = window
        self.roll_samples = round(roll_s * rate)
        self.resume_at = self.roll_samples
        self.block = rate // 50  # 20 ms energy measurements
        self.quiet_samples = round(self.QUIET_S * rate)
        self.no_text_samples = round(self.NO_TEXT_S * rate)
        self.wait_samples = round(self.WAIT_S * rate)
        self.last_text_end = 0
        self.quiet = 0
        self.lead = None
        self.pending = []
        self.onset = 0
        self.varying = 0

    def observe(self, pcm, delta, end):
        """Process a window only after the original stream has seen it."""
        if delta.strip():
            self.last_text_end = end
            self.pending.clear()
            self.quiet = 0
            self.lead = None
            return None
        if not self.roll_samples or end <= self.resume_at or pcm.size != self.window:
            return None

        power = np.mean(pcm.reshape(-1, self.block) ** 2, axis=1)
        if power.mean() < self.ACTIVE_POWER:
            self.pending.clear()
            self.quiet = min(self.quiet + self.window, self.quiet_samples)
            self.lead = pcm.copy()
            return None
        if not self.pending:
            quiet, lead = self.quiet, self.lead
            self.quiet, self.lead = 0, None
            start = end - self.window
            if quiet < self.quiet_samples or start - self.last_text_end < self.no_text_samples:
                return None

            self.onset = start
            self.varying = 0
            # Keep a quiet lead-in and any initial low-energy sound in the
            # preceding window. All replay audio follows the last shown text.
            lead_power = np.mean(lead.reshape(-1, self.block) ** 2, axis=1)
            activity = np.flatnonzero(np.concatenate((lead_power, power)) >= self.LEAD_POWER)
            first = max(0, int(activity[0]) - 1) * self.block
            lead_in = np.concatenate((lead, pcm))[first:]
            self.pending.append(lead_in)
        else:
            self.pending.append(pcm.copy())

        # A knock will run out of active windows. Steady noise can be loud
        # throughout, so require energy to vary in multiple windows as well.
        self.varying += int(power.max() > 4 * power.min())
        if end - self.onset < self.wait_samples:
            return None
        buffered = self.pending
        self.pending = []
        return np.concatenate(buffered) if self.varying >= 2 else None

    def record(self, end, replay_samples):
        # The new stream must fill its own rolling context before rearming.
        self.resume_at = end - replay_samples + self.roll_samples
        return {
            "onset_s": round(self.onset / self.rate, 3),
            "audio_s": round(end / self.rate, 3),
            "replay_start_s": round((end - replay_samples) / self.rate, 3),
        }


class RecoveringStream:
    """Present successive SDK streams as one append-only Web recording."""

    def __init__(self, model, *, sample_rate, language):
        self.model = model
        self.options = {"sample_rate": sample_rate, "language": language}
        info = model.info
        self.window = info["samples_per_token"]
        self.policy = ResetPolicy(sample_rate, self.window, roll_s=info["roll_s"])
        self.pending = np.empty(0, dtype=np.float32)
        self.fed = 0
        self.stream_text = ""
        self.last_char = ""
        self.join_replay = False
        self.finish_reason = None
        self.stream = model.create_stream(**self.options)

    def _append(self, piece):
        if piece:
            if self.join_replay and piece[0].isalnum():
                piece = " " + piece
            self.join_replay = False
            self.last_char = piece[-1]
        return piece

    def _feed(self, pcm):
        update = self.stream.feed(pcm)
        self.fed += pcm.size
        recovery = None
        if not update.finish_reason:
            replay = self.policy.observe(pcm, update.delta, self.fed)
            if replay is not None:
                self.stream.close()
                self.stream = self.model.create_stream(**self.options)
                self.join_replay = bool(self.options["language"] == "en" and
                                        self.last_char and not self.last_char.isspace())
                update = self.stream.feed(replay)
                recovery = self.policy.record(self.fed, replay.size)
        self.stream_text = update.text
        self.finish_reason = update.finish_reason
        return self._append(update.delta), recovery

    def feed(self, pcm):
        data = np.concatenate((self.pending, pcm))
        pieces, recoveries = [], []
        offset = 0
        while data.size - offset >= self.window and not self.finish_reason:
            end = offset + self.window
            piece, recovery = self._feed(data[offset:end])
            pieces.append(piece)
            if recovery is not None:
                recoveries.append(recovery)
            offset = end
        self.pending = data[offset:].copy() if not self.finish_reason else np.empty(0, dtype=np.float32)
        return {"delta": "".join(pieces), "finish_reason": self.finish_reason,
                "recoveries": recoveries}

    def finish(self):
        tail = ""
        if self.pending.size:
            tail, _ = self._feed(self.pending)
        result = self.stream.finish()
        if not result.text.startswith(self.stream_text):
            raise RuntimeError("The ASR result changed previously emitted text")
        return {"delta": tail + self._append(result.text[len(self.stream_text):]),
                "finish_reason": result.finish_reason}

    def close(self):
        self.stream.close()
