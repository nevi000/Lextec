# Übergabe an das Law-Team – was wir von Ihnen brauchen

Sie müssen den Code nicht verstehen. Alles, was Sie liefern, sind YAML-Dateien im Ordner `knowledge_base/` (Anleitung: [`KNOWLEDGE_BASE.md`](KNOWLEDGE_BASE.md)). Die mitgelieferten Dateien sind **technische Beispiele ohne juristische Aussagekraft** – bitte ersetzen bzw. überarbeiten.

## Checkliste

### A. Pro Rechtsproblem (mind. die 4 geplanten: Mietkündigung, Wohnungsmängel, Arbeitskündigung, nicht bezahlter Lohn)
- [ ] **Identifikation:** `title_de`, `classification.description`, 3–5 `typical_situations` (hilft der KI bei der Zuordnung)
- [ ] **Fakten (ca. 8–15):** je `id`, `label_de`, `data_type`, `question_de` (verständlich, in der Sprache der Sozialarbeiterin), `why_needed_de`, `priority`
- [ ] **Welche Fakten sind immer nötig (`required`), welche nur unter Bedingung (`required_if`)?**
- [ ] **Juristische Prüfregeln (ca. 3–5):** Bedingung + Hinweistext + Quelle
- [ ] **Eskalationsregeln (ca. 3–5):** Bedingung, `urgency`, `reason_code`, verständliche Begründung, empfohlene Fachpersonen
- [ ] **Rechtsquellen:** Welcher Artikel stützt welche Regel? (Eintrag in `sources.yaml`; keine Gesetzestexte kopieren)
- [ ] `content_status` erst auf `LEGALLY_REVIEWED`, wenn fachlich geprüft

### B. Übergreifend
- [ ] **Globale Eskalationskriterien** (`routing/global_escalation.yaml`): Die vorhandenen Schwellenwerte (z. B. Sicherheit der Zuordnung < 0.5, mehr als 3 gleichzeitige Rechtsprobleme) sind **technische Platzhalter** – bitte fachlich festlegen oder streichen.
- [ ] **Fachpersonen-Typen** (`referrals/professionals.yaml`): Welche Stellen/Rollen sollen empfohlen werden? Bezeichnungen und Kurzbeschreibung.
- [ ] **Mindestens 10 realistische Schweizer Testszenarien** (`tests/scenarios.yaml`) mit erwarteter Entscheidung (`ASK`/`PROCEED`/`ESCALATE`) und Begründung; als `LEGALLY_VALIDATED` markieren, wenn geprüft.
- [ ] **Rechtlich-ethisches Framework** (separates Dokument, Sub-Challenge 2): Eskalationskriterien, besondere Schutzbedürftigkeit, Vertraulichkeit/Haftung/Transparenz, revDSG, grenzüberschreitende Nutzung, EU AI Act, verständliche Nutzerinformation.
- [ ] **Datenschutz-Entscheid:** Darf die Gemini-API (Google, extern) mit echten Fällen verwendet werden? Bis zur Klärung nur synthetische Daten.

### C. Entscheidungen, die wir von Ihnen brauchen
1. Welche Situationen **müssen** immer an eine Fachperson (unabhängig vom Rechtsgebiet)?
2. Wann gilt eine Information als **ausreichend** für «Weiter bearbeiten» (PROCEED)? Was darf das System dann tun – und was nicht?
3. Sind die **Formulierungen** der Rückfragen und Begründungen für Sozialarbeitende verständlich und korrekt?
4. Wie soll mit **Fristen** umgegangen werden? (Das System berechnet bewusst keine Fristen; es kann nur «Frist läuft» als Fakt erfassen und eskalieren.)
5. Welche Rechtsquellen sollen als **Quelle für ein Briefing** gelten, und wer prüft sie?

## So prüfen Sie Ihre Arbeit selbst
1. Datei speichern.
2. In der App: **Knowledge Base → «YAML neu laden»**. Grün = gültig; rot = Fehlerliste mit Datei und Feld.
3. **Evaluation → «Evaluation ausführen»**: zeigt, ob Ihre Testszenarien die erwartete Entscheidung liefern und warum nicht.
4. Beispielfall durchspielen: **Fälle → «Neuen Fall erfassen»** und die Schilderung eingeben (im Mock-Modus nur mit den vier Demo-Rechtsgebieten).

## Was die Software bewusst NICHT tut
- Keine Rechtsberatung, keine Fristenberechnung, keine verbindliche Aussage.
- Keine Diagnosen, keine Krisen-/Notfallerkennung (ausdrücklich nicht im Umfang dieser Version).
- Keine automatische Kontaktaufnahme mit Fachstellen. «Übergabe» ist nur eine Empfehlung; Status «angefragt»/«bestätigt» setzt die Sozialarbeiterin selbst.
- Rechtsquellen werden **nicht als verifiziert** angezeigt, solange kein Prüfverfahren existiert.
