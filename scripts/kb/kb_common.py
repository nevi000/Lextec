"""Gemeinsame Helfer für den Issue-Importer (Quellen-Import, Bedingungs-Kurzschreibweise, YAML-Ausgabe).

Nichts hier erfindet Rechtsinhalte: Gesetzeswortlaute und BGE-Kernaussagen werden 1:1 aus den
extrahierten Dossier-Tabellen (docs/legal_inputs/issues_extracted/*.json) übernommen.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "knowledge_base"
EXTRACTED = ROOT / "docs" / "legal_inputs" / "issues_extracted"
SOURCES_YAML = KB / "legal_sources" / "sources.yaml"

SR_NUMBERS = {
    "OR": "220",
    "ZPO": "272",
    "SchKG": "281.1",
    "VMWG": "221.213.11",
    "BV": "101",
    "DSG": "235.1",
    "ZGB": "210",
}
STATUTE_NAMES = {
    "OR": "Obligationenrecht (OR)",
    "ZPO": "Zivilprozessordnung (ZPO)",
    "SchKG": "Schuldbetreibungs- und Konkursgesetz (SchKG)",
    "VMWG": "Verordnung über die Miete und Pacht von Wohn- und Geschäftsräumen (VMWG)",
}
VALID_AS_OF = {"OR": "2026-10-01", "ZPO": "2026-07-01", "SchKG": "2026-01-01", "VMWG": "2025-10-01"}
ORIGIN = {
    "OR": "OR_admin.pdf (SR 220, Stand 1.10.2026)",
    "ZPO": "ZPO.pdf (SR 272, Stand 1.7.2026)",
    "SchKG": "SCHKG.pdf (SR 281.1, Stand 1.1.2026)",
    "VMWG": "VMWG (SR 221.213.11, Stand 1.10.2025)",
}


# ------------------------------------------------------------------------------------ yaml io
def dump_yaml(obj: Any) -> str:
    return yaml.safe_dump(
        obj, allow_unicode=True, sort_keys=False, width=100, default_flow_style=False
    )


def load_extracted(n: int) -> dict:
    return json.loads((EXTRACTED / f"issue_{n:02d}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------- condition shorthand
def eq(ref: str, value: Any) -> dict:
    return {"ref": ref, "op": "equals", "value": value}


def ne(ref: str, value: Any) -> dict:
    return {"ref": ref, "op": "not_equals", "value": value}


def inn(ref: str, values: list) -> dict:
    return {"ref": ref, "op": "in", "value": values}


def unk(ref: str) -> dict:
    return {"ref": ref, "op": "is_unknown"}


def known(ref: str) -> dict:
    return {"ref": ref, "op": "is_known"}


def gt(ref: str, value: Any) -> dict:
    return {"ref": ref, "op": "greater_than", "value": value}


def lt(ref: str, value: Any) -> dict:
    return {"ref": ref, "op": "less_than", "value": value}


def all_(*c: dict) -> dict:
    return {"all": list(c)}


def any_(*c: dict) -> dict:
    return {"any": list(c)}


def F(x: str) -> str:  # noqa: N802 - fact reference
    return f"fact.{x}"


def D(x: str) -> str:  # noqa: N802 - derived reference
    return f"derived.{x}"


ALWAYS = {"ref": "ctx.has_user_input", "op": "equals", "value": True}


# ------------------------------------------------------------------------------- source import
def _norm_tokens(s: str) -> list[str]:
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(Art|Abs|lit|Ziff|und|bis|ff)\b\.?", " ", s)
    s = s.replace("§", " ")
    return [t for t in re.findall(r"[0-9]+[a-z]*|[a-z]\b", s, flags=re.I)]


def parse_statute_cell(cell: str) -> list[dict]:
    """'Art. 257d Abs. 1 OR' -> [{statute, id, article, paragraph, label}]; splits ' / ' variants."""
    out: list[dict] = []
    for part in [p.strip() for p in cell.split(" / ")]:
        m = re.match(r"^(Art\.|§)\s*(.+?)\s+(OR|ZPO|SchKG|VMWG|BV|DSG|ZGB|GOG ZH)\b(.*)$", part)
        if not m:
            continue
        kind, body, stat, rest = m.groups()
        tokens = _norm_tokens(body)
        if not tokens:
            continue
        if stat == "GOG ZH":
            sid = "ZH_GOG_" + "_".join(t.upper() for t in tokens)
        else:
            sid = f"CH_{stat.upper()}_" + "_".join(t.upper() for t in tokens)
        art = tokens[0]
        para = re.sub(r"\(.*?\)", "", body).strip()
        para = re.sub(r"^\s*" + re.escape(art), "", para).strip(" ,")
        out.append(
            {
                "statute": stat,
                "id": sid,
                "article": art.lower(),
                "paragraph": para or None,
                "label": f"{'§' if kind == '§' else 'Art.'} {body.strip()} {stat}".replace("  ", " "),
                "cantonal": stat == "GOG ZH",
            }
        )
    return out


def parse_case_cell(cell: str) -> list[dict]:
    """Cell of a Leitentscheide table -> list of {id, citation, case_number?, date?}."""
    out: list[dict] = []
    for m in re.finditer(r"BGE\s+(\d{2,3})\s+([IV]{1,3}[a-z]?)\s+(\d{1,4})", cell):
        v, abt, s = m.groups()
        item = {"id": f"BGE_{v}_{abt}_{s}", "citation": f"BGE {v} {abt} {s}"}
        out.append(item)
    for m in re.finditer(r"BGer\s+(4[AC][_.]\d+[/_]\d{4})", cell):
        raw = m.group(1)
        item = {"id": "BGER_" + re.sub(r"[^0-9A-Za-z]+", "_", raw).upper(), "citation": f"BGer {raw}"}
        out.append(item)
    m = re.search(r"Obergericht ZH,?\s+(LF\d+)(?:-O/U)?\s+vom\s+([\d.]+)", cell)
    if m:
        out.append(
            {
                "id": f"OGZH_{m.group(1)}",
                "citation": f"Obergericht ZH, {m.group(1)} vom {m.group(2)}",
            }
        )
    # only keep first (primary) citation when the cell lists a decision with its full-text twin
    seen: set[str] = set()
    uniq = []
    for x in out:
        if x["id"] not in seen:
            seen.add(x["id"])
            uniq.append(x)
    return uniq


def _dossier_status(prufstand: str) -> str:
    return "DOSSIER_CHECKED" if "Volltext" in (prufstand or "") else "DOSSIER_PENDING"


def collect_dossier_sources(n: int) -> list[dict]:
    """All source entries (new format of sources.yaml) found in the tables of dossier n."""
    d = load_extracted(n)
    found: list[dict] = []
    for sec in d["sections"]:
        for it in sec["items"]:
            if it["type"] != "table" or not it["rows"]:
                continue
            head = [h.lower() for h in it["rows"][0]]
            joined = " ".join(head)
            if head and head[0].startswith("artikel"):
                core_i = next(i for i, h in enumerate(head) if h.startswith("wortlaut"))
                page_i = next((i for i, h in enumerate(head) if h.startswith("pdf")), None)
                fn_i = next((i for i, h in enumerate(head) if h.startswith("funktion")), None)
                for row in it["rows"][1:]:
                    for p in parse_statute_cell(row[0]):
                        e = {
                            "id": p["id"],
                            "provider": "other" if p["cantonal"] else "fedlex",
                            "type": "statute",
                            "language": "de",
                            "title_de": p["label"],
                            "dossier_status": "DOSSIER_CHECKED",
                            "verification_status": "UNVERIFIED",
                            "article": p["article"],
                        }
                        if p["cantonal"]:
                            e["jurisdiction"] = "ZH"
                            e["statute"] = "GOG ZH"
                            e["fedlex_sync"] = False
                        else:
                            e["sr_number"] = SR_NUMBERS[p["statute"]]
                            e["statute"] = p["statute"]
                            e["title_de"] = f"{STATUTE_NAMES.get(p['statute'], p['statute'])}, {p['label'].split(p['statute'])[0].strip()}"
                            e["valid_as_of"] = VALID_AS_OF.get(p["statute"])
                            e["origin_ref"] = ORIGIN.get(p["statute"])
                        if p["paragraph"]:
                            e["paragraph"] = p["paragraph"]
                        e["text_de"] = row[core_i]
                        if fn_i is not None and len(row) > fn_i:
                            e["legal_question_de"] = row[fn_i]
                        if page_i is not None and len(row) > page_i and row[page_i]:
                            e["origin_ref"] = (e.get("origin_ref") or "") + f", {row[page_i]}"
                        e["_issue"] = n
                        found.append(e)
            elif "kernaussage" in joined and any(
                h.startswith(("bge", "entscheid", "urteil")) for h in head
            ):
                ci = next(i for i, h in enumerate(head) if h.startswith(("bge", "entscheid")))
                core_i = next(i for i, h in enumerate(head) if h.startswith("kernaussage"))
                pr_i = next((i for i, h in enumerate(head) if h.startswith("prüfstand")), None)
                fn_i = next((i for i, h in enumerate(head) if h.startswith("funktion")), None)
                for row in it["rows"][1:]:
                    if len(row) <= core_i:
                        continue
                    cites = parse_case_cell(row[ci])
                    for c in cites:
                        e = {
                            "id": c["id"],
                            "provider": "other" if c["id"].startswith("OGZH") else "bger",
                            "type": "case_law",
                            "language": "de",
                            "title_de": c["citation"],
                            "citation": c["citation"],
                            "dossier_status": _dossier_status(row[pr_i]) if pr_i is not None else "DOSSIER_PENDING",
                            "verification_status": "UNVERIFIED",
                            "core_statement_de": row[core_i],
                            "scope_de": row[ci],
                        }
                        if c["id"].startswith("OGZH"):
                            e["jurisdiction"] = "ZH"
                        if fn_i is not None and len(row) > fn_i and row[fn_i]:
                            e["legal_question_de"] = row[fn_i]
                        e["_issue"] = n
                        found.append(e)
            elif head and head[0].startswith("entscheid") and "lehrbuch" in joined:
                for row in it["rows"][1:]:
                    for c in parse_case_cell(row[0].replace("E. ", " ")):
                        e = {
                            "id": c["id"],
                            "provider": "bger",
                            "type": "case_law",
                            "language": "de",
                            "title_de": c["citation"],
                            "citation": c["citation"],
                            "dossier_status": "DOSSIER_PENDING",
                            "verification_status": "UNVERIFIED",
                            "core_statement_de": row[1],
                            "limits_de": "Nur über das Lehrbuch zitiert, Volltext nicht geprüft.",
                            "scope_de": row[0],
                            "_issue": n,
                        }
                        found.append(e)
    return found


# Quellen, die nicht in den Tabellen stehen, aber in den Dossiers (Text) verwendet werden.
EXTRA_SOURCES: list[dict] = [
    {
        "id": "BGER_4A_68_2014",
        "provider": "bger",
        "type": "case_law",
        "title_de": "BGer 4A_68/2014 vom 16.6.2014 (vollständiges Urteil zu BGE 140 III 315)",
        "citation": "BGer 4A_68/2014",
        "case_number": "4A_68/2014",
        "decision_date": "2014-06-16",
        "dossier_status": "DOSSIER_CHECKED",
        "considerations": ["E. 4.2", "E. 4.3", "E. 4.4", "E. 5.3"],
        "core_statement_de": "Eine Geldschuld muss nicht persönlich erfüllt werden; zahlt ein Dritter (z. B. der Sozialdienst) innert der Mahnfrist, tilgt das die Schuld der Mieterin (Art. 68 OR). Erst nach Fristende zurücküberwiesene Zahlungen gelten als angenommen.",
        "scope_de": "Zahlung durch Dritte innert Zahlungsfrist (Art. 257d OR)",
        "relevant_fact_ids": ["third_party_payment", "payment_returned_by_landlord"],
    },
    {
        "id": "BGER_4A_366_2008",
        "provider": "bger",
        "type": "case_law",
        "title_de": "BGer 4A_366/2008",
        "citation": "BGer 4A_366/2008",
        "case_number": "4A_366/2008",
        "dossier_status": "DOSSIER_CHECKED",
        "considerations": ["E. 4"],
        "core_statement_de": "Das Konto der Vermieterschaft muss bis zum letzten Tag der Frist gutgeschrieben sein; knapp drei Wochen zwischen Fristablauf und Kündigung sind «wohl an der Grenze» des Zulässigen, längeres Zuwarten kann als Verzicht verstanden werden.",
        "scope_de": "Rechtzeitigkeit der Zahlung; Wartezeit bis zur Kündigung",
    },
    {
        "id": "BGER_4A_585_2010",
        "provider": "bger",
        "type": "case_law",
        "title_de": "BGer 4A_585/2010",
        "citation": "BGer 4A_585/2010",
        "case_number": "4A_585/2010",
        "dossier_status": "DOSSIER_CHECKED",
        "considerations": ["E. 3.1", "E. 3.5"],
        "core_statement_de": "Neuere Praxis: Eine Kündigung vor Ablauf der Zahlungsfrist ist unwirksam; Ausnahme, wenn am letzten Tag verfasst und erst nach Fristablauf zugestellt.",
        "limits_de": "Betraf eher Geschäftsräume; Übernahme für Wohnungen als Teamentscheid (7.11.2026).",
    },
    {
        "id": "OGZH_LF250009",
        "provider": "other",
        "type": "case_law",
        "jurisdiction": "ZH",
        "title_de": "Obergericht ZH, LF250009 vom 14.4.2025",
        "citation": "Obergericht ZH, LF250009 vom 14.4.2025",
        "decision_date": "2025-04-14",
        "dossier_status": "DOSSIER_CHECKED",
        "considerations": ["E. 3.1", "E. 3.4"],
        "core_statement_de": "Verrechnungserklärung innert der 30-Tage-Frist und gegenüber der Vermieterschaft; die Vollstreckungsbehörde prüft fürsorgerische Massnahmen.",
    },
    {
        "id": "MGZH_ZMP_2018_1",
        "provider": "other",
        "type": "case_law",
        "jurisdiction": "ZH",
        "title_de": "Mietgericht Zürich, ZMP 2018 Nr. 1",
        "citation": "ZMP 2018 Nr. 1",
        "dossier_status": "DOSSIER_PENDING",
        "core_statement_de": "«kann gekündigt werden» genügt als Androhung; Kündigung kurz vor einem vereinbarten Gespräch über Gegenforderungen war treuwidrig.",
    },
    {
        "id": "LEHRBUCH_MIETE_31",
        "provider": "other",
        "type": "other",
        "title_de": "Lehrbuch «§ 31 Miete (Art. 253–273c OR) und Pacht» (Auszug des Law-Teams)",
        "dossier_status": "DOSSIER_PENDING",
        "legal_question_de": "Bibliografische Angabe (Autor:in, Titel, Auflage) steht laut Dossier noch aus.",
        "core_statement_de": "Sekundärquelle; Randziffern (N) und Buchseiten (S.) werden in den Dossiers zitiert.",
    },
    {
        "id": "PRODUKTREGEL",
        "provider": "other",
        "type": "other",
        "title_de": "Produktregel / Teamentscheid (7.11.2026)",
        "dossier_status": "DOSSIER_CHECKED",
        "core_statement_de": "Interne Produktschwelle oder -regel des Teams. Keine Gesetzes- oder Gerichtsaussage.",
    },
    {
        "id": "CH_BV_12",
        "provider": "fedlex",
        "type": "statute",
        "sr_number": "101",
        "statute": "BV",
        "article": "12",
        "title_de": "Bundesverfassung (BV), Art. 12",
        "dossier_status": "DOSSIER_CHECKED",
        "text_de": "Wer in Not gerät und nicht in der Lage ist, für sich zu sorgen, hat Anspruch auf Hilfe und Betreuung und auf die Mittel, die für ein menschenwürdiges Dasein unerlässlich sind.",
        "legal_question_de": "Anspruch richtet sich gegen das Gemeinwesen, nicht gegen die Vermieterschaft (Route SOZIAL).",
        "origin_ref": "BV (SR 101, Stand 3.3.2024), PDF-S. 4",
    },
    {
        "id": "BAG_SCHIMMEL_2021",
        "provider": "other",
        "type": "other",
        "title_de": "BAG «Schimmel in Wohnräumen» (2021)",
        "dossier_status": "DOSSIER_CHECKED",
        "core_statement_de": "Gesundheitliche Einschätzung (Kategorien nach Fläche); keine rechtliche Einordnung des Mangels. Betroffene Personen mit Beschwerden sollen ärztlich abklären lassen; stark befallene Räume nach Möglichkeit nicht nutzen.",
        "limits_de": "Das System nutzt die BAG-Einteilung nur für die Dringlichkeit, nicht für Aussagen zu Rechten.",
    },
    {
        "id": "IDG_ZH_17",
        "provider": "other",
        "type": "statute",
        "jurisdiction": "ZH",
        "statute": "IDG ZH",
        "article": "17",
        "fedlex_sync": False,
        "title_de": "IDG ZH (LS 170.4), § 17 Abs. 1",
        "dossier_status": "DOSSIER_PENDING",
        "text_de": "Weitergabe besonderer Personendaten nur mit formellgesetzlicher Grundlage, ausdrücklicher Einwilligung im Einzelfall oder zur Abwendung einer Gefahr für Leib und Leben.",
        "legal_question_de": "Grundlage für consent_briefing; Anwendbarkeit des IDG auf das Start-up ist «voraussichtlich» (Teamentscheid), nicht endgültig geklärt.",
    },
    {
        "id": "CH_DSG_6_7",
        "provider": "fedlex",
        "type": "statute",
        "sr_number": "235.1",
        "statute": "DSG",
        "article": "6",
        "paragraph": "Abs. 7 lit. a",
        "title_de": "Datenschutzgesetz (DSG), Art. 6 Abs. 7 lit. a",
        "dossier_status": "DOSSIER_PENDING",
        "text_de": "Einwilligung muss bei besonders schützenswerten Personendaten ausdrücklich erfolgen.",
        "legal_question_de": "Grundlage für consent_briefing (falls DSG statt IDG gilt).",
    },
]


def merge_sources(new_entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Merge into sources.yaml content; existing ids are never overwritten. Returns (sources, added_ids)."""
    data = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8"))
    have = {s["id"] for s in data["sources"]}
    added: list[str] = []
    for e in new_entries:
        e = {k: v for k, v in e.items() if not k.startswith("_") and v not in (None, "")}
        e.setdefault("language", "de")
        e.setdefault("verification_status", "UNVERIFIED")
        e.setdefault("dossier_status", "DOSSIER_PENDING")
        if e["id"] in have:
            continue
        have.add(e["id"])
        data["sources"].append(e)
        added.append(e["id"])
    return data, added


