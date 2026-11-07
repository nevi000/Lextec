"""Status model for Fedlex-backed sources.

Three layers that must never be mixed up:
1. RETRIEVAL   - did the system fetch the official text (and is it still fresh)?
2. WORDING     - does the wording quoted in the knowledge base occur in that official text?
3. INTERPRETATION - did the law team review how the source is USED? (A statute can be retrieved and quoted
                   correctly while the legal conclusion drawn from it is still unreviewed.)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RetrievalStatus = Literal[
    "NOT_APPLICABLE",  # not a Fedlex statute (case law, other provider, no article)
    "NOT_RETRIEVED",
    "RETRIEVED",  # official text fetched and stored; fresh enough
    "RETRIEVED_STALE",  # stored, but older than the freshness window: possibly outdated
    "NOT_FOUND",  # statute / article / version not found at Fedlex
    "VERSION_AMBIGUOUS",
    "VERSION_NOT_FOUND",
    "EXTRACTION_FAILED",
    "REFERENCE_MISMATCH",  # SR number and the statute abbreviation in the KB disagree
    "ERROR",  # network / HTTP / response problem
]
WordingStatus = Literal["MATCHED", "MISMATCH", "NO_COMPARABLE_TEXT", "NOT_COMPARED"]
InterpretationStatus = Literal["NOT_REVIEWED", "REVIEWED"]

RETRIEVAL_LABEL_DE: dict[str, str] = {
    "NOT_APPLICABLE": "Kein Fedlex-Bundesrecht",
    "NOT_RETRIEVED": "Noch nicht abgerufen",
    "RETRIEVED": "Amtlicher Text abgerufen",
    "RETRIEVED_STALE": "Gespeicherte Fassung, möglicherweise veraltet",
    "NOT_FOUND": "Quelle bei Fedlex nicht gefunden",
    "VERSION_AMBIGUOUS": "Fassung nicht eindeutig",
    "VERSION_NOT_FOUND": "Keine Fassung für den Stichtag",
    "EXTRACTION_FAILED": "Extraktion fehlgeschlagen",
    "REFERENCE_MISMATCH": "Quellenabgleich fehlgeschlagen (Referenz widersprüchlich)",
    "ERROR": "Abruf fehlgeschlagen",
}
WORDING_LABEL_DE: dict[str, str] = {
    "MATCHED": "Wortlaut mit Wissensbasis abgeglichen",
    "MISMATCH": "Wortlaut weicht von der Wissensbasis ab",
    "NO_COMPARABLE_TEXT": "Kein Wortlaut in der Wissensbasis zum Abgleichen",
    "NOT_COMPARED": "Wortlaut noch nicht abgeglichen",
}


class FedlexInfo(BaseModel):
    origin: Literal["FEDLEX", "FIXTURE", "NONE"] = "NONE"
    retrieval_status: RetrievalStatus = "NOT_RETRIEVED"
    retrieval_label_de: str = RETRIEVAL_LABEL_DE["NOT_RETRIEVED"]
    wording_status: WordingStatus = "NOT_COMPARED"
    wording_label_de: str = WORDING_LABEL_DE["NOT_COMPARED"]
    wording_details: dict = {}
    interpretation_status: InterpretationStatus = "NOT_REVIEWED"
    interpretation_label_de: str = "Interpretation: noch nicht durch das Law-Team geprüft"
    interpretation_reviewed_by: str | None = None
    interpretation_reviewed_at: str | None = None
    message: str | None = None  # last failure message, if any
    # what was stored
    article_label: str | None = None  # e.g. "Art. 266l OR"
    law_abbreviation: str | None = None
    law_title: str | None = None
    heading: str | None = None
    language: str | None = None
    version_identifier: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    reference_date: str | None = None  # the date the version was selected for
    version_covers_reference: bool | None = None
    retrieved_at: str | None = None
    verified_at: str | None = None  # time of the successful wording match
    official_eli_uri: str | None = None
    official_document_url: str | None = None
    official_article_url: str | None = None
    article_url_note: str | None = None
    content_hash: str | None = None
    official_text: str | None = None
    cache_age_days: int | None = None
