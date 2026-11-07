"""Erzeugt die Wissensbasis-Dateien der Issues 2-7 aus den Dossiers und den Specs.

    python scripts/kb/build_issue_kb.py            # Quellen mergen + Issue-YAMLs + Szenarien schreiben

1. Quellenkatalog: Gesetzesartikel- und Leitentscheide-Tabellen aller 7 Dossiers (siehe kb_common.py)
   werden in knowledge_base/legal_sources/sources.yaml gemerged. Vorhandene Einträge werden NIE überschrieben.
2. Pro Spec (scripts/kb/specs/issue_0N.py, Variable SPEC) wird knowledge_base/legal_issues/<ID>.yaml
   und knowledge_base/tests/scenarios_<ID>.yaml geschrieben.
Die Specs enthalten ausschliesslich Inhalte der Dossiers (Fakten, Regeln, erlaubte Aussagen, Briefing);
Issue 1 wird von Hand gepflegt (CH_TENANCY_TERMINATION.yaml) und hier nicht angefasst.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "specs"))

import kb_common as k  # noqa: E402

SPEC_MODULES = ["issue_02", "issue_03", "issue_04", "issue_05", "issue_06", "issue_07"]

HEADER = """# yaml-language-server: $schema=../../schemas/issue_definition.schema.json
# ============================================================================================
# {title}
# GENERIERT durch scripts/kb/build_issue_kb.py aus scripts/kb/specs/{module}.py und dem Law-Dossier
# docs/legal_inputs/issues/{dossier}. Änderungen bitte in der Spec vornehmen und neu generieren.
#
# STATUS: content_status DRAFT. Das Dossier ist KEINE endgültige Freigabe für den Einsatz mit
# echten Klienten (offene Prüfpunkte: docs/ISSUE_COVERAGE_MATRIX.md und docs/ALL_ISSUES_INTEGRATION.md).
# PRODUKTENTSCHEIDE (Teamentscheide 7.11.2026) sind keine Gesetzesfristen. Das System berechnet und
# nennt NIE ein Fristende. Dringlichkeit: HIGH = «sofort», MEDIUM = «bald», LOW = «normal».
# ============================================================================================
"""


def build_sources() -> list[str]:
    entries: list[dict] = []
    for n in range(1, 8):
        entries += k.collect_dossier_sources(n)
    entries += k.EXTRA_SOURCES
    data, added = k.merge_sources(entries)
    data["version"] = "0.3-issues-1-7"
    k.SOURCES_YAML.write_text(
        "# yaml-language-server: $schema=../../schemas/sources.schema.json\n"
        "# Quellenkatalog (Fedlex-Gesetze, BGE/BGer, kantonale Quellen, Lehrbuch, Produktregeln).\n"
        "# Issue 1: von Hand; Issues 2-7: aus den Tabellen der Dossiers importiert (scripts/kb/build_issue_kb.py).\n"
        "# dossier_status = Prüfstand laut Law-Dossier (NICHT automatisch verifiziert).\n"
        "# verification_status = Live-Verifikation durch dieses System (Fedlex-Sync).\n"
        + k.dump_yaml(data),
        encoding="utf-8",
        newline="\n",
    )
    return added


def build_authorities() -> int:
    """Hängt neue Stellen (kb_common.AUTHORITIES_NEW) an authorities.yaml an; bestehende bleiben unberührt."""
    import yaml

    path = k.KB / "referrals" / "authorities.yaml"
    text = path.read_text(encoding="utf-8")
    have = {a["id"] for a in yaml.safe_load(text)["authorities"]}
    new = [a for a in k.AUTHORITIES_NEW if a["id"] not in have]
    if not new:
        return 0
    lines: list[str] = []
    for a in new:
        lines.append("")
        lines.extend("  " + ln for ln in k.dump_yaml([a]).rstrip("\n").split("\n"))
    path.write_text(
        text.rstrip("\n")
        + "\n\n  # --- Issues 2-7 (scripts/kb/kb_common.py AUTHORITIES_NEW; nur Dossier-Angaben, contact_verified bleibt false) ---"
        + "\n".join(lines)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return len(new)


def build_issue(module: str) -> tuple[str, int, int]:
    mod = importlib.import_module(module)
    spec = mod.SPEC
    doc: dict = {
        "schema_version": 1,
        "id": spec["id"],
        "version": spec.get("version", "1.0-dossier-2026-11-07"),
        "content_status": "DRAFT",
        "jurisdiction": "CH",
        "canton": "ZH",
        "legal_area": "tenancy",
        "issue": spec["issue"],
        "title_de": spec["title_de"],
        "description": spec["description"],
        "provenance_de": spec["provenance_de"],
        "classification": spec["classification"],
    }
    if spec.get("derived"):
        doc["derived"] = spec["derived"]
    doc["facts"] = spec["facts"]
    doc["escalation_rules"] = spec["escalation"]
    doc["legal_rules"] = spec["legal"]
    srcs: list[str] = []
    for lr in spec["legal"]:
        for s in lr["legal_source_ids"]:
            if s not in srcs:
                srcs.append(s)
    doc["legal_source_ids"] = spec.get("legal_source_ids", srcs)
    doc["default_professionals"] = spec["default_professionals"]
    doc["briefing_template"] = "expert_briefing_v1"
    doc["briefing_profile"] = spec["briefing"]
    out = k.KB / "legal_issues" / f"{spec['id']}.yaml"
    out.write_text(
        HEADER.format(title=spec["title_de"], module=module, dossier=spec["dossier"])
        + k.dump_yaml(doc),
        encoding="utf-8",
        newline="\n",
    )
    sc = {"schema_version": 1, "version": "1.0-issues", "scenarios": spec["scenarios"]}
    sout = k.KB / "tests" / f"scenarios_{spec['id']}.yaml"
    sout.write_text(
        f"# GENERIERT aus scripts/kb/specs/{module}.py - SYNTHETIC_TECHNICAL, keine echten Fälle.\n"
        + k.dump_yaml(sc),
        encoding="utf-8",
        newline="\n",
    )
    return spec["id"], len(spec["facts"]), len(spec["escalation"]) + len(spec["legal"])


def main() -> None:
    added = build_sources()
    print(f"Quellen: {len(added)} neu importiert")
    print(f"Stellen: {build_authorities()} neu")
    for m in SPEC_MODULES:
        try:
            importlib.import_module(m)
        except ModuleNotFoundError as exc:
            if exc.name == m:
                print(f"{m}: noch keine Spec")
                continue
            raise
        iid, nf, nr = build_issue(m)
        print(f"{iid}: {nf} Fakten, {nr} Regeln")


if __name__ == "__main__":
    main()
