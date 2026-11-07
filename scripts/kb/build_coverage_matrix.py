"""Erzeugt docs/ISSUE_COVERAGE_MATRIX.md aus den Dossiers (JSON) und der tatsächlichen Wissensbasis.

    python scripts/kb/build_coverage_matrix.py

Statuswerte: IMPLEMENTED | PARTIAL | PENDING_LEGAL_REVIEW | NOT_APPLICABLE | BLOCKED.
Zählwerte und Zuordnungen werden aus den Dateien geprüft (Abbruch bei Abweichung), damit die Matrix nicht veraltet.
"""

from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "apps" / "api"))

import kb_common as k  # noqa: E402
import yaml  # noqa: E402

from app.services.knowledge.loader import load_knowledge_base  # noqa: E402

ISSUES = {
    1: "CH_TENANCY_TERMINATION",
    2: "CH_TENANCY_PAYMENT_WARNING",
    3: "CH_TENANCY_PAYMENT_DEFAULT",
    4: "CH_TENANCY_EXTENSION",
    5: "CH_TENANCY_DEFECTS",
    6: "CH_TENANCY_EVICTION",
    7: "CH_TENANCY_RENT_INCREASE",
}
TITLES = {
    1: "Kündigung durch die Vermieterschaft", 2: "Zahlungsaufforderung mit Kündigungsandrohung",
    3: "Kündigung wegen Zahlungsverzug", 4: "Erstreckung des Mietverhältnisses", 5: "Mängel an der Mietsache",
    6: "Ausweisung und Räumung", 7: "Mietzinserhöhung",
}
ENGINE = "ENGINE"  # Zeile wird von der generischen Engine abgedeckt (kein Issue-Regel-ID)

# Dossier-Zeile (Reihenfolge der Tabelle «Eskalationsregeln») -> Regel-IDs (oder ENGINE_*)
ESC_MAP: dict[int, list[list[str]]] = {
    1: [["ENGINE_ASK"], ["TT_UNKNOWN_DELIVERY_OR_RECEIPT"], ["TT_DAYS_GE_20"], ["TT_DAYS_GT_30"], ["TT_DAYS_LT_20_ALL_KNOWN"],
        ["TT_FORM_MISSING", "TT_FAMILY_HOME_NOT_SEPARATE", "TT_CO_TENANT_NOT_NOTIFIED"], ["TT_PRIOR_DISPUTE", "TT_FAMILY_CHANGE"],
        ["TT_REASON_SPECIAL"], ["TT_HARDSHIP"], ["TT_MOVE_OUT_LT_60"], ["TT_PAYMENT_DEFAULT"], ["TT_AGREEMENT"],
        ["TT_OUT_OF_SCOPE_ROLE", "TT_OUT_OF_SCOPE_OBJECT", "TT_FURNISHED_ROOM"], ["TT_EXPERT_REQUESTED"]],
    2: [["ENGINE_ASK"], ["PW_FRIST_LAEUFT_NICHT_BEZAHLT"], ["PW_EMPFANG_ODER_FRIST_UNBEKANNT"], ["PW_FRIST_UNTER_30"],
        ["PW_ANDROHUNG_FEHLT_ODER_UNKLAR", "PW_BETRAG_UNKLAR"], ["PW_FAMILIENWOHNUNG_NICHT_SEPARAT", "PW_MITMIETER_NICHT_ALLE"],
        ["PW_MIETE_ZURUECKBEHALTEN"], ["PW_GEGENFORDERUNG"], ["PW_SOZIALDIENST_ZAHLUNG_AUSGEBLIEBEN"], ["PW_DRITTZAHLUNG_STREIT"],
        ["PW_FRIST_ABGELAUFEN"], ["PW_KUENDIGUNG_ERHALTEN"], ["PW_ABSPRACHE"], ["PW_ZAHLUNGSBEFEHL"]],
    3: [["PD_GRUNDREGEL"], ["PD_GRUNDREGEL", "ENGINE_ASK"], ["PD_EMPFANG_UNBEKANNT_ODER_GE20"], ["PD_PRUEFFRAGE1_MAHNUNG"],
        ["PD_PRUEFFRAGE2_ZAHLUNG"], ["PD_PRUEFFRAGE3_FORM"], ["PD_GERICHT"], ["PD_SELBSTHILFE"], ["PD_SOZIALDIENST_ZAHLT"],
        ["PD_KEINE_ANSCHLUSSLOESUNG"]],
    4: [["EX_ZAHLUNGSVERZUG", "EX_AUSSCHLUSS_ANDERE"], ["EX_UNBEFRISTET_FRIST"], ["EX_BEFRISTET_FRIST"], ["EX_ZWEITERSTRECKUNG"],
        ["EX_FRIST_VERPASST"], ["EX_HAERTEGRUENDE"], ["EX_ERSATZ_ODER_VERGLEICH"], ["EX_KEINE_SUCHE"], ["EX_SONDERFRAGEN"]],
    5: [["DF_ZAHLUNGSAUFFORDERUNG"], ["DF_MIETE_GEKUERZT"], ["DF_HINTERLEGUNG_LAEUFT"], ["DF_HINTERLEGUNG_GEPLANT"],
        ["DF_GESUNDHEIT_GEFAHR", "DF_H1_BESCHWERDEN", "DF_H2_GROSSER_BEFALL", "DF_H3_NICHT_MEIDBAR", "DF_H4_KEINE_ZWISCHENUNTERKUNFT",
         "DF_H5_GEMEINDE_ZUWEISUNG", "DF_H7_GESUNDHEIT_UNBEKANNT"],
        ["DF_AUSZIEHEN"], ["DF_KUENDIGUNG_NACH_MELDUNG"], ["DF_SCHADEN"], ["DF_SELBST_REPARIEREN"], ["DF_BEHOERDENBRIEF"],
        ["DF_URSACHE_UNKLAR"], ["ENGINE_PROCEED"], ["DF_KEINE_REAKTION_30"]],
    6: [["EV_GRUNDREGEL"], ["EV_RAEUMUNG_STEHT"], ["EV_SELBSTHILFE"], ["EV_NUR_KUENDIGUNG_ZAHLUNGSVERZUG", "EV_NUR_KUENDIGUNG_ANDERE"],
        ["EV_STADIUM_UNKLAR"], ["EV_UNTERSCHRIFT_AUSZUG"]],
    7: [["ENGINE_ASK"], ["RI_FRIST_20_ODER_UNBEKANNT"], ["RI_KEIN_FORMULAR", "RI_KUENDIGUNGSDROHUNG"], ["RI_PRUEFUNG_GRUNDREGEL"],
        ["RI_SUBVENTIONIERT_GENOSSENSCHAFT"], ["RI_UNTERSCHRIFT"], ["RI_NICHT_FINANZIERBAR"], ["ENGINE_PROCEED"],
        ["RI_KUENDIGUNG_IM_SCHREIBEN"]],
}

