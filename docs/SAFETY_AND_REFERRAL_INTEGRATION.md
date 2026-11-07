# Sicherheitsreaktion und Fachstellen-Integration

**Status: technisch umgesetzt und getestet, fachlich NICHT freigegeben.** Vor dem Einsatz mit echten Klientendaten müssen
Fachpersonen (Krisenintervention, Opferhilfe) und das Law-Team die Punkte in Abschnitt 9 prüfen.

## 1. Warum die Warnung früher nicht erschien (Ursache im Code)

Es gab im System **keine Sicherheitserkennung**. `safety` kam nur in den Eingabedateien des Law-Teams
(`docs/legal_inputs/*.yaml`) vor, nie im Code: Die Datei `triage_config.yaml` (Stichwort-Gruppe `P1`, Stufe «notfall») und der Abschnitt `safety_routing`
der Referral-Datei wurden nicht geladen. `signals.yaml` und `safety_keywords.yaml`, auf die die Referral-Datei verweist, existieren nicht. Die
Entscheidungs-Engine kannte nur `ASK | PROCEED | ESCALATE`. In dem Testfall führte die juristische Klassifikation (Mietkündigung, Härtegründe) zu
einer normalen Eskalation mit Dringlichkeit «bald»; die Gewalt- und Selbstgefährdungsaussagen wurden von keiner Komponente gelesen. Es war
also keine Fehlpriorisierung eines erkannten Signals, sondern ein fehlender Baustein. Das Frontend kannte ebenfalls keinen Notfallzustand.

## 2. Architektur (Erweiterung, keine zweite Engine)

```
Nachricht ─► SafetyDetector (deterministisch, ohne KI) ─► safety_events (DB, bleibt nach Reload)
                                                              │
Case State + Events ─► decide() ─► rechtliches Ergebnis (unverändert: ASK/PROCEED/ESCALATE)
                                └► Sicherheits-Overlay: effective_action, safety, referrals
```

- `knowledge_base/safety/safety_signals.yaml`: Erkennungsmuster und Kurztexte (Entwurf).
- `knowledge_base/referrals/referral_network.yaml`: Law-Team-Datei v1.1 (07.11.2026), Konsequenzen je Kategorie (`safety_routing`), Kontakte, `role_resolution`.
- `app/services/safety/`: `detector.py` (Erkennung), `assess.py` (Sicherheitszustand, Kontakte, Regionalplanung), `config.py`.
- `app/services/referrals/network.py`: Schema, Rollenauflösung, Kontaktkarten (Validierung, Schutzadressen).
- Persistenz: Tabelle `safety_events` (Migration `0004`), Hinweis wird nie gelöscht.
- Die Erkennung läuft in `add_message` **vor und unabhängig** von KI, Issue-Klassifikation und Analysestatus; die Entscheidung wird sofort neu berechnet. Sie funktioniert auch, wenn der KI-Aufruf fehlschlägt oder das Rechtsgebiet nicht unterstützt wird (Test).
- Kein Gemini-Aufruf, keine Kosten: Das Paket `safety` importiert die KI-Schicht nicht (Test). Die KI-Extraktion wurde bewusst nicht um Sicherheitsfelder erweitert (siehe 9).

## 3. Kategorien und Priorität

`IMMEDIATE_SAFETY_RESPONSE > ESCALATE > ASK > PROCEED` (strengste gewinnt). Die Konsequenzen stammen unverändert aus `safety_routing` der Law-Team-Datei:

| Kategorie | Aktion | Sicherheitszustand bei klarer Aussage |
|---|---|---|
| `ACUTE_SELF_HARM`, `ACUTE_DANGER_VIOLENCE` | IMMEDIATE_SAFETY_RESPONSE | **IMMEDIATE** (Notfallmodus) |
| `DOMESTIC_VIOLENCE`, `SEXUAL_VIOLENCE_HARASSMENT`, `CHILD_ENDANGERMENT`, `EXPLOITATION_TRAFFICKING`, `MENTAL_HEALTH_CRISIS`, `EXISTENTIAL_EMERGENCY` | ESCALATE | **HUMAN_CHECK** (Hinweiskarte, Kontakte, Rechtliches bleibt Hauptansicht) |
| `MENTAL_HEALTH_VULNERABILITY` | FLAG | nur Briefing-Flag |
| unklare / zurückliegende / bedingt formulierte Aussagen | – | **UNCLEAR** (ruhiger Hinweis, keine Nummern) |

