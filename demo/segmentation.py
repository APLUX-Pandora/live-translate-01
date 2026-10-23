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
    def __init__(self, language, delay_tokens=3, soft_wait_s=3.5, hard_wait_s=None):
        self.language = language
        self.delay_tokens = delay_tokens
        self.soft_wait_s = soft_wait_s
        self.hard_wait_s = hard_wait_s if hard_wait_s is not None else (24.0 if language == "en" else 12.0)
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
            terminal = bool(re.search(r"[.!?][\s”’\"')\]}]*$", text))
            # A demonstrative can be an object: "This is useful for that."
            if terminal:
                open_ends -= {"that", "this", "these", "those"}
            complete = words[-1].lower() not in open_ends
            if terminal and re.search(
                    r'\bdo\s+you\s+want\s+(?:people|users|them|us)\s+to\s+'
                    r'(?:open|read|write|create|use|install|download|configure|share)\s*\?$',
                    text.strip(), re.I):
                complete = False
            if terminal and re.search(
                    r"\b(?:if|when|while|because|though|unless|until|that)\s+"
                    r"(?:i|you|we|they|he|she|it)\s+"
                    r"(?:have|has|had|are|is|was|were|can|could|will|would|should|must|do|does|did)"
                    r"\s*[.!?]$", text.strip(), re.I):
                complete = False
            if pause:
                # Subject pronouns and unfinished modifier phrases need their continuation.
                complete = complete and words[-1].lower() not in {"i", "we", "they", "he", "she"}
                modifier_tail = re.search(
                    r"\b(?:a|an|the|my|your|our|their|its|another|some)\s+"
                    r"(?:(?:very|more|less)\s+)?"
                    r"(?:separate|original|specific|particular|different|single|additional|next|other|new|old)"
                    r"\s*$", text, re.I)
                complete = complete and not modifier_tail and not self._dependent_construction(text)
            return bool(complete and (not pause or len(words) >= 4))
        return not pause or len(re.findall(r"[\w]", text)) >= 8

    @staticmethod
    def _dependent_construction(text):
        # Be conservative around subordinate clauses and paired comparisons.
        return bool(re.search(
            r"\b(?:if|when|while|because|although|though|unless|until|whereas|whether|whose|which|who|what|how)\b"
            r"|\bby\s+the\s+time\b|\bas\s+(?:much|many|little|few|long|short|good|bad)\b"
            r"|\b(?:more|less|better|worse)\b[^.!?]*\bthan\b", text, re.I))

    def _useful_clause(self, text, remainder="", early=True):
        units = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\d+", text) if self.language == "en" else re.findall(r"[\w]", text)
        minimum = (8 if early else 4) if self.language == "en" else (12 if early else 6)
        if self.language == "en":
            # A comma alone does not close a translation unit. Wait until the next
            # coordinate clause has its own explicit subject and predicate lead-in.
            continuation = re.match(
                r"\s*(?:and|but|so|yet)\s+(?:i|we|you|they|he|she|it|this|that|there)"
                r"\s+(?:[A-Za-z]+(?:['’][A-Za-z]+)?)\b", remainder, re.I)
            predicate = re.search(
                r"\b(?:am|is|are|was|were|have|has|had|do|does|did|can|could|will|would|should|must|may|might)\b"
                r"|\b(?:i|we|you|they|he|she|it)\s+[A-Za-z]+(?:['’][A-Za-z]+)?\b", text, re.I)
            if not continuation or not predicate or self._dependent_construction(text):
                return False
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
        semantic_quiet = 1.2 if self.language == "en" else 0.48
        speech_quiet = 1.6 if self.language == "en" else 0.64
        if quiet >= semantic_quiet and self.semantic_ready and self.latest_eot >= 0.65 and complete:
            return output+self._commit(len(self.pending), "semantic_pause")
        if quiet >= speech_quiet and silence_s >= max(0.8, speech_quiet) and complete:
            return output+self._commit(len(self.pending), "speech_pause")
        age = audio_s-self.times[0]
        max_chars = 96 if self.language == "zh" else 512
        if age >= self.soft_wait_s or len(self.pending) >= max_chars:
            clauses = [i for i in self._boundaries(clauses=True) if self._useful_clause(self.pending[:i], self.pending[i:], early=age < 6.0 and len(self.pending) < max_chars)]
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
