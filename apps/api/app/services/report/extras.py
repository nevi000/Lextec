"""Collect the report-only data (chronology, conversation, location) from the stored case. Pure and deterministic:
only what is stored is used; nothing is invented, no AI call."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.schemas.briefing import ChronologyEvent, ConversationItem, ReportExtras
from app.schemas.decision import DecisionResult
from app.services.knowledge.loader import KnowledgeBase
from app.services.referrals.network import Location
from app.services.safety.assess import location_from_facts

try:
    ZURICH = ZoneInfo("Europe/Zurich")
except (
    Exception
):  # tzdata missing (Windows without the tzdata package): fall back to UTC and say so
    ZURICH = UTC

MAX_TEXT = 700
ORIGIN_DE = {
    "AI_EXTRACTED": "aus der Schilderung (KI), nicht bestätigt",
    "USER_ANSWER": "Angabe (Antwort erfasst)",
    "USER_CORRECTION": "von der Sozialarbeiterin korrigiert",
}


def local(dt: datetime) -> datetime:
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(ZURICH)


def fmt_dt(dt: datetime) -> str:
    return local(dt).strftime("%d.%m.%Y %H:%M")


def _date(value) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def build_extras(
    *,
    kb: KnowledgeBase,
    decision: DecisionResult,
    rows: list,
    messages: list,
    active_issue_ids: list[str],
    facts_state: dict,
    ai_name: str,
    today: date,
) -> ReportExtras:
    defs = {f.id: f for i in kb.issues.values() for f in i.facts}
    loc: Location = location_from_facts(kb, active_issue_ids, facts_state)

    events: list[ChronologyEvent] = []
    for r in rows:
        d = defs.get(r.fact_id)
        if d is None or d.data_type != "date" or r.status != "KNOWN":
            continue
        day = _date(r.value)
        if day is None:
            continue
        source = "bestätigt" if r.confirmed else ORIGIN_DE.get(r.origin, r.origin)
        events.append(
            ChronologyEvent(
                date=day.isoformat(), label_de=d.label_de, source_de=source, future=day > today
            )
        )
    for m in messages:
        label = {
            "DESCRIPTION": "Schilderung erfasst",
            "ANSWER": "Antwort erfasst",
            "NOTE": "Ergänzung erfasst",
        }.get(m.kind, "Eingabe erfasst")
        events.append(
            ChronologyEvent(
                date=local(m.created_at).date().isoformat(),
                label_de=label,
                source_de=f"Eingabe {fmt_dt(m.created_at)}",
            )
        )
    events.sort(key=lambda e: (e.date or "9999", e.label_de))

    row_by_id = {r.fact_id: r for r in rows}
    conv: list[ConversationItem] = []
    for m in messages:
        text = m.content.strip()
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT].rstrip() + " …"
        question = None
        status = None
        if m.kind == "ANSWER" and m.answers_fact_id:
            fd = defs.get(m.answers_fact_id)
            question = fd.question_de if fd else m.answers_fact_id
            fr = row_by_id.get(m.answers_fact_id)
            if fr is not None and fr.status == "UNKNOWN":
                status = "gefragt, Person weiss es nicht"
        conv.append(
            ConversationItem(
                kind=m.kind,
                at=fmt_dt(m.created_at),
                question_de=question,
                text=text,
                status_de=status,
            )
        )

    return ReportExtras(
        location_canton=loc.canton,
        location_municipality=loc.municipality,
        safety=decision.safety,
        referrals=decision.referrals,
        chronology=events,
        conversation=conv,
        documents=[],  # no upload support yet: never invent documents
        extraction_model=ai_name,
        kb_status="LEGALLY_REVIEWED"
        if active_issue_ids
        and all(
            kb.issues[i].content_status == "LEGALLY_REVIEWED"
            for i in active_issue_ids
            if i in kb.issues
        )
        else "DRAFT",
        inputs_count=len(messages),
        effective_action=decision.effective_action,
    )