`effective_action` (angezeigte Hauptaktion) ist bei IMMEDIATE `IMMEDIATE_SAFETY_RESPONSE`, sonst die rechtliche Aktion. Das rechtliche Ergebnis (`action`, Regeln, offene Fragen) bleibt vollständig im Case State.
Bei IMMEDIATE wird `main_reason_code = SAFETY_IMMEDIATE_RESPONSE`, `max_urgency = HIGH` («sofort») gesetzt und eine Übergabe-Empfehlung angelegt (nicht «angefragt»). Mehrere Kategorien bleiben erhalten; die Reihenfolge folgt `safety_routing`.

**Normalisierung/Konflikte:** Die Referral-Datei kennt zusätzlich die Aktion `FLAG` (neben ASK/PROCEED/ESCALATE/IMMEDIATE_SAFETY_RESPONSE); sie wird im Schema ausdrücklich unterstützt. Kategorienamen und Aktionen stimmen mit der Referral-Datei überein; ein Ladetest prüft, dass jede Kategorie Muster **und** Konsequenz hat. Die Stichwortliste `P1` aus `triage_config.yaml` wurde nicht blind übernommen, sondern
als Ausgangspunkt der Muster verwendet; `triage_config.yaml` (Schwellen, Sicherheitsaktionen) bleibt unverändert.

## 4. Erkennung (kein naives Keyword-Matching)

Pro Satz werden Muster geprüft und dann bewertet:
- **Verneinung** («keine Suizidgedanken») → kein Signal; Verneinung gilt nur für denselben Gedanken («… , aber ich werde aus dem Fenster springen» bleibt akut).
- **Zurückliegend** («vor fünf Jahren») → höchstens UNCLEAR, nie akut.
- **Hypothetisch** («würde», «angenommen») → UNCLEAR. Bedingte Drohungen («wenn …, bringe ich mich um») bleiben akut.
- **Fachlicher Kontext** («arbeite in der Suizidprävention») → blosse Erwähnungen werden verworfen; konkrete Absichts-/Drohmuster nie.
- **Dritte**: Aussagen über die Klientin (die Sozialarbeiterin berichtet) zählen; «Er will mich umbringen» (Gewalt) wird von «Ich will mich umbringen» (Selbstgefährdung) getrennt.
- Deutsch, Schweizerdeutsch, Französisch, Englisch (Grundmuster). Evidenz (Originalsatz), Regel-ID, Zeitpunkt, Nachricht werden gespeichert.
Regressionstests: `tests/test_safety.py` (Treffer und Fehlalarm-Schutz). Die Muster sind ein Entwurf: Falsch-negative sind möglich, die Liste ist durch Fachpersonen zu erweitern.

## 5. Notfall-Oberfläche

Bei IMMEDIATE steht ganz oben (nie eingeklappt, `role="alert"`): «Akute Gefahr erkannt – jetzt handeln», kurze Erklärung nach Gefahrentyp,
grosse Anruf-Buttons («144 anrufen», «117 anrufen», `tel:`), fünf bis sieben Sofortschritte, getrennt davon «Ergänzende Beratung (keine Notrufnummern)»
(143, 147, 142 mit Hinweis «keine Notrufnummer») und eingeklappt «Weiterführende Stellen» (regional, z. B. Opferberatung Zürich). Die juristische Bearbeitung ist
unter «Juristische Fallbearbeitung (nachrangig …)» eingeklappt, nichts geht verloren. Der Status in Liste und Kopf lautet «Akute Gefahr – Sicherheit klären».
«Als bearbeitet dokumentieren» speichert eine Notiz (`POST /api/cases/{id}/safety-events/{id}/acknowledge`), entfernt die Warnung aber **nicht**.
Ein Tippen auf eine Nummer öffnet nur die Telefon-App; es wird nichts gespeichert oder als Telefonat/Übergabe gewertet (Übergabestatus bleibt «empfohlen»).

