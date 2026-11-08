# Knowledge Base – Leitfaden für das Law-Team

Die Knowledge Base (KB) besteht aus YAML-Dateien im Ordner `knowledge_base/`. **Neue Rechtsprobleme, Fakten, Rückfragen und Regeln werden ausschliesslich dort gepflegt – ohne Python-Änderungen.** Die Software liest die Dateien beim Start (oder über «YAML neu laden» auf der Seite *Knowledge Base*).

> Alle mitgelieferten Dateien sind **DEMO / SYNTHETISCH / NICHT JURISTISCH VALIDIERT**. Sie zeigen nur, wie die Technik funktioniert. Es sind keine Schweizer Rechtsaussagen. Setzen Sie `content_status` erst auf `LEGALLY_REVIEWED`, wenn der Inhalt von einer Fachperson geprüft ist.

## 1. Ordnerstruktur

```
knowledge_base/
├── legal_issues/        ein File pro Rechtsproblem (z. B. tenancy_termination.yaml)
├── routing/             globale Eskalationsregeln (global_escalation.yaml)
├── legal_sources/       Rechtsquellen als Metadaten (sources.yaml)
├── referrals/           Fachpersonen-Typen (professionals.yaml)
├── briefings/           Briefing-Vorlagen (expert_briefing.yaml)
└── tests/               Testszenarien mit erwarteter Entscheidung (scenarios.yaml)
```

**Tipp:** In VS Code die Erweiterung «YAML» (Red Hat) installieren (wird vorgeschlagen). Jede Datei verweist in der ersten Zeile auf ein Schema aus `schemas/`; der Editor meldet Tippfehler, unbekannte Felder und falsche Werte sofort.

## 2. Wie entscheidet das System?

Das Sprachmodell **versteht und strukturiert** nur den Text. Die Entscheidung trifft eine deterministische Regel-Engine in dieser Reihenfolge:

1. **ESCALATE** – wenn irgendeine Eskalationsregel zutrifft (global oder des Rechtsgebiets) oder das Rechtsgebiet nicht abgedeckt ist.
2. **ASK** – sonst, wenn erforderliche Fakten fehlen, unklar oder widersprüchlich sind. Das System stellt die wichtigste Frage.
3. **PROCEED** – nur, wenn alle erforderlichen Fakten bekannt sind **und** keine Eskalationsregel zutrifft.

Wichtig für Sie:
* **Eine Regel kann nie «PROCEED» erzwingen.** Regeln können nur eskalieren. PROCEED entsteht ausschliesslich durch «alles Nötige bekannt, nichts löst aus».
* Bei ESCALATE bleiben fehlende Fakten sichtbar (sie helfen der Fachperson).
* Ein unbekanntes Rechtsgebiet oder eine fehlerhafte YAML-Datei führt **nie** zu PROCEED, sondern zur Eskalation.

## 3. Ein Rechtsproblem definieren (`legal_issues/*.yaml`)

```yaml
# yaml-language-server: $schema=../../schemas/issue_definition.schema.json
schema_version: 1                   # aktuell immer 1
id: tenancy_termination             # eindeutig, snake_case, = technischer Name
version: "0.1-demo"                 # Ihre Versionsnummer (Text)
content_status: DEMO_SYNTHETIC      # DEMO_SYNTHETIC | DRAFT | LEGALLY_REVIEWED
                                    # DRAFT = classifiable, not yet legally released; LEGALLY_REVIEWED = released;
                                    # DEMO_SYNTHETIC = placeholder content: loaded for old cases/tests, NEVER offered to the
                                    # classifier for new cases (KnowledgeBase.catalog_issues()).
jurisdiction: CH
legal_area: tenancy
issue: landlord_termination
title_de: Mietkündigung             # so sieht es die Sozialarbeiterin
description: "Kurzbeschreibung"

classification:                     # Hilfe für die KI-Zuordnung
  description: "Passt, wenn ..."
  typical_situations: ["Der Vermieter hat die Wohnung gekündigt."]
  related_issues: [tenancy_defects] # müssen existierende IDs sein

facts:                              # siehe 3.1
legal_rules:                        # siehe 3.2
escalation_rules:                   # siehe 3.3
legal_source_ids: [CH_OR_266L]      # müssen in sources.yaml existieren
default_professionals: [tenancy_law_counsel]   # müssen in professionals.yaml existieren
briefing_template: expert_briefing_v1
```