# Elemente, die nicht (oder nur teilweise) abgebildet sind -> ehrlich ausweisen
KNOWN_GAPS: dict[int, list[tuple[str, str, str]]] = {
    1: [("Ortsübliche Kündigungstermine (Art. 266c OR)", "PENDING_LEGAL_REVIEW",
         "Nicht hart kodiert (Teamvorgabe): Prüfhinweis TT_HINT_LOCAL_TERMS. Amtliche Quelle der Termine für Zürcher Gemeinden fehlt (Law-Team).")],
    2: [("Muster-Mahnung für den Upload-Test", "BLOCKED", "Optionale Zulieferung des Law-Teams steht aus."),
        ("Kommunale Richtlinie zur Übernahme von Mietrückständen (Sozialhilfe)", "BLOCKED", "Optionale Zulieferung steht aus."),
        ("Kontakt Schuldenberatung Kanton Zürich", "PENDING_LEGAL_REVIEW", "Stelle als SCHULDENBERATUNG_ZH geführt, Kontakt nicht verifiziert (laut Dossier nachzutragen)."),
        ("Konkubinat: Partner als Mitmieter prüfen", "PARTIAL", "Über die Fragen zu Mitmietern/Familienwohnung abgedeckt; kein eigener Prüfhinweis.")],
    3: [("BGE 127 III 548 / BGE 121 III 156 (optionale Volltexte)", "BLOCKED", "Optionale Zulieferung des Law-Teams steht aus."),
        ("Muster-Kündigungsformular des Kantons Zürich (Upload-Test)", "BLOCKED", "Optionale Zulieferung steht aus."),
        ("Anfechtungsempfehlung", "NOT_APPLICABLE", "Teamentscheid: Das System empfiehlt nie selbst, der Entscheid bleibt bei der Rechtsperson.")],
    4: [("Zürcher Entscheide zu Erstreckung bei Wohnungen mit Kindern", "BLOCKED", "Empfohlene Zulieferung des Law-Teams steht aus (BGE-Dauer-Entscheide betreffen Geschäftsräume)."),
        ("Zürcher Wohnhilfe-/Wohnungssuche-Stellen", "PENDING_LEGAL_REVIEW", "WOHNHILFE_ZH als Platzhalter ohne Kontakt."),
        ("Konkubinat als Härtegrund", "PARTIAL", "Nur als Faktum erfasst (Teamentscheid); Bewertung durch die Rechtsperson.")],
    5: [("Musterbrief «Mängelmeldung» ausfüllen", "BLOCKED", "Teamentscheid erlaubt das Ausfüllen (ohne Prozentzahl, ohne Hinterlegungsandrohung); die Brief-Erzeugung ist noch nicht gebaut."),
        ("Stichwortliste «Gefahr» für das Keyword-Netz", "PARTIAL", "Globale Safety-Erkennung besteht; Mängel-spezifische Stichwörter (Gas, Strom, Einsturz) sind über das Faktum health_safety_danger abgedeckt, nicht über ein eigenes Netz."),
        ("Gesundheitsbehörde / kommunale Stelle bei Schimmel", "PENDING_LEGAL_REVIEW", "Nur AWEL als allgemeine Auskunft; kommunale Eingriffsstelle ist im Dossier offen."),
        ("Planungs- und Baugesetz ZH (PBG)", "BLOCKED", "Optional laut Dossier, nicht geliefert.")],
    6: [("Streitwert-Berechnung (4A_391/2013 E. 5, OG ZH LF260018 E. 5.1)", "NOT_APPLICABLE", "Das System berechnet keine Fristen oder Streitwerte; Prüfpunkt für die Rechtsperson."),
        ("Keyword-Netz «Audienz», «Einzelgericht», «Räumungstermin», «Schloss ausgewechselt»", "IMPLEMENTED", "In issue_keywords.py (Mock/Prefilter); die globale Eskalation gilt zusätzlich."),
        ("Zürcher Entscheide mit Erfolg der Mieterin", "BLOCKED", "Optionale Zulieferung steht aus.")],
    7: [("Formularprüfung automatisch aus dem Upload (OCR/Layout)", "PARTIAL", "Pflichtangaben nach Art. 19 VMWG werden als Fakten abgefragt und von der Sozialarbeiterin am Original bestätigt; keine automatische Dokumentanalyse."),
        ("Mietzinslimiten der Sozialhilfe der Demo-Gemeinde", "BLOCKED", "Optionale Zulieferung steht aus; das System nennt keine Limite."),
        ("Zürcher Entscheid zu Erhöhung (Referenzzinssatz/Renovation)", "BLOCKED", "Optionale Zulieferung steht aus."),
        ("Referenzzinssatz-Wert / Missbräuchlichkeitsberechnung", "NOT_APPLICABLE", "Bewusst nicht implementiert (Verbot laut Dossier).")],
}