## 6. Schweizer Nummern

| Nummer | Funktion | Prüfung |
|---|---|---|
| 144 | Sanität / Rettungsdienst (Notruf) | laut Law-Datei; offizielle Quellseite (z. B. bag.admin.ch) vom Law-Team zu ergänzen |
| 117 | Polizei (Notruf) | wie 144 |
| 143 | Die Dargebotene Hand (Krisenberatung) | am 07.11.2026 auf https://www.143.ch/ geprüft |
| 147 | Pro Juventute (Kinder/Jugendliche) | am 07.11.2026 auf https://www.147.ch/ geprüft |
| 142 | Nationale Opferhilfe-Nummer, seit 1. Mai 2026, **keine Notrufnummer** | am 07.11.2026 auf https://www.opferhilfe-schweiz.ch/ geprüft |

Selbstgefährdung: 144 primär, 143/147 ergänzend. Gewalt: 117 primär, 142 ergänzend, 144 bei Verletzungen (Schritttext). Beide: 144 und 117. Die Seite bj.admin.ch (Opferhilfe) war unter der geprüften URL nicht erreichbar (404); die Funktion von 142 wurde über opferhilfe-schweiz.ch belegt.

## 7. Fachstellen aus der Wissensbasis

- `referral_network.yaml` ist die Law-Team-Datei v1.1, **inhaltlich unverändert** übernommen (66 Stellen, `role_resolution`, `issue_rules`, `safety_routing`, `cross_cutting`). Die bisherigen Dateien `professionals.yaml` / `authorities.yaml` bleiben unverändert und werden weiter für die bestehende Briefing-Logik genutzt. `docs/legal_inputs/referral_rules.yaml` (v1.0) und `referral_rules (1).yaml` (v1.1) bleiben als Eingaben erhalten.
- **Ergänzungen der Integration** (in der Datei mit `INTEGRATION` markiert, vom Law-Team zu bestätigen): `address_protected: true` bei den drei Frauenhäusern; `secondary: [unentgeltliche_rechtsauskunft]` für `CH_TENANCY_TERMINATION` (damit die Rechtsauskunft als weitere Anlaufstelle erscheint); `official_check` bei 142/143/147; Abschnitt `signal_bindings`.
- **Rollenauflösung** (`resolve_role`): `KANTON:Gemeinde` → `KANTON` → `default`. Der Kanton kommt aus dem Issue (`canton: ZH`, solange die Wohnung nicht als ausserhalb des Kantons bestätigt ist) oder aus einer **eindeutig** zuordenbaren Gemeinde; die Gemeinde aus dem Fakt `property_municipality`. Nie wird «Zürich» vorausgesetzt.
- **Signale für bedingte Verweisungen** (`conditional.when.signal`) werden nur aus belegbaren Regeln/Kategorien abgeleitet (`signal_bindings`: z. B. `legal_deadline_risk`, `imminent_housing_loss`). Nicht ableitbare Signale (`low_income`, `debt`, …) lösen **nichts** aus.
- Doppelte Organisationen werden entfernt; Reihenfolge nach Priorität (primär → CRITICAL-bedingt → weitere). Anzeige: höchstens drei Stellen, der Rest unter «Weitere Anlaufstellen». Die KI wählt nichts aus.
- Beispiele (getestet): Stadt Zürich → Schlichtungsbehörde Bezirk Zürich, Mieterverband Zürich, weitere: Rechtsauskunft Bezirksgericht Zürich. Winterthur → Schlichtungsbehörde je Bezirk (Verzeichnis), Mieterverband Geschäftsstelle Winterthur; keine Zürcher Stadtstellen. Unbekannter Ort → nur allgemeine Stelle (`default`), Hinweis «Kein Wohnort bestätigt»; nationale Notfallnummern hängen nie vom Ort ab.
- **Offen:** Eine Rückfrage nach Kanton/Gemeinde bei fehlendem Wohnort ist nicht umgesetzt (nur der sichere Fallback).

