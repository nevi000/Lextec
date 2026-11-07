"""Adapter for the law team's reference data (sample/bridge_fall_0011.json) -> report view model.

Only used to verify that the integrated template reproduces the delivered reference briefing (and as a documented
example of the interface). Real reports are built from the database by view.build_view().
"""

from __future__ import annotations

from typing import Any

from app.services.report.view import ACTION_LABEL, LEVEL_LABEL, de


def _tl(b: dict[str, Any]) -> dict[str, Any]:
    level = {"sofort": "ROT", "bald": "AMBER", "normal": "GRUEN"}.get(
        b["urgency"]["level"], "AMBER"
    )
    if b["decision"]["action"] == "IMMEDIATE_SAFETY_RESPONSE":
        level = "ROT"
    elif b["decision"]["action"] in ("ESCALATE", "ASK") and level == "GRUEN":
        level = "AMBER"
    missing = len(b.get("missing_mandatory") or [])
    return {
        "level": level,
        "label": LEVEL_LABEL[level],
        "reasons": [
            f"Dringlichkeit «{b['urgency']['level']}»",
            b["decision"]["label"],
            "Pflichtangaben vollständig" if not missing else f"{missing} Pflichtangabe(n) fehlen",
        ],
    }


def view_from_bridge_sample(b: dict[str, Any], network: Any = None) -> dict[str, Any]:
    from app.services.referrals.network import build_card

    orgs = network.org_map() if network is not None else {}
    bodies = []
    for s in b.get("bodies", []):
        org = orgs.get(s.get("ref_id"))
        card = build_card(org) if org is not None else None
        bodies.append(
            {
                "label": s["label"],
                "purpose": s.get("purpose", ""),
                "contact": {
                    "address": de(card.address) if card else None,
                    "phone": " / ".join(p.display for p in card.phones)
                    if card and card.phones
                    else None,
                    "hours": de(card.hours) if card else None,
                    "web": card.web if card else None,
                    "email": card.email if card else None,
                }
                if card
                else None,
                "costs": s.get("costs"),
                "web": s.get("web"),
                "contact_primary": bool(card and card.quality == "OFFICIAL"),
                "quality": card.quality_label_de if card else "Kontakt fehlt",
                "unverified": not (card and card.verified),
                "emergency": False,
                "not_emergency_number": False,
            }
        )
    groups = [
        {
            "title": g["title"],
            "facts": [
                {
                    "label": f["label"],
                    "value": f["value"],
                    "src": f.get("src"),
                    "evidence": f.get("evidence"),
                    "key": bool(f.get("key")),
                    "note": None if f["value"] is not None else "ungeklärt",
                }
                for f in g["facts"]
            ],
        }
        for g in b["fact_groups"]
    ]
    sources = [
        {
            "id": s["id"],
            "title": s["title"],
            "law": s["law"],
            "kind": s["kind"],
            "status": s["status"],
            "wording_note": None,
            "meta": s.get("meta", ""),
            "text": s.get("text", ""),
            "text_label": "Wortlaut laut Referenzdatei",
            "links": [],
            "relevant": True,  # the reference sample shows every source in full
            "referenced_by": s.get("referenced_by", []),
        }
        for s in b["sources"]
    ]
    u = b["urgency"]
    return {
        "doc_type": "Fallbericht",
        "case_id": b["case_id"],
        "version": b["version"],
        "created_at": b["created_at"],
        "case_state": b["case_state"],
        "kb_version": b["kb_version"],
        "kb_status": b["kb_status"],
        "inputs_count": b["inputs_count"],
        "issue_label": b["issue_label"],
        "issues": [
            {"label": a["label"], "confidence": a.get("confidence"), "evidence": a.get("evidence")}
            for a in b["legal_areas"]
        ],
        "unsupported": [],
        "canton": b.get("canton"),
        "municipality": b.get("municipality"),
        "client": {"label": b["client"]["label"], "submitted_by": b["client"]["submitted_by"]},
        "person": [],
        "sections": [],
        "disclaimers": b["disclaimers"],
        "summary": b["summary"],
        "summary_source": b.get("summary_source", ""),
        "urgency": {
            "level": u["level"],
            "rows": [
                {"label": "Tage seit Empfang", "value": u.get("days_since_receipt"), "note": ""}
            ],
            "note": u.get("note", ""),
            "hints": [{"text": u["legal_deadline_hint"], "sources": []}]
            if u.get("legal_deadline_hint")
            else [],
        },
        "tl": _tl(b),
        "decision": {
            "action": b["decision"]["action"],
            "effective_action": b["decision"]["action"],
            "label": b["decision"]["label"] or ACTION_LABEL.get(b["decision"]["action"]),
            "code": b["decision"]["code"],
            "reason": b["decision"]["reason"],
            "rules_checked": b["decision"]["rules_checked"],
            "rules_fired": b["decision"]["rules_fired"],
        },
        "handover": {"to": b["handover"]["to"], "status": b["handover"]["status"]},
        "next_steps": b["next_steps"],
        "documents_received": b["documents_received"],
        "documents_requested": b["documents_requested"],
        "documents_index": [],
        "fact_groups": groups,
        "open_mandatory_questions": b["open_mandatory_questions"],
        "missing_all": b["missing_mandatory"],
        "contradictions": b["contradictions"],
        "unconfirmed_ai": [],
        "legal_checks": [
            {
                "point": "Offen, Prüfung durch Fachperson",
                "state": "offen",
                "text": c["text"],
                "issue": None,
                "sources": c["sources"],
            }
            for c in b["legal_checks"]
        ],
        "risks": b["risks"],
        "general_hints": b["general_hints"],
        "legal_areas": [
            {"label": a["label"], "confidence": a.get("confidence"), "evidence": a.get("evidence")}
            for a in b["legal_areas"]
        ],
        "bodies": bodies,
        "bodies_note": b.get("bodies_note", ""),
        "safety": None,
        "chronology": [],
        "conversation": [],
        "sources": sources,
        "src_title": {s["id"]: s["title"] for s in sources},
        "sources_note": b.get("sources_note", ""),
        "extraction_model": b.get("extraction_model", "KI"),
        "has_extras": False,
    }
