# Fedlex-Integration

Amtliche Gesetzestexte des Bundes (Fedlex) werden deterministisch abgerufen, lokal versioniert gespeichert und im
Expert Briefing mit Herkunft und ehrlichem Status angezeigt. **Kein LLM, kein API-Key, keine Falldaten.**
Fedlex liefert Quellen, keine Entscheidungen: Die Regel-Engine (ESCALATE > ASK > PROCEED) bleibt unverändert und
arbeitet auch bei einem Fedlex-Ausfall identisch.

## 1. Architektur

```
knowledge_base/legal_sources/sources.yaml   (Source-IDs, sr_number/statute/article/paragraph/letter)
          │
          ▼
FedlexService.sync()  ── http.py ──► Fedlex SPARQL + /filestore/  (nur per CLI/POST, nie beim Briefing)
   catalog.py  (SR → Erlass → Fassung → XML-URL)
   akn.py      (Akoma Ntoso → Artikel/Absatz/Buchstabe, Wortlautvergleich)
          │
          ▼
DB: source_snapshots (versioniert) · source_sync_state · source_wording_checks
          │
          ▼
CachedFedlexProvider (liest nur den Cache) ──► SourceRegistry ──► Briefing / API / UI
```

`app/services/sources/fedlex/`: `http.py`, `reference.py`, `catalog.py`, `akn.py`, `models.py` (`FedlexInfo`),
`service.py`, `provider.py`, `cli.py`, `livetest.py`, `fixtures.py`, `inputs.py`. Der bestehende
`SourceProvider`-Vertrag bleibt; weitere Provider (z. B. Bundesgericht/entscheidsuche) können dahinter ergänzt
werden. Die acht BGE bleiben getrennt (`DOSSIER_CHECKED`), sie werden **nicht** als Fedlex-verifiziert dargestellt.

## 2. Endpunkte (tatsächlich verwendet)

- SPARQL: `https://fedlex.data.admin.ch/sparqlendpoint` (öffentlich, POST `query=`).
- Dokumente: `https://fedlex.data.admin.ch/filestore/...` (Akoma-Ntoso-XML je Fassung und Sprache).
- Ansicht (Deep-Link, Anker nicht serverseitig geprüft): `https://www.fedlex.admin.ch/eli/cc/<…>/de#art_266_l`.

Es werden nur Prädikate des JOLux-Modells verwendet, die gegen den Live-Dienst geprüft wurden
(`historicalLegalId`, `isMemberOf`, `dateApplicability`, `dateEndApplicability`, `isRealizedBy`, `isEmbodiedBy`,
`isExemplifiedBy`, `userFormat`, `titleShort`). SPARQL-Variablen dürfen nicht `?from` heissen (Gateway liefert 400).

## 3. Auflösung und Fassungen

1. SR-Nummer → alle Erlasse, die diese Nummer je trugen (SR ist über die Zeit **nicht eindeutig**: 272 = GestG/ZPO,
   101 = BV 1874/1999). Auswahl nach Inkrafttreten/Ausserkrafttreten am Stichtag; bleiben mehrere übrig → `VERSION_AMBIGUOUS`.
2. Fassung: `dateApplicability`/`dateEndApplicability` am Stichtag (Standard `APP_TODAY` bzw. heute, optional
   `--date` oder `--as-of-dossier`). Zukünftige Fassungen existieren und werden nie mit der geltenden verwechselt;
   existiert eine neuere, wird das gemeldet (`newer_version`).
3. XML laden, Artikel über `eId` (`art_266_l`) suchen, Artikelnummer gegenprüfen (kein Nachbarartikel), Absatz
   (`Abs. 1–2`) und Buchstabe (`lit. c`) exakt extrahieren, Fussnoten ausschliessen. Nicht gefunden → `NOT_FOUND`,
   nichts wird erraten (Sammelartikel wie `art_226_a_226_d` werden nicht aufgelöst).

## 4. Cache und Sync

Tabelle `source_snapshots`: eine Zeile je Quelle, Fassung, Sprache und Inhalts-Hash; ältere Fassungen werden **nie**
überschrieben. Wiederholter Sync ist idempotent (frischer Cache → 0 Requests). `origin` trennt `FEDLEX` von `FIXTURE`.
Cache älter als `FEDLEX_CACHE_MAX_AGE_DAYS` (14) wird als «Gespeicherte Fassung, möglicherweise veraltet» angezeigt,
nie als heute verifiziert. Offline arbeitet die App vollständig aus dem Cache.

