"""Safety assessment from stored safety events, and regional referral planning.

Priority (strictest wins): IMMEDIATE_SAFETY_RESPONSE > ESCALATE > ASK > PROCEED. The legal decision is never
deleted or altered; the safety state sits next to it and may override the *displayed* main action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.schemas.safety import ReferralCard, ReferralPlan, SafetyAssessment, SafetySignalOut
from app.services.knowledge.loader import KnowledgeBase
from app.services.referrals.network import (
    Location,
    Org,
    ReferralNetwork,
    build_card,
    infer_canton,
    resolve_role,
)

HEADLINE_IMMEDIATE = "Akute Gefahr erkannt – jetzt handeln"
HEADLINE_UNCLEAR = "Mögliches Sicherheitssignal – bitte klären"
EXPLAIN_UNCLEAR = (
    "Eine Aussage könnte auf eine Gefährdung hinweisen, ist aber nicht eindeutig (zum Beispiel zeitlich zurückliegend "
    "oder bedingt formuliert). Bitte klären Sie die aktuelle Situation im Gespräch. Es wird keine Diagnose gestellt."
)
STATE_RANK = {"NONE": 0, "UNCLEAR": 1, "HUMAN_CHECK": 2, "IMMEDIATE": 3}


@dataclass
class SafetyEventState:
    """Plain input for the pure decision engine (mirrors the persisted SafetyEvent row)."""

    category: str
    certainty: str  # ACUTE | UNCLEAR
    evidence: str
    rule_id: str
    id: str | None = None
    message_id: str | None = None
    modifiers: list[str] | None = None
    detected_at: datetime | None = None
    acknowledged: bool = False
    acknowledged_note: str | None = None
    acknowledged_at: datetime | None = None


def location_from_facts(kb: KnowledgeBase, issue_ids: list[str], facts: dict) -> Location:
    """Canton/municipality only from confirmed case data; never defaulted to Zürich."""
    net = kb.referral_network
    municipality = None
    f = facts.get("property_municipality")
    if f is not None and getattr(f.status, "value", f.status) == "KNOWN" and f.value:
        municipality = str(f.value).strip()
    canton = None
    in_zh = facts.get("property_in_canton_zh")
    for iid in issue_ids:
        issue = kb.issues.get(iid)
        if issue and issue.canton:
            known_false = (
                in_zh is not None
                and getattr(in_zh.status, "value", in_zh.status) == "KNOWN"
                and in_zh.value is False
            )
            if not known_false:
                canton = issue.canton
                break
    if canton is None and net is not None:
        canton = infer_canton(net, municipality)
    return Location(canton=canton, municipality=municipality)


# ------------------------------------------------------------------------------------ safety
def _route_index(net: ReferralNetwork) -> dict[str, tuple[int, object]]:
    return {r.category: (i, r) for i, r in enumerate(net.safety_routing)}


def _resolve_orgs(
    net: ReferralNetwork, roles: list[str], loc: Location, notes: list[str] | None = None
) -> list[tuple[Org, str, str]]:
    """Role/org ids -> [(org, role, how)], skipping unresolved and inactive organisations."""
    orgs = net.org_map()
    out: list[tuple[Org, str, str]] = []
    for role in roles:
        org_id, how = resolve_role(net, role, loc)
        org = orgs.get(org_id or "")
        if org is not None and not org.active:
            if notes is not None:
                notes.append(
                    f"{org.label} nimmt derzeit nicht auf; nicht als reguläre Empfehlung angeboten."
                )
            default_id = (net.role_resolution.get(role) or {}).get("default")
            alt = orgs.get(default_id or "")
            org, how = (
                (alt, "default")
                if alt is not None and alt.active and alt.id != org.id
                else (None, "none")
            )
        if org is not None:
            out.append((org, role, how))
    return out


def assess_safety(
    kb: KnowledgeBase, events: list[SafetyEventState], loc: Location, active_rule_ids: list[str]
) -> SafetyAssessment:
    net = kb.referral_network
    if net is None or not events:
        return SafetyAssessment()
    routes = _route_index(net)
    labels = {c.id: c.label_de for c in (kb.safety_config.categories if kb.safety_config else [])}
    responses = kb.safety_config.responses if kb.safety_config else {}

    signals: list[SafetySignalOut] = []
    best: dict[str, str] = {}  # category -> strongest certainty
    for e in events:
        route = routes.get(e.category)
        if route is None:
            continue
        action = route[1].action  # type: ignore[attr-defined]
        signals.append(
            SafetySignalOut(
                id=e.id,
                category=e.category,
                label_de=labels.get(e.category, e.category),
                certainty=e.certainty,  # type: ignore[arg-type]
                action=action,
                evidence_quote=e.evidence,
                message_id=e.message_id,
                rule_id=e.rule_id,
                modifiers=e.modifiers or [],
                detected_at=e.detected_at,
                acknowledged=e.acknowledged,
                acknowledged_note=e.acknowledged_note,
                acknowledged_at=e.acknowledged_at,
            )
        )
        if best.get(e.category) != "ACUTE":
            best[e.category] = e.certainty

    state = "NONE"
    immediate: list[str] = []
    human: list[str] = []
    flags: list[str] = []
    for cat, certainty in sorted(best.items(), key=lambda kv: routes[kv[0]][0]):
        action = routes[cat][1].action  # type: ignore[attr-defined]
        flag = routes[cat][1].briefing_flag  # type: ignore[attr-defined]
        if action == "FLAG":
            if flag and certainty == "UNCLEAR":
                flags.append(flag)
            continue
        if certainty == "ACUTE" and action == "IMMEDIATE_SAFETY_RESPONSE":
            immediate.append(cat)
            level = "IMMEDIATE"
        elif certainty == "ACUTE":
            human.append(cat)
            level = "HUMAN_CHECK"
        else:
            level = "UNCLEAR"
        if STATE_RANK[level] > STATE_RANK[state]:
            state = level
        if level in ("IMMEDIATE", "HUMAN_CHECK") and flag:
            flags.append(flag)

    result = SafetyAssessment(
        state=state, signals=signals, immediate_categories=immediate, briefing_flags=flags
    )  # type: ignore[arg-type]
    if state == "NONE":
        return result
    if state == "UNCLEAR":
        result.headline_de, result.explanation_de = HEADLINE_UNCLEAR, EXPLAIN_UNCLEAR
        return result

    focus = immediate or human
    result.legal_secondary = state == "IMMEDIATE"
    result.headline_de = (
        HEADLINE_IMMEDIATE
        if state == "IMMEDIATE"
        else (responses[focus[0]].headline_de if focus[0] in responses else labels.get(focus[0]))
    )
    explain = [responses[c].explanation_de for c in focus if c in responses]
    result.explanation_de = " ".join(dict.fromkeys(explain)) or None
    steps: list[str] = []
    for c in focus:
        steps.extend(responses[c].steps_de if c in responses else [])
    unique = list(dict.fromkeys(steps))
    # the closing step (resume normal intake) always comes last, also when several categories contribute
    result.steps_de = [x for x in unique if not x.startswith("Die normale Fallaufnahme")] + [
        x for x in unique if x.startswith("Die normale Fallaufnahme")
    ]

    orgs = net.org_map()
    seen: set[str] = set()
    for cat in focus:
        route = routes[cat][1]
        for org_id in route.show_to_user:  # type: ignore[attr-defined]
            org = orgs.get(org_id)
            if org is None or not org.active or org.id in seen:
                continue
            seen.add(org.id)
            card = build_card(org, reason=labels.get(cat), rule_ref=f"safety_routing:{cat}")
            (
                result.contacts_immediate
                if card.kind == "emergency"
                else result.contacts_counselling
            ).append(card)
        roles = list(route.referrals)  # type: ignore[attr-defined]
        active_signals = _active_signals(net, active_rule_ids, list(best))
        for cond in route.conditional:  # type: ignore[attr-defined]
            if cond.when.get("signal") in active_signals:
                roles.extend(cond.add)
        for org, role, _how in _resolve_orgs(net, roles, loc):
            if org.id in seen:
                continue
            seen.add(org.id)
            result.contacts_further.append(
                build_card(
                    org,
                    reason=f"Weiterführend nach der akuten Situation ({labels.get(cat)})",
                    rule_ref=f"safety_routing:{cat}:{role}",
                )
            )
    # emergency numbers first: 144 / 117 in the order of the configured categories
    return result


def _active_signals(
    net: ReferralNetwork, rule_ids: list[str], safety_categories: list[str]
) -> set[str]:
    out: set[str] = set()
    for sig, b in net.signal_bindings.items():
        if set(b.rules) & set(rule_ids) or set(b.safety_categories) & set(safety_categories):
            out.add(sig)
    return out


# ------------------------------------------------------------------------------------ referrals
def plan_referrals(
    kb: KnowledgeBase,
    issue_ids: list[str],
    loc: Location,
    rule_ids: list[str],
    safety: SafetyAssessment,
) -> ReferralPlan:
    net = kb.referral_network
    if net is None:
        return ReferralPlan()
    signals = _active_signals(net, rule_ids, [s.category for s in safety.signals])
    notes: list[str] = []
    unresolved: list[str] = []
    entries: list[tuple[int, str, str, str, str]] = []  # (rank, group, role, reason, ref)
    for rule in net.issue_rules:
        if rule.issue_id not in issue_ids:
            continue
        for role in rule.referrals.primary:
            entries.append(
                (
                    10,
                    "primary",
                    role,
                    rule.reason_for_referral or "",
                    f"issue_rules:{rule.issue_id}:primary",
                )
            )
        for cond in rule.referrals.conditional:
            sig = cond.when.get("signal", "")
            if sig in signals:
                grp = "primary" if (cond.urgency or "").upper() == "CRITICAL" else "more"
                for role in cond.add:
                    entries.append(
                        (
                            15 if grp == "primary" else 25,
                            grp,
                            role,
                            f"wegen: {sig}",
                            f"issue_rules:{rule.issue_id}:{sig}",
                        )
                    )
        for role in rule.referrals.secondary:
            entries.append(
                (30, "more", role, "weitere Anlaufstelle", f"issue_rules:{rule.issue_id}:secondary")
            )
    for cc in net.cross_cutting:
        if cc.get("signal") in signals:
            for role in cc.get("add", []):
                entries.append(
                    (40, "more", role, f"wegen: {cc['signal']}", f"cross_cutting:{cc['signal']}")
                )

    orgs = net.org_map()
    primary: list[ReferralCard] = []
    more: list[ReferralCard] = []
    seen: set[str] = set()
    for _rank, grp, role, reason, ref in sorted(entries, key=lambda e: e[0]):
        resolved = _resolve_orgs(net, [role], loc, notes)
        if not resolved:
            unresolved.append(role)
            continue
        org, _r, how = resolved[0]
        if org.id in seen:
            continue
        seen.add(org.id)
        if how == "default" and org.id == role and loc.canton:
            notes.append(
                f"{org.label}: Zuständigkeit für {loc.describe()} nicht bestätigt, allgemeine Anlaufstelle gezeigt."
            )
        card = build_card(org, reason=reason or None, rule_ref=ref)
        (primary if grp == "primary" and len(primary) < 3 else more).append(card)
    del orgs
    location_de = (
        loc.describe() or "Kein Wohnort bestätigt: es werden nur allgemeine Anlaufstellen gezeigt."
    )
    return ReferralPlan(
        primary=primary,
        more=more,
        location_de=location_de,
        notes_de=list(dict.fromkeys(notes)),
        unresolved_roles=list(dict.fromkeys(unresolved)),
    )