def doc_tables(n):
    d = k.load_extracted(n)
    return d


def esc_rows(n):
    d = doc_tables(n)
    for s in d["sections"]:
        for it in s["items"]:
            if it["type"] == "table" and it["rows"] and it["rows"][0][0] == "Wenn":
                return it["rows"][1:]
    return []


def section_bullets(n, start_prefix, stop_prefixes):
    d = doc_tables(n)
    out, on = [], False
    for s in d["sections"]:
        for it in s["items"]:
            if it["type"] == "p" and it["text"].startswith(start_prefix):
                on = True
                continue
            if it["type"] == "p" and it["text"].startswith(stop_prefixes):
                on = False
            if on and it["type"] == "bullet":
                out.append(it["text"])
    return out


def open_points(n):
    d = doc_tables(n)
    open_, done = [], []
    for s in d["sections"]:
        for it in s["items"]:
            if it["type"] in ("bullet", "p") and it["text"].startswith(("☐", "☒")):
                (open_ if it["text"].startswith("☐") else done).append(it["text"][1:].strip())
    return open_, done


def missing_deliveries(n):
    d = doc_tables(n)
    out, on = [], False
    for s in d["sections"]:
        if s["heading"].startswith("Was wir noch von euch brauchen"):
            for it in s["items"]:
                if it["type"] in ("bullet", "p"):
                    out.append(it["text"])
    return out


def status_cell(s):
    return f"`{s}`"