# ------------------------------------------------------------------------------ spec constructors
def fact(
    id: str,
    label: str,
    q: str,
    why: str,
    *,
    type: str = "boolean",
    group: str = "",
    enum: dict | None = None,
    req: bool = False,
    req_if: dict | None = None,
    prio: str = "medium",
    esc: bool = False,
    hint: str = "",
    src: list[str] | None = None,
    deps: list[str] | None = None,
    desc: str = "",
    no_evidence: bool = False,
) -> dict:
    d: dict[str, Any] = {"id": id}
    if group:
        d["group"] = group
    d["label_de"] = label
    if desc:
        d["description"] = desc
    d["data_type"] = type
    if enum:
        d["enum_values"] = list(enum.keys())
        d["enum_labels_de"] = dict(enum)
    if req:
        d["required"] = True
    if req_if:
        d["required_if"] = req_if
    d["priority"] = prio
    if esc:
        d["escalation_relevant"] = True
        d["handover_priority"] = "high"  # facts read by escalation rules are most valuable to the expert
    if deps:
        d["depends_on"] = deps
    if src:
        d["source_ids"] = src
    if hint:
        d["extraction_hint_de"] = hint
    if no_evidence:
        d["store_evidence"] = False
    d["question_de"] = q
    d["why_needed_de"] = why
    return d


