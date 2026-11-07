"""Case State -> Report View Model (the data contract of the Jinja templates).

    stored CaseBriefing (+ ReportExtras)  ->  build_view()  ->  dict  ->  expert_briefing.html.j2  ->  PDF

The adapter only re-arranges data that the backend already decided or stored. It contains NO decision logic:
the traffic light is a plain mapping of the backend's decision/urgency/safety state (never a second rule engine),
deadlines are never computed, missing data is marked as missing and never estimated.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.schemas.briefing import CaseBriefing, IssueBriefing
from app.schemas.decision import URGENCY_LABEL_DE
from app.services.knowledge.loader import KnowledgeBase
from app.services.report.extras import fmt_dt

SRC_OF_LEVEL = {
    "DOCUMENTED": "doc",
    "CONFIRMED": "confirmed",
    "STATED": "user",
    "AI_EXTRACTED": "ai",
    "SYSTEM_DERIVED": "derived",
}
NOTE_OF_LEVEL = {
    "UNKNOWN": "gefragt, unbekannt",
    "NOT_ASKED": "nicht erfragt",
    "UNCLEAR": "unklar oder widersprüchlich",
}
ACTION_LABEL = {
    "PROCEED": "Weiter bearbeiten",
    "ASK": "Rückfrage nötig",
    "ESCALATE": "Fachperson nötig",
    "IMMEDIATE_SAFETY_RESPONSE": "Akute Gefahr: Sicherheitsreaktion",
}
LEVEL_LABEL = {
    "ROT": "Sofort bearbeiten",
    "AMBER": "Bald bearbeiten",
    "GRUEN": "Ordentlich bearbeiten",
}
CONTACT_NOT_CAPTURED = "nicht erfasst"
UMLAUT_FIX = {
    "Zuerich": "Zürich",
    "moeglich": "möglich",
    "taeglich": "täglich",
    "Roeschibach": "Röschibach",
    "Neumuehle": "Neumühle",
    "Foerrlibuck": "Förrlibuck",
    "Aemtler": "Ämtler",
    "fuer": "für",
    "Schlichtungsbehoerde": "Schlichtungsbehörde",
    "Paritaetische": "Paritätische",
    "Gebuehr": "Gebühr",
    "Maengel": "Mängel",
    "Geschaeftsstelle": "Geschäftsstelle",
    "Beratungsangebot": "Beratungsangebot",
    "moegliche": "mögliche",
    "pruefen": "prüfen",
    "ueber": "über",
    "Kuendigung": "Kündigung",
    "muendlich": "mündlich",
    "haengigem": "hängigem",
    "Aufnahmestopp": "Aufnahmestopp",
}


def de(text: str | None) -> str | None:
    """The law team's contact file writes umlauts as ae/oe/ue; restore the common ones for display only."""
    if not text:
        return text
    for a, b in UMLAUT_FIX.items():
        text = text.replace(a, b)
    return text


# ----------------------------------------------------------------------------------------- traffic light
def traffic_light(b: CaseBriefing) -> dict[str, Any]:
    """Display mapping of the BACKEND's result. No thresholds, no own rules. Safety never maps lower than the
    backend's safety state; deviations from case_summary_v1.yaml are documented in docs/NEW_BRIEFING_INTEGRATION.md."""
    ex = b.extras
    action = b.decision.action.value
    urgency = b.decision.max_urgency
    safety = ex.safety.state if ex and ex.safety else "NONE"
    level = {"HIGH": "ROT", "MEDIUM": "AMBER", "LOW": "GRUEN"}.get(urgency or "", None)
    if level is None:
        level = "GRUEN" if action == "PROCEED" else "AMBER"
    if action in ("ESCALATE", "ASK") and level == "GRUEN":
        level = "AMBER"
    reasons: list[str] = []
    label = LEVEL_LABEL[level]
    if safety == "IMMEDIATE":
        level, label = "ROT", "Sofort handeln"
        reasons.append("Akute Gefahr erkannt (Sicherheitsreaktion)")
    elif safety == "HUMAN_CHECK":
        if level == "GRUEN":
            level, label = "AMBER", LEVEL_LABEL["AMBER"]
        reasons.append("Sicherheitshinweis: menschliche Abklärung nötig")
    elif safety == "UNCLEAR":
        reasons.append("Unklares Sicherheitssignal")
    if urgency:
        reasons.append(f"Dringlichkeit «{URGENCY_LABEL_DE[urgency]}»")  # type: ignore[index]
    reasons.append(
        ACTION_LABEL.get((ex.effective_action if ex and ex.effective_action else action), action)
    )
    missing = len(b.missing_information)
    reasons.append(
        "Pflichtangaben vollständig" if not missing else f"{missing} Pflichtangabe(n) fehlen"
    )
    return {"level": level, "label": label, "reasons": reasons}


