# Referral Rules v1.2 – Integration

Eingabe des Law-Teams: `docs/legal_inputs/referral_rules (1).yaml` (Version 1.2, 07.11.2026; unverändert erhalten).
Produktiv geladen wird **`knowledge_base/referrals/referral_rules.yaml`** (erzeugt durch `scripts/kb/build_referral_v12.py`).
Die bisher produktive Version ist gesichert unter `docs/legal_inputs/previous/referral_network_v1.1_integrated.yaml`; die alte Datei
`referral_network.yaml` existiert nicht mehr. Der Loader lehnt eine zweite Referral-Datei neben der geladenen ab. Prüfung:
`GET /api/knowledge-base/status` und Test `test_v12_is_the_active_referral_file` (Version `1.2`).

## 1. Unterschiede v1.1 → v1.2

| | v1.1 | v1.2 |
|---|---|---|
| Stellen | 66 | 121 (12 Schlichtungsbehörden/Bezirksgerichte, 11 Rechtsauskünfte, 13 KESB, 14 kjz, Soziale Dienste Winterthur, IKA Bezirk Affoltern, Kantonales Sozialamt …) |
| Gemeinden | nur Zürich, Winterthur in `role_resolution` | **neu `municipalities`: alle 160 Zürcher Gemeinden** (BFS, Bezirk, Region, Stelle je Rolle, `sozialdienst_status`) |
| Rollenwerte | eine ID | eine ID **oder Liste** (erster Eintrag = Standard) |
| Kontakte | teils sekundär | Mehrheit `contact_source: primary` (offizielle Website geprüft) |
| Korrekturen | | u. a. Mieterverband-Adressen, KESB Stadt Zürich, **Telefon der Schlichtungsbehörde Zürich entfernt** |
| Issue-ID Zahlungsverzug | – | `CH_TENANCY_TERMINATION_ARREARS` (in der Anwendung `CH_TENANCY_PAYMENT_DEFAULT`) |

Software-Ergänzungen (im YAML mit `# INTEGRATION` markiert, vom Law-Team zu bestätigen): `official_check` bei 142/143/147,
`address_protected` bei Frauenhäusern, Alias der Issue-ID, `secondary` bei Issue 1, `signal_bindings`, `role_location_basis`, `municipality_aliases`.

## 2. Auflösung einer Rolle (`resolve_role_options`)

1. `municipalities["ZH:<Gemeinde>"].<rolle>`
2. `role_resolution[<rolle>]["ZH:<Gemeinde>"]`
3. `role_resolution[<rolle>]["ZH"]` (kantonale Stelle, mit Hinweis «Kantonsweit»)
4. `role_resolution[<rolle>]["default"]` (allgemein/national)

Ohne bestimmbare Gemeinde wird **nie** eine örtliche Stelle vorgetäuscht (Stufe 3/4 mit Hinweis «Gemeinde nicht bestimmt»).
Listenwerte liefern alle Optionen in dieser Reihenfolge; die erste kann prominent sein, weitere stehen unter «Weitere Anlaufstellen» mit
dem Grund «weitere Option in dieser Region». Dieselbe Stelle erscheint nie doppelt (Deduplikation über alle Regeln und Issues).
Eine Empfehlung entsteht nur aus einer Issue-Regel, einem Signal oder einer Sicherheitskategorie – nicht aus der blossen Existenz in der Gemeinde.

## 3. Gemeinde, BFS, Aliase

* Normalisierung: Gross-/Kleinschreibung, Leerzeichen, Umlaute (`zuerich` = `Zürich`), Suffix `(ZH)` (`Benken` → `Benken (ZH)`).
* Aliase (`municipality_aliases`): `Glattbrugg → Opfikon`, `Effretikon → Illnau-Effretikon` (Beispiele des Law-Teams, `status: law_team`) sowie
  Stadtquartiere/Ortsteile von Zürich und Winterthur (`status: quartier`, Software-Ergänzung, zu bestätigen). **Mehrdeutige Namen** (z. B. nur «Affoltern») sind
  nicht aufgeführt und werden nicht zugeordnet. Der Validator verbietet Aliase, die zugleich eine Gemeinde sind.
* Die BFS-Nummer ist im Gemeindeeintrag (eindeutig, geprüft); eine PLZ-Tabelle liegt nicht vor und wird nicht erfunden.
* Die Zuordnung geschieht rein deterministisch; Gemini liefert höchstens die genannte Ortsbezeichnung als Fakt (`property_municipality`). Keine KI-Aufrufe für Rollen, Kontakte, Sortierung oder PDF.

## 4. Ortsbezug je Rolle