### 3.1 Fakten (`facts`)

```yaml
- id: landlord_termination_received_date   # snake_case, eindeutig innerhalb des Rechtsproblems
  label_de: Datum des Kündigungserhalts    # Kurzname im Fallüberblick
  data_type: date                          # string | boolean | date | integer | enum
  required_if: { ref: fact.landlord_termination_received, op: equals, value: true }
  priority: high                           # high | medium | low  -> Reihenfolge der Rückfragen
  question_de: "An welchem Datum wurde die Kündigung zugestellt?"
  why_needed_de: "Warum fragen wir das? (wird der Sozialarbeiterin angezeigt)"
```

| Feld | Bedeutung |
|---|---|
| `required: true` | Muss immer geklärt werden (sonst ASK). |
| `required_if: <Bedingung>` | Nur erforderlich, wenn die Bedingung zutrifft (bedingter Fakt). Nicht zusammen mit `required` verwenden. |
| ohne beides | Optional: wird angezeigt, blockiert aber nichts. |
| `enum_values: [..]` | Nur bei `data_type: enum`. |
| `priority` | `high` zuerst. Bei gleicher Priorität gilt die Reihenfolge in der Datei. |

**Gemeinsame Fakten:** Dieselbe Fakt-ID (z. B. `deadline_pending`) darf in mehreren Rechtsproblemen vorkommen. Sie wird dann **einmal** gefragt und gilt für alle. Der `data_type` muss überall gleich sein. Fakten mit unterschiedlicher Bedeutung brauchen unterschiedliche IDs (z. B. `landlord_…` / `employer_…`).

**Achtung bei `required_if`:** Ein bedingter Fakt wird erst erforderlich, wenn der Fakt in der Bedingung **bekannt** ist. Der Fakt in der Bedingung sollte deshalb selbst `required` sein, sonst wird der bedingte Fakt nie gefragt.

### 3.2 Rechtliche Prüfregeln (`legal_rules`)

Hinweise für die Fachperson. Sie erscheinen im Briefing unter «Erkannte rechtliche Risiken» und verändern die Entscheidung **nicht**.

```yaml
- id: TEN_FORM_CHECK                 # eindeutig in der GANZEN KB
  description: "Interne Beschreibung"
  when: { ref: fact.landlord_termination_official_form, op: equals, value: false }
  result_code: TERMINATION_FORM_QUESTIONABLE
  result_de: "Text, der im Briefing erscheint."
  legal_source_ids: [CH_OR_266L]
```

### 3.3 Eskalationsregeln (`escalation_rules`)

```yaml
- id: TEN_DEADLINE_PENDING
  description: "Interne Beschreibung"
  when: { ref: fact.deadline_pending, op: equals, value: true }
  action: ESCALATE                   # einziger erlaubter Wert
  urgency: HIGH                      # HIGH | MEDIUM | LOW
  reason_code: DEADLINE_PENDING_EXPERT_REVIEW   # maschinenlesbar, erscheint in Entscheid + Briefing
  reason_de: "Begründung in einfacher Sprache für die Sozialarbeiterin."
  professionals: [tenancy_law_counsel]          # empfohlene Fachpersonen
```

Das System **berechnet keine Fristen und erfindet keine Schwellenwerte.** Fristen-Logik ist ausschliesslich das, was Sie als Bedingung formulieren (z. B. «Person gibt an, dass eine Frist läuft»).

## 4. Bedingungen (die «Regelsprache»)

Eine Bedingung ist ein **Blatt** oder eine **Verknüpfung**:

```yaml
# Blatt: ref + op (+ value)
{ ref: fact.deadline_pending, op: equals, value: true }

# Verknüpfungen: all (UND), any (ODER), not (NICHT) – beliebig verschachtelbar
all:
  - { ref: fact.rent_arrears, op: equals, value: true }
  - any:
      - { ref: fact.housing_loss_threatened, op: equals, value: true }
      - { ref: issue.employment_termination, op: exists }
```

### `ref` – worauf sich die Bedingung bezieht

