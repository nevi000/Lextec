"""Structured-output contracts for AI tasks. Model output is untrusted until validated."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DetectedIssue(BaseModel):
    issue_id: str = Field(description="ID aus dem Katalog der unterstützten Rechtsprobleme.")
    confidence: float = Field(ge=0.0, le=1.0, description="Sicherheit der Zuordnung 0..1.")
    evidence_quote: str = Field(description="Wörtliches Zitat aus der Nachricht.")
    source_message_id: str


class ExtractedFact(BaseModel):
    fact_id: str = Field(description="ID aus dem Fakten-Katalog.")
    value: str = Field(
        description="Wert als Text. boolean: 'ja'/'nein'; date: YYYY-MM-DD; integer: Ziffern."
    )
    ambiguous: bool = Field(
        default=False, description="True, wenn die Aussage unklar oder nicht eindeutig ist."
    )
    unknown: bool = Field(
        default=False,
        description="True NUR wenn die Nachricht die Antwort auf diese Frage ist (answers_fact_id) und "
        "die Person ausdrücklich sagt, sie wisse es nicht. value dann leer lassen.",
    )
    ambiguity_note: str | None = None
    evidence_quote: str = Field(description="Wörtliches Zitat aus der Nachricht.")
    source_message_id: str


class UnrecognizedIssue(BaseModel):
    description: str = Field(description="Kurze Beschreibung des nicht abgedeckten Rechtsproblems.")
    evidence_quote: str
    source_message_id: str


class ContradictionCandidate(BaseModel):
    fact_id: str
    note: str


class ExtractionResult(BaseModel):
    detected_issues: list[DetectedIssue] = []
    facts: list[ExtractedFact] = []
    unrecognized_issues: list[UnrecognizedIssue] = []
    contradiction_candidates: list[ContradictionCandidate] = []
    summary_de: str = Field(
        default="", description="Kurze sachliche Zusammenfassung (max. 3 Sätze)."
    )


class InputMessage(BaseModel):
    id: str
    kind: str
    content: str
    answers_fact_id: str | None = None


class IssueCatalogEntry(BaseModel):
    id: str
    title_de: str
    description: str = ""
    typical_situations: list[str] = []


class FactCatalogEntry(BaseModel):
    id: str
    label_de: str
    data_type: str
    enum_values: list[str] = []
    enum_labels_de: dict[str, str] = {}
    hint_de: str = ""  # extraction guidance from the knowledge base
    question_de: str = ""  # only used by the mock provider (answers); not sent to the model


class ExtractionInput(BaseModel):
    new_messages: list[InputMessage]
    earlier_messages: list[InputMessage] = []
    issue_catalog: list[IssueCatalogEntry]
    fact_catalog: list[FactCatalogEntry]
    known_facts: dict[str, str] = {}
    existing_summary: str = ""
    today: str = ""  # ISO date; for relative dates ("gestern", "vor drei Tagen")