```powershell
cd apps\api
.\.venv\Scripts\python.exe -m app.cli fedlex sync --issue CH_TENANCY_TERMINATION      # Issue 1
.\.venv\Scripts\python.exe -m app.cli fedlex sync --all-referenced
.\.venv\Scripts\python.exe -m app.cli fedlex sync --issue CH_TENANCY_TERMINATION --force
.\.venv\Scripts\python.exe -m app.cli fedlex sync --issue CH_TENANCY_TERMINATION --offline
.\.venv\Scripts\python.exe -m app.cli fedlex verify --issue CH_TENANCY_TERMINATION    # offline Wortlautabgleich
.\.venv\Scripts\python.exe -m app.cli fedlex status --issue CH_TENANCY_TERMINATION
.\.venv\Scripts\python.exe -m app.cli fedlex map-inputs                               # Zuordnung Rechtsteam-YAMLs
.\.venv\Scripts\python.exe -m app.cli fedlex live-test                                # 3 echte Artikel
.\.venv\Scripts\python.exe -m app.cli fedlex seed-fixtures                            # Testdaten (FIXTURE)
```
(`PYTHONIOENCODING=utf-8`, falls die Windows-Konsole Umlaute nicht darstellt.) API: `GET /api/sources/fedlex/status`
(liest nur den Cache), `POST /api/sources/fedlex/sync` (einzige Route, die Fedlex kontaktieren darf).

## 5. Statusmodell (drei getrennte Ebenen)

| Ebene | Werte (UI-Text) |
|---|---|
| Abruf | `NOT_RETRIEVED` «Noch nicht abgerufen» · `RETRIEVED` «Amtlicher Text abgerufen» · `RETRIEVED_STALE` «Gespeicherte Fassung, möglicherweise veraltet» · `NOT_FOUND` · `VERSION_AMBIGUOUS` · `VERSION_NOT_FOUND` · `EXTRACTION_FAILED` · `REFERENCE_MISMATCH` «Quellenabgleich fehlgeschlagen» · `ERROR` |
| Wortlaut | `MATCHED` · `MISMATCH` · `NO_COMPARABLE_TEXT` · `NOT_COMPARED` |
| Interpretation | `NOT_REVIEWED` «noch nicht durch das Law-Team geprüft» · `REVIEWED` (nur mit Eintrag `interpretation_review` in der KB) |

Ein abgerufener Artikel beweist **keine** Rechtsfolge im Einzelfall (z. B. Art. 266o OR ≠ Nichtigkeit einer konkreten
Kündigung). Daher gibt es keinen pauschalen Text «Juristisch verifiziert». Fixture-Daten heissen «Testdaten (Fixture),
kein amtlicher Abruf». Daneben bleibt `dossier_status` (Prüfstand laut Law-Dossier) ein eigenes Feld.

Wortlautvergleich: Die in «…» zitierten Fragmente der KB werden nach Normalisierung (Unicode NFKC, Anführungszeichen,
Gedankenstriche, Leerraum) im amtlichen Text gesucht. Abweichung → `MISMATCH`, es wird nie «identisch» behauptet.
Semantische Prüfungen wären nur als gekennzeichnete Vorschläge zulässig; es gibt keine.

## 6. Sicherheit

Nur `https`, Host-Allowlist (`fedlex.data.admin.ch`), TLS-Prüfung an, manuelle Redirects (max. 3, nur erlaubte Hosts),
Dokument-URLs nur unter `/filestore/`, Grössenlimit, Timeouts, begrenzte Parallelität, Mindestabstand, Retry mit
Backoff nur bei 429/5xx/Netzwerk, `defusedxml` (keine externen Entities), nur validierte Identifikatoren (SR-Muster,
ELI-Muster) in SPARQL. Anfragen enthalten ausschliesslich öffentliche Gesetzesreferenzen, nie Falldaten. Das Paket
`fedlex` importiert keine KI-Schicht (per Test abgesichert); die Gemini-Kostenkontrolle ist unberührt.

## 7. Konfiguration (`.env.example`)

