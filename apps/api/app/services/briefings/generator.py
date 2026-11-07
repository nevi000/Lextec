"""Builds a CaseBriefing from validated structured state. No LLM involved: nothing invented."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.domain.enums import Action, FactOrigin, FactStatus, IssueStatus
from app.models.tables import Case, CaseFact, CaseIssue, Handover
from app.schemas.briefing import (
    AuthorityOut,
    BriefingDecision,
    BriefingFact,
    BriefingHandover,
    BriefingIssue,
    BriefingOverview,
    BriefingProfessional,
    BriefingRisk,
    BriefingSource,
    BriefingUncertainty,
    BriefingUnsupportedIssue,
    CaseBriefing,
    DerivedRow,
    IssueBriefing,
    IssueGroup,
    IssueRow,
    ReviewPointOut,
)
from app.schemas.decision import URGENCY_LABEL_DE, DecisionResult
from app.services.knowledge.loader import KnowledgeBase
from app.services.knowledge.schema import IssueDefinition
from app.services.sources.registry import SourceRegistry

PROVENANCE = {
    FactOrigin.AI_EXTRACTED.value: "REPORTED_BY_AI_EXTRACTION",
    FactOrigin.USER_ANSWER.value: "ANSWER_RECORDED",
    FactOrigin.USER_CORRECTION.value: "CORRECTED_BY_USER",
}

# answer entered by the client on the phone (Sprachbrücke), accepted by the social worker; no legal verification implied
BRIDGE_LABEL_DE = "Angabe der ratsuchenden Person, via Sprachbrücke erfasst und durch die Sozialarbeiterin bestätigt"

EVIDENCE_LABEL_DE = {
    "DOCUMENTED": "Dokumentarisch belegt",
    "CONFIRMED": "Von der Sozialarbeiterin bestätigt oder korrigiert",
    "STATED": "Von der Sozialarbeiterin als Antwort erfasst",
    "AI_EXTRACTED": "Von der KI aus der Schilderung extrahiert (nicht bestätigt)",
    "SYSTEM_DERIVED": "Systemseitig abgeleitet",
    "UNKNOWN": "Gefragt, der Klientin unbekannt",
    "UNCLEAR": "Unklar oder widersprüchlich",
    "NOT_ASKED": "Noch ungeklärt (nicht gefragt)",
}

DERIVED_LABEL_DE = {
    "days_since_earliest_receipt": "Tage seit dem frühesten bekannten Empfangshinweis",
    "days_until_termination_date": "Tage bis zum angegebenen Kündigungstermin",
}


def display_value(value) -> str:
    if value is True:
        return "Ja"
    if value is False:
        return "Nein"
    if value is None:
        return "–"
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):  # ISO date -> Swiss format
        y, m, d = text.split("-")
        return f"{d}.{m}.{y}"
    return text


def evidence_level(row: CaseFact | None) -> str:
    if row is None or row.status == FactStatus.MISSING.value:
        return "NOT_ASKED"
    if row.status == FactStatus.UNKNOWN.value:
        return "UNKNOWN"
    if row.status in (FactStatus.AMBIGUOUS.value, FactStatus.CONTRADICTORY.value):
        return "UNCLEAR"
    if row.documented:
        return "DOCUMENTED"
    if row.confirmed or row.origin == FactOrigin.USER_CORRECTION.value:
        return "CONFIRMED"
    if row.origin == FactOrigin.USER_ANSWER.value:
        return "STATED"
    return "AI_EXTRACTED"


def next_steps_for(decision: DecisionResult, kb: KnowledgeBase) -> list[str]:
    pros = [
        kb.professionals[p].label_de
        for p in decision.recommended_professionals
        if p in kb.professionals
    ]
    steps: list[str] = []
    if decision.action == Action.ESCALATE:
        who = ", ".join(pros) if pros else "eine geeignete Fachperson"
        urgency = (
            f" (Dringlichkeit: {URGENCY_LABEL_DE[decision.max_urgency]})"
            if decision.max_urgency
            else ""
        )
        steps.append(
            f"Fall an {who} übergeben{urgency}. Die Übergabe ist nur empfohlen, nicht erfolgt."
        )
        steps.append(
            "Dieses Briefing und die zugrunde liegenden Angaben der Fachperson zur Verfügung stellen."
        )
        for r in decision.related_routes:
            steps.append(f"Weiterleitung: {r.title_de}. {r.note_de}")
        if decision.missing_facts:
            steps.append("Wenn möglich, die offenen Angaben vor der Übergabe klären.")
    elif decision.action == Action.ASK:
        steps.append("Offene Angaben mit der ratsuchenden Person klären.")
        for m in decision.missing_facts[:3]:
            steps.append(f"Nachfragen: {m.question_de}")
    else:
        steps.append("Angaben mit der ratsuchenden Person durchgehen und bei Bedarf korrigieren.")
        steps.append("Briefing prüfen und für den nächsten Bearbeitungsschritt verwenden.")
        steps.append("Hinweis: Das System gibt keine verbindliche Rechtsauskunft.")
    return steps


def _authority(kb: KnowledgeBase, aid: str) -> AuthorityOut | None:
    a = kb.authorities.get(aid)
    if a is None:
        return None
    note = (
        f"Kontaktdaten und Kosten geprüft am {a.verified_at}."
        if a.contact_verified
        else "Kontaktdaten, Öffnungszeiten und Kosten sind NICHT verifiziert. Vor der Weitergabe auf der "
        "offiziellen Seite prüfen."
    )
    return AuthorityOut(
        id=a.id,
        name_de=a.name_de,
        purpose_de=a.purpose_de,
        cost_de=a.cost_de,
        scope_de=a.scope_de,
        source_note_de=a.source_note_de,
        url_hint=a.url_hint,
        contact_verified=a.contact_verified,
        verified_at=a.verified_at,
        verification_note_de=note,
    )


def _relevance(fd, status: FactStatus, required_now: dict) -> str:
    """Maps stored fact state + knowledge-base applicability to the report's meaning (no new legal criteria)."""
    if status == FactStatus.KNOWN:
        return "KNOWN"
    if status == FactStatus.UNKNOWN:
        return "ASKED_UNKNOWN"
    if status == FactStatus.CONTRADICTORY:
        return "CONTRADICTORY"
    if status == FactStatus.AMBIGUOUS:
        return "UNCLEAR"
    if status == FactStatus.NOT_APPLICABLE:
        return "NOT_APPLICABLE"
    m = required_now.get(fd.id)
    if m is not None:
        return "DEFERRED" if m.deferred else "MISSING_REQUIRED"
    if fd.required_if is not None and not fd.required:
        return "NOT_APPLICABLE"  # condition of the knowledge base is not met (e.g. no family home)
    return "OPTIONAL_UNANSWERED"


