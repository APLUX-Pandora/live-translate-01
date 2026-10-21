"""Business-layer phrase boundaries for an append-only streaming transcript."""
from dataclasses import dataclass
import re


@dataclass
class Segment:
    id: int
    text: str
    start_s: float
    end_s: float
    reason: str


class Segmenter:
    def __init__(self, language, delay_tokens=3, soft_wait_s=3.5, hard_wait_s=12.0):
        self.language = language
        self.delay_tokens = delay_tokens
        self.soft_wait_s, self.hard_wait_s = soft_wait_s, hard_wait_s
        self.pending, self.times = "", []
        self.count = self.serial = 0
        self.last_text_s = None
        self.semantic_due = None
        self.semantic_ready = False
        self.armed = False
        self.latest_eot = 0.0

    def _complete_phrase(self, text, pause=False):
        if self.language == "en":
            words = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\d+", text)
            if not words:
                return False
            open_ends = {"a", "an", "the", "to", "of", "for", "with", "from", "in", "on", "at", "by",
                         "and", "or", "but", "because", "if", "when", "while", "that", "which", "whose",
                         "this", "these", "those", "my", "your", "our", "their", "its", "just", "very",
                         "first", "second", "third", "another", "each", "every", "such"}
            return words[-1].lower() not in open_ends and (not pause or len(words) >= 4)
        return not pause or len(re.findall(r"[\w]", text)) >= 8

    def _useful_clause(self, text, early=True):
        # Earlier submission needs enough context; never commit a short lead-in.
        units = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\d+", text) if self.language == "en" else re.findall(r"[\w]", text)
        if self.language == "en" and re.search(
                r"\b(?:what|who|which|where|how)\b[^.!?]*\b(?:is|are|was|were|does|do|did|can|could|would|will|should)\s*[,，:：]$", text, re.I):
            return False
        minimum = (8 if early else 4) if self.language == "en" else (12 if early else 6)
        return len(units) >= minimum and self._complete_phrase(text)

    def _boundaries(self, clauses=False):
        text = self.pending
        marks = "。！？!?；;" + ("，,：:" if clauses else "")
        result = []
        for i, char in enumerate(text):
            boundary = char in marks
            if char == ".":
                left = text[:i]
                right = text[i+1:]
                # A decimal, an initial, or a common title is not a sentence end.
                abbreviation = re.search(r"(?:\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc)|\b[A-Za-z])$", left, re.I)
                decimal = bool(left and left[-1].isdigit() and (not right or right[0].isdigit()))
                boundary = not abbreviation and not decimal and (not right or not right[0].isalnum())
            if not boundary or not self._complete_phrase(text[:i+1]):
                continue
            end = i+1
            while end < len(text) and text[end] in '”’"\'）)]}。！？!?':
                end += 1
            result.append(end)
        return result

    def _commit(self, end, reason):
        raw, times = self.pending[:end], self.times[:end]
        self.pending, self.times = self.pending[end:], self.times[end:]
        self.semantic_ready = False
        self.semantic_due = None
        if not raw.strip():
            return []
        self.serial += 1
        return [Segment(self.serial, raw, times[0], times[-1], reason)]

    def push(self, piece, audio_s, eot=0.0, silence_s=0.0):
        self.count += 1
        self.latest_eot = eot
        if not self.pending.strip():
            # A leading silence prediction must not commit the first spoken word.
            self.semantic_due = None
            self.semantic_ready = False
        if eot < 0.4:
            self.armed = True
        elif eot >= 0.65 and self.armed and self.pending.strip():
            self.semantic_due, self.armed = self.count + self.delay_tokens, False
        if self.semantic_due is not None and self.count >= self.semantic_due:
            self.semantic_ready, self.semantic_due = True, None
        if piece:
            self.pending += piece
            self.times.extend([audio_s]*len(piece))
            self.last_text_s = audio_s
        return self.tick(audio_s, silence_s)

    def tick(self, audio_s, silence_s=0.0):
        if not self.pending.strip():
            return []
        output = []
        # Hold a terminal mark briefly to collect punctuation, quotes and decimals.
        while self.pending.strip():
            boundaries = self._boundaries()
            if not boundaries:
                break
            end = boundaries[0]
            if end == len(self.pending) and audio_s-self.times[end-1] < 0.32:
                break
            output += self._commit(end, "sentence")
        if not self.pending.strip():
            return output
        quiet = audio_s-(self.last_text_s if self.last_text_s is not None else audio_s)
        complete = self._complete_phrase(self.pending, pause=True)
        if quiet >= 0.48 and self.semantic_ready and self.latest_eot >= 0.65 and complete:
            return output+self._commit(len(self.pending), "semantic_pause")
        if quiet >= 0.64 and silence_s >= 0.8 and complete:
            return output+self._commit(len(self.pending), "speech_pause")
        age = audio_s-self.times[0]
        max_chars = 96 if self.language == "zh" else 256
        if age >= self.soft_wait_s or len(self.pending) >= max_chars:
            clauses = [i for i in self._boundaries(clauses=True) if self._useful_clause(self.pending[:i], early=age < 6.0 and len(self.pending) < max_chars)]
            if clauses:
                return output+self._commit(clauses[-1], "clause")
        if age >= self.hard_wait_s or len(self.pending) >= max_chars:
            # With no natural boundary, prefer a complete English word. Chinese
            # unpunctuated speech still needs a bounded fallback, recorded explicitly.
            end = len(self.pending)
            if self.language == "en" and quiet < 0.48:
                spaces = list(re.finditer(r"\s+", self.pending))
                if spaces and spaces[-1].start() > 0:
                    end = spaces[-1].end()
                elif len(self.pending) < 512:
                    return output
            output += self._commit(end, "maximum_wait")
        return output

    def finish(self):
        return self._commit(len(self.pending), "finish") if self.pending else []
