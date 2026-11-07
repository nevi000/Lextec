"""Akoma Ntoso (LegalDocML) parsing, article extraction and wording comparison.

Structure (verified on the real OR and ZPO documents): ``article[@eId="art_266_l"]`` with
``num`` ("Art. 266" + italic "l"), optional ``heading``, ``paragraph[@eId="art_266_l/para_1"]`` and, for
letters, ``item[@eId="art_113/para_2/lbl_c"]``. Footnotes (``authorialNote``) are not statute text.

Parsing uses defusedxml: no external entities, no DTD tricks, no entity expansion bombs.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

from defusedxml import ElementTree as SafeET

from app.services.sources.fedlex.http import FedlexBadResponse
from app.services.sources.fedlex.reference import ArticleRef

AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
NS = {"a": AKN}


class ExtractionError(Exception):
    code = "EXTRACTION_FAILED"


class ArticleNotFound(ExtractionError):
    code = "ARTICLE_NOT_FOUND"


@dataclass
class Item:
    label: str
    eid: str
    text: str


@dataclass
class ParagraphText:
    num: str
    eid: str
    text: str
    items: list[Item] = field(default_factory=list)


@dataclass
class ExtractedArticle:
    eid: str
    label: str  # "Art. 266l" as printed
    heading: str | None
    paragraphs: list[ParagraphText]
    selected_text: str  # the requested paragraphs / letter (or the whole article)
    full_text: str

    def structure(self) -> list[dict]:
        return [
            {"num": p.num, "eid": p.eid, "text": p.text, "items": [vars(i) for i in p.items]}
            for p in self.paragraphs
        ]


class AknDocument:
    def __init__(self, raw: bytes):
        self.sha256 = hashlib.sha256(raw).hexdigest()
        try:
            self.root = SafeET.fromstring(raw)
        except Exception as exc:  # ParseError, forbidden entities, truncated documents ...
            raise FedlexBadResponse(
                f"Dokument nicht als sicheres XML lesbar: {type(exc).__name__}"
            ) from exc
        if not self.root.tag.endswith("}akomaNtoso"):
            raise FedlexBadResponse("Kein Akoma-Ntoso-Dokument.")
        self._articles = {
            a.get("eId"): a for a in self.root.iterfind(".//a:article", NS) if a.get("eId")
        }
        if not self._articles:
            raise FedlexBadResponse("Dokument enthält keine Artikel (unvollständig?).")

    # -- metadata from the FRBR block -------------------------------------------------------------
    def meta(self) -> dict[str, str | None]:
        out: dict[str, str | None] = {"uri": None, "date_applicability": None}
        for el in self.root.iterfind(".//a:meta//a:FRBRWork/a:FRBRuri", NS):
            out["uri"] = el.get("value")
        for el in self.root.iterfind(".//a:meta//a:FRBRWork/a:FRBRdate", NS):
            if el.get("name") == "jolux:dateApplicability":
                out["date_applicability"] = el.get("date")
        return out

    # -- extraction ---------------------------------------------------------------------------------
    def extract(self, ref: ArticleRef) -> ExtractedArticle:
        art = self._articles.get(ref.eid)
        if art is None:
            raise ArticleNotFound(
                f"{ref.label} nicht gefunden (eId {ref.eid}). Möglicherweise Teil eines Sammelartikels "
                "oder nicht vorhanden; es wird nichts geraten."
            )
        printed = _flatten_num(art)
        if _squash(printed) != _squash(ref.label):  # guard against picking a neighbouring article
            raise ExtractionError(
                f"Artikelnummer im Dokument ({printed!r}) passt nicht zu {ref.label!r}."
            )
        heading_el = art.find("a:heading", NS)
        heading = _norm(_flatten(heading_el)) if heading_el is not None else None

        paragraphs: list[ParagraphText] = []
        for p in art.findall("a:paragraph", NS):
            num_el = p.find("a:num", NS)
            num = _norm(_flatten(num_el)) if num_el is not None else ""
            body = _norm(_flatten(p, skip={"num"}))
            items = [
                Item(
                    label=_norm(_flatten(i.find("a:num", NS)))
                    if i.find("a:num", NS) is not None
                    else "",
                    eid=i.get("eId") or "",
                    text=_norm(_flatten(i, skip={"num"})),
                )
                for i in p.iterfind(".//a:item", NS)
            ]
            paragraphs.append(
                ParagraphText(num=num, eid=p.get("eId") or "", text=body, items=items)
            )
        if not paragraphs:  # single-paragraph articles without <paragraph>
            body = _norm(_flatten(art, skip={"num", "heading"}))
            if not body:
                raise ExtractionError(f"{ref.label}: kein Text im Artikel gefunden.")
            paragraphs = [ParagraphText(num="", eid=ref.eid, text=body)]

        full = " ".join(_with_num(p) for p in paragraphs)
        return ExtractedArticle(
            eid=ref.eid,
            label=printed,
            heading=heading,
            paragraphs=paragraphs,
            selected_text=_select(ref, paragraphs, full),
            full_text=full,
        )


def _with_num(p: ParagraphText) -> str:
    return f"{p.num} {p.text}".strip()


def _select(ref: ArticleRef, paragraphs: list[ParagraphText], full: str) -> str:
    if ref.para_from is None:
        return full
    chosen = [
        p
        for p in paragraphs
        if p.num.isdigit() and ref.para_from <= int(p.num) <= (ref.para_to or ref.para_from)
    ]
    if not chosen:
        raise ArticleNotFound(f"{ref.label} {ref.paragraph_text}: Absatz nicht vorhanden.")
    if ref.letter:
        target = chosen[
            -1
        ]  # "Abs. 2 lit. c" / "Abs. 1-2 lit. c": the letter belongs to the last paragraph
        hit = [i for i in target.items if i.eid.endswith(f"lbl_{ref.letter}")]
        if not hit:
            raise ArticleNotFound(
                f"{ref.label} Abs. {target.num} lit. {ref.letter}: Buchstabe nicht vorhanden."
            )
        intro = target.text.split(":")[0] + ":" if ":" in target.text else ""
        lead = " ".join(_with_num(p) for p in chosen[:-1])
        return " ".join(
            x
            for x in (
                lead,
                f"{target.num} {intro}".strip(),
                f"{hit[0].label} {hit[0].text}".strip(),
            )
            if x
        )
    return " ".join(_with_num(p) for p in chosen)


# ---- text helpers -----------------------------------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# Block-level elements are adjacent in the XML without whitespace ("...einreichen:a. bei ...;b. bei ...").
# They must be separated, otherwise words and list labels fuse (found on real data: Art. 273 Abs. 2 OR).
_BLOCK = {
    "p",
    "item",
    "listIntroduction",
    "blockList",
    "paragraph",
    "subparagraph",
    "num",
    "heading",
    "intro",
    "wrapUp",
}


def _flatten(el, skip: set[str] | None = None) -> str:
    """Text of an element without footnotes (authorialNote) and optionally without some children."""
    if el is None:
        return ""
    skip = skip or set()
    parts: list[str] = [el.text or ""]
    for child in el:
        name = _local(child.tag)
        if name != "authorialNote" and name not in skip:
            sep = " " if name in _BLOCK else ""
            parts.append(sep + _flatten(child) + sep)
        parts.append(child.tail or "")
    return "".join(parts)


def _flatten_num(article) -> str:
    n = article.find("a:num", NS)
    return _norm(_flatten(n)) if n is not None else ""


_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s.replace(" ", " ").replace(" ", " ")).strip()


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s).casefold()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_compare(text).encode("utf-8")).hexdigest()


# ---- wording comparison --------------------------------------------------------------------------------------
_QUOTES = str.maketrans({c: "'" for c in '«»‹›„“”‚‘’"`´'})
_DASHES = str.maketrans({c: "-" for c in "–—−‐‑"})


def normalize_for_compare(s: str) -> str:
    """Unicode (NFKC), typographic quotes/dashes, spaces. Case and wording are NOT touched."""
    s = unicodedata.normalize("NFKC", s).translate(_QUOTES).translate(_DASHES)
    s = s.replace(" ", " ").replace(" ", " ")
    return _WS.sub(" ", s).strip()


_QUOTED = re.compile(r"«([^»]+)»")


def quoted_fragments(kb_text: str | None) -> list[str]:
    """Verbatim fragments of a knowledge-base text: what stands in «...», split at elisions (…)."""
    if not kb_text:
        return []
    out: list[str] = []
    for q in _QUOTED.findall(kb_text):
        for piece in re.split(r"…|\.\.\.", q):
            piece = normalize_for_compare(piece).strip(" ,;")
            if len(piece) >= 5:
                out.append(piece)
    return out


def compare_wording(kb_text: str | None, official: ExtractedArticle) -> dict:
    """Do all quoted KB fragments occur in the official text (after normalisation)?

    MATCHED   - every quoted fragment found verbatim (numbered or plain paragraph form).
    MISMATCH  - at least one fragment not found: wording differs, nothing is declared identical.
    NO_COMPARABLE_TEXT - the KB holds no quoted wording to compare.
    """
    frags = quoted_fragments(kb_text)
    if not frags:
        return {"status": "NO_COMPARABLE_TEXT", "fragments": 0, "missing": []}
    plain = normalize_for_compare(" ".join(p.text for p in official.paragraphs))
    numbered = normalize_for_compare(official.full_text)
    selected = normalize_for_compare(official.selected_text)
    haystacks = (selected, numbered, plain)
    missing = [f for f in frags if not any(f in h for h in haystacks)]
    return {
        "status": "MATCHED" if not missing else "MISMATCH",
        "fragments": len(frags),
        "missing": missing,
    }
