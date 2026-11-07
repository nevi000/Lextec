#!/usr/bin/env python3
"""Rendert ein LexTec-Bridge-Expert-Briefing im Layout der Fallzusammenfassung.

    python render_briefing.py sample/bridge_fall_0011.json --out output/Expert_Briefing_FALL-0011.pdf

- Daten: JSON wie sample/bridge_fall_0011.json (Struktur des Bridge-Briefings).
- Kontaktangaben der Stellen werden ueber "ref_id" aus knowledge_base/referrals/referral_rules.yaml ergaenzt.
- Ampel: aus Bridge-Dringlichkeit und Entscheid abgeleitet, nicht vom Sprachmodell.
- Fristende wird bewusst NICHT berechnet (Produktentscheid von Bridge).
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from render_summary import ROOT, TEMPLATES, data_uri, html_to_pdf

RULES = ROOT / "knowledge_base" / "referrals" / "referral_rules.yaml"

URGENCY_TO_LEVEL = {"sofort": "ROT", "bald": "AMBER", "normal": "GRUEN", "spaeter": "GRUEN", "später": "GRUEN"}
LEVEL_LABEL = {"ROT": "Sofort bearbeiten", "AMBER": "Bald bearbeiten", "GRUEN": "Ordentlich bearbeiten"}


def traffic_light(b: dict) -> dict:
    action = b["decision"]["action"]
    level = URGENCY_TO_LEVEL.get(b["urgency"]["level"], "AMBER")
    if action == "IMMEDIATE_SAFETY_RESPONSE":
        level = "ROT"
    elif action == "ESCALATE" and level == "GRUEN":
        level = "AMBER"
    reasons = [f"Stufe «{b['urgency']['level']}»", b["decision"]["label"]]
    reasons.append("Pflichtangaben vollständig" if not b.get("missing_mandatory") else f"{len(b['missing_mandatory'])} Pflichtangaben fehlen")
    return {"level": level, "label": LEVEL_LABEL[level], "reasons": reasons}


UMLAUT_FIX = {"Zuerich": "Zürich", "moeglich": "möglich", "taeglich": "täglich", "Roeschibach": "Röschibach",
              "Neumuehle": "Neumühle", "Foerrlibuck": "Förrlibuck", "Aemtler": "Ämtler"}


def de(text: str | None) -> str | None:
    """referral_rules.yaml schreibt Umlaute als ae/oe/ue; fuer die Ausgabe zurueckwandeln."""
    if not text:
        return text
    for a, b in UMLAUT_FIX.items():
        text = text.replace(a, b)
    return text


def contact_from_rules(entry: dict) -> dict | None:
    c = entry.get("contact") or {}
    if c.get("locations"):
        return {"address": f"{len(c['locations'])} Sozialzentren, Zuteilung nach Wohnadresse",
                "phone": None, "hours": de(c.get("hours"))}
    if not any(c.get(k) for k in ("address", "phone", "hours")):
        return None
    phone = c.get("phone") or c.get("phone_24h")
    return {"address": de(c.get("address")), "phone": de(phone), "hours": de(c.get("hours"))}


def enrich_bodies(b: dict) -> str:
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    index = {p["id"]: p for p in rules["professionals"]}
    for s in b["bodies"]:
        entry = index.get(s.get("ref_id"))
        s["contact"] = contact_from_rules(entry) if entry else None
        s["contact_primary"] = bool(entry and entry.get("contact_source") == "primary")
    return rules.get("last_reviewed") or "unbekannt"


def load_logo() -> str | None:
    for name in ("lextec_logo.svg", "lextec_logo.png"):
        f = ROOT / "assets" / name
        if f.exists():
            return data_uri(f) if f.suffix == ".png" else "data:image/svg+xml;base64," + base64.b64encode(f.read_bytes()).decode()
    return None


def build(data_path: Path, out_path: Path, html_out: Path | None = None) -> Path:
    b = json.loads(data_path.read_text(encoding="utf-8"))
    rr_checked = enrich_bodies(b)
    tl = traffic_light(b)
    src_title = {s["id"]: s["title"] for s in b["sources"]}
    fx = {f["label"]: f for g in b["fact_groups"] for f in g["facts"]}
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
    html = env.get_template("expert_briefing.html.j2").render(b=b, tl=tl, src_title=src_title, fx=fx, logo=load_logo(), rr_checked=rr_checked)
    pdf = html_to_pdf(html, {"case_id": b["case_id"]})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(pdf)
    if html_out:
        html_out.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("data_json", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "Expert_Briefing.pdf")
    ap.add_argument("--html", type=Path, default=None, help="optional: gerendertes HTML speichern (zum Portieren in die Bridge-App)")
    a = ap.parse_args()
    print(build(a.data_json, a.out, a.html))
