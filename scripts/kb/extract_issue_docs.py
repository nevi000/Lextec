"""Extract the law team's Word dossiers (docs/legal_inputs/issues/issue_0N.docx) into structured JSON.

Output: docs/legal_inputs/issues_extracted/issue_0N.json  (sections -> paragraphs / bullets / tables / footnotes)
Nothing is interpreted here; this is a lossless, machine-readable copy that the importer and the coverage matrix use.

    python scripts/kb/extract_issue_docs.py
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "legal_inputs" / "issues"
OUT = ROOT / "docs" / "legal_inputs" / "issues_extracted"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def text_of(el) -> str:
    parts = []
    for n in el.iter():
        if n.tag == W + "t":
            parts.append(n.text or "")
        elif n.tag == W + "tab":
            parts.append("\t")
        elif n.tag == W + "br":
            parts.append("\n")
    return "".join(parts)


def extract(path: Path) -> dict:
    z = zipfile.ZipFile(path)
    body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    sections: list[dict] = [{"heading": "", "items": []}]
    for ch in body:
        if ch.tag == W + "p":
            st = ch.find(f"{W}pPr/{W}pStyle")
            style = (st.get(W + "val") if st is not None else "").lower()
            t = text_of(ch).strip()
            if not t:
                continue
            if style.startswith("heading") or style.startswith("berschrift"):
                sections.append({"heading": t, "items": []})
                continue
            is_bullet = ch.find(f"{W}pPr/{W}numPr") is not None
            sections[-1]["items"].append({"type": "bullet" if is_bullet else "p", "text": t})
        elif ch.tag == W + "tbl":
            rows = []
            for tr in ch.findall(W + "tr"):
                rows.append(
                    [" / ".join(text_of(p).strip() for p in tc.iter(W + "p") if text_of(p).strip()) for tc in tr.findall(W + "tc")]
                )
            sections[-1]["items"].append({"type": "table", "rows": rows})
    notes = []
    for name in z.namelist():
        if name.startswith(("word/footnotes", "word/endnotes")):
            for fn in ET.fromstring(z.read(name)):
                t = text_of(fn).strip()
                if t:
                    notes.append(t)
    title = next((s["heading"] for s in sections if s["heading"]), path.stem)
    return {"file": path.name, "title": title, "sections": sections, "footnotes": notes}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in sorted(SRC.glob("issue_0?.docx")):
        data = extract(f)
        (OUT / (f.stem + ".json")).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        n_tables = sum(1 for s in data["sections"] for i in s["items"] if i["type"] == "table")
        n_rows = sum(len(i["rows"]) for s in data["sections"] for i in s["items"] if i["type"] == "table")
        print(f"{f.name}: {len(data['sections'])} sections, {n_tables} tables, {n_rows} rows, {len(data['footnotes'])} footnotes")


if __name__ == "__main__":
    main()
