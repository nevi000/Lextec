"""`python -m app.services.knowledge.cli [path]` - validate the whole knowledge base."""

from __future__ import annotations

import sys
from pathlib import Path

from app.core.config import get_settings
from app.services.decisions.evaluation import run_scenarios
from app.services.knowledge.loader import load_knowledge_base


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]) if argv else get_settings().knowledge_base_dir
    kb = load_knowledge_base(root)
    print(f"Wissensbasis: {root}  ({kb.version})")
    for f in kb.files:
        mark = "OK  " if f.ok and not f.errors else "FEHLER"
        print(f"  [{mark}] {f.path}  ({f.kind}{', v' + f.version if f.version else ''})")
        for e in f.errors:
            print(f"        - {e}")
    for e in kb.cross_errors:
        print(f"  [FEHLER] {e}")
    if kb.valid:
        summary = run_scenarios(kb)
        print(f"\nValidierung bestanden. Szenarien: {summary.passed}/{summary.total} bestanden.")
        for r in summary.results:
            if not r.passed:
                print(f"  - {r.scenario_id}: " + " ".join(r.mismatches))
        return 0 if summary.failed == 0 else 2
    print(f"\n{len(kb.errors)} Fehler gefunden.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
