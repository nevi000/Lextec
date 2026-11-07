"""Parsing of statute references: article numbers with letter suffixes, paragraphs, letters.

Examples handled: "266l", "273", "8bis", paragraph "1", "Abs. 1", "Abs. 1–2", "Abs. 4–5",
"Abs. 1–2 lit. c", "Abs. 1 lit. b", letter "c".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SR_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,4}){0,3}$")
_ARTICLE = re.compile(r"^(\d{1,4})\s*([a-z]{1,10})?$", re.IGNORECASE)
_PARA = re.compile(
    r"^(?:Abs\.?\s*)?(?P<a>\d{1,2})(?:\s*[–\-]\s*(?P<b>\d{1,2}))?(?:\s*(?:lit\.?\s*)(?P<l>[a-z]))?$",
    re.IGNORECASE,
)
_LETTER_ONLY = re.compile(r"^(?:lit\.?\s*)?([a-z])$", re.IGNORECASE)


class ReferenceError_(ValueError):
    pass


@dataclass(frozen=True)
class ArticleRef:
    number: int
    suffix: str  # "" | "a" | "l" | "bis" ...
    para_from: int | None = None
    para_to: int | None = None
    letter: str | None = None

    @property
    def eid(self) -> str:
        return f"art_{self.number}" + (f"_{self.suffix}" if self.suffix else "")

    @property
    def label(self) -> str:
        """'Art. 266l' (no law abbreviation)."""
        return f"Art. {self.number}{self.suffix}"

    @property
    def paragraph_text(self) -> str | None:
        if self.para_from is None:
            return None
        rng = (
            str(self.para_from)
            if self.para_to in (None, self.para_from)
            else f"{self.para_from}–{self.para_to}"
        )
        return f"Abs. {rng}" + (f" lit. {self.letter}" if self.letter else "")


def parse_article(article: str) -> tuple[int, str]:
    m = _ARTICLE.match(article.strip())
    if not m:
        raise ReferenceError_(f"Ungültige Artikelnummer: {article!r}")
    return int(m.group(1)), (m.group(2) or "").lower()


def parse_reference(
    article: str, paragraph: str | None = None, letter: str | None = None
) -> ArticleRef:
    number, suffix = parse_article(article)
    pf = pt = None
    lit = None
    if paragraph:
        m = _PARA.match(paragraph.strip())
        if not m:
            raise ReferenceError_(f"Ungültiger Absatz: {paragraph!r}")
        pf = int(m.group("a"))
        pt = int(m.group("b")) if m.group("b") else pf
        lit = (m.group("l") or "").lower() or None
        if pt < pf:
            raise ReferenceError_(f"Absatzbereich verkehrt: {paragraph!r}")
    if letter:
        m2 = _LETTER_ONLY.match(letter.strip())
        if not m2:
            raise ReferenceError_(f"Ungültiger Buchstabe: {letter!r}")
        lit = m2.group(1).lower()
    return ArticleRef(number, suffix, pf, pt, lit)
