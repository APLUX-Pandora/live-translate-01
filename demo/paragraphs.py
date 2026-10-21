"""One source-of-truth paragraph stream for transcript and translated display."""
import re


class ParagraphTracker:
    def __init__(self, delay_tokens=3, enabled=True, horizon=2.0, threshold=0.6):
        self.delay_tokens = delay_tokens
        self.options = dict(enabled=enabled, horizon=horizon, threshold=threshold)
        self.paragraphs = []
        self.armed, self.pending, self.due = False, False, None
        self.resets = 0

    def configure(self, **options):
        if any(self.options.get(k) != v for k, v in options.items()):
            self.options.update(options)
            self.armed, self.pending, self.due = False, False, None

    def _append(self, piece, timestamp, new=False):
        if not piece:
            return []
        if new or not self.paragraphs:
            if not piece.strip():
                return []
            self.paragraphs.append(dict(id=len(self.paragraphs)+1, text="", start_s=timestamp, revision=0))
        row = self.paragraphs[-1]
        row["text"] += piece
        row["revision"] += 1
        return [dict(row, piece=piece)]

    def push(self, piece, tokens, probability, resets, timestamp):
        if resets > self.resets and self.paragraphs:
            self.pending = True
        self.resets = resets
        if self.due is not None and tokens >= self.due:
            self.due = None
            if self.paragraphs:
                self.pending = True
        parts = []
        if piece:
            if self.pending and self.paragraphs:
                # A closing mark emitted after the turn belongs to the old text.
                match = re.match(r'''^[\s.,!?;:)\]"'”’。，！？；：、）》」』]+''', piece)
                lead = match.group(0) if match else ""
                rest = piece[len(lead):]
                parts += self._append(lead, timestamp)
                if rest.strip():
                    parts += self._append(rest, timestamp, new=True)
                    self.pending = False
            else:
                parts += self._append(piece, timestamp)
        if self.options["enabled"] and probability is not None:
            on = probability >= self.options["threshold"]
            if on and self.armed:
                self.due, self.armed = tokens+self.delay_tokens, False
            if not on and self.paragraphs:
                self.armed = True
        return parts

    def snapshot(self):
        return [dict(row) for row in self.paragraphs]