def esc_rule(
    id: str,
    desc: str,
    when: dict,
    urg: str,
    code: str,
    reason: str,
    pros: list[str],
    *,
    route: str | None = None,
    suppress: bool = False,
) -> dict:
    d: dict[str, Any] = {
        "id": id,
        "description": desc,
        "when": when,
        "urgency": urg,
        "reason_code": code,
        "reason_de": reason,
        "professionals": pros,
    }
    if route:
        d["routes_to_issue"] = route
    if suppress:
        d["suppress_standard_statements"] = True
    return d


def legal(
    id: str, desc: str, when: dict, code: str, text: str, src: list[str], kind: str = "HINT"
) -> dict:
    return {
        "id": id,
        "description": desc,
        "kind": kind,
        "when": when,
        "result_code": code,
        "result_de": text,
        "legal_source_ids": src,
    }


def scenario(
    id: str,
    title: str,
    action: str,
    *,
    issues: list[str],
    facts: dict | None = None,
    unknown: list[str] | None = None,
    urgency: str | None = None,
    rules: list[str] | None = None,
    not_rules: list[str] | None = None,
    routes: list[str] | None = None,
    reasons: list[str] | None = None,
    missing: list[str] | None = None,
    today: str | None = None,
    has_input: bool = True,
) -> dict:
    d: dict[str, Any] = {
        "id": id,
        "title_de": title,
        "validation": "SYNTHETIC_TECHNICAL",
        "has_user_input": has_input,
        "issues": [{"id": i, "confidence": 0.9} for i in issues],
    }
    if facts:
        d["facts"] = facts
    if unknown:
        d["unknown_facts"] = unknown
    if today:
        d["today"] = today
    d["expected_action"] = action
    if urgency:
        d["expected_urgency"] = urgency
    if rules:
        d["expected_rule_ids"] = rules
    if not_rules:
        d["expected_not_rule_ids"] = not_rules
    if routes:
        d["expected_route_issue_ids"] = routes
    if reasons:
        d["expected_reason_codes"] = reasons
    if missing:
        d["expected_missing_facts"] = missing
    return d


