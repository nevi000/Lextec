# Fallbericht und Fallaufnahme: Abstimmung (Briefing Case Alignment)

Der Fallbericht ist jetzt aus **demselben Datenmodell** wie die Fallaufnahme aufgebaut. Es gibt keine zweite Faktenliste für das PDF.
Ausgangspunkt war `docs/briefing_reference/Fallbericht_FALL-0014_v2.pdf` (9 Seiten bei 4 Eingaben).

## 1. Datenfluss

```
Issue-YAML (Fakten, required / required_if / optional, Regeln, briefing_profile)
   -> Fallaufnahme (Fragen, KI-Extraktion, Korrekturen)  ->  Case State (Fakten + Status + Herkunft)
   -> Decision (Rule Engine: missing_facts, Regeln, Dringlichkeit)
   -> generator._issue_briefing()  : je Zeile eine `relevance`  (KB-Anwendbarkeit + gespeicherter Status)
   -> report/view.py               : Auswahl, Zusammenführen, Quellenfilter  (keine Fachlogik)
   -> Jinja (expert_briefing.html.j2) -> HTML-Vorschau / PDF
```

Der Renderer entscheidet nichts Juristisches: `relevance` entsteht aus `FactDef.required`, `FactDef.required_if` (wie die Engine) und dem
gespeicherten Status; offene wichtige Angaben stammen aus `decision.missing_facts`. Es gibt keine KI-Aufrufe beim Rendern.

## 2. Statusabbildung (`IssueRow.relevance`)

| Fachliche Bedeutung | interner Status / Quelle | Darstellung im Bericht |
|---|---|---|
| KNOWN | `KNOWN` | Wert mit Herkunft (Angabe / KI nicht bestätigt / bestätigt) |
| HUMAN_CORRECTED | Herkunft `USER_CORRECTION` / bestätigt | Wert, «bestätigt», hat Vorrang |
| AI_EXTRACTED | Herkunft `AI_EXTRACTED` | Wert, Kennzeichen «KI», unter «aus der Schilderung erkannt, nicht bestätigt» gelistet |
| MISSING_REQUIRED | `MISSING` und in `decision.missing_facts` | Zeile «Offen / wichtige Angabe offen» und Liste «Wichtige Angaben, die noch fehlen» |
| DEFERRED | in `missing_facts` mit `deferred` | wie oben, mit «zurückgestellt» |
| ASKED_UNKNOWN | `UNKNOWN` | «Unbekannt – erfragt, derzeit unbekannt»; Liste «Erfragt, derzeit unbekannt» |
| CONTRADICTORY / UNCLEAR | `CONTRADICTORY` / `AMBIGUOUS` | «Unklar / widersprüchlich», Abschnitt «Offene Punkte und Unklarheiten» |
| OPTIONAL_UNANSWERED | `MISSING`, nicht erforderlich | **nicht angezeigt** |
| NOT_ASKED (nicht relevant) | `MISSING`, keine Regel/Pflicht | **nicht angezeigt** |
| NOT_APPLICABLE | `NOT_APPLICABLE` oder `required_if` nicht erfüllt | **nicht angezeigt** |

Berichtsversionen, die vor dieser Änderung gespeichert wurden, haben `relevance = None` und rendern wie bisher (nichts wird nachträglich verändert).

## 3. Field Mapping Matrix (Seite 1 der Vorlage)

