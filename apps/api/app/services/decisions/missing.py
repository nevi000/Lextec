"""Missing Information Engine: required facts vs. current case state.

Fact states and what the engine does with them:

* MISSING (never asked)          -> required: ASK.   optional: offered as optional follow-up.
* AMBIGUOUS / CONTRADICTORY      -> required: ASK again (answers resolve them).
* UNKNOWN (asked, "weiss nicht") -> NEVER asked again. Required facts in this state trigger a
                                    human review (built-in rule); they do not count as missing.
* KNOWN / NOT_APPLICABLE         -> resolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import FactStatus
from app.domain.state import CaseSnapshot
from app.schemas.decision import MissingFact, NextQuestion
from app.services.knowledge.loader import KnowledgeBase
from app.services.knowledge.schema import FactDef
from app.services.rules.conditions import EvalContext, fires

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def known_values(snapshot: CaseSnapshot) -> dict:
    return {fid: fs.value for fid, fs in snapshot.facts.items() if fs.status == FactStatus.KNOWN}


def unknown_ids(snapshot: CaseSnapshot) -> frozenset[str]:
    return frozenset(fid for fid, fs in snapshot.facts.items() if fs.status == FactStatus.UNKNOWN)


@dataclass
class FactAnalysis:
    missing: list[MissingFact] = field(default_factory=list)  # required, to be (re-)asked
    unknown_required: list[MissingFact] = field(default_factory=list)  # required, asked, unknown
    optional_open: list[MissingFact] = field(default_factory=list)  # optional, not yet answered


def _to_missing(
    fd: FactDef, issue_ids: list[str], status: FactStatus, deferred: bool
) -> MissingFact:
    return MissingFact(
        fact_id=fd.id,
        issue_ids=list(issue_ids),
        label_de=fd.label_de,
        status=status,
        priority=fd.priority,
        question_de=fd.question_de,
        why_needed_de=fd.why_needed_de,
        deferred=deferred,
        data_type=fd.data_type,
        enum_values=list(fd.enum_values),
        enum_labels_de=dict(fd.enum_labels_de),
    )


def analyze_facts(
    kb: KnowledgeBase, snapshot: CaseSnapshot, active_issue_ids: list[str]
) -> FactAnalysis:
    env = EvalContext(
        facts=known_values(snapshot),
        ctx={},
        active_issues=frozenset(active_issue_ids),
        unknown=unknown_ids(snapshot),
    )
    # one record per fact id (facts may be shared by several issues); required if required anywhere
    records: dict[str, tuple[FactDef, list[str], bool]] = {}
    order: list[str] = []
    for issue_id in active_issue_ids:
        for fd in kb.issues[issue_id].facts:
            req = fd.required or fires(fd.required_if, env)
            if fd.id in records:
                prev, ids, prev_req = records[fd.id]
                ids.append(issue_id)
                best = fd if PRIORITY_RANK[fd.priority] < PRIORITY_RANK[prev.priority] else prev
                records[fd.id] = (best, ids, prev_req or req)
            else:
                records[fd.id] = (fd, [issue_id], req)
                order.append(fd.id)

    idx = {fid: n for n, fid in enumerate(order)}
    out = FactAnalysis()
    for fid in order:
        fd, ids, required = records[fid]
        fs = snapshot.facts.get(fid)
        status = fs.status if fs else FactStatus.MISSING
        if status in (FactStatus.KNOWN, FactStatus.NOT_APPLICABLE):
            continue
        deferred = bool(fs and fs.deferred)
        item = _to_missing(fd, ids, status, deferred)
        if status == FactStatus.UNKNOWN:
            if required:
                out.unknown_required.append(item)
            continue
        (out.missing if required else out.optional_open).append(item)

    key = lambda m: (PRIORITY_RANK[m.priority], idx[m.fact_id])  # noqa: E731
    out.missing.sort(key=key)
    out.unknown_required.sort(key=key)
    out.optional_open.sort(key=key)
    return out


def find_missing(
    kb: KnowledgeBase, snapshot: CaseSnapshot, active_issue_ids: list[str]
) -> list[MissingFact]:
    """Required facts that still have to be asked, in question order."""
    return analyze_facts(kb, snapshot, active_issue_ids).missing


def _question(m: MissingFact, optional: bool) -> NextQuestion:
    return NextQuestion(
        fact_id=m.fact_id,
        question_de=m.question_de,
        why_needed_de=m.why_needed_de,
        data_type=m.data_type,
        enum_values=m.enum_values,
        enum_labels_de=m.enum_labels_de,
        deferred=m.deferred,
        optional=optional,
    )


def pick_next_question(
    missing: list[MissingFact], optional_open: list[MissingFact] | None = None
) -> NextQuestion | None:
    """Highest-priority required question that was not deferred; deferred ones only if nothing
    else is left. Optional questions are offered only when no required question remains."""
    if missing:
        fresh = [m for m in missing if not m.deferred]
        return _question(fresh[0] if fresh else missing[0], False)
    fresh_opt = [m for m in (optional_open or []) if not m.deferred]
    if fresh_opt:
        return _question(fresh_opt[0], True)
    return None


def effective_required(
    kb: KnowledgeBase, snapshot: CaseSnapshot, active_issue_ids: list[str]
) -> dict[str, bool]:
    """fact_id -> whether the fact is currently required (static or via required_if)."""
    env = EvalContext(
        facts=known_values(snapshot),
        ctx={},
        active_issues=frozenset(active_issue_ids),
        unknown=unknown_ids(snapshot),
    )
    out: dict[str, bool] = {}
    for issue_id in active_issue_ids:
        for fd in kb.issues[issue_id].facts:
            req = fd.required or fires(fd.required_if, env)
            out[fd.id] = out.get(fd.id, False) or req
    return out