`FEDLEX_ENABLED`, `FEDLEX_SPARQL_URL`, `FEDLEX_CACHE_ENABLED`, `FEDLEX_CACHE_MAX_AGE_DAYS`, `FEDLEX_TIMEOUT_SECONDS`,
`FEDLEX_MAX_CONCURRENT_REQUESTS`, `FEDLEX_MIN_REQUEST_INTERVAL_SECONDS`, `FEDLEX_MAX_RETRIES`,
`FEDLEX_MAX_RESPONSE_BYTES`, `FEDLEX_LANGUAGE`. `FEDLEX_ENABLED=false` = nur Cache, kein Netzwerk.

## 8. Neue Quellen für ein neues Issue ergänzen

In `knowledge_base/legal_sources/sources.yaml` einen Eintrag mit `provider: fedlex`, `type: statute`, `sr_number`,
`statute`, `article`, optional `paragraph`/`letter`, `valid_as_of` und – wenn vorhanden – dem Dossier-Wortlaut in
«…» anlegen. Konsistente IDs: `CH_<GESETZ>_<ARTIKEL>[_<ABSATZ>]` (`CH_OR_266L`, `CH_OR_273_1`). Referenzen aus Regeln,
Aussagen und Prüfpunkten nutzen diese IDs (Aliasse bleiben rückwärtskompatibel). Danach
`fedlex sync --issue <ID>`. Den Gesetzestext nirgends duplizieren: Er kommt aus dem Cache. Quellen ohne Wortlaut gelten
als `REFERENCED_ONLY` und erhalten `NO_COMPARABLE_TEXT`.

## 9. Prüfung durch das Rechtsteam

Die inhaltliche Auslegung wird im KB-Eintrag unter `interpretation_review` (Prüfer:in, Datum, Notiz) festgehalten; erst
dann zeigt das UI «Interpretation geprüft». Die drei Rechtsteam-Dateien (`docs/legal_inputs/*.yaml`) bleiben
unverändert; `fedlex map-inputs` erzeugt `knowledge_base/references/legal_inputs_mapping.md` (aufgelöst / nicht im
Wissensbestand / nicht auflösbar / völkerrechtlich). Es werden keine Haftungs- oder Eskalationsregeln aktiviert,
keine Triage-Schwellen oder Sicherheitsaktionen geändert; `verified: true` einer Organisation heisst nicht, dass
Kontakte heute neu geprüft wurden. Völkerrecht (EMRK, UN) wird nicht automatisch aufgelöst.

## 10. Tests

- Ohne Netzwerk: `apps/api/tests/test_fedlex.py` (MockTransport + aus echten Snapshots gekürzte Fixtures in
  `tests/fixtures/fedlex/`): SR-Auflösung, Fassungswahl (aktuell/historisch/zukünftig/mehrdeutig), Buchstaben-Artikel,
  Absätze/Buchstaben, Namespaces, ungültige/fehlende Artikel, defekte/unvollständige Antworten, Timeouts, SSRF,
  Grössenlimit, Cache (Hit/Miss/offline/idempotent/Versionen/veraltet), Source-ID-Mapping, Briefing-Status,
  keine KI-Aufrufe, keine Falldaten in Requests, Entscheidung identisch mit/ohne Cache.
- Echt: `python -m app.cli fedlex live-test` (OR Art. 266l, OR Art. 273 Abs. 1, ZPO Art. 113 Abs. 2 lit. c, plus
  Negativprobe Art. 266zz; 8 Requests, Wegwerf-Datenbank). Gehört bewusst **nicht** zur Standard-Testsuite.
- Browser: `apps/web/e2e/fedlex.spec.ts` (synthetischer Mietfall → ESCALATE → Briefing mit Art. 266l/266o, Fixture-Kennzeichnung, PDF).

## 11. Grenzen

- Der Artikel-Deep-Link ist ein Ansichts-Anker und wird nicht automatisch geprüft; massgebend sind ELI und XML-URL.
- Nur Deutsch ist konfiguriert/geprüft; Sammelartikel und Übergangsbestimmungen werden nicht aufgelöst.
- Pro Lauf wird eine Stichtags-Fassung gewählt (Briefing: frühestes Zustelldatum, sonst heute); Fristen werden nicht berechnet.
- Bundesgerichtsentscheide sind nicht angebunden (Provider-Schnittstelle vorbereitet).
- Die rechtliche Auslegung bleibt Sache der Fachperson.