| ref | Bedeutung |
|---|---|
| `fact.<id>` | Ein Fakt **desselben Rechtsproblems** (Typ: boolean → `true/false`, date → `"2026-01-15"`, integer → Zahl, string/enum → Text). |
| `issue.<id>` | Ob das Rechtsproblem im Fall erkannt ist (`op: exists`). |
| `ctx.<name>` | Fallweite Kennzahlen: `has_user_input`, `active_issue_count`, `unsupported_issue_count`, `min_classification_confidence` (0–1), `contradictory_fact_count`, `missing_required_count`. |

### Operatoren

| `op` | `value` | Bedeutung |
|---|---|---|
| `equals` / `not_equals` | ja | gleich / ungleich (Text ohne Gross-/Kleinschreibung) |
| `in` | Liste | Wert ist einer der Listenwerte |
| `greater_than` / `less_than` | ja | grösser / kleiner (Zahlen und ISO-Daten `YYYY-MM-DD`) |
| `exists` / `is_known` | nein | Fakt ist **bekannt** |
| `is_missing` | nein | Fakt ist **nicht bekannt** (fehlt, unklar oder widersprüchlich) |

Es gibt keine Formeln, kein Python, kein `eval`. Ein unbekannter Operator oder ein Tippfehler macht die Datei **ungültig** (siehe 7.).

### Unbekannte Werte (wichtig!)

Die Engine rechnet dreiwertig: **wahr / falsch / unbekannt**.

* Vergleiche (`equals`, `in`, `greater_than`, …) mit einem Fakt, der **nicht bekannt** ist (fehlt, unklar, widersprüchlich), ergeben **unbekannt**.
* `not` von unbekannt bleibt unbekannt. `all`: falsch, sobald ein Teil falsch ist; sonst unbekannt, wenn ein Teil unbekannt ist. `any`: wahr, sobald ein Teil wahr ist.
* **Eine Regel löst nur aus, wenn ihre Bedingung sicher wahr ist.** Unbekannt löst nie aus. Fehlende Angaben werden stattdessen durch Rückfragen (ASK) geklärt.
* Konsequenz: `not: {fact.x equals true}` löst bei unbekanntem `x` **nicht** aus. Wollen Sie «x ist nicht bekannt» abfragen, verwenden Sie `is_missing`.

## 5. Quellen, Fachpersonen, Vorlagen

**`legal_sources/sources.yaml`** – nur Metadaten, kein Gesetzestext:

```yaml
- id: CH_OR_266L                     # UPPER_SNAKE_CASE
  provider: fedlex                   # fedlex | entscheidsuche | other
  type: statute                      # statute | case_law | other
  sr_number: "220"
  article: "266l"
  language: de
  title_de: "Obligationenrecht (OR), Art. 266l"
  verification_status: UNVERIFIED    # nur setzen, wenn WIRKLICH geprüft
```
Eine Quelle wird in der Software **nie** als «verifiziert» angezeigt, solange kein Prüfverfahren existiert (Stand heute: keines; siehe `IMPLEMENTATION_STATUS.md`).

**`referrals/professionals.yaml`**: `id`, `label_de`, `description_de` der Fachpersonen-Typen.
**`briefings/expert_briefing.yaml`**: Reihenfolge der Abschnitte des Briefings.

## 6. Neues Rechtsproblem hinzufügen – Schritt für Schritt

1. `knowledge_base/legal_issues/tenancy_defects.yaml` kopieren, in z. B. `social_assistance.yaml` umbenennen.
2. `id`, `title_de`, `legal_area`, `issue`, `version` anpassen; `content_status: DRAFT`.
3. Fakten mit Fragen, `required`/`required_if` und `priority` eintragen (ca. 8–15).
4. Prüf- und Eskalationsregeln mit eindeutigen IDs ergänzen (je ca. 3–5).
5. Neue Quellen in `sources.yaml`, neue Fachpersonen in `professionals.yaml` eintragen, falls nötig.
6. **Mindestens 2–3 Testszenarien** in `tests/scenarios.yaml` ergänzen (siehe 8.).
7. Prüfen: `cd apps/api` → `.venv\Scripts\python.exe -m app.services.knowledge.cli`
8. In der App auf **Knowledge Base → «YAML neu laden»** klicken. Das neue Rechtsproblem wird für neue Analysen sofort erkannt – ohne Neustart.

Die KI ordnet Texte automatisch den Rechtsproblemen der KB zu (anhand von `title_de` und `classification`). Gute `typical_situations` verbessern die Zuordnung. *Hinweis:* Der **Mock-Modus** erkennt nur die vier mitgelieferten Rechtsgebiete anhand fester Stichwörter; ein neues Rechtsproblem wird erst mit der echten KI (Gemini) automatisch erkannt.

