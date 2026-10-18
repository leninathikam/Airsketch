"""Bounded transcript, ordered by clip sequence and safe for retry."""
import threading


class NotesStore:
    MAX_CHARS = 200_000
    MAX_CLIPS = 2000

    def __init__(self):
        self._lock = threading.Lock()
        self._lines = {}

    def get(self, sequence):
        with self._lock:
            return self._lines.get(sequence)

    def add(self, text, sequence, digest=""):
        if not isinstance(text, str):
            raise ValueError("Text must be a string.")
        if type(sequence) is not int or not 0 <= sequence < self.MAX_CLIPS:
            raise ValueError("Clip sequence is out of range.")
        cleaned = " ".join(text.split())
        with self._lock:
            if sequence in self._lines:
                if self._lines[sequence][1] != digest:
                    raise ValueError("Clip sequence already contains different audio.")
                return
            if sum(len(item[0]) for item in self._lines.values()) + len(cleaned) > self.MAX_CHARS:
                raise ValueError("Lecture is full. Download notes and start a new lecture.")
            self._lines[sequence] = (cleaned, digest)

    def text(self):
        with self._lock:
            return " ".join(self._lines[key][0] for key in sorted(self._lines) if self._lines[key][0])