| Briefing-Feld (Seite 1) | Fact-ID | Issue | Frage vorhanden | Pflicht? | Anzeige im Bericht | Verbindung |
|---|---|---|---|---|---|---|
| Person: Name | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: Vorname | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: Geburtsdatum | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: Adresse | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: Telefon | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: E-Mail | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: Bevorzugter Kontakt | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: Sprache | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: Dolmetschbedarf | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: Haushalt | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Person: Einwilligung zur Datenweitergabe | – | – | nein | nein | nur wenn erfasst; sonst ein Sammelhinweis | **fehlt bewusst** (Personalien werden nicht erfasst, kein Pflichtfeld) |
| Vermieter / Verwaltung | – | CH_TENANCY_TERMINATION | nein | nein | wird nicht angezeigt | **kein Fakt in der Wissensbasis** (Law-Team-Entscheid) |
| Mietobjekt (Gemeinde) | `property_municipality` | CH_TENANCY_TERMINATION | ja | Pflicht | nur wenn bekannt (sonst unter «offene Punkte», falls Pflicht) | verbunden |
| Objektart | `object_type` | CH_TENANCY_TERMINATION | ja | Pflicht | nur wenn bekannt (sonst unter «offene Punkte», falls Pflicht) | verbunden |
| Familienwohnung | `family_home_with_spouse` | CH_TENANCY_TERMINATION | ja | Pflicht | nur wenn bekannt (sonst unter «offene Punkte», falls Pflicht) | verbunden |
| Mietbeginn | – | CH_TENANCY_TERMINATION | nein | nein | wird nicht angezeigt | **kein Fakt in der Wissensbasis** (Law-Team-Entscheid) |
| Vertragsart / Befristung | `contract_term_type` | CH_TENANCY_TERMINATION | ja | Pflicht | nur wenn bekannt (sonst unter «offene Punkte», falls Pflicht) | verbunden |
| Kündigungsfristen und -termine | `contract_termination_dates` | CH_TENANCY_TERMINATION | ja | optional | nur wenn bekannt | verbunden (seit Issue-1-Update; ortsübliche Termine nur als Prüfhinweis) |
| Mietzins / Mt. (CHF) | `rent_amount_chf` | CH_TENANCY_TERMINATION | ja | optional | nur wenn bekannt (sonst unter «offene Punkte», falls Pflicht) | verbunden |
| Nebenkosten / Mt. | – | CH_TENANCY_TERMINATION | nein | nein | wird nicht angezeigt | **kein Fakt in der Wissensbasis** (Law-Team-Entscheid) |
| Kaution | – | CH_TENANCY_TERMINATION | nein | nein | wird nicht angezeigt | **kein Fakt in der Wissensbasis** (Law-Team-Entscheid) |
| Referenzzinssatz bei Vertragsabschluss | – | CH_TENANCY_TERMINATION | nein | nein | wird nicht angezeigt | **kein Fakt in der Wissensbasis** (Law-Team-Entscheid) |


Konsequenz: Felder ohne Fakt (Personalien, Vermieter, Mietbeginn, Nebenkosten, Kaution, Referenzzinssatz) werden **nicht** angezeigt und **nicht** zu
Pflichtfragen. Der Bericht trägt dafür einen einzigen ruhigen Satz («Personalien werden in LexTec Bridge nicht erfasst und sind für die Einschätzung nicht
erforderlich»). Wer solche Angaben will, ergänzt in der Wissensbasis einen Fakt (ggf. `required: false`) und im `report_profile.yaml` eine Zeile mit `fact_id`;
Änderungen an Eskalationslogik sind dafür nicht nötig.

## 4. Was der Bericht zeigt

* **Seite 1:** Fall, Dringlichkeit (aus der Rule Engine), Kurzsachverhalt, nur **bekannte** Eckdaten, Fristhinweise (ohne unbekannte abgeleitete Werte), «Das Wichtigste».
* **Seite 2:** Entscheid mit Begründung, **Offene Punkte und Unklarheiten** (wichtige Angaben als Kurzliste, erfragt-unbekannt, Widersprüche, unbestätigte KI-Angaben), Prozess, Einwilligung, Stellen (die vier relevantesten).
* **Seite 3:** Rechtliche Prüfung (Prüfpunkte, freigegebene Hinweise), Notizzeilen.
* **Anhang:** erfasste Angaben (nur relevante Zeilen, leere Gruppen entfallen; gemeinsame Fakten mehrerer Issues einmal), Chronologie, Gespräch, Unterlagen (ein Satz), Rechtsquellen.
* **«Ja» ohne Details:** `FactDef.true_value_note_de` (z. B. «Bereits reagiert: Ja – Art der Reaktion nicht näher bestimmt; daraus wird nichts abgeleitet»). Das System leitet keinen genaueren Sachverhalt ab.