def shared_facts(ids: list[str]) -> list[dict]:
    """Copy fact definitions from the Issue-1 file (same id => same fact, asked only once per case)."""
    issue1 = yaml.safe_load(
        (KB / "legal_issues" / "CH_TENANCY_TERMINATION.yaml").read_text(encoding="utf-8")
    )
    by_id = {f["id"]: f for f in issue1["facts"]}
    out = []
    for i in ids:
        f = dict(by_id[i])
        out.append(f)
    return out


# --------------------------------------------------------------------------- Stellen (Authorities)
# Nur Angaben aus den Dossiers. Keine erfundenen Kontakte; Telefon/Adresse nur, wenn das Dossier sie nennt.
AUTHORITIES_NEW: list[dict] = [
    {"id": "SCHULDENBERATUNG_ZH", "name_de": "Schuldenberatung Kanton Zürich",
     "purpose_de": "Mietrückstände, Betreibungen, Zahlungsplan als Verhandlungsbasis.",
     "cost_de": "Kontakt und Kosten prüfen (laut Dossier noch zu ergänzen).", "source_note_de": "Dossier Issue 2/3: Kontakt nachzutragen (offiziell prüfen)."},
    {"id": "WOHNHILFE_ZH", "name_de": "Fachstellen für Wohnungssuche / kommunale Wohnhilfe (Kanton Zürich)",
     "purpose_de": "Unterstützung bei der Wohnungssuche.", "cost_de": "Unterschiedlich.",
     "source_note_de": "Dossier Issue 4: Zürcher Wohnhilfe- bzw. Wohnungssuche-Stellen noch zu ergänzen."},
    {"id": "EINZELGERICHT_BEZIRKSGERICHT_ZH", "name_de": "Einzelgericht des Bezirksgerichts (in Zürich: «Einzelgericht Audienz»)",
     "purpose_de": "Entscheidet über das Ausweisungsgesuch im Verfahren für klare Fälle und über die Vollstreckung.",
     "source_note_de": "§ 24 lit. c, e GOG ZH; OG ZH LF260018."},
    {"id": "MIETGERICHT_ZH", "name_de": "Mietgericht des Bezirks",
     "purpose_de": "Klage nach Klagebewilligung oder Ablehnung eines Entscheidvorschlags; Ausweisung auf dem ordentlichen Weg.",
     "cost_de": "Kosten möglich; deshalb immer Rechtsperson.", "source_note_de": "§§ 21, 26 GOG ZH; Obergericht ZH, Seite «Hinterlegung»."},
    {"id": "OBERGERICHT_ZH_ZIVILKAMMER", "name_de": "Obergericht des Kantons Zürich, II. Zivilkammer",
     "purpose_de": "Berufung und Beschwerde gegen Ausweisungsentscheide.", "source_note_de": "OG ZH LF260018."},
    {"id": "STADTAMMANNAMT_ZH", "name_de": "Gemeinde- bzw. Stadtammannamt",
     "purpose_de": "Vollzug der Räumung, Räumungstermin, nötigenfalls mit Polizei.", "source_note_de": "§ 147 GOG ZH; Checkliste Obergericht ZH."},
    {"id": "KASSE_BEZIRKSGERICHT_ZH", "name_de": "Kasse des Bezirksgerichts",
     "purpose_de": "Einzahlung der hinterlegten Mietzinse nach Depositionsanweisung der Schlichtungsbehörde.",
     "source_note_de": "Obergericht ZH, Seite «Hinterlegung»; § 66 Abs. 2 GOG ZH."},
    {"id": "AWEL_SCHIMMEL", "name_de": "AWEL, Abteilung Luft, Klima und Strahlung, Sektion Emissionskontrolle (Baudirektion Kanton Zürich)",
     "purpose_de": "Allgemeine Auskunft zu Schimmel, Gesundheitsrisiken, Vorgehen und Zuständigkeiten; keine Durchsetzung gegenüber der Vermieterschaft.",
     "scope_de": "Telefon laut Dossier: 043 257 41 64. Rechtsberatung: Verweis auf Mieterverband.",
     "source_note_de": "Kanton Zürich, Umweltpraxis (ZUP) Nr. 113, März 2026, S. 33 f. Eine kommunale Behörde, die bei Schimmel in Mietwohnungen eingreift, ist nicht genannt (offen)."},
    {"id": "NOTUNTERKUNFT_FAMILIEN_STADT_ZH", "name_de": "Notunterkunft für Familien, Stadt Zürich (Soziale Einrichtungen und Betriebe)",
     "purpose_de": "Obdachlose Familien mit Wohnsitz in der Stadt Zürich, höchstens 6 Monate. Keine Selbstanmeldung: Zuweisung über die Sozialen Dienste bzw. das Sozialzentrum im Quartier, in dringenden Fällen direkt.",
     "cost_de": "Kostengutsprache nötig.", "scope_de": "Soziale Dienste: 044 412 65 54 (laut Dossier). Prozessdauer 4–6 Wochen (am Original bestätigt, 7.11.2026).",
     "source_note_de": "Stadt Zürich, Seite «Notunterkunft für Familien»; Heilsarmee-Übersicht, Stand 30.6.2026, S. 4."},
    {"id": "NOTSCHLAFSTELLE_ZH", "name_de": "Notschlafstelle Rosengartenstrasse 30, 8037 Zürich (Stadt Zürich)",
     "purpose_de": "Sofortige Übernachtung ohne Anmeldung, ab 18 Jahren, Wohnsitz Stadt Zürich (sonst Entscheid des Teams), keine Tiere; für Familien mit Kindern nicht geeignet.",
     "cost_de": "Kostenlos.", "scope_de": "Telefon laut Dossier: 044 415 77 14.", "source_note_de": "Heilsarmee-Übersicht, Stand 30.6.2026, S. 3."},
    {"id": "SEKRETARIAT_WOHNEN_OBDACH_ZH", "name_de": "Sekretariat Wohnen und Obdach, Strassburgstrasse 5, 8004 Zürich",
     "purpose_de": "Anmeldung für alle städtischen Wohnangebote (Übergangswohnen, Wohnintegration).", "cost_de": "Kostengutsprache nötig; Selbstzahlende im Einzelfall.",
     "scope_de": "Telefon laut Dossier: 044 412 65 54.", "source_note_de": "Heilsarmee-Übersicht, Stand 30.6.2026, S. 1."},
    {"id": "BWO_REFERENZZINSSATZ", "name_de": "Bundesamt für Wohnungswesen (BWO)",
     "purpose_de": "Veröffentlicht den hypothekarischen Referenzzinssatz. Das System nennt keinen aktuellen Wert, weil er sich ändert.",
     "source_note_de": "Dossier Issue 7; nur Information."},
    {"id": "KONTROLLBEHOERDE_SUBVENTIONIERT", "name_de": "Kontrollierende Behörde bei subventionierten Wohnungen",
     "purpose_de": "Mietzinskontrolle statt Anfechtung nach Art. 270 ff. OR.", "source_note_de": "Art. 253b Abs. 3 OR; Stelle je nach Wohnung, noch zu klären."},
]
