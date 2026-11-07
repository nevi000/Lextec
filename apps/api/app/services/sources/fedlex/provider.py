"""CachedFedlexProvider: read-only SourceProvider backed by the local snapshot cache.

It never touches the network, so briefings and the UI work offline and a Fedlex outage can never affect
a case or the decision engine. Statuses are DERIVED from what is stored:

* an old snapshot is "possibly outdated" and can never count as verified today;
* a fixture snapshot (tests/demo data) is labelled as such and never counts as a Fedlex retrieval;
* VerificationStatus.VERIFIED requires: real Fedlex origin + fresh + wording MATCHED.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.domain.enums import VerificationStatus
from app.models.tables import SourceSnapshot, SourceSyncState, SourceWordingCheck
from app.services.knowledge.loader import KnowledgeBase
from app.services.sources.fedlex.models import (
    RETRIEVAL_LABEL_DE,
    WORDING_LABEL_DE,
    FedlexInfo,
)
from app.services.sources.fedlex.service import is_fedlex_statute, kb_text_hash

FAILURE_STATES = {
    "NOT_FOUND",
    "VERSION_AMBIGUOUS",
    "VERSION_NOT_FOUND",
    "EXTRACTION_FAILED",
    "REFERENCE_MISMATCH",
    "ERROR",
}
ARTICLE_URL_NOTE = (
    "Link nach dem Muster des Fedlex-Viewers (Anker = Artikel-ID aus dem amtlichen Dokument); "
    "der Anker wurde nicht automatisch geprüft."
)


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


class CachedFedlexProvider:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: Settings,
        kb: KnowledgeBase,
        reference_date: date | None = None,
    ):
        self._sf = session_factory
        self._s = settings
        self._kb = kb
        self.reference_date = reference_date or settings.app_today or date.today()

    # ---- SourceProvider protocol (kept compatible with the original metadata-only provider) ----------
    def verify(self, source_id: str) -> tuple[VerificationStatus, str]:
        info = self.info(source_id)
        if info.retrieval_status == "NOT_APPLICABLE":
            return (
                VerificationStatus.UNVERIFIED,
                "Kein Fedlex-Bundesrecht: vom System nicht live verifiziert. Prüfstand laut Law-Dossier separat ausgewiesen.",
            )
        if info.origin == "FIXTURE":
            return VerificationStatus.UNVERIFIED, "Testdaten (Fixture), nicht von Fedlex abgerufen."
        if info.retrieval_status == "RETRIEVED" and info.wording_status == "MATCHED":
            return (
                VerificationStatus.VERIFIED,
                f"Amtlicher Wortlaut bei Fedlex abgerufen ({info.retrieved_at}) und mit der Wissensbasis abgeglichen. "
                "Die juristische Interpretation ist davon getrennt.",
            )
        if info.wording_status == "MISMATCH" or info.retrieval_status in FAILURE_STATES:
            return VerificationStatus.FAILED, f"{info.retrieval_label_de}. {info.wording_label_de}."
        return VerificationStatus.UNVERIFIED, f"{info.retrieval_label_de}. {info.wording_label_de}."

    # ---- details ------------------------------------------------------------------------------------------
    def info(self, source_id: str, reference_date: date | None = None) -> FedlexInfo:
        canon = self._kb.resolve_source_id(source_id) or source_id
        src = self._kb.sources.get(canon)
        info = FedlexInfo()
        if src is None or not is_fedlex_statute(src):
            info.retrieval_status = "NOT_APPLICABLE"
            info.retrieval_label_de = RETRIEVAL_LABEL_DE["NOT_APPLICABLE"]
            info.wording_status = "NO_COMPARABLE_TEXT"
            info.wording_label_de = WORDING_LABEL_DE["NO_COMPARABLE_TEXT"]
            if src is not None:
                self._interpretation(info, src)
            return info

        ref = reference_date or self.reference_date
        info.reference_date = ref.isoformat()
        self._interpretation(info, src)
        with self._sf() as s:
            snaps = list(
                s.scalars(
                    select(SourceSnapshot)
                    .where(SourceSnapshot.source_id == src.id)
                    .order_by(SourceSnapshot.retrieved_at.desc())
                )
            )
            state = s.get(SourceSyncState, src.id)
            snap = self._choose(snaps, ref.isoformat())
            if snap is None:
                status = (
                    state.status if state and state.status in FAILURE_STATES else "NOT_RETRIEVED"
                )
                info.retrieval_status = status  # type: ignore[assignment]
                info.retrieval_label_de = RETRIEVAL_LABEL_DE[status]
                info.message = state.message if state else None
                return info

            info.origin = snap.origin  # type: ignore[assignment]
            info.language = snap.language
            info.article_label = snap.article_label
            info.law_abbreviation = snap.law_abbreviation
            info.law_title = snap.law_title
            info.heading = snap.heading
            info.version_identifier = snap.version_identifier
            info.valid_from, info.valid_to = snap.valid_from, snap.valid_to
            info.version_covers_reference = (snap.valid_from or "") <= ref.isoformat() and (
                snap.valid_to is None or ref.isoformat() <= snap.valid_to
            )
            info.retrieved_at = _aware(snap.retrieved_at).isoformat(timespec="seconds")
            info.official_eli_uri = snap.eli_uri
            info.official_document_url = snap.document_url
            info.official_article_url = snap.article_url
            info.article_url_note = ARTICLE_URL_NOTE
            info.content_hash = snap.content_hash
            info.official_text = snap.text
            age = datetime.now(UTC) - _aware(snap.last_checked_at)
            info.cache_age_days = age.days
            stale = age > timedelta(days=self._s.fedlex_cache_max_age_days)
            info.retrieval_status = "RETRIEVED_STALE" if stale else "RETRIEVED"
            info.retrieval_label_de = RETRIEVAL_LABEL_DE[info.retrieval_status]
            if snap.origin == "FIXTURE":  # test data is never presented as an official retrieval
                info.retrieval_label_de = "Testdaten (Fixture), kein amtlicher Abruf"
            if (
                state
                and state.status in FAILURE_STATES
                and _aware(state.attempted_at) > _aware(snap.last_checked_at)
            ):
                info.message = f"Letzter Abruf fehlgeschlagen ({state.status}): {state.message}"

            check = s.scalar(
                select(SourceWordingCheck).where(
                    SourceWordingCheck.source_id == src.id,
                    SourceWordingCheck.snapshot_id == snap.id,
                    SourceWordingCheck.kb_text_hash == kb_text_hash(src),
                )
            )
            if check is not None:
                info.wording_status = check.status  # type: ignore[assignment]
                info.wording_details = check.details or {}
                if check.status == "MATCHED" and not stale and snap.origin == "FEDLEX":
                    info.verified_at = _aware(check.checked_at).isoformat(timespec="seconds")
            info.wording_label_de = WORDING_LABEL_DE[info.wording_status]
            return info

    @staticmethod
    def _choose(snaps: list[SourceSnapshot], ref_iso: str) -> SourceSnapshot | None:
        """The snapshot whose version covers the reference date; else the newest (flagged as not covering)."""
        if not snaps:
            return None
        covering = [
            s
            for s in snaps
            if (s.valid_from or "") <= ref_iso and (s.valid_to is None or ref_iso <= s.valid_to)
        ]
        real = [s for s in covering if s.origin == "FEDLEX"] or covering
        return (real or snaps)[0]

    @staticmethod
    def _interpretation(info: FedlexInfo, src) -> None:
        r = src.interpretation_review
        if r.status == "REVIEWED":
            info.interpretation_status = "REVIEWED"
            info.interpretation_reviewed_by = r.reviewed_by
            info.interpretation_reviewed_at = r.reviewed_at
            info.interpretation_label_de = (
                f"Interpretation vom Law-Team geprüft ({r.reviewed_by}, {r.reviewed_at})"
            )

    # ---- bulk status ----------------------------------------------------------------------------------------
    def status_table(self, source_ids: list[str]) -> list[tuple[str, FedlexInfo]]:
        return [(sid, self.info(sid)) for sid in source_ids]