## 5. Quellenauswahl

* Wortlaut (auf 700 Zeichen gekürzt) nur für Quellen hinter einem **ausgelösten** Prüfpunkt.
* Alle anderen im Bericht zitierten Quellen (Prüfpunkte, freigegebene Hinweise) als Kurzverweis mit Status (Dossier / Wortlaut abgerufen / Interpretation) und bei Urteilen mit gekürzter Kernaussage.
* Nicht zitierte Quellen der Wissensbasis erscheinen nicht. Die vier Ebenen (Abruf, Wortlautabgleich, Interpretationsfreigabe, Dossierstand) bleiben getrennt und sichtbar.

## 6. Mehrere Issues

Jedes aktive Issue liefert seine `briefing_profile`-Gruppen; gleiche Fakt-IDs werden über alle Issues hinweg **einmal** gezeigt, die höchste Dringlichkeit gilt,
Prüfpunkte tragen den Issue-Namen. Es gibt keine issue-spezifischen Templates: neue Issues erscheinen allein durch ihre Wissensbasis-Daten.

## 7. Versionen

Jede Version speichert Briefing und Zusatzdaten (`ReportExtras`) zum Erstellzeitpunkt; ältere Versionen bleiben unverändert (Test `test_j_old_briefing_versions_stay_unchanged`).
Neue Antworten markieren den Bericht als veraltet (`briefing_stale`), «Fallbericht aktualisieren» erzeugt eine neue Version.
Bei fehlgeschlagener KI-Analyse wird kein Bericht erzeugt (409), statt Angaben zu erfinden.

## 8. Ergebnis FALL-0014 (Regressionstest)

Gleicher Fall (4 Eingaben): **5 Seiten statt 9** (3 Hauptseiten, 2 Seiten Anhang); die erste und zweite Seite beantworten: was passiert ist, was bekannt ist, was unklar ist,
Dringlichkeit, warum Übergabe, nächste Schritte. Quellen: 3 mit Wortlaut, 12 als Kurzverweis statt 15 Volltexte. Kein «Fehlt»-Katalog, keine Personalien-Liste.
Mehrere Issues und Räumung: 6–7 Seiten (sie haben mehr Prüfpunkte und Stellen).

## 9. Bekannte Einschränkungen

* Seite 1 und die Faktenliste im Anhang können dieselben Eckdaten wiederholen (Seite 1 ist eine Zusammenfassung).
* Die Seitenzahl wächst mit der Zahl der Issues und der ausgelösten Prüfpunkte; es gibt keine feste Obergrenze, damit nichts abgeschnitten wird.
* Die Zuordnung «optional oder relevant» folgt allein der Wissensbasis (`required`, `required_if`); eine feinere Gewichtung (z. B. Fakten, die eine ausgelöste Regel liest) ist nicht umgesetzt.
* Keine Dokumentenfunktion (Upload): Der Bericht sagt das in einem Satz.

## 10. Offene Punkte für das Law-Team

1. Sollen Vermieter, Mietbeginn, Nebenkosten, Kaution, Referenzzinssatz als **optionale** Fakten eingeführt werden (nicht als Pflicht)?
2. Sollen weitere «Ja»-Antworten (z. B. `hardship_present`, `prior_dispute_3y`) einen Hinweis auf fehlende Details erhalten?
3. Welche Quellen sollen im Hauptbericht immer mit Wortlaut erscheinen (aktuell nur bei ausgelösten Prüfpunkten)?
4. Soll die Einwilligung (`consent_briefing`) auf Seite 1 statt Seite 2 stehen?