# ----------------------------------------------------------------------------------------- helpers
def _fact(
    label: str, display: str | None, level: str, quote: str | None = None, key: bool = False
) -> dict:
    if level in NOTE_OF_LEVEL or display in (None, "", "–"):
        return {
            "label": label,
            "value": None,
            "src": None,
            "evidence": None,
            "key": key,
            "note": NOTE_OF_LEVEL.get(level, "nicht erfasst"),
        }
    return {
        "label": label,
        "value": display,
        "src": SRC_OF_LEVEL.get(level, "user"),
        "evidence": quote,
        "key": key,
        "note": None,
    }


def _statement_has_deadline(text: str) -> bool:
    return bool(re.search(r"\binnert\b|\bTage\b|\bTagen\b|Frist", text))


def _source_view(s) -> dict[str, Any]:
    ref = s.source
    f = ref.fedlex
    retrieved = bool(
        f and f.origin == "FEDLEX" and f.retrieval_status in ("RETRIEVED", "RETRIEVED_STALE")
    )
    is_case_law = ref.type == "case_law"
    if is_case_law:
        title = ref.citation or ref.title_de
        law = ref.case_number or "Bundesgericht"
        text = ref.core_statement_de or ""
        text_label = "Kernaussage laut Law-Dossier"
        meta_parts = [p for p in (ref.decision_date, "; ".join(ref.considerations or [])) if p]
    else:
        title = ref.title_de
        law = f"{(f.law_title if f and f.law_title else ref.statute or '')}, SR {ref.sr_number}".strip(
            ", "
        )
        if retrieved and f and f.official_text:
            text, text_label = f.official_text, "Amtlicher Wortlaut (Fedlex)"
        elif f and f.origin == "FIXTURE":
            text, text_label = (
                f.official_text or ref.text_de or "",
                "Testdaten (kein amtlicher Abruf)",
            )
        else:
            text, text_label = (
                ref.text_de or "",
                "Zitat laut Law-Dossier (nicht von Fedlex abgerufen)",
            )
        meta_parts = []
        if retrieved and f:
            meta_parts.append(
                f"Fassung {f.version_identifier}, gültig ab {f.valid_from}"
                + (f" bis {f.valid_to}" if f.valid_to else "")
            )
            if f.retrieved_at:
                meta_parts.append(f"abgerufen {f.retrieved_at[:16].replace('T', ' ')}")
        elif ref.valid_as_of:
            meta_parts.append(f"Stand laut Dossier {ref.valid_as_of}")
    return {
        "id": ref.id,
        "title": title,
        "law": law,
        "kind": "case_law" if is_case_law else "statute",
        "status": {
            "dossier": ref.dossier_status == "DOSSIER_CHECKED",
            "official_text": retrieved,
            "wording_matched": bool(retrieved and f and f.wording_status == "MATCHED"),
            "interpretation_reviewed": bool(f and f.interpretation_status == "REVIEWED"),
        },
        "wording_note": (
            "Wortlaut weicht von der Wissensbasis ab"
            if f and retrieved and f.wording_status == "MISMATCH"
            else None
        ),
        "meta": "; ".join(meta_parts),
        "text": text,
        "text_label": text_label,
        "links": [
            {"label": lab, "url": url}
            for lab, url in (
                ("Artikel in Fedlex", f.official_article_url if retrieved and f else None),
                ("Amtliches XML", f.official_document_url if retrieved and f else None),
            )
            if url
        ],
        "referenced_by": s.referenced_by,
    }


