"""FedlexService: deterministic sync of referenced statutes into the local cache (no LLM, no case data).

Flow per run: collect sources -> serve from fresh cache or group by (SR, language, reference date) ->
find the statute valid on that date -> choose the version -> fetch the structured XML once -> extract each
article -> store a versioned snapshot -> compare the knowledge-base wording -> record the outcome.
A failure of one source never affects another, and never touches the decision engine.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.tables import SourceSnapshot, SourceSyncState, SourceWordingCheck
from app.services.knowledge.loader import KnowledgeBase
from app.services.knowledge.schema import SourceDef
from app.services.sources.fedlex import catalog
from app.services.sources.fedlex.akn import (
    AknDocument,
    ArticleNotFound,
    ExtractedArticle,
    ExtractionError,
    compare_wording,
    content_hash,
)
from app.services.sources.fedlex.http import FedlexError, FedlexHttp
from app.services.sources.fedlex.reference import ArticleRef, ReferenceError_, parse_reference

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


@dataclass
class SourceResult:
    source_id: str
    status: str  # RETRIEVED | CACHED | NOT_FOUND | VERSION_AMBIGUOUS | ... | SKIPPED
    message: str = ""
    label: str = ""
    version_identifier: str | None = None
    wording_status: str | None = None
    newer_version: str | None = None


@dataclass
class SyncReport:
    reference_date: str
    results: list[SourceResult] = field(default_factory=list)
    requests: int = 0
    offline: bool = False

    def count(self, *statuses: str) -> int:
        return sum(1 for r in self.results if r.status in statuses)

    @property
    def failed(self) -> list[SourceResult]:
        ok = {"RETRIEVED", "CACHED", "SKIPPED"}
        return [r for r in self.results if r.status not in ok]


def is_fedlex_statute(src: SourceDef) -> bool:
    return bool(
        src.provider == "fedlex"
        and src.type == "statute"
        and src.sr_number
        and src.article
        and src.fedlex_sync
    )


def kb_text_hash(src: SourceDef) -> str:
    return hashlib.sha256((src.text_de or "").encode("utf-8")).hexdigest()


def article_label(src: SourceDef, ref: ArticleRef) -> str:
    abbr = f" {src.statute}" if src.statute else ""
    para = f" {ref.paragraph_text}" if ref.paragraph_text else ""
    return f"{ref.label}{para}{abbr}"


class FedlexService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: Settings,
        kb: KnowledgeBase,
        http: FedlexHttp | None = None,
    ):
        self._sf = session_factory
        self._s = settings
        self._kb = kb
        self._http = http

    # ------------------------------------------------------------------------------ selection
    def collect_issue_sources(self, issue_id: str) -> list[str]:
        """Every source id an issue references (rules, facts, briefing profile), de-duplicated."""
        issue = self._kb.issues.get(issue_id)
        if issue is None:
            raise KeyError(f"Unbekanntes Issue: {issue_id}")
        ids: list[str] = list(issue.legal_source_ids)
        for f in issue.facts:
            ids += f.source_ids
        for r in issue.legal_rules:
            ids += r.legal_source_ids
        if issue.briefing_profile:
            for p in issue.briefing_profile.review_points:
                ids += p.source_ids
        out: list[str] = []
        for i in ids:
            canon = self._kb.resolve_source_id(i)
            if canon and canon not in out:
                out.append(canon)
        return out

    def all_referenced_sources(self) -> list[str]:
        seen: list[str] = []
        for issue_id in self._kb.issues:
            for sid in self.collect_issue_sources(issue_id):
                if sid not in seen:
                    seen.append(sid)
        return seen

    # ------------------------------------------------------------------------------ sync
    def sync(
        self,
        source_ids: list[str],
        reference_date: date,
        *,
        force: bool = False,
        offline: bool = False,
        as_of_dossier: bool = False,
    ) -> SyncReport:
        report = SyncReport(
            reference_date.isoformat(), offline=offline or not self._s.fedlex_enabled
        )
        sources: list[SourceDef] = []
        for sid in dict.fromkeys(source_ids):
            canon = self._kb.resolve_source_id(sid)
            if canon is None:
                report.results.append(
                    SourceResult(sid, "NOT_FOUND", "Unbekannte Source-ID in der Wissensbasis.")
                )
                continue
            src = self._kb.sources[canon]
            if not is_fedlex_statute(src):
                report.results.append(
                    SourceResult(canon, "SKIPPED", "Kein Fedlex-Gesetz (anderer Provider/Typ).")
                )
                continue
            sources.append(src)

        groups: dict[tuple[str, str, str], list[SourceDef]] = {}
        for src in sources:
            ref_date = reference_date
            if as_of_dossier and src.valid_as_of:
                ref_date = date.fromisoformat(src.valid_as_of)
            groups.setdefault(
                (src.sr_number or "", self._s.fedlex_language, ref_date.isoformat()), []
            ).append(src)

        http = self._http or FedlexHttp(self._s)
        try:
            for (sr, lang, ref_iso), members in groups.items():
                ref_date = date.fromisoformat(ref_iso)
                pending: list[SourceDef] = []
                for src in members:
                    cached = (
                        None
                        if force or not self._s.fedlex_cache_enabled
                        else self._fresh_snapshot(src, lang, ref_date)
                    )
                    if cached is not None:
                        self._ensure_wording(src, cached)
                        self._set_state(
                            src.id,
                            "RETRIEVED",
                            f"Aus dem Cache ({cached.version_identifier}).",
                            ref_iso,
                        )
                        report.results.append(
                            SourceResult(
                                src.id,
                                "CACHED",
                                "Frischer Cache-Eintrag.",
                                cached.article_label,
                                cached.version_identifier,
                                self._wording_status(src, cached),
                            )
                        )
                    else:
                        pending.append(src)
                if not pending:
                    continue
                if report.offline:
                    for src in pending:
                        self._set_state(
                            src.id, "NOT_RETRIEVED", "Offline: nichts im Cache.", ref_iso
                        )
                        report.results.append(
                            SourceResult(src.id, "NOT_RETRIEVED", "Offline und nicht im Cache.")
                        )
                    continue
                self._sync_group(http, sr, lang, ref_date, pending, report)
        finally:
            report.requests = getattr(http, "request_count", 0)
            if self._http is None:
                http.close()
        return report

    def _sync_group(self, http, sr, lang, ref_date, members, report) -> None:
        ref_iso = ref_date.isoformat()

        def fail_all(exc: Exception, status: str) -> None:
            for src in members:
                self._set_state(src.id, status, str(exc), ref_iso)
                report.results.append(SourceResult(src.id, status, str(exc)))

        try:
            cands = catalog.find_candidates(http, sr, lang)
            cand = catalog.select_candidate(cands, ref_date)
            versions = catalog.list_versions(http, cand.abstract_uri)
            version = catalog.select_version(versions, ref_date)
            newer = catalog.newer_version_exists(versions, version)
            xml_url = catalog.find_xml_url(http, version.uri, lang)
            if not xml_url:
                raise catalog.SourceNotFound(
                    f"Kein XML-Dokument für Fassung {version.identifier} ({lang})."
                )
            doc = AknDocument(http.get_document(xml_url))
            meta = doc.meta()
            if meta["uri"] and meta["uri"].rstrip("/") != version.uri.rstrip("/"):
                raise ExtractionError(
                    f"Dokument ({meta['uri']}) passt nicht zur gewählten Fassung ({version.uri})."
                )
        except catalog.CatalogError as exc:
            fail_all(exc, exc.code)
            return
        except ExtractionError as exc:
            fail_all(exc, exc.code)
            return
        except FedlexError as exc:
            log.warning("Fedlex sync failed for SR %s: %s", sr, exc.code)
            fail_all(exc, "ERROR")
            return

        for src in members:
            try:
                if (
                    src.statute
                    and cand.abbreviation
                    and src.statute.casefold() != cand.abbreviation.casefold()
                ):
                    raise _RefMismatch(
                        f"SR {sr} ist bei Fedlex «{cand.abbreviation}», die Wissensbasis nennt «{src.statute}»."
                    )
                ref = parse_reference(src.article or "", src.paragraph, src.letter)
                article = doc.extract(ref)
                snap = self._store_snapshot(
                    src, ref, article, cand, version, xml_url, doc.sha256, lang, ref_iso
                )
                self._ensure_wording(src, snap, article)
                self._set_state(src.id, "RETRIEVED", "Amtlicher Text abgerufen.", ref_iso)
                report.results.append(
                    SourceResult(
                        src.id,
                        "RETRIEVED",
                        "Amtlicher Text abgerufen.",
                        snap.article_label,
                        version.identifier,
                        self._wording_status(src, snap),
                        newer.identifier if newer else None,
                    )
                )
            except _RefMismatch as exc:
                self._set_state(src.id, "REFERENCE_MISMATCH", str(exc), ref_iso)
                report.results.append(SourceResult(src.id, "REFERENCE_MISMATCH", str(exc)))
            except ArticleNotFound as exc:
                self._set_state(src.id, "NOT_FOUND", str(exc), ref_iso)
                report.results.append(SourceResult(src.id, "NOT_FOUND", str(exc)))
            except (ExtractionError, ReferenceError_) as exc:
                self._set_state(src.id, "EXTRACTION_FAILED", str(exc), ref_iso)
                report.results.append(SourceResult(src.id, "EXTRACTION_FAILED", str(exc)))

    # ------------------------------------------------------------------------------ persistence
    def _fresh_snapshot(self, src: SourceDef, lang: str, ref_date: date) -> SourceSnapshot | None:
        iso = ref_date.isoformat()
        max_age = timedelta(days=self._s.fedlex_cache_max_age_days)
        with self._sf() as s:
            rows = s.scalars(
                select(SourceSnapshot)
                .where(
                    SourceSnapshot.source_id == src.id,
                    SourceSnapshot.language == lang,
                    SourceSnapshot.origin == "FEDLEX",
                )
                .order_by(SourceSnapshot.retrieved_at.desc())
            )
            for r in rows:
                covers = (r.valid_from or "") <= iso and (r.valid_to is None or iso <= r.valid_to)
                if covers and _now() - _aware(r.last_checked_at) <= max_age:  # type: ignore[operator]
                    s.expunge(r)
                    return r
        return None

    def _store_snapshot(
        self,
        src,
        ref: ArticleRef,
        art: ExtractedArticle,
        cand,
        version,
        xml_url,
        doc_hash,
        lang,
        ref_iso,
    ):
        chash = content_hash(art.selected_text)
        abbr = cand.abbreviation or src.statute
        article_path = cand.abstract_uri.removeprefix("https://fedlex.data.admin.ch")
        with self._sf() as s:
            existing = s.scalar(
                select(SourceSnapshot).where(
                    SourceSnapshot.source_id == src.id,
                    SourceSnapshot.version_identifier == version.identifier,
                    SourceSnapshot.language == lang,
                    SourceSnapshot.content_hash == chash,
                )
            )
            if (
                existing is not None
            ):  # idempotent: same version + same wording -> only refresh the check time
                existing.last_checked_at = _now()
                existing.requested_reference_date = ref_iso
                s.commit()
                s.refresh(existing)
                s.expunge(existing)
                return existing
            snap = SourceSnapshot(
                source_id=src.id,
                origin="FEDLEX",
                sr_number=src.sr_number or "",
                language=lang,
                law_abbreviation=abbr,
                law_title=cand.title,
                article=src.article or "",
                paragraph=src.paragraph,
                letter=src.letter,
                article_label=f"{ref.label}{(' ' + ref.paragraph_text) if ref.paragraph_text else ''} {abbr or ''}".strip(),
                requested_reference_date=ref_iso,
                version_identifier=version.identifier,
                valid_from=version.valid_from,
                valid_to=version.valid_to,
                abstract_uri=cand.abstract_uri,
                eli_uri=version.uri,
                document_url=xml_url,
                article_url=f"{self._s.fedlex_viewer_base}{article_path}/{lang}#{art.eid}",
                article_eid=art.eid,
                heading=art.heading,
                text=art.selected_text,
                structure=art.structure(),
                content_hash=chash,
                document_hash=doc_hash,
            )
            s.add(snap)
            s.commit()
            s.refresh(snap)
            s.expunge(snap)
            return snap

    def _set_state(self, source_id: str, status: str, message: str, ref_iso: str | None) -> None:
        with self._sf() as s:
            row = s.get(SourceSyncState, source_id)
            if row is None:
                s.add(
                    SourceSyncState(
                        source_id=source_id, status=status, message=message, reference_date=ref_iso
                    )
                )
            else:
                row.status, row.message, row.reference_date, row.attempted_at = (
                    status,
                    message,
                    ref_iso,
                    _now(),
                )
            s.commit()

    # ------------------------------------------------------------------------------ wording check
    def _ensure_wording(
        self, src: SourceDef, snap: SourceSnapshot, article: ExtractedArticle | None = None
    ) -> None:
        h = kb_text_hash(src)
        with self._sf() as s:
            have = s.scalar(
                select(SourceWordingCheck).where(
                    SourceWordingCheck.source_id == src.id,
                    SourceWordingCheck.snapshot_id == snap.id,
                    SourceWordingCheck.kb_text_hash == h,
                )
            )
            if have is not None:
                return
            art = article or _article_from_snapshot(snap)
            result = compare_wording(src.text_de, art)
            s.add(
                SourceWordingCheck(
                    source_id=src.id,
                    snapshot_id=snap.id,
                    kb_text_hash=h,
                    status=result["status"],
                    details={"fragments": result["fragments"], "missing": result["missing"]},
                )
            )
            s.commit()

    def _wording_status(self, src: SourceDef, snap: SourceSnapshot) -> str:
        with self._sf() as s:
            row = s.scalar(
                select(SourceWordingCheck).where(
                    SourceWordingCheck.source_id == src.id,
                    SourceWordingCheck.snapshot_id == snap.id,
                    SourceWordingCheck.kb_text_hash == kb_text_hash(src),
                )
            )
            return row.status if row else "NOT_COMPARED"

    def reverify(self, source_ids: list[str]) -> list[SourceResult]:
        """Offline: re-run the wording comparison against stored snapshots (e.g. after a KB text edit)."""
        out: list[SourceResult] = []
        for sid in dict.fromkeys(source_ids):
            canon = self._kb.resolve_source_id(sid)
            src = self._kb.sources.get(canon or "")
            if src is None or not is_fedlex_statute(src):
                continue
            with self._sf() as s:
                snap = s.scalar(
                    select(SourceSnapshot)
                    .where(SourceSnapshot.source_id == src.id)
                    .order_by(SourceSnapshot.retrieved_at.desc())
                )
                if snap is not None:
                    s.expunge(snap)
            if snap is None:
                out.append(SourceResult(src.id, "NOT_RETRIEVED", "Kein Snapshot im Cache."))
                continue
            self._ensure_wording(src, snap)
            out.append(
                SourceResult(
                    src.id,
                    "CACHED",
                    "Wortlaut neu abgeglichen.",
                    snap.article_label,
                    snap.version_identifier,
                    self._wording_status(src, snap),
                )
            )
        return out


class _RefMismatch(Exception):
    pass


def _article_from_snapshot(snap: SourceSnapshot) -> ExtractedArticle:
    from app.services.sources.fedlex.akn import Item, ParagraphText

    paragraphs = [
        ParagraphText(
            num=p.get("num", ""),
            eid=p.get("eid", ""),
            text=p.get("text", ""),
            items=[
                Item(label=i["label"], eid=i["eid"], text=i["text"]) for i in p.get("items", [])
            ],
        )
        for p in (snap.structure or [])
    ]
    full = " ".join(f"{p.num} {p.text}".strip() for p in paragraphs) or snap.text
    return ExtractedArticle(
        eid=snap.article_eid or "",
        label=snap.article_label,
        heading=snap.heading,
        paragraphs=paragraphs,
        selected_text=snap.text,
        full_text=full,
    )