def main() -> None:
    kb = load_knowledge_base(k.KB)
    assert kb.valid, kb.errors
    all_hints = {iid: [lr for lr in kb.issues[iid].legal_rules] for iid in ISSUES.values()}
    scen_by_issue: dict[str, int] = {}
    for sc in kb.scenarios:
        for i in sc.issues:
            scen_by_issue[i["id"]] = scen_by_issue.get(i["id"], 0) + 1
    lines: list[str] = []
    w = lines.append
    w("# Issue-Abdeckungsmatrix (Issues 1–7)")
    w("")
    w("> GENERIERT durch `scripts/kb/build_coverage_matrix.py` aus den Law-Dossiers (`docs/legal_inputs/issues_extracted/*.json`) und der geladenen Wissensbasis. Nicht von Hand ändern.")
    w("> Stand der Dossiers: 7.11.2026. **Kein Issue ist juristisch freigegeben** (`content_status: DRAFT`).")
    w("")
    w("Statuswerte: `IMPLEMENTED` (in KB/Engine abgebildet und getestet) · `PARTIAL` (teilweise oder nur als Faktum/Hinweis) · "
      "`PENDING_LEGAL_REVIEW` (umgesetzt, aber fachlich/juristisch noch zu bestätigen) · `NOT_APPLICABLE` (bewusst nicht umgesetzt, Dossier verbietet es) · "
      "`BLOCKED` (Zulieferung fehlt).")
    w("")
    w("## Übersicht")
    w("")
    w("| Issue | KB-ID | Fakten | Eskalationsregeln | Rechtsregeln (HINT / REVIEW) | Szenarien | Dossier-Eskalationszeilen abgedeckt |")
    w("|---|---|---:|---:|---:|---:|---|")
    totals_rows = 0
    for n, iid in ISSUES.items():
        d = kb.issues[iid]
        hint = sum(1 for lr in d.legal_rules if lr.kind == "HINT")
        rev = sum(1 for lr in d.legal_rules if lr.kind == "REVIEW_POINT")
        rows = esc_rows(n)
        assert len(rows) == len(ESC_MAP[n]), (n, len(rows), len(ESC_MAP[n]))
        totals_rows += len(rows)
        sc = scen_by_issue.get(iid, 0) or sum(1 for s in kb.scenarios if any(i["id"] == iid for i in s.issues))
        w(f"| {n} {TITLES[n]} | `{iid}` | {len(d.facts)} | {len(d.escalation_rules)} | {hint} / {rev} | {sc} | {len(rows)} / {len(rows)} |")
    w("")
    w(f"Insgesamt {totals_rows} Eskalationszeilen aus den Dossiers; jede ist einer oder mehreren Regel-IDs zugeordnet (siehe unten).")
    w("")
    rule_ids = {r.id for d in kb.issues.values() for r in d.escalation_rules}
    for n, iid in ISSUES.items():
        d = kb.issues[iid]
        w(f"## Issue {n} – {TITLES[n]} (`{iid}`)")
        w("")
        # --- Struktur
        src = k.collect_dossier_sources(n)
        src_ids = [s["id"] for s in src]
        missing_src = [s for s in src_ids if s not in kb.sources]
        assert not missing_src, (n, missing_src)
        statutes = sum(1 for s in src if s["type"] == "statute")
        cases = sum(1 for s in src if s["type"] == "case_law")
        w("### Elemente")
        w("")
        w("| Dossier-Element | Status | Umsetzung |")
        w("|---|---|---|")
        w(f"| Gesetzesartikel ({statutes}) | {status_cell('IMPLEMENTED')} | Alle als Quellen in `sources.yaml` (Wortlaut `text_de`, `valid_as_of`, PDF-Seite); Fedlex-Verifikation steht aus (`UNVERIFIED`). |")
        w(f"| Leitentscheide ({cases}) | {status_cell('PENDING_LEGAL_REVIEW')} | Alle als Quellen mit Kernaussage/Fundstelle; Prüfstand «Volltext» laut Dossier, nicht systemseitig verifiziert. |")
        w(f"| Benötigte Informationen | {status_cell('IMPLEMENTED')} | {len(d.facts)} Fakten inkl. gemeinsam genutzter Vorprüfung; bedingte Pflicht über `required_if`; gleiche Frage nur einmal pro Fall. |")
        w(f"| Grenzen und Ausnahmefälle | {status_cell('PARTIAL' if n in (2, 4) else 'IMPLEMENTED')} | Als Eskalationsregeln, Prüfhinweise (REVIEW_POINT) und Aussagenfilter; nicht 1:1 abgebildete Randfälle siehe «Lücken». |")
        w(f"| Verfahren und Fristen | {status_cell('IMPLEMENTED')} | Nur als Aussage/Hinweis und Produktschwelle; **kein berechnetes Fristende**. |")
        w(f"| Stellen und Behörden | {status_cell('PENDING_LEGAL_REVIEW')} | `authorities.yaml` (`contact_verified: false`) und `referral_network.yaml` (Signale); keine erfundenen Kontakte. |")
        w(f"| Eskalationsregeln | {status_cell('IMPLEMENTED')} | Tabelle unten. |")
        w(f"| Erlaubte/verbotene Aussagen | {status_cell('IMPLEMENTED')} | Tabellen unten; Policy-Muster in `forbidden_statements.yaml`. |")
        w(f"| Briefing für die Fachperson | {status_cell('IMPLEMENTED')} | `briefing_profile` (Gruppen, Prüfpunkte, Dokumente, Stellen) im gemeinsamen Fallbericht; Template nicht dupliziert. |")
        w(f"| Teamentscheide (7.11.2026) | {status_cell('IMPLEMENTED')} | Siehe Eskalations- und Aussagen-Tabellen; Einwilligung `consent_briefing`; G7 pro Fakt (max. 2 Nachfragen, danach UNKNOWN → Eskalation)" + ("; Issue 6 ohne Rückfrage-Runden." if n == 6 else ".") + " |")
        w("")
        # --- Eskalation
        w("### Eskalationsregeln des Dossiers")
        w("")
        w("| # | Wenn (Dossier) | Route / Dringlichkeit (Dossier) | Regel-ID(s) | Status |")
        w("|---:|---|---|---|---|")
        for i, (row, ids) in enumerate(zip(esc_rows(n), ESC_MAP[n]), start=1):
            real = [x for x in ids if not x.startswith("ENGINE_")]
            for x in real:
                assert x in rule_ids or x in {lr.id for lr in d.legal_rules}, (n, x)
            engine = [x for x in ids if x.startswith("ENGINE_")]
            idtxt = ", ".join(f"`{x}`" for x in real) + ("; " if real and engine else "") + (
                "Engine (ASK)" if "ENGINE_ASK" in engine else "Engine (PROCEED)" if "ENGINE_PROCEED" in engine else "")
            wenn = row[0].replace("|", "/")
            route = f"{row[1]} · {row[2]}".replace("|", "/") if len(row) > 2 else row[1]
            w(f"| {i} | {wenn} | {route} | {idtxt} | {status_cell('IMPLEMENTED')} |")
        extra_rules = {
            1: "Zusätzlich aus den Teamentscheiden: `TT_FIXED_TERM_LE_75` (befristet, ≤ 75 Tage bis Vertragsende → sofort).",
            5: "Zusätzlich H6 als Prüfhinweis `DF_REVIEW_SUBVENTIONIERT` (kein Routing, nur Hinweis auf Issue 7).",
        }
        if n in extra_rules:
            w("")
            w(extra_rules[n])
        w("")
        # --- Erlaubte Aussagen
        allowed = [re.match(r"«(.+?)»", b).group(1) for b in section_bullets(n, "Erlaubte Aussagen", ("Verbotene Aussagen", "Briefing")) if re.match(r"«(.+?)»", b)]
        hints = [lr for lr in d.legal_rules if lr.kind == "HINT"]
        if n == 1:
            hints = [lr for lr in hints]
        w(f"### Erlaubte Aussagen ({len(allowed)})")
        w("")
        w("| Aussage (Dossier, gekürzt) | Status | HINT-ID |")
        w("|---|---|---|")
        for a in allowed:
            best, bid = 0.0, ""
            for lr in hints:
                r = SequenceMatcher(None, a, lr.result_de).ratio()
                if r > best:
                    best, bid = r, lr.id
            ok = best >= 0.72
            w(f"| {a[:110].replace('|', '/')}{'…' if len(a) > 110 else ''} | {status_cell('IMPLEMENTED' if ok else 'PARTIAL')} | " + (f"`{bid}`" if ok else f"nur sinngemäss/gar nicht (`{bid}`, {best:.2f})") + " |")
        w("")
        forb = section_bullets(n, "Verbotene Aussagen", ("Briefing", "Grund- und Menschenrechte"))
        w(f"### Verbotene Aussagen ({len(forb)})")
        w("")
        w(f"Alle {len(forb)} Dossier-Punkte sind über `policies/forbidden_statements.yaml` (Muster, beim Laden und zur Laufzeit geprüft) bzw. als Systemregel (keine Fristberechnung, keine Prognose, keine Prozentzahl, kein Referenzzinssatz) umgesetzt; "
          "die konkreten Beispielsätze sind in `apps/api/tests/test_issues_2_7.py::test_forbidden_statements_from_the_dossiers_are_blocked` bzw. `test_issue01.py` getestet. Abstrakte Punkte wie «Jedes berechnete Fristende» sind durch `FB_DEADLINE_END_DATE` und Textprüfungen der KB abgedeckt.")
        w("")
        # --- Lücken
        gaps = KNOWN_GAPS.get(n, [])
        w("### Lücken und offene Zulieferungen")
        w("")
        w("| Punkt | Status | Anmerkung |")
        w("|---|---|---|")
        for g in gaps:
            w(f"| {g[0]} | {status_cell(g[1])} | {g[2]} |")
        w("")
        op, done = open_points(n)
        w("### Offene Prüfpunkte laut Dossier (☐) – juristische Bestätigung")
        w("")
        if op:
            for x in op:
                w(f"- ☐ {x}  → {status_cell('PENDING_LEGAL_REVIEW')}")
        else:
            w("- keine")
        w("")
        w(f"Bereits vom Law-Team erledigt (☒): {len(done)}.")
        w("")
        md = missing_deliveries(n)
        if md:
            w("### «Was wir noch von euch brauchen» (Dossier)")
            w("")
            for x in md:
                w(f"- {x}")
            w("")
    w("## Querschnitt")
    w("")
    w("| Thema | Status | Anmerkung |")
    w("|---|---|---|")
    w(f"| Mehrere Issues pro Fall, Cross-Issue-Verweise aus YAML (`routes_to_issue`) | {status_cell('IMPLEMENTED')} | Geladene Issues werden zusätzlich angewendet; Status DRAFT wird im Hinweis ausgewiesen. |")
    w(f"| Gleiche Frage nur einmal (gemeinsame Fakten-IDs) | {status_cell('IMPLEMENTED')} | `analyze_facts` führt Fakten über Issues zusammen. |")
    w(f"| Höchste Dringlichkeit, zusammengeführte Gründe, deduplizierte Fachstellen | {status_cell('IMPLEMENTED')} | Engine sortiert nach Dringlichkeit; Referral-Plan dedupliziert. |")
    w(f"| Rückfrage-Runden (G7): max. 2 Nachfragen pro Fakt | {status_cell('IMPLEMENTED')} | Pro Fakt (bestehende Logik «zweimal unklar → unbekannt»); Issue 6 ohne Rückfrageschleife. Ein globaler Rundenzähler über den ganzen Fall existiert nicht. |")
    w(f"| `consent_briefing` (Status, Zeitpunkt, Erfasser, Geltungsbereich) | {status_cell('IMPLEMENTED')} | Fakt in allen Issues; Block im Fallbericht; blockiert die lokale Fallaufnahme nicht. Es gibt keinen Freigabe-Workflow für die tatsächliche externe Weitergabe. |")
    w(f"| Datenschutzrechtliche Einordnung (IDG ZH vs. DSG) | {status_cell('PENDING_LEGAL_REVIEW')} | Im Bericht als «voraussichtlich» gekennzeichnet; Bestätigung vor produktivem Einsatz nötig. |")
    w(f"| Gesundheitsangaben (H1–H7) ohne Diagnose/Ursache | {status_cell('IMPLEMENTED')} | Nur ja/nein; Wortlaut wird nicht gespeichert (`store_evidence: false`). |")
    w(f"| Gemini-Klassifikation für alle 7 Issues | {status_cell('IMPLEMENTED')} | Katalog dynamisch aus der KB; Fakten-Katalog per Keyword-Prefilter begrenzt (Kostenkontrolle); Entscheidungen bleiben deterministisch. |")
    w(f"| Fedlex-Verifikation der neuen Gesetzesquellen | {status_cell('PENDING_LEGAL_REVIEW')} | `python -m app.services.sources.fedlex.cli sync` (nur nach Freigabe); bis dahin `UNVERIFIED`. |")
    w("")
    out = k.ROOT / "docs" / "ISSUE_COVERAGE_MATRIX.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"geschrieben: {out} ({len(lines)} Zeilen)")


if __name__ == "__main__":
    main()