def _issue_briefing(
    kb: KnowledgeBase,
    issue: IssueDefinition,
    rows: dict[str, CaseFact],
    decision: DecisionResult,
    case: Case,
    bridge_message_ids: frozenset[str] = frozenset(),
) -> IssueBriefing | None:
    prof = issue.briefing_profile
    if prof is None:
        return None
    defs = {f.id: f for f in issue.facts}
    required_now = {
        m.fact_id: m for m in decision.missing_facts
    }  # required (or conditionally required) and open
    groups: list[IssueGroup] = []
    unknown_facts: list[str] = []
    for g in prof.groups:
        out_rows: list[IssueRow] = []
        for fid in g.fact_ids:
            fd = defs[fid]
            row = rows.get(fid)
            status = FactStatus(row.status) if row else FactStatus.MISSING
            level = evidence_level(row)
            if status == FactStatus.KNOWN and row is not None:
                shown = fd.enum_labels_de.get(str(row.value), display_value(row.value))
            elif status == FactStatus.UNKNOWN:
                shown = "Unbekannt"
                unknown_facts.append(fd.label_de)
            else:
                shown = "–"
            relevance = _relevance(fd, status, required_now)
            note = (
                fd.true_value_note_de
                if status == FactStatus.KNOWN and row is not None and row.value is True
                else None
            ) or None
            out_rows.append(
                IssueRow(
                    relevance=relevance,
                    note_de=note,
                    fact_id=fid,
                    label_de=fd.label_de,
                    value_display=shown,
                    status=status,
                    evidence_level=level,  # type: ignore[arg-type]
                    evidence_label_de=BRIDGE_LABEL_DE
                    if row is not None
                    and row.source_message_id in bridge_message_ids
                    and level in ("STATED", "CONFIRMED")
                    else EVIDENCE_LABEL_DE[level],
                    evidence_quote=row.evidence_quote
                    if row and status == FactStatus.KNOWN
                    else None,
                )
            )
        groups.append(IssueGroup(id=g.id, title_de=g.title_de, rows=out_rows))

    derived = [
        DerivedRow(
            id=k,
            label_de=DERIVED_LABEL_DE.get(k, k),
            value=v,
            note_de="Systemseitig aus den Angaben abgeleitet, nur für die interne Dringlichkeit. Kein Fristende.",
        )
        for k, v in decision.derived_values.items()
    ]
    mine = [t for t in decision.triggered_rules if t.scope != "ISSUE" or t.issue_id == issue.id]
    review: list[ReviewPointOut] = []
    if not decision.statements_suppressed:
        review += [
            ReviewPointOut(text_de=p.text_de, source_ids=p.source_ids) for p in prof.review_points
        ]
        review += [
            ReviewPointOut(text_de=f.result_de, source_ids=f.legal_source_ids, triggered=True)
            for f in decision.legal_findings
            if f.issue_id == issue.id
        ]
    authorities = [a for aid in prof.authority_ids if (a := _authority(kb, aid)) is not None]
    return IssueBriefing(
        issue_id=issue.id,
        title_de=issue.title_de,
        intro_de=prof.intro_de,
        canton=issue.canton,
        concern_de=case.summary or issue.title_de,
        groups=groups,
        derived=derived,
        triggered_rules=mine,
        max_urgency=decision.max_urgency,
        max_urgency_label_de=URGENCY_LABEL_DE[decision.max_urgency]
        if decision.max_urgency
        else None,
        urgency_note_de=(
            "Interne Dringlichkeitsbewertung nach Produktschwellen (z. B. 20 Tage, 60 Tage). Das sind "
            "Produktentscheide und keine gesetzlichen Fristen. Das System nennt kein Fristende; Berechnung "
            "und Beurteilung der Frist erfolgen durch die Fachperson."
        ),
        open_questions=[m.question_de for m in decision.missing_facts],
        unknown_facts=unknown_facts,
        documents_to_request=prof.documents_to_request,
        review_points=review,
        authorities=authorities,
        statements_suppressed=decision.statements_suppressed,
    )