## 7. Validierung – Fehlermeldungen

`python -m app.services.knowledge.cli` (oder die Seite *Knowledge Base*) prüft u. a.:

* ungültiges YAML, fehlende Pflichtfelder, unbekannte Felder
* doppelte IDs (Rechtsproblem, Fakt innerhalb des Rechtsproblems, Regeln KB-weit)
* unbekannte Operatoren, falsche `value`-Typen, ungültige `ref`
* Verweise auf nicht existierende Fakten, Quellen, Fachpersonen, Briefing-Vorlagen, verwandte Rechtsprobleme
* gleicher Fakt mit unterschiedlichem `data_type` in mehreren Rechtsproblemen
* `action` ≠ `ESCALATE`, nicht unterstützte `schema_version`
* Testszenarien, die auf unbekannte Rechtsprobleme verweisen

Jede Meldung nennt **Datei und Feld**, z. B. `legal_issues/tenancy_termination.yaml: escalation_rules.0.when.op: …`. **Eine fehlerhafte Datei wird nicht geladen** – das betroffene Rechtsgebiet gilt dann als «nicht abgedeckt» und wird eskaliert.

## 8. Testszenarien (`tests/scenarios.yaml`)

```yaml
- id: SC_EMP_DEADLINE
  title_de: "Arbeitskündigung mit laufender Frist"
  validation: LEGALLY_VALIDATED       # SYNTHETIC_TECHNICAL | LEGALLY_VALIDATED
  issues: [{ id: employment_termination, confidence: 0.9 }]
  unsupported_issues: []              # Texte nicht abgedeckter Rechtsprobleme
  facts:                              # Fall-Zustand: nur bekannte Fakten
    employer_termination_received: true
    deadline_pending: true
  expected_action: ESCALATE           # ASK | PROCEED | ESCALATE
  expected_rule_ids: [EMP_DEMO_DEADLINE_PENDING]
  expected_reason_codes: [DEADLINE_PENDING_EXPERT_REVIEW]
  expected_missing_facts: []          # optional; wenn gesetzt, muss die Menge exakt stimmen
```

Szenarien beschreiben den **Fall-Zustand** (erkannte Rechtsprobleme + bekannte Fakten), nicht den Chat-Text. So testen sie ausschliesslich Ihre Regeln, unabhängig von der KI. Ausführen: Seite *Evaluation* oder der CLI-Befehl oben. Nur `validation: LEGALLY_VALIDATED` zählt später als juristisch validiert; die Software berechnet bewusst **keine Genauigkeits-Prozentzahl**.

## 9. Versionierung

Jede Entscheidung speichert die **KB-Version** (`kb-…`, ein Hash über alle YAML-Dateien). Ändert sich eine Datei, ändert sich die Version – so ist später nachvollziehbar, nach welchem Regelstand entschieden wurde. Pflegen Sie zusätzlich `version` pro Datei für Ihre eigene Nachvollziehbarkeit.

## 10. Erweiterungen (Issue 1)

* **Fakt-Zustände:** `is_unknown` = «gefragt, Klientin weiss es nicht». `is_missing` bleibt «nicht bekannt» (also auch unbekannt). Eine *erforderliche* Angabe in diesem Zustand eskaliert automatisch (`SYSTEM_REQUIRED_FACT_UNKNOWN`); gewünschte Dringlichkeit zusätzlich per Regel (`fact.x is_unknown`).
* **Abgeleitete Werte (`derived`)** für Zeit-Regeln, **nur interne Dringlichkeit**:
  ```yaml
  derived:
    - { id: days_since_earliest_receipt, kind: days_since_earliest, facts: [pickup_notice_date, receipt_date] }
  escalation_rules:
    - id: X
      when: { ref: derived.days_since_earliest_receipt, op: greater_than, value: 19 }   # = 20 oder mehr Tage
  ```
  Ein nicht berechenbarer Wert (kein Datum bekannt) ist *unbekannt* und löst nie aus. Schwellen, die Produktentscheide sind, in `description` mit **PRODUKTENTSCHEID** kennzeichnen.
