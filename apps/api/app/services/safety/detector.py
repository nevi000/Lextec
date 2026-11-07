"""Deterministic safety-signal detection (no AI, no database).

Runs on every user message, independent of the legal issue classification and of whether the AI analysis worked.
It is NOT a naive keyword match: every hit is checked for negation, past reference, hypothetical wording,
professional/quote context and the sentence it stands in. Unclear hits stay visible as UNCLEAR, never as a diagnosis.
Patterns and their consequences live in knowledge_base/safety/safety_signals.yaml and referral_network.yaml.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.services.safety.config import SafetySignalsFile

ACUTE = "ACUTE"
UNCLEAR = "UNCLEAR"

_TRANSLIT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_SENTENCE = re.compile(r"[.!?;\n]+")
# a new thought starts here: modifiers before this point do not belong to a hit after it
_BOUNDARY = re.compile(
    r"\b(aber|sondern|jedoch|mais|but)\b|[:]|\bund\s+(ich|er|sie|wir|es|man|werde|will|muss|wird)\b"
)


def normalize(text: str) -> str:
    t = text.lower().translate(_TRANSLIT)
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


@dataclass
class DetectedSignal:
    category: str
    certainty: str  # ACUTE | UNCLEAR
    evidence: str  # the sentence as written (shortened)
    rule_id: str
    modifiers: list[str] = field(default_factory=list)  # e.g. ["historical"], explains a downgrade


class Detector:
    def __init__(self, cfg: SafetySignalsFile):
        self.cfg = cfg
        m = cfg.modifiers
        self._neg = [re.compile(p) for p in m.negation]
        self._hist = [re.compile(p) for p in m.historical]
        self._hyp = [re.compile(p) for p in m.hypothetical]
        self._pro = [re.compile(p) for p in m.professional]
        # quote markers are configured but never suppress a hit: a client's quoted words stay visible
        self._cats: list[tuple[str, list[re.Pattern], list[re.Pattern]]] = [
            (
                c.id,
                [re.compile(p) for p in c.acute],
                [re.compile(p) for p in c.mention],
            )
            for c in cfg.categories
        ]

    # -- helpers ---------------------------------------------------------------------------------
    @staticmethod
    def _window(sentence: str, start: int, end: int) -> tuple[int, int]:
        """The part of the sentence that belongs to the same thought as the hit."""
        lo = 0
        for b in _BOUNDARY.finditer(sentence, 0, start):
            lo = b.end() if b.start() < start else lo
        hi = len(sentence)
        nxt = _BOUNDARY.search(sentence, end)
        if nxt:
            hi = nxt.start()
        return lo, hi

    def _negated(self, sentence: str, start: int, end: int) -> bool:
        lo, hi = self._window(sentence, start, end)
        before = sentence[max(lo, start - 35) : start]
        after = sentence[end : min(hi, end + 12)]
        return any(p.search(before) or p.search(after) for p in self._neg)

    def _hypothetical(self, sentence: str, start: int, end: int) -> bool:
        lo, hi = self._window(sentence, start, end)
        return any(p.search(sentence[lo:hi]) for p in self._hyp)

    def _any(self, patterns: list[re.Pattern], sentence: str) -> bool:
        return any(p.search(sentence) for p in patterns)

    # -- detection -------------------------------------------------------------------------------
    def detect(self, text: str) -> list[DetectedSignal]:
        raw = text or ""
        # normalisation never changes the length of ASCII-only text; keep sentence boundaries aligned
        best: dict[str, DetectedSignal] = {}
        for raw_sentence in _SENTENCE.split(raw):
            if not raw_sentence.strip():
                continue
            s = normalize(raw_sentence)
            historical = self._any(self._hist, s)
            professional = self._any(self._pro, s)
            for cat_id, acute, mention in self._cats:
                found = self._classify(
                    cat_id, acute, mention, s, historical, professional, raw_sentence
                )
                if found is None:
                    continue
                cur = best.get(cat_id)
                if cur is None or (cur.certainty == UNCLEAR and found.certainty == ACUTE):
                    best[cat_id] = found
        return list(best.values())

    def _classify(
        self,
        cat_id: str,
        acute: list[re.Pattern],
        mention: list[re.Pattern],
        s: str,
        historical: bool,
        professional: bool,
        raw_sentence: str,
    ) -> DetectedSignal | None:
        evidence = raw_sentence.strip()[:240]
        for i, pat in enumerate(acute):
            for m in pat.finditer(s):
                if self._negated(s, m.start(), m.end()):
                    continue
                mods: list[str] = []
                certainty = ACUTE
                if historical:
                    certainty, mods = UNCLEAR, ["historical"]
                elif self._hypothetical(s, m.start(), m.end()):
                    certainty, mods = UNCLEAR, ["hypothetical"]
                return DetectedSignal(
                    cat_id, certainty, evidence, f"SAFETY_{cat_id}_ACUTE_{i + 1}", mods
                )
        if historical or professional:
            return None  # a mere mention in past or professional context is no signal
        for i, pat in enumerate(mention):
            for m in pat.finditer(s):
                if self._negated(s, m.start(), m.end()):
                    continue
                return DetectedSignal(
                    cat_id, UNCLEAR, evidence, f"SAFETY_{cat_id}_MENTION_{i + 1}", []
                )
        return None