## 8. Kontaktqualität

`contact_source` wird sichtbar gemacht: `primary` → «offizielle Website, geprüft am …»; `secondary` → «Fachverzeichnis … vor produktivem Einsatz auf der Website der Stelle bestätigen»; `none` → «Kontaktdaten nicht belegt». Nationale Nummern → «Nationale Nummer, am … geprüft».
`verified: true` (Angebot/Zuständigkeit belegt) wird nie als «Kontakt heute geprüft» dargestellt; `verified: false` zeigt «Zuständigkeit noch nicht geprüft».
`active: false` (z. B. Brava, Aufnahmestopp) wird nicht angeboten; wenn möglich tritt der `default` der Rolle ein. Schutzadressen (Frauenhäuser, Typ `shelter` oder Flag) werden **nie** ausgegeben, nur Telefonnummern.
Fehlende Telefonnummern/Öffnungszeiten werden nicht ergänzt. Links: nur `https`/`http`, `tel:` nur mit Ziffern, `mailto:` nur nach Prüfung (Backend und Frontend).
Namen und Adressen stammen unverändert aus der Law-Datei (teils ohne Umlaute).

## 9. Vom Law-Team / von Fachpersonen freizugeben

1. Erkennungsmuster und Kurztexte (Selbstgefährdung, Gewalt): Vollständigkeit, Falsch-negative, Formulierungen; Abgleich mit offiziellen Empfehlungen (z. B. 143, Opferhilfe, kantonale Krisendienste). Die Texte sind **nicht klinisch geprüft**.
2. Einordnung «ongoing Gewalt (z. B. «schlägt mich seit Jahren») = IMMEDIATE» und «Äusserung der Selbstgefährdung als Ideation (z. B. «Suizidgedanken») = akut» (bewusst vorsichtig).
3. Offizielle Quellseite für 117/144; die Ergänzungen unter Abschnitt 7; `signal_bindings`.
4. Sekundäre Kontakte vor Produktivbetrieb auf den Websites der Stellen bestätigen; `reviewed_by` ist leer.
5. KI-Unterstützung für Sicherheitssignale (Gemini-Schema) ist bewusst nicht aktiviert: Die deterministische Erkennung ist das Sicherheitsnetz; eine KI-Erweiterung wäre ein Zusatzsignal, nie die Entscheidung.
6. Datenschutz: keine automatische Weitergabe personenbezogener Daten an Stellen (nDSG); nur Anzeige von Kontakten.

## 10. Tests

Backend `tests/test_safety.py` (Treffer A–C, Fehlalarm D–F, Entscheidungspriorität, Persistenz/Reload/KI-Ausfall, Dokumentation ohne Entwarnung, Übergabe unverändert L,
Zürich/Winterthur G/H, Fallback I, inaktive Stelle J, Schutzadresse K, unsichere Links, Kontaktqualität, KB-Konsistenz, keine KI-Imports), Frontend `safety.test.tsx`, Browser `e2e/safety.spec.ts`
(Selbstgefährdung, Gewalt, kombiniert, Mietfall + Gewalt, Persistenz nach Reload, Fachstellenkarten mit echten Kontakten, Winterthur, Mobile ohne Überlauf).

## 11. Synthetisch testen

Neuer Fall → «Was ist passiert?»: `Ich werde aus dem Fenster springen.` / `Mein Vermieter will mich schlagen und bedroht mich gerade.` /
`Mein Vermieter droht mich zu schlagen und ich werde aus dem Fenster springen.` Für Fachstellen:
`Meine Klientin hat in Zürich eine Wohnungskündigung erhalten. Sie ist alleinige Mieterin. Die Kündigung wurde ihr am 4. November 2026 mit normaler Post zugestellt. Laut ihrer Aussage wurde kein amtliches Kündigungsformular verwendet.` (ersetzen Sie «Zürich» durch «Winterthur» für die Winterthurer Auflösung).
Nur synthetische Daten verwenden.