* **Fakt-Felder:** `group`, `enum_labels_de` (Anzeige), `extraction_hint_de` (Hinweis an die KI), `source_ids`, `depends_on`, `escalation_relevant`.
* **Regeln:** `legal_rules[].kind: HINT` (freigegebene allgemeine Aussage) oder `REVIEW_POINT` (Prüfhinweis); **`legal_source_ids` ist Pflicht**. Eskalationsregeln: `routes_to_issue` (Issue-ID aus `routing/related_issues.yaml`), `suppress_standard_statements: true` (Fall ausserhalb des Moduls).
* **Issue-Briefing:** `briefing_profile` (Gruppen von Fakten, Prüfpunkte, anzufordernde Dokumente, Stellen aus `referrals/authorities.yaml`).
* **Quellen:** `dossier_status` (Prüfstand laut Law-Team) ist getrennt von `verification_status` (Live-Prüfung durch das System; bleibt `UNVERIFIED`). Gerichtsentscheide: `citation`, `case_number`, `decision_date`, `considerations`, `core_statement_de`, `scope_de`, `limits_de`, `relevant_fact_ids`, `url` (nur wenn geprüft).
* **Stellen:** `contact_verified: true` nur zusammen mit `verified_at`; sonst zeigt die Software «nicht verifiziert». Keine Nummern erfinden.
* **Policy `policies/forbidden_statements.yaml`:** reguläre Ausdrücke für verbotene Aussagen. Jeder KB-Text wird beim Laden dagegen geprüft; ein Treffer ist ein Validierungsfehler. Neue verbotene Formulierungen hier ergänzen und in `apps/api/tests/test_issue01.py` (`FORBIDDEN_SAMPLES`) mit einem Beispielsatz absichern.
* **Szenarien:** zusätzlich `unknown_facts`, `today`, `expected_urgency`, `expected_not_rule_ids`, `expected_route_issue_ids`.

## 11. Neues Issue über die Generatoren (Dossier → YAML)

Die sieben Mietrechts-Issues entstehen aus den Dossiers in `docs/legal_inputs/issues/` (Quelle bleibt unverändert). Änderungen gehören in die Spezifikation, nicht in die generierte YAML-Datei.

1. Dossier nach `docs/legal_inputs/issues/issue_08.docx`, dann `python scripts/kb/extract_issue_docs.py`.
2. `scripts/kb/specs/issue_08.py` nach dem Muster von `issue_05.py` anlegen und in `SPEC_MODULES` (`build_issue_kb.py`) eintragen.
3. Gesetzes- und BGE-Tabellen kommen automatisch in `sources.yaml`; zusätzliche Quellen in `EXTRA_SOURCES`, neue Stellen in `AUTHORITIES_NEW`.
4. Verbotene Aussagen als Muster in `policies/forbidden_statements.yaml`, mit je einem Testsatz.
5. Referral: `issue_rules` und `signal_bindings` in `referrals/referral_network.yaml`.
6. Mock-Schlüsselwörter in `app/services/ai/issue_keywords.py` (nur Tests/Prefilter).
7. `python scripts/kb/build_issue_kb.py && python -m app.services.knowledge.cli`, danach `python scripts/kb/build_coverage_matrix.py` (erzeugt `ISSUE_COVERAGE_MATRIX.md`).

## 12. Offene Entscheide für das Law-Team

* Alle sieben Issues sind `DRAFT`. Offene Prüfpunkte und nicht abgebildete Dossier-Aussagen stehen in [`ISSUE_COVERAGE_MATRIX.md`](ISSUE_COVERAGE_MATRIX.md) (generiert).
* Globale Schwellen (`routing/global_escalation.yaml`: Zuordnungssicherheit < 0.5, mehr als 3 Rechtsprobleme) sind technische Platzhalter.
* Welche Situationen müssen immer an eine Fachperson? Wann ist eine Information für PROCEED ausreichend? Sind Formulierungen für Sozialarbeitende verständlich?
* Fristen: Das System berechnet keine Fristen; «Frist läuft» ist nur ein Fakt, der eskaliert.
* 150 kommunale Sozialdienste sind einzeln zu verifizieren; Datenschutz-Entscheid zur Gemini-API mit echten Fällen steht aus (bis dahin nur synthetische Daten).
* Selbsttest: In der App **Knowledge Base → «YAML neu laden»**, dann **Evaluation → «Evaluation ausführen»**.
