"""Legal source registry + provider abstraction.

Two separate statuses are carried for every source and must never be mixed up:

* ``dossier_status``      - what the law team's dossier says (checked against their PDFs / full texts,
                             pending, or only mentioned). NOT something this system verified.
* ``verification_status`` - live verification BY THIS SYSTEM. No live retrieval (Fedlex SPARQL) is
                             implemented, so nothing is ever reported VERIFIED by this module.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from app.domain.enums import VerificationStatus
from app.services.knowledge.loader import KnowledgeBase
from app.services.sources.fedlex.models import FedlexInfo


class SourceRef(BaseModel):
    id: str
    provider: str
    type: str
    sr_number: str | None = None
    statute: str | None = None
    article: str | None = None
    paragraph: str | None = None
    language: str = "de"
    title_de: str
    text_de: str | None = None
    legal_question_de: str | None = None
    valid_as_of: str | None = None
    origin_ref: str | None = None
    dossier_status: str = "DOSSIER_PENDING"
    verification_status: VerificationStatus
    verification_note: str
    # case law
    citation: str | None = None
    case_number: str | None = None
    decision_date: str | None = None
    considerations: list[str] = []
    core_statement_de: str | None = None
    scope_de: str | None = None
    limits_de: str | None = None
    relevant_fact_ids: list[str] = []
    url: str | None = None
    # Fedlex-backed details (retrieval / wording / interpretation are SEPARATE statuses)
    aliases: list[str] = []
    fedlex: FedlexInfo | None = None


class SourceProvider(Protocol):
    def verify(self, source_id: str) -> tuple[VerificationStatus, str]: ...


class MetadataOnlyProvider:
    """Default provider: honest about the fact that nothing was retrieved or checked by the system."""

    def verify(self, source_id: str) -> tuple[VerificationStatus, str]:
        return (
            VerificationStatus.UNVERIFIED,
            "Vom System nicht live verifiziert (Fedlex/BGer nicht angebunden). "
            "Der Prüfstand laut Law-Dossier ist separat ausgewiesen.",
        )


class SourceRegistry:
    def __init__(self, kb: KnowledgeBase, provider: SourceProvider | None = None):
        self._kb = kb
        self._provider = provider or MetadataOnlyProvider()

    def get(self, source_id: str) -> SourceRef | None:
        canon = self._kb.resolve_source_id(source_id)
        s = self._kb.sources.get(canon or "")
        if s is None:
            return None
        status, note = self._provider.verify(s.id)
        info_fn = getattr(self._provider, "info", None)
        fedlex = info_fn(s.id) if callable(info_fn) else None
        data = s.model_dump(exclude={"verification_status", "interpretation_review", "fedlex_sync"})
        return SourceRef(**data, verification_status=status, verification_note=note, fedlex=fedlex)

    def all(self) -> list[SourceRef]:
        return [r for sid in self._kb.sources if (r := self.get(sid)) is not None]