def build_briefing(
    *,
    kb: KnowledgeBase,
    case: Case,
    issues: list[CaseIssue],
    facts: list[CaseFact],
    message_count: int,
    decision: DecisionResult,
    handover: Handover | None,
    ai_external: bool,
    registry: SourceRegistry | None = None,
    bridge_message_ids: frozenset[str] = frozenset(),
) -> CaseBriefing:
    registry = registry or SourceRegistry(kb)
    now = datetime.now(UTC)
    rows = {f.fact_id: f for f in facts}

    legal_areas: list[BriefingIssue] = []
    unsupported: list[BriefingUnsupportedIssue] = []
    statuses: set[str] = set()
    issue_briefings: list[IssueBriefing] = []
    for iss in issues:
        if (
            iss.classification_status == IssueStatus.DETECTED
            and iss.issue_definition_id in kb.issues
        ):
            d = kb.issues[iss.issue_definition_id]
            statuses.add(d.content_status)
            legal_areas.append(
                BriefingIssue(
                    issue_id=d.id,
                    title_de=d.title_de,
                    legal_area=d.legal_area,
                    confidence=iss.confidence,
                    evidence=iss.evidence,
                    content_status=d.content_status,
                )
            )
            ib = _issue_briefing(kb, d, rows, decision, case, bridge_message_ids)
            if ib is not None:
                issue_briefings.append(ib)
        else:
            unsupported.append(
                BriefingUnsupportedIssue(description=iss.description, evidence=iss.evidence)
            )

    defs = {}
    for iss_def in kb.issues.values():
        for f in iss_def.facts:
            defs.setdefault(f.id, f)

    known: list[BriefingFact] = []
    uncertain: list[BriefingUncertainty] = []
    for f in facts:
        fd = defs.get(f.fact_id)
        label = fd.label_de if fd else f.fact_id
        if f.status == FactStatus.KNOWN:
            shown = (
                fd.enum_labels_de.get(str(f.value), display_value(f.value))
                if fd
                else display_value(f.value)
            )
            known.append(
                BriefingFact(
                    fact_id=f.fact_id,
                    label_de=label,
                    value=f.value,
                    value_display=shown,
                    origin=FactOrigin(f.origin),
                    provenance=PROVENANCE.get(f.origin, "REPORTED_BY_AI_EXTRACTION"),  # type: ignore[arg-type]
                    evidence_level=evidence_level(f),  # type: ignore[arg-type]
                    confirmed=f.confirmed,
                    documented=bool(f.documented),
                    evidence_quote=f.evidence_quote,
                    updated_at=getattr(f, "updated_at", None),
                )
            )
        elif f.status in (
            FactStatus.AMBIGUOUS.value,
            FactStatus.CONTRADICTORY.value,
            FactStatus.UNKNOWN.value,
        ):
            vals = [display_value(f.value)] if f.value is not None else []
            vals += [display_value(c.get("value")) for c in (f.conflicting_values or [])]
            uncertain.append(
                BriefingUncertainty(
                    fact_id=f.fact_id,
                    label_de=label,
                    status=FactStatus(f.status),
                    values=vals,
                    note=f.evidence_quote,
                )
            )

    # sources: legal findings, approved statements, profile review points, issue-level sources
    refs: dict[str, set[str]] = {}
    for iss in legal_areas:
        d = kb.issues[iss.issue_id]
        for sid in d.legal_source_ids:
            refs.setdefault(sid, set()).add(d.id)
    for lf in decision.legal_findings:
        for sid in lf.legal_source_ids:
            refs.setdefault(sid, set()).add(lf.rule_id)
    for st in decision.approved_statements:
        for sid in st.source_ids:
            refs.setdefault(sid, set()).add(st.rule_id)
    for ib in issue_briefings:
        for rp in ib.review_points:
            for sid in rp.source_ids:
                refs.setdefault(sid, set()).add(ib.issue_id)
    sources = [
        BriefingSource(source=s, referenced_by=sorted(by))
        for sid, by in refs.items()
        if (s := registry.get(sid)) is not None
    ]

    pros = [
        BriefingProfessional(
            id=p,
            label_de=kb.professionals[p].label_de,
            description_de=kb.professionals[p].description_de,
        )
        for p in decision.recommended_professionals
        if p in kb.professionals
    ]

    handover_view = None
    if handover is not None:
        notes = {
            "RECOMMENDED": "Übergabe empfohlen, noch nicht angefragt.",
            "HANDOFF_REQUESTED": "Übergabe wurde von der Fachperson als angefragt erfasst.",
            "HANDOFF_COMPLETED": "Übergabe wurde bestätigt: " + (handover.completion_note or ""),
        }
        handover_view = BriefingHandover(status=handover.status, note=notes[handover.status])  # type: ignore[arg-type]

    template = kb.templates.get("expert_briefing_v1")
    unreviewed = sorted(s for s in statuses if s != "LEGALLY_REVIEWED")
    kb_notice = (
        "Die verwendeten Wissensbasis-Inhalte sind nicht juristisch freigegeben "
        f"({', '.join(unreviewed)}). Das Law-Dossier ist keine endgültige Freigabe für den Einsatz mit echten "
        "Klienten; rechtliche Hinweise sind als Entwurf zu verstehen."
        if unreviewed
        else None
    )
    ai_notice = (
        "Extraktion mit externer KI (Gemini); Angaben wurden an einen externen Dienst übermittelt."
        if ai_external
        else "Extraktion im Mock-Modus (keine externe KI)."
    )

    return CaseBriefing(
        template_id=template.id if template else "expert_briefing_v1",
        section_order=template.sections if template else [],
        case_version=case.version,
        knowledge_base_version=decision.knowledge_base_version,
        knowledge_base_notice=kb_notice,
        ai_mode_notice=ai_notice,
        overview=BriefingOverview(
            case_display_id=case.display_id,
            title=case.title,
            summary=case.summary,
            message_count=message_count,
            action=decision.action,
            created_at=now,
        ),
        legal_areas=legal_areas,
        unsupported_issues=unsupported,
        known_facts=known,
        missing_information=decision.missing_facts,
        uncertainties=uncertain,
        legal_sources=sources,
        legal_risks=[
            BriefingRisk(
                rule_id=lf.rule_id,
                issue_id=lf.issue_id,
                result_code=lf.result_code,
                result_de=lf.result_de,
                source_ids=lf.legal_source_ids,
            )
            for lf in decision.legal_findings
        ],
        safety_state=decision.safety.state if decision.safety else "NONE",
        safety_flags=list(decision.safety.briefing_flags) if decision.safety else [],
        safety_signal_categories=sorted({x.category for x in decision.safety.signals})
        if decision.safety
        else [],
        recommended_referral_ids=[
            c.id for c in (decision.referrals.primary + decision.referrals.more)
        ]
        if decision.referrals
        else [],
        approved_statements=decision.approved_statements,
        related_routes=decision.related_routes,
        decision=BriefingDecision(
            action=decision.action,
            main_reason_code=decision.main_reason_code,
            reason_codes=decision.reason_codes,
            explanation_de=decision.explanation_de,
            rules_evaluated=len(decision.evaluated_rules),
            rules_triggered=decision.triggered_rule_ids,
            max_urgency=decision.max_urgency,
            max_urgency_label_de=URGENCY_LABEL_DE[decision.max_urgency]
            if decision.max_urgency
            else None,
        ),
        escalation_reasons=decision.triggered_rules,
        recommended_professionals=pros,
        handover=handover_view,
        next_steps=next_steps_for(decision, kb),
        issue_briefings=issue_briefings,
    )