def _body_from_card(c) -> dict[str, Any]:
    phones = [p.display for p in c.phones]
    address = c.address or ("Schutzadresse, nur telefonisch" if c.address_protected else None)
    return {
        "label": de(c.label),
        "purpose": de(c.reason_de or c.access or ""),
        "contact": {
            "address": de(address),
            "phone": " / ".join(phones) if phones else None,
            "hours": de(c.hours),
            "web": c.web,
            "email": c.email,
        },
        "costs": de(c.costs),
        "web": c.web,
        "contact_primary": c.quality in ("OFFICIAL", "NATIONAL"),
        "quality": c.quality_label_de,
        "unverified": not c.verified or c.quality == "UNDOCUMENTED",
        "emergency": c.kind == "emergency",
        "not_emergency_number": c.not_emergency_number,
    }


# ----------------------------------------------------------------------------------------- main
def build_view(
    *,
    briefing: CaseBriefing,
    case_display_id: str,
    version: int,
    created_at: datetime,
    kb: KnowledgeBase,
    kb_version: str | None = None,
) -> dict[str, Any]:
    b = briefing
    ex = b.extras
    issues: list[IssueBriefing] = b.issue_briefings
    profile = kb.report_profile

    # -- facts (issue-specific groups) ----------------------------------------------------------------
    fact_groups: list[dict] = []
    row_by_id: dict[str, tuple[str, str, str | None]] = {}
    for ib in issues:
        for g in ib.groups:
            title = f"{ib.title_de}: {g.title_de}" if len(issues) > 1 else g.title_de
            facts = []
            for r in g.rows:
                facts.append(
                    _fact(
                        r.label_de,
                        r.value_display,
                        r.evidence_level,
                        r.evidence_quote,
                        key=r.status == "KNOWN",
                    )
                )
                row_by_id.setdefault(
                    r.fact_id, (r.value_display, r.evidence_level, r.evidence_quote)
                )
            fact_groups.append({"title": title, "facts": facts})
        for d in ib.derived:
            row_by_id.setdefault(
                d.id, (str(d.value) if d.value is not None else "", d.evidence_level, None)
            )
    if not fact_groups and b.known_facts:  # unsupported / no issue profile: generic list
        fact_groups.append(
            {
                "title": "Erfasste Angaben",
                "facts": [
                    _fact(f.label_de, f.value_display, f.evidence_level, f.evidence_quote)
                    for f in b.known_facts
                ],
            }
        )
    for f in b.known_facts:
        row_by_id.setdefault(f.fact_id, (f.value_display, f.evidence_level, f.evidence_quote))

    # -- page-1 key data from the report profile (data-driven, per issue) -----------------------------------
    person = []
    for pf in profile.person_fields if profile else []:
        person.append({"label": pf.label, "value": None, "note": CONTACT_NOT_CAPTURED})
    sections: list[dict] = []
    for ib in issues:
        secs = (profile.issue_sections.get(ib.issue_id) if profile else None) or []
        for sec in secs:
            rows = []
            for r in sec.rows:
                if r.fact_id and r.fact_id in row_by_id:
                    disp, lvl, quote = row_by_id[r.fact_id]
                    rows.append(_fact(r.label, disp, lvl, quote))
                elif r.fact_id:
                    rows.append({**_fact(r.label, None, "NOT_ASKED"), "note": "nicht erfragt"})
                else:
                    rows.append({**_fact(r.label, None, "NOT_ASKED"), "note": CONTACT_NOT_CAPTURED})
            sections.append({"title": sec.title, "rows": rows})
        if not secs:  # no profile for this issue: the most important known facts, generic
            known = [f for g in ib.groups for f in g.rows if f.status == "KNOWN"][:8]
            if known:
                sections.append(
                    {
                        "title": f"Eckdaten: {ib.title_de}",
                        "rows": [
                            _fact(r.label_de, r.value_display, r.evidence_level, r.evidence_quote)
                            for r in known
                        ],
                    }
                )

    # -- urgency / deadline hints (never a computed end date) -----------------------------------------------
    derived_rows = [
        {"label": d.label_de, "value": d.value, "note": d.note_de}
        for ib in issues
        for d in ib.derived
    ]
    deadline_hints = [
        {"text": a.text_de, "sources": a.source_ids}
        for a in b.approved_statements
        if _statement_has_deadline(a.text_de)
    ]
    max_u = b.decision.max_urgency
    urgency_note = next((ib.urgency_note_de for ib in issues if ib.urgency_note_de), "")

    # -- decision / handover ---------------------------------------------------------------------------------
    action = b.decision.action.value
    eff = (ex.effective_action if ex else None) or action
    tl = traffic_light(b)
    professionals = [p.label_de for p in b.recommended_professionals]
    handover_status = {
        "RECOMMENDED": "Übergabe empfohlen, noch nicht angefragt.",
        "HANDOFF_REQUESTED": "Übergabe angefragt (von der Sozialarbeiterin markiert).",
        "HANDOFF_COMPLETED": "Übergabe bestätigt (von der Sozialarbeiterin dokumentiert).",
    }
    h = b.handover
    handover = {
        "to": ", ".join(professionals) if professionals else "keine Fachperson empfohlen",
        "status": handover_status.get(h.status.value, h.status.value)
        if h
        else "Keine Übergabe empfohlen.",
    }

    # -- referrals ----------------------------------------------------------------------------------------
    bodies: list[dict] = []
    bodies_note = ""
    if ex and ex.referrals and (ex.referrals.primary or ex.referrals.more):
        bodies = [_body_from_card(c) for c in ex.referrals.primary + ex.referrals.more]
        bodies_note = " ".join(ex.referrals.notes_de)
        if ex.referrals.location_de:
            bodies_note = f"Zuordnung nach: {ex.referrals.location_de}. {bodies_note}".strip()
    else:  # older versions: the dossier authorities of the issue
        for ib in issues:
            for a in ib.authorities:
                bodies.append(
                    {
                        "label": a.name_de,
                        "purpose": a.purpose_de,
                        "contact": None,
                        "costs": a.cost_de,
                        "web": a.url_hint,
                        "contact_primary": False,
                        "quality": a.verification_note_de,
                        "unverified": not a.contact_verified,
                        "emergency": False,
                        "not_emergency_number": False,
                    }
                )
        bodies_note = "Kontaktangaben nicht durchgehend geprüft; vor der Weitergabe bestätigen."

    # -- safety banner ----------------------------------------------------------------------------------------
    safety = None
    if ex and ex.safety and ex.safety.state != "NONE":
        s = ex.safety
        safety = {
            "state": s.state,
            "headline": s.headline_de,
            "explanation": s.explanation_de,
            "steps": s.steps_de,
            "contacts": [
                _body_from_card(c) for c in (s.contacts_immediate + s.contacts_counselling)
            ],
            "further": [_body_from_card(c) for c in s.contacts_further],
            "flags": s.briefing_flags,
            "signals": [
                {
                    "label": x.label_de,
                    "certainty": x.certainty,
                    "quote": x.evidence_quote,
                    "acknowledged": x.acknowledged,
                    "note": x.acknowledged_note,
                }
                for x in s.signals
            ],
        }

    # -- sources --------------------------------------------------------------------------------------------------
    sources = [_source_view(s) for s in b.legal_sources]
    src_title = {s["id"]: s["title"] for s in sources}

    # -- checks / hints -------------------------------------------------------------------------------------------
    legal_checks = []
    for ib in issues:
        for rp in ib.review_points:
            legal_checks.append(
                {
                    "point": "Regel ausgelöst, menschliche Prüfung nötig"
                    if rp.triggered
                    else "Offen, Prüfung durch Fachperson",
                    "state": "unklar" if rp.triggered else "offen",
                    "text": rp.text_de,
                    "issue": ib.title_de if len(issues) > 1 else None,
                    "sources": rp.source_ids,
                }
            )
    general_hints = [{"text": a.text_de, "sources": a.source_ids} for a in b.approved_statements]

    contradictions = [
        f"{u.label_de}: " + (" / ".join(u.values) if u.values else "unklar")
        for u in b.uncertainties
    ]
    unconfirmed_ai = [f.label_de for f in b.known_facts if f.evidence_level == "AI_EXTRACTED"]
    documented = [
        f"Belegt (Unterlage markiert): {f.label_de}"
        for f in b.known_facts
        if f.evidence_level == "DOCUMENTED"
    ]
    requested = list(dict.fromkeys(d for ib in issues for d in ib.documents_to_request))

    next_steps = [{"title": s, "detail": ""} for s in b.next_steps]
    if safety and safety["state"] == "IMMEDIATE":
        next_steps.insert(
            0,
            {
                "title": "Jetzt Notfallhilfe kontaktieren",
                "detail": "Die Sicherheitsreaktion hat Vorrang vor der juristischen Bearbeitung. Dieser Bericht ersetzt keine Kontaktaufnahme.",
            },
        )

    areas = [
        {"label": a.title_de, "confidence": a.confidence, "evidence": a.evidence}
        for a in b.legal_areas
    ]
    unsupported = [u.description or "nicht abgedecktes Rechtsproblem" for u in b.unsupported_issues]
    issue_label = (
        " · ".join([a["label"] for a in areas] + [f"{u} (nicht abgedeckt)" for u in unsupported])
        or "Rechtsproblem noch nicht erkannt"
    )

    return {
        "doc_type": "Fallbericht",
        "case_id": case_display_id,
        "version": str(version),
        "created_at": fmt_dt(created_at),
        "case_state": f"v{b.case_version}",
        "kb_version": kb_version or b.knowledge_base_version,
        "kb_status": (ex.kb_status if ex and ex.kb_status else "DRAFT"),
        "inputs_count": str(ex.inputs_count if ex else b.overview.message_count),
        "issue_label": issue_label,
        "issues": areas,
        "unsupported": unsupported,
        "canton": ex.location_canton if ex else None,
        "municipality": ex.location_municipality if ex else None,
        "client": {
            "label": "Klientin / Klient",
            "submitted_by": ex.created_by_note if ex else "eine Sozialarbeiterin",
        },
        "person": person,
        "sections": sections,
        "disclaimers": {
            "kb_draft": b.knowledge_base_notice
            or "Die verwendeten Wissensbasis-Inhalte sind nicht juristisch freigegeben.",
            "external_ai": b.ai_mode_notice,
            "responsibility": "Dieser Bericht ist eine strukturierte Fallübersicht und keine Rechtsauskunft. Angaben vor Verwendung prüfen.",
        },
        "summary": b.overview.summary or "Es liegt noch keine Zusammenfassung vor.",
        "summary_source": "KI-erstellt aus den Eingaben; Aussagen der Klientin bleiben Aussagen",
        "urgency": {
            "level": URGENCY_LABEL_DE.get(max_u, "nicht bestimmt") if max_u else "nicht bestimmt",
            "rows": derived_rows,
            "note": urgency_note,
            "hints": deadline_hints,
        },
        "tl": tl,
        "decision": {
            "action": action,
            "effective_action": eff,
            "label": ACTION_LABEL.get(eff, eff),
            "code": b.decision.main_reason_code,
            "reason": b.decision.explanation_de,
            "rules_checked": b.decision.rules_evaluated,
            "rules_fired": b.decision.rules_triggered,
        },
        "handover": handover,
        "next_steps": next_steps,
        "documents_received": documented,
        "documents_requested": requested,
        "documents_index": [],  # no upload support yet: the index only lists what is missing
        "fact_groups": fact_groups,
        "open_mandatory_questions": [q for ib in issues for q in ib.open_questions]
        or [m.question_de for m in b.missing_information],
        "missing_all": [m.label_de for m in b.missing_information],
        "contradictions": contradictions,
        "unconfirmed_ai": unconfirmed_ai,
        "legal_checks": legal_checks,
        "risks": [r.result_de for r in b.legal_risks],
        "general_hints": general_hints,
        "legal_areas": areas,
        "bodies": bodies,
        "bodies_note": bodies_note,
        "safety": safety,
        "chronology": [e.model_dump() for e in (ex.chronology if ex else [])],
        "conversation": [c.model_dump() for c in (ex.conversation if ex else [])],
        "sources": sources,
        "src_title": src_title,
        "sources_note": (
            "«Im Law-Dossier geprüft» ist der Prüfstand laut Law-Team. «Amtlicher Wortlaut abgerufen» heisst nur, dass der Text bei Fedlex "
            "gefunden und gespeichert wurde. Ob eine Auslegung fachlich freigegeben ist, zeigt die Zeile «Interpretation». Bundesgerichtsentscheide "
            "sind eine eigene Quellenart und nicht an Fedlex angebunden."
        ),
        "extraction_model": (ex.extraction_model if ex and ex.extraction_model else "KI"),
        "has_extras": ex is not None,
    }