`role_location_basis`: `property` (Gemeinde der Wohnung) für Schlichtungsbehörde, Rechtsauskunft, Mieterverband, Ombudsstelle; `residence` (Wohnsitzgemeinde) für
Sozialdienst, Notunterkunft, KESB, kjz, Opferberatung, Frauenhaus, Frauenzentrale, Schuldenberatung. Neuer **optionaler** Fakt `client_residence_municipality`
(nie Pflicht, wird nur bei ausdrücklich abweichender Wohnsitzgemeinde gesetzt). Fehlt er, gilt die Gemeinde der Wohnung, im Hinweis der Karte vermerkt.

## 5. Verifikationsstatus

* `contact_source: primary|secondary|none` und `verified` bleiben getrennt: Karten zeigen «Offizielle Quelle», «Fachverzeichnis (vor Nutzung bestätigen)» oder
  «Kontaktdaten nicht belegt». `verified: false` → «Zuständigkeit noch nicht geprüft».
* `sozialdienst_status` je Gemeinde: `verified` (Stelle gezeigt), `traeger_verified_contact_open` (Trägerschaft genannt, Kontakt als offen vermerkt),
  `to_verify` (**allgemeine kantonale Anlaufstelle** + Hinweis «noch nicht einzeln geprüft», keine erfundene Gemeindestelle). Beide Hinweise stehen auf der Karte
  (`local_note_de`), im Bericht und sind kein Validierungsfehler. Aktuell: 2 verified, 8 Trägerschaft, 150 to_verify.
* Telefonnummern werden normalisiert: `044 763 17 00 (Telefonzentrale)` → Nummer `044 763 17 00` (klickbar), Zusatz «Telefonzentrale»; Mehrfachnummern werden getrennt.
* Interne Feldnamen (z. B. «Feld web im Abschnitt municipalities») werden nicht angezeigt; Gründe sind Klartext statt Signal-IDs.

## 6. Safety

Safety-Routen und `FLAG` (Schema) sind unverändert; die Sicherheitslogik arbeitet unabhängig von der Rechts-Referral-Auswahl. Notrufnummern (117/144) bleiben nationale Einträge,
Schutzadressen von Frauenhäusern werden nie ausgegeben (Validator verbietet sie, `address_protected`); die öffentliche Notunterkunft Durchgangsheim ANKER Winterthur darf ihre Adresse zeigen.
Keine automatische Kontaktaufnahme; Öffnungszeiten werden nur als «laut Wissensbasis» angezeigt.

## 7. Frontend und Briefing

Phase 3 zeigt höchstens drei prominente Stellen, den Rest unter «Weitere Anlaufstellen»; Karten tragen Zuständigkeit (`scope_de`), Telefon mit Zusatz und Verifikationshinweis.
Das Expert Briefing nutzt dasselbe Referral-Ergebnis (`ReportExtras`, beim Erstellen gespeichert): bis zu vier Stellen mit Zuständigkeit und Hinweis, kein eigener Rechenweg im Renderer.

## 8. Validator

Technisch ungültig (Fehler): YAML, doppelte BFS, falsche Anzahl Zürcher Gemeinden (≠ 160), fehlende/unbekannte Rolle, unbekannte Stellen-ID (auch in Listen), ungültiger `sozialdienst_status`,
Alias auf unbekannte Gemeinde oder mehrdeutiger Alias, Schutzadresse hinterlegt, zweite Referral-Datei. Fachlich ungeprüft (**kein** Fehler): `to_verify`, `contact_source: none`, `verified: false`.

## 9. Tests

`tests/test_referral_v12.py` (A Zürich, B Winterthur, C Bülach, D `to_verify`/Trägerschaft, E Glattbrugg-Alias, F unbekannte Gemeinde, G Listenrollen, H Mehrfach-Issues ohne Duplikate, I Ausweisung,
J Safety, K Verifikation/Telefon, L Briefing = Frontend, M Rückwärtskompatibilität, N Wohnung vs. Wohnsitz, Validator-Fehler, keine KI-Aufrufe) und E2E `referral_v12.spec.ts` (Zürich und Bülach im Browser).

## 10. Offen

* Die 150 `to_verify`-Sozialdienste müssen vom Law-Team einzeln geprüft werden (Arbeitsliste `gemeinden_pruefliste.csv` laut Datei, nicht mitgeliefert).
* Aliase `status: quartier` bestätigen; PLZ-basierte Zuordnung für alle Ortsteile ist nicht umgesetzt (keine geprüfte PLZ-Tabelle).
* Andere Kantone haben keine Gemeindetabelle: dort kantonale bzw. nationale Stellen.
* `reviewed_by` der Datei ist `null`.
