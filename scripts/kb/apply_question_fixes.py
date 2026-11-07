"""Apply scripts/kb/question_fixes.py to the issue YAML files and to the spec generators (kept consistent).

Idempotent: a question that already has the new wording is left alone. Run from the repo root:
    apps/api/.venv/Scripts/python.exe scripts/kb/apply_question_fixes.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from question_fixes import FIXES, WHY_FIXES  # noqa: E402

YAML_FILES = sorted((ROOT / "knowledge_base" / "legal_issues").glob("CH_TENANCY_*.yaml"))
SPEC_FILES = sorted((ROOT / "scripts" / "kb" / "specs").glob("*.py"))
FACT_START = re.compile(r"^(\s*)- id:\s*(\S+)\s*$")
KEY = re.compile(r"^(\s*)(question_de|why_needed_de):")


def current_questions() -> dict[str, tuple[str, str]]:
    """fact_id -> (question, file name) of the first file that defines it."""
    out: dict[str, tuple[str, str]] = {}
    for f in YAML_FILES:
        for fact in yaml.safe_load(f.read_text(encoding="utf-8")).get("facts", []):
            out.setdefault(fact["id"], (fact["question_de"], f.name))
    return out


def patch_yaml(path: Path, before: dict[str, tuple[str, str]]) -> int:
    lines = path.read_text(encoding="utf-8").split("\n")
    out: list[str] = []
    cur = None
    n = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        m = FACT_START.match(line)
        if m:
            cur = m.group(2)
        k = KEY.match(line)
        if k and cur in FIXES:
            indent = len(k.group(1))
            j = i + 1
            while j < len(lines) and (lines[j].strip() == "" or len(lines[j]) - len(lines[j].lstrip()) > indent):
                if lines[j].strip() == "":
                    break
                j += 1
            if k.group(2) == "question_de":
                new = FIXES[cur][1]
                out.append(f"{k.group(1)}question_de: {json.dumps(new, ensure_ascii=False)}")
                n += 1
                i = j
                continue
            if k.group(2) == "why_needed_de" and cur in WHY_FIXES:
                block = " ".join(x.strip() for x in lines[i:j]).split(":", 1)[1].strip().strip("\"'")
                old, new = WHY_FIXES[cur]
                out.append(f"{k.group(1)}why_needed_de: {json.dumps(block.replace(old, new), ensure_ascii=False)}")
                n += 1
                i = j
                continue
        out.append(line)
        i += 1
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")
    return n


def patch_specs(before: dict[str, tuple[str, str]]) -> int:
    n = 0
    for sp in SPEC_FILES:
        t = sp.read_text(encoding="utf-8")
        orig = t
        for fid, (_kind, new, _note) in FIXES.items():
            old = before.get(fid, ("", ""))[0]
            if old and old != new:
                for q in ('"', "'"):
                    lit = f"{q}{old}{q}"
                    if lit in t:
                        t = t.replace(lit, json.dumps(new, ensure_ascii=False))
                        n += 1
        for fid, (old, new) in WHY_FIXES.items():
            if old in t:
                t = t.replace(old, new)
        if t != orig:
            sp.write_text(t, encoding="utf-8", newline="\n")
    return n


if __name__ == "__main__":
    before = current_questions()
    missing = [f for f in FIXES if f not in before]
    assert not missing, f"unknown fact ids: {missing}"
    rp = ROOT / "scripts" / "kb" / "question_fixes_report.json"
    prev = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {}
    for f in FIXES:  # keep the ORIGINAL wording across re-runs
        if f in prev and prev[f]["old"] != FIXES[f][1]:
            before[f] = (prev[f]["old"], before[f][1])
    report = {f: {"issue_file": before[f][1], "old": before[f][0], "new": FIXES[f][1], "kind": FIXES[f][0], "note": FIXES[f][2]} for f in FIXES}
    (ROOT / "scripts" / "kb" / "question_fixes_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    y = sum(patch_yaml(p, before) for p in YAML_FILES)
    s = patch_specs(before)
    print(f"yaml question blocks patched: {y}; spec literals patched: {s}; facts in table: {len(FIXES)}")
