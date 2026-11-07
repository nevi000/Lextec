"""Statement policy guard: forbidden statements (Law-Dossier Issue 1, section 6).

Free text produced by the AI (summary, reworded questions) is checked against the knowledge-base
policy `policies/forbidden_statements.yaml`. A hit is replaced by a safe fallback; it is never shown.
The knowledge-base texts themselves are checked when the KB is loaded (see loader `_check_text_policy`).
"""

from __future__ import annotations

from app.services.knowledge.loader import KnowledgeBase


def find_violations(kb: KnowledgeBase, text: str) -> list[str]:
    """IDs of all forbidden-statement rules that match `text`."""
    return [rule.id for rule, patterns in kb.forbidden if any(p.search(text) for p in patterns)]


def sanitize(kb: KnowledgeBase, text: str, fallback: str | None = None) -> tuple[str, list[str]]:
    """Return (safe_text, violated_rule_ids). Violating text is replaced by the fallback."""
    hits = find_violations(kb, text)
    if hits:
        return (fallback if fallback is not None else kb.safe_fallback_de), hits
    return text, []
