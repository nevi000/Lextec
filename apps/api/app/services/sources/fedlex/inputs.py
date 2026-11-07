"""Map the law team's free-text ``legal_basis`` entries (referral_rules / liability_flags / triage_config) to
knowledge-base source ids. Documentation only: it NEVER modifies the inputs, activates rules, changes triage
thresholds or decides anything. Fedlex provides sources, not decisions.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import REPO_ROOT, Settings
from app.services.knowledge.loader import KnowledgeBase

INPUT_FILES = ("referral_rules.yaml", "liability_flags.yaml", "triage_config.yaml")
INTERNATIONAL = ("EMRK", "UN-", "UNO", "Konvention", "EGMR")
# Only unambiguous, Swiss-federal abbreviations that exist in the Fedlex classified compilation.
STATUTES = ("OR", "ZPO", "BV", "ZGB", "StGB")
_ENTRY = re.compile(
    r"^Art\.\s*(?P<art>\d+[a-z]{0,3})(?:\s*Abs\.\s*(?P<abs>\d+))?(?:\s*lit\.\s*(?P<lit>[a-z]))?\s+(?P<law>[A-Za-zÄÖÜ]+)\b"
)
_PIPE = "\\|"


def _collect(node, path: str, out: list[tuple[str, str]]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "legal_basis" and isinstance(v, list):
                out += [(path, str(x)) for x in v]
            else:
                _collect(v, f"{path}/{k}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            label = v.get("id") if isinstance(v, dict) and isinstance(v.get("id"), str) else str(i)
            _collect(v, f"{path}[{label}]", out)


def classify(entry: str, kb: KnowledgeBase) -> tuple[str, list[str], str]:
    """-> (status, source ids, note). Status: RESOLVED | NOT_IN_KB | UNRESOLVABLE | INTERNATIONAL."""
    if any(t in entry for t in INTERNATIONAL):
        return (
            "INTERNATIONAL",
            [],
            "Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch).",
        )
    if re.search(r"\bff\.|\d[a-z]?\s*[-–]\s*\d", entry) or not entry.startswith("Art."):
        return (
            "UNRESOLVABLE",
            [],
            "Bereich/Sammelverweis/Freitext: bewusst nicht automatisch aufgelöst (Rechtsteam).",
        )
    m = _ENTRY.match(entry)
    if not m or m["law"] not in STATUTES:
        return "UNRESOLVABLE", [], "Gesetz nicht eindeutig (z. B. kantonales Recht / nur Name)."
    art, para, law = m["art"], m["abs"], m["law"]
    hits = [
        s.id
        for s in kb.sources.values()
        if s.provider == "fedlex"
        and (s.statute or "") == law
        and (s.article or "").lower() == art.lower()
        and (
            para is None
            or not s.paragraph
            or re.sub(r"\D", "", s.paragraph.split("lit")[0]) == para
        )
    ]
    if hits:
        return "RESOLVED", sorted(hits), ""
    return (
        "NOT_IN_KB",
        [],
        f"Art. {art} {law} ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden.",
    )


def build_report(kb: KnowledgeBase, root: Path | None = None) -> tuple[str, dict[str, int]]:
    base = root or (REPO_ROOT / "docs" / "legal_inputs")
    rows: list[tuple[str, str, str, list[str], str]] = []
    for name in INPUT_FILES:
        f = base / name
        if not f.exists():
            continue
        found: list[tuple[str, str]] = []
        _collect(yaml.safe_load(f.read_text(encoding="utf-8")), name, found)
        for where, entry in found:
            st, ids, note = classify(entry, kb)
            rows.append((where, entry, st, ids, note))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r[2]] = counts.get(r[2], 0) + 1
    lines = [
        "# Zuordnung der Rechtsgrundlagen des Rechtsteams zu Quellen-IDs",
        "",
        "_Generiert mit `python -m app.cli fedlex map-inputs`. Reine Dokumentation: Es werden keine Regeln aktiviert,",
        "keine Triage-Schwellen oder Sicherheitsaktionen geändert. `verified: true` einer Organisation bedeutet nicht,",
        "dass Kontakte heute neu geprüft wurden._",
        "",
        "Zusammenfassung: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())),
        "",
        "| Fundstelle | Angabe des Rechtsteams | Status | Quellen-ID | Hinweis |",
        "|---|---|---|---|---|",
    ]
    for where, entry, st, ids, note in rows:
        esc = entry.replace("|", _PIPE)
        lines.append(f"| `{where}` | {esc} | {st} | {', '.join(ids) or '-'} | {note} |")
    return "\n".join(lines) + "\n", counts


def run_map_inputs(
    settings: Settings, kb: KnowledgeBase, _sf: sessionmaker[Session], check: bool = False
) -> int:
    text, counts = build_report(kb)
    out = REPO_ROOT / "knowledge_base" / "references" / "legal_inputs_mapping.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"Report: {out}\n" + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if check:
        print(
            "Hinweis: Existenzprüfung gegen Fedlex läuft über `fedlex sync` der aufgelösten Quellen; "
            "NOT_IN_KB-Einträge werden nicht automatisch angelegt."
        )
    return 0
