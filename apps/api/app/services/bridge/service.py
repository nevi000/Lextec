"""LexTec Sprachbrücke: one QR connection per case, all questions follow the existing question selection.

Rules of the design
* The backend row (``VoiceBridgeSession``) is the single source of truth; both devices only poll it.
* The question shown on the phone is ALWAYS derived from ``CaseService.current_decision`` (the existing engine).
  Nothing here selects, generates or reorders questions.
* A phone answer is a *proposal*. Nothing reaches the case state until the social worker accepts it; then the
  normal answer path (``add_message`` → analysis → decision) runs unchanged.
* The phone sees no case data at all - only the current question, translated, and its own state.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import secrets
import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from functools import wraps
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import AppError, ConflictError, NotFoundError
from app.domain.enums import MessageKind
from app.models.tables import Case, TranslationCache, VoiceBridgeSession
from app.schemas.bridge import (
    BridgeOption,
    MobileQuestion,
    MobileState,
    PendingAnswer,
    WorkerQuestion,
    WorkerState,
)
from app.services.ai.base import (
    AIBudgetExceededError,
    AIConfigurationError,
    AIInvalidResponseError,
    AIRateLimitError,
    AIUnavailableError,
    CallContext,
)
from app.services.cases.service import CaseService

log = logging.getLogger("lextec.bridge")

LANGUAGES = {"de": "Deutsch", "en": "English", "ar": "العربية", "uk": "Українська"}
LANGUAGE_NAMES_DE = {"de": "Deutsch", "en": "Englisch", "ar": "Arabisch", "uk": "Ukrainisch"}
RTL = {"ar"}
CONNECTED_WITHIN_SECONDS = 12
ACTIVE_BASES = {
    "WAITING_FOR_CONNECTION",
    "WAITING_FOR_QUESTION",
    "QUESTION_ACTIVE",
    "AWAITING_WORKER_REVIEW",
}


class BridgeGone(AppError):
    status_code = 410
    code = "bridge_ended"


class BridgeUnauthorized(AppError):
    status_code = 401
    code = "bridge_unauthorized"


# ---- concurrency ---------------------------------------------------------------------------------------------------
# Desktop and phone poll the same session at the same time. Every state change of a session runs under one in-process
# lock (single API process) and starts from a fresh read, so two requests can never create two instances of the same
# question or translate it twice (the cause of the earlier IntegrityError / HTTP 500 → «Connection lost»).
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bridge-translate")
TRANSLATION_MAX_ATTEMPTS = 5  # per question instance (the first try counts)
TRANSLATION_MIN_INTERVAL_S = 3.0
LAST_SEEN_WRITE_EVERY_S = 3.0  # the heartbeat is a poll; do not write to the DB on every poll


def _lock_for(session_id: str) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(session_id, threading.RLock())


def _locked(fn):
    @wraps(fn)
    def inner(self, row, *a, **k):
        with _lock_for(row.id):
            self.s.refresh(row)
            return fn(self, row, *a, **k)

    return inner


TRANSLATION_HINTS = {
    "limit": "Das Tageslimit für KI-Aufrufe ist erreicht (AI_DAILY_REQUEST_LIMIT). Es wurde nichts an Gemini gesendet.",
    "rate_limited": "Gemini hat zu viele Anfragen gemeldet (Ratenlimit). Bitte kurz warten und erneut versuchen.",
    "unavailable": "Gemini ist gerade nicht erreichbar oder zu langsam. Bitte erneut versuchen.",
    "config": "Die Gemini-Konfiguration wurde abgelehnt (Schlüssel oder Modell). Bitte Konfiguration prüfen.",
    "invalid": "Die Übersetzung war nicht verwertbar (Format oder Zahlenprüfung). Bitte erneut versuchen.",
    "error": "Die Übersetzung ist fehlgeschlagen. Bitte erneut versuchen.",
}


def classify_translation_error(exc: Exception) -> str:
    if isinstance(exc, AIBudgetExceededError):
        return "limit"
    if isinstance(exc, AIRateLimitError):
        return "rate_limited"
    if isinstance(exc, AIConfigurationError):
        return "config"
    if isinstance(exc, AIUnavailableError):
        return "unavailable"
    if isinstance(exc, AIInvalidResponseError):
        return "invalid"
    return "error"


def _cache_key(text: str, src: str, dst: str) -> str:
    return hashlib.sha256(f"{src}>{dst}\n{text}".encode()).hexdigest()


def translate_cached(
    factory: sessionmaker[Session], ai: Any, texts: list[str], target: str, case_id: str
) -> list[str]:
    """DE -> target with a persistent cache. Own short sessions; the provider call happens outside any transaction.
    Cache writes tolerate concurrent writers (a duplicate key is simply ignored)."""
    out: dict[str, str] = {}
    missing: list[str] = []
    with factory() as s:
        for text in dict.fromkeys(texts):
            hit = s.get(TranslationCache, _cache_key(text, "de", target))
            if hit is not None:
                out[text] = hit.translated
            else:
                missing.append(text)
    if missing:
        translated = ai.translate(missing, "de", target, CallContext(case_id, "translate"))
        with factory() as s:
            for src, dst in zip(missing, translated, strict=True):
                out[src] = dst
                try:
                    with s.begin_nested():
                        s.add(
                            TranslationCache(
                                key=_cache_key(src, "de", target),
                                source_lang="de",
                                target_lang=target,
                                source_text=src,
                                translated=dst,
                            )
                        )
                except IntegrityError:
                    pass  # another request stored the same translation first
            s.commit()
    return [out[x] for x in texts]


def run_translation(
    factory: sessionmaker[Session], ai: Any, session_id: str, instance_id: str
) -> None:
    """Translate the current question of a session in the background and store the outcome (never raises)."""
    try:
        with factory() as s:
            row = s.get(VoiceBridgeSession, session_id)
            if (
                row is None
                or row.ended_at is not None
                or row.question_instance_id != instance_id
                or row.translation_status != "PENDING"
                or not row.question_json
            ):
                return
            snap, lang, case_id = dict(row.question_json), row.language or "de", row.case_id
        opts = snap.get("options", [])
        texts = [snap["question_de"]] + ([snap["why_de"]] if snap.get("why_de") else [])
        texts += [o["label_de"] for o in opts]
        result: dict | None = None
        code: str | None = None
        try:
            res = translate_cached(factory, ai, texts, lang, case_id)
            it = iter(res)
            q = next(it)
            why = next(it) if snap.get("why_de") else ""
            result = {"question": q, "why": why, "options": {o["value"]: next(it) for o in opts}}
        except Exception as exc:  # noqa: BLE001 - classified below, never silent, never a connection problem
            code = classify_translation_error(exc)
            log.warning("bridge translation failed: %s (%s)", code, type(exc).__name__)
        with _lock_for(session_id), factory() as s:
            row = s.get(VoiceBridgeSession, session_id)
            if (
                row is None
                or row.ended_at is not None
                or row.question_instance_id != instance_id
                or row.translation_status != "PENDING"
            ):
                return  # the question moved on meanwhile
            if result is not None:
                row.translation_json = result
                row.translation_status = "OK"
                row.translation_error = None
            else:
                row.translation_status = "FAILED"
                row.translation_error = TRANSLATION_HINTS.get(code or "error")
                qj = dict(row.question_json or {})
                qj["tr_error_code"] = code
                row.question_json = qj
            row.rev += 1
            s.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("bridge translation worker error: %s", type(exc).__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _private_v4(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and a.is_private and not a.is_loopback and not a.is_link_local


def lan_candidates() -> list[str]:
    """Private IPv4 addresses of this machine, the one used for the default route first.

    The default-route address (what the OS would use to reach the internet/router) is the best guess for the Wi-Fi/Ethernet
    the phone is on; virtual adapters (WSL/Hyper-V, Docker, VPN) usually come after it. The list is only a proposal: the
    desktop shows all of them and lets the social worker pick or type the right one."""
    found: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(
                ("10.255.255.255", 1)
            )  # no packet is sent; selects the default-route interface
            found.append(sock.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(str(info[4][0]))
    except OSError:
        pass
    out: list[str] = []
    for ip in found:
        if _private_v4(ip) and ip not in out:
            out.append(ip)
    return out


def lan_ip() -> str | None:
    c = lan_candidates()
    return c[0] if c else None


def canonical_german(fd: Any, kind: str, value: str | None) -> tuple[str, str]:
    """Validate a structured value against the fact definition. Returns (german text for the case, readable form).

    The German text is what the existing deterministic parser understands («Ja», «Nein», a date, a number,
    the enum label), so no re-translation and no AI is involved for structured answers."""
    v = (value or "").strip()
    t = fd.data_type
    if t == "boolean":
        if v not in {"true", "false"}:
            raise AppError("Ungültige Antwort.", code="invalid_value")
        return ("Ja" if v == "true" else "Nein"), ("Ja" if v == "true" else "Nein")
    if t == "date":
        try:
            d = date.fromisoformat(v)
        except ValueError:
            raise AppError("Ungültiges Datum.", code="invalid_value") from None
        return d.isoformat(), d.strftime("%d.%m.%Y")
    if t == "integer":
        digits = v.replace("'", "").replace(" ", "")
        if not digits.isdigit() or len(digits) > 9:
            raise AppError("Ungültige Zahl.", code="invalid_value")
        return str(int(digits)), str(int(digits))
    if t == "enum":
        if v not in fd.enum_values:
            raise AppError("Ungültige Auswahl.", code="invalid_value")
        label = fd.enum_labels_de.get(v, v)
        return label, label
    if not v:
        raise AppError("Bitte eine Antwort eingeben.", code="invalid_value")
    return v, v


class BridgeService:
    def __init__(
        self,
        session: Session,
        cases: CaseService,
        *,
        ttl_minutes: int = 120,
        session_factory: sessionmaker[Session] | None = None,
        inline_translation: bool = False,
    ):
        self.s = session
        self.cases = cases
        self.ttl = timedelta(minutes=ttl_minutes)
        self.factory = session_factory
        self.inline = inline_translation  # tests: translate synchronously (deterministic)

    # ------------------------------------------------------------------ lookup -------------
    def active_for_case(self, case_id: str) -> VoiceBridgeSession | None:
        row = self.s.scalars(
            select(VoiceBridgeSession)
            .where(VoiceBridgeSession.case_id == case_id, VoiceBridgeSession.ended_at.is_(None))
            .order_by(VoiceBridgeSession.created_at.desc())
        ).first()
        if row is not None and self._expired(row):
            self._end(row, "EXPIRED")
            self.s.commit()
            return None
        return row

    def by_token(self, token: str | None) -> VoiceBridgeSession:
        if not token or len(token) > 200:
            raise BridgeUnauthorized("Ungültiger Zugangsschlüssel.")
        row = self.s.scalars(
            select(VoiceBridgeSession).where(VoiceBridgeSession.token_hash == hash_token(token))
        ).first()
        if row is None:
            raise BridgeUnauthorized("Ungültiger Zugangsschlüssel.")
        if row.ended_at is None and self._expired(row):
            self._end(row, "EXPIRED")
            self.s.commit()
        if row.ended_at is not None:
            raise BridgeGone("Diese Sitzung ist beendet.")
        return row

    def _expired(self, row: VoiceBridgeSession) -> bool:
        exp = _aware(row.expires_at)
        return exp is not None and exp <= _now()

    def _end(self, row: VoiceBridgeSession, status: str) -> None:
        row.status = status
        row.ended_at = _now()
        row.join_token = None
        row.rev += 1

    # ------------------------------------------------------------------ lifecycle ----------
    def start(self, case_id: str) -> tuple[VoiceBridgeSession, str]:
        case = self.cases.get_case(case_id)
        if case.status == "CLOSED":
            raise ConflictError("Der Fall ist abgeschlossen. Bitte zuerst wieder öffnen.")
        old = self.active_for_case(case_id)
        if old is not None:
            self._end(old, "COMPLETED")  # one active bridge per case: the old QR stops working
        token = secrets.token_urlsafe(32)
        row = VoiceBridgeSession(
            case_id=case_id,
            token_hash=hash_token(token),
            join_token=token,
            status="WAITING_FOR_CONNECTION",
            expires_at=_now() + self.ttl,
        )
        self.s.add(row)
        self.s.commit()
        return row, token

    @_locked
    def end(self, row: VoiceBridgeSession) -> None:
        if row.ended_at is None:
            self._end(row, "COMPLETED")
            self.s.commit()

    @_locked
    def set_paused(self, row: VoiceBridgeSession, paused: bool) -> None:
        if row.paused != paused:
            row.paused = paused
            row.rev += 1
            self.s.commit()

    @_locked
    def set_language(self, row: VoiceBridgeSession, language: str) -> None:
        if language not in LANGUAGES:
            raise AppError("Diese Sprache wird nicht unterstützt.", code="unsupported_language")
        if row.language != language:
            row.language = language
            row.connected_at = row.connected_at or _now()
            row.join_token = None  # the QR is no longer needed once the phone is connected
            row.status = "WAITING_FOR_QUESTION"
            row.question_instance_id = (
                None  # force a fresh (translated) instance in the new language
            )
            row.question_fact_id = None
            row.rev += 1
            self.s.commit()
        self.sync(row)

    # ------------------------------------------------------------------ translation --------
    def _begin_translation(self, row: VoiceBridgeSession) -> bool:
        """Mark the question as «translation pending». Returns True if a job must be dispatched after the commit."""
        row.translation_json = None
        row.translation_error = None
        if row.language in (None, "de"):
            row.translation_status = "NONE"
            return False
        qj = dict(row.question_json or {})
        qj["tr_attempts"] = int(qj.get("tr_attempts", 0)) + 1
        qj["tr_last"] = time.time()
        qj.pop("tr_error_code", None)
        row.question_json = qj
        row.translation_status = "PENDING"
        return True

    def _dispatch(self, row: VoiceBridgeSession) -> None:
        """Run the translation OUTSIDE the request that noticed the new question (a slow Gemini call must never
        block a poll). Tests translate inline."""
        if self.factory is None or not row.question_instance_id:
            return
        args = (self.factory, self.cases.ai, row.id, row.question_instance_id)
        if self.inline:
            run_translation(*args)
            self.s.refresh(row)
        else:
            _POOL.submit(run_translation, *args)

    # ------------------------------------------------------------------ sync ---------------
    def _snapshot(self, nq: Any) -> dict:
        fd = self.cases._fact_def(nq.fact_id)
        options: list[dict] = []
        if fd is not None and fd.data_type == "enum":
            options = [
                {"value": v, "label_de": nq.enum_labels_de.get(v) or fd.enum_labels_de.get(v, v)}
                for v in fd.enum_values
            ]
        return {
            "fact_id": nq.fact_id,
            "question_de": nq.question_de,
            "why_de": nq.why_needed_de or "",
            "data_type": fd.data_type if fd is not None else "string",
            "options": options,
            "optional": bool(nq.optional),
        }

    def _clear_question(self, row: VoiceBridgeSession) -> None:
        row.question_instance_id = None
        row.question_fact_id = None
        row.question_json = None
        row.translation_json = None
        row.translation_status = "NONE"
        row.translation_error = None
        self._clear_answer(row)

    @staticmethod
    def _clear_answer(row: VoiceBridgeSession) -> None:
        row.answer_json = None
        row.answer_request_id = None
        row.answer_submitted_at = None

    @_locked
    def sync(self, row: VoiceBridgeSession) -> VoiceBridgeSession:
        """Align the bridge with the engine's current question. Idempotent; the only place questions change.

        Runs under the session lock from a fresh read: desktop and phone polls are serialised, so a new question is
        created exactly once. Only a state change writes to the database."""
        if row.ended_at is not None:
            return row
        if self._expired(row):
            self._end(row, "EXPIRED")
            self.s.commit()
            return row
        before = (row.status, row.question_instance_id, row.question_fact_id)
        dispatch = False
        if row.language is None:
            row.status = "WAITING_FOR_CONNECTION"
        else:
            case = self.s.get(Case, row.case_id)
            if case is None or case.status == "CLOSED":
                self._end(row, "COMPLETED")
                self.s.commit()
                return row
            decision = self.cases.current_decision(row.case_id)
            nq = decision.next_question if decision is not None else None
            safety = getattr(decision, "safety", None) if decision is not None else None
            urgent = bool(safety is not None and getattr(safety, "state", None) == "IMMEDIATE")
            fact_id = nq.fact_id if (nq is not None and not urgent) else None
            if fact_id is None:
                if row.question_fact_id is not None:
                    self._clear_question(row)
                row.status = "WAITING_FOR_QUESTION"
            elif fact_id != row.question_fact_id:
                # new question (also when the desk answered/skipped it meanwhile): a pending phone answer for the
                # old question is superseded, never applied to the new one
                self._clear_answer(row)
                row.question_fact_id = fact_id
                row.question_instance_id = uuid.uuid4().hex
                row.question_json = self._snapshot(nq)
                dispatch = self._begin_translation(row)
                row.status = "QUESTION_ACTIVE"
            elif row.status not in ("QUESTION_ACTIVE", "AWAITING_WORKER_REVIEW"):
                row.status = "QUESTION_ACTIVE"
        changed = (row.status, row.question_instance_id, row.question_fact_id) != before
        if changed:
            row.rev += 1
            self.s.commit()
        else:
            self.s.rollback()  # nothing to write: end the read transaction (no lock held on the database file)
        if dispatch:
            self._dispatch(row)
        return row

    # ------------------------------------------------------------------ phone side ---------
    def touch(self, row: VoiceBridgeSession) -> None:
        """Heartbeat = the phone's poll. Written at most every few seconds and with a targeted UPDATE (it must never
        overwrite fields another request just changed)."""
        seen = _aware(row.last_seen_at)
        now = _now()
        if seen is not None and (now - seen).total_seconds() < LAST_SEEN_WRITE_EVERY_S:
            return
        self.s.execute(
            update(VoiceBridgeSession)
            .where(VoiceBridgeSession.id == row.id)
            .values(last_seen_at=now)
        )
        self.s.commit()

    def effective_status(self, row: VoiceBridgeSession) -> str:
        if row.paused and row.status in ACTIVE_BASES and row.status != "WAITING_FOR_CONNECTION":
            return "PAUSED"
        return row.status

    def mobile_state(self, row: VoiceBridgeSession) -> MobileState:
        status = self.effective_status(row)
        q = None
        notice = None
        if status == "QUESTION_ACTIVE" and row.question_json:
            snap = row.question_json
            tr = row.translation_json
            if row.language in (None, "de") or row.translation_status == "NONE":
                q = MobileQuestion(
                    instance_id=row.question_instance_id or "",
                    data_type=snap["data_type"],
                    text=snap["question_de"],
                    why=snap.get("why_de", ""),
                    options=[
                        BridgeOption(value=o["value"], label=o["label_de"]) for o in snap["options"]
                    ],
                    optional=snap.get("optional", False),
                )
            elif row.translation_status == "OK" and tr:
                q = MobileQuestion(
                    instance_id=row.question_instance_id or "",
                    data_type=snap["data_type"],
                    text=tr["question"],
                    why=tr.get("why", ""),
                    options=[
                        BridgeOption(
                            value=o["value"], label=tr["options"].get(o["value"], o["label_de"])
                        )
                        for o in snap["options"]
                    ],
                    optional=snap.get("optional", False),
                )
            elif row.translation_status == "PENDING":
                notice = "translation_pending"  # being prepared: a normal short wait, not an error
            else:
                notice = (
                    "translation_failed"  # never show an untranslated or wrong-language question
                )
        return MobileState(
            status=status,
            rev=row.rev,
            language=row.language,
            rtl=row.language in RTL,
            question=q,
            notice=notice,
        )  # type: ignore[arg-type]

    @_locked
    def submit(
        self,
        row: VoiceBridgeSession,
        instance_id: str,
        request_id: str,
        kind: str,
        value: str | None,
    ) -> None:
        if row.answer_request_id == request_id:
            return  # the very same request again: idempotent, nothing changes
        if row.paused or row.status != "QUESTION_ACTIVE" or not row.question_json:
            raise ConflictError(
                "Im Moment kann keine Antwort entgegengenommen werden.", code="not_accepting"
            )
        if instance_id != row.question_instance_id:
            raise ConflictError("Diese Frage ist nicht mehr aktuell.", code="stale_question")
        fd = self.cases._fact_def(row.question_json["fact_id"])
        if fd is None:
            raise AppError("Unbekannte Frage.", code="unknown_fact")
        lang = row.language or "de"
        payload: dict[str, Any]
        if kind == "unknown":
            payload = {
                "kind": "unknown",
                "original": "unknown",
                "german": "Weiss nicht",
                "status": "STRUCTURED",
            }
        elif fd.data_type == "string":
            text = (value or "").strip()
            if not text:
                raise AppError("Bitte eine Antwort eingeben.", code="invalid_value")
            german, status = text, "ORIGINAL_GERMAN"
            if lang != "de":
                try:
                    german = self.cases.ai.translate(
                        [text], lang, "de", CallContext(row.case_id, "translate_answer")
                    )[0]
                    status = "MACHINE"
                except Exception as exc:  # noqa: BLE001
                    log.warning("bridge answer translation failed: %s", type(exc).__name__)
                    german, status = "", "FAILED"
            payload = {"kind": "text", "original": text, "german": german, "status": status}
        else:
            german, readable = canonical_german(fd, kind, value)
            payload = {
                "kind": "value",
                "original": readable,
                "value": value,
                "german": german,
                "status": "STRUCTURED",
            }
        row.answer_json = payload
        row.answer_request_id = request_id
        row.answer_submitted_at = _now()
        row.status = "AWAITING_WORKER_REVIEW"
        row.rev += 1
        self.s.commit()

    # ------------------------------------------------------------------ worker side --------
    @_locked
    def accept(
        self, row: VoiceBridgeSession, corrected_value: str | None, corrected_text_de: str | None
    ) -> None:
        if row.status != "AWAITING_WORKER_REVIEW" or not row.answer_json or not row.question_json:
            raise ConflictError("Es liegt keine Antwort zur Prüfung vor.", code="nothing_to_review")
        ans = row.answer_json
        fact_id = row.question_json["fact_id"]
        fd = self.cases._fact_def(fact_id)
        if fd is None:
            raise AppError("Unbekannte Frage.", code="unknown_fact")
        if ans["kind"] == "unknown" and not corrected_value and not corrected_text_de:
            self.cases.answer_unknown(row.case_id, fact_id)
        else:
            if ans["kind"] == "text" or (ans["kind"] == "unknown" and corrected_text_de):
                content = (corrected_text_de or ans["german"] or "").strip()
                if not content:
                    raise AppError(
                        "Die maschinelle Übersetzung fehlt. Bitte die deutsche Fassung selbst eintragen.",
                        code="translation_required",
                    )
            elif corrected_value is not None:
                content, _ = canonical_german(fd, "value", corrected_value)
            else:
                content = ans["german"]
            self.cases.add_message(
                row.case_id,
                content,
                MessageKind.ANSWER,
                fact_id,
                origin="VOICE_BRIDGE",
                original_text=ans["original"]
                if row.language != "de" or ans["kind"] == "text"
                else None,
                original_language=row.language,
            )
            self.cases.analyze_pending(row.case_id)
        self._clear_question(row)
        row.status = "WAITING_FOR_QUESTION"
        row.rev += 1
        self.s.commit()
        self.sync(row)

    @_locked
    def reask(self, row: VoiceBridgeSession) -> None:
        if row.status != "AWAITING_WORKER_REVIEW":
            raise ConflictError("Es liegt keine Antwort zur Prüfung vor.", code="nothing_to_review")
        self._clear_answer(row)
        row.question_instance_id = (
            uuid.uuid4().hex
        )  # a new instance: late retries of the old one are stale
        row.status = "QUESTION_ACTIVE"
        row.rev += 1
        self.s.commit()

    @_locked
    def skip(self, row: VoiceBridgeSession) -> None:
        if not row.question_fact_id:
            raise ConflictError("Es gibt keine aktive Frage.", code="no_question")
        self.cases.defer_fact(
            row.case_id, row.question_fact_id, "Über die Sprachbrücke übersprungen"
        )
        self.sync(row)

    @_locked
    def retry_translation(self, row: VoiceBridgeSession) -> None:
        if not row.question_json or row.status != "QUESTION_ACTIVE":
            raise ConflictError("Es gibt keine aktive Frage.", code="no_question")
        if row.translation_status != "FAILED":
            return  # pending or fine: nothing to retry
        qj = row.question_json
        if int(qj.get("tr_attempts", 0)) >= TRANSLATION_MAX_ATTEMPTS:
            raise ConflictError(
                "Die Übersetzung wurde mehrfach versucht. Bitte erklären Sie die Frage selbst oder ziehen Sie eine Dolmetschperson bei.",
                code="retry_limit",
            )
        if time.time() - float(qj.get("tr_last", 0)) < TRANSLATION_MIN_INTERVAL_S:
            raise ConflictError("Bitte einen Moment warten.", code="retry_too_soon")
        self._begin_translation(row)
        row.rev += 1
        self.s.commit()
        self._dispatch(row)

    def worker_state(
        self, row: VoiceBridgeSession | None, *, public_base_url: str | None
    ) -> WorkerState:
        if row is None:
            return WorkerState(active=False)
        seen = _aware(row.last_seen_at)
        connected = bool(seen and (_now() - seen).total_seconds() <= CONNECTED_WITHIN_SECONDS)
        q = None
        if row.question_json and row.question_instance_id:
            snap, tr = row.question_json, row.translation_json
            translated = None
            if tr:
                translated = tr["question"]
            q = WorkerQuestion(
                instance_id=row.question_instance_id,
                fact_id=snap["fact_id"],
                text_de=snap["question_de"],
                text_translated=translated,
                translation_status=row.translation_status,  # type: ignore[arg-type]
                translation_error=row.translation_error,
                translation_error_code=(row.question_json or {}).get("tr_error_code"),
                data_type=snap["data_type"],
                options=[
                    BridgeOption(
                        value=o["value"],
                        label=(tr or {}).get("options", {}).get(o["value"], o["label_de"]),
                    )
                    for o in snap["options"]
                ],
                options_de=[
                    BridgeOption(value=o["value"], label=o["label_de"]) for o in snap["options"]
                ],
            )
        ans = None
        if row.answer_json:
            a = row.answer_json
            ans = PendingAnswer(
                kind=a["kind"],
                original=a["original"],
                language=row.language or "de",
                german=a["german"],
                machine_translated=a["status"] == "MACHINE",
                translation_status=a["status"],
                submitted_at=(_aware(row.answer_submitted_at) or _now()).isoformat(),
            )
        return WorkerState(
            active=True,
            session_id=row.id,
            status=self.effective_status(row),  # type: ignore[arg-type]
            rev=row.rev,
            language=row.language,
            language_name=LANGUAGE_NAMES_DE.get(row.language or ""),
            phone_connected=connected,
            last_seen_seconds=int((_now() - seen).total_seconds()) if seen else None,
            join_token=row.join_token,
            lan_ip=lan_ip(),
            lan_candidates=lan_candidates(),
            public_base_url=public_base_url,
            expires_at=(_aware(row.expires_at) or _now()).isoformat(),
            question=q,
            answer=ans,
        )


def ensure_case(svc: CaseService, case_id: str) -> None:
    if svc.s.get(Case, case_id) is None:
        raise NotFoundError("Fall nicht gefunden.")
