# LexTec Sprachbrücke (mehrsprachige Fallaufnahme per QR)

**Eine Fallaufnahme. Zwei Geräte. Zwei Sprachen. Die Sozialarbeiterin behält die Kontrolle.**

## 1. Idee
In Phase 2 («Fragen klären») aktiviert die Sozialarbeiterin die Sprachbrücke **einmal**. Die ratsuchende Person scannt **einen** QR-Code, wählt ihre Sprache
(Deutsch, English, العربية, Українська) und sieht danach **automatisch jede aktuelle Frage** in ihrer Sprache. Es gibt keinen Button «Frage senden».
Antworten sind *Vorschläge*: erst nach Bestätigung durch die Sozialarbeiterin gelangen sie in den Fall, danach erscheint die nächste Frage von selbst.

## 2. Rollen
| | Sozialarbeiterin (Desktop, lokal) | Ratsuchende Person (Smartphone) |
|---|---|---|
| Frage | sieht die Engine-Frage + Übersetzung | sieht **nur** die aktuelle Frage (übersetzt) |
| Antwort | übernehmen, korrigieren, erneut fragen, überspringen | senden (Ja/Nein, Auswahl, Datum, Zahl, Freitext, «Weiss nicht») |
| Ablauf | pausieren, fortsetzen, beenden, Fallbericht, Eskalation | nichts davon |
| Zugriff | gesamte App | nur `/api/bridge/*` mit Sitzungstoken |

Das Smartphone kann nicht springen, nicht überspringen, keine Regeln/Eskalationen ändern, keinen Bericht und keine Fallinformationen abrufen
(`MobileState` enthält nur: Status, Revision, Sprache, RTL, aktuelle Frage, Hinweis).

## 3. Synchronisierung und Zustandsautomat
Der **Backend-Zustand** (`bridge_sessions`) ist die einzige Quelle; beide Geräte pollen alle 2 s (`GET …/voice-bridge` bzw. `GET /api/bridge/state`, `rev` zählt jede Änderung).
Polling statt WebSocket: einfachste zuverlässige Lösung für den lokalen Prototyp, reconnect-sicher (ein Reload braucht nur den Token), keine Zusatzinfrastruktur.

`WAITING_FOR_CONNECTION → WAITING_FOR_QUESTION → QUESTION_ACTIVE → AWAITING_WORKER_REVIEW → (übernommen) → WAITING_FOR_QUESTION/QUESTION_ACTIVE …`
sowie `PAUSED` (Flag, überlagert den Status), `COMPLETED`, `EXPIRED`. (`ANSWER_SUBMITTED` und `AWAITING_WORKER_REVIEW` fallen zusammen: die Antwort wird beim Eingang sofort zur Prüfung vorgelegt.)

`BridgeService.sync()` ist die **einzige Stelle, an der sich die Frage ändert**. Sie fragt `CaseService.current_decision()` (die bestehende Question Selection / Rule Engine) nach `next_question`.
Ändert sich die Fakt-ID (Antwort am Desktop, Überspringen, Übernahme, Eskalation), entsteht eine **neue Frageinstanz** (`question_instance_id`); eine wartende Handy-Antwort zur alten Frage wird verworfen, nie der neuen zugeordnet.
Bei unmittelbarer Sicherheitslage (`safety.state == IMMEDIATE`) wird keine Frage ans Handy gegeben.

* **Veraltete Antworten:** `instance_id` ≠ aktuelle Instanz → `409 stale_question`; vor jeder Antwort wird synchronisiert (kein Race zwischen Fragewechsel und Antwort).
* **Doppelte Requests:** gleiche `request_id` → idempotent (keine zweite Verarbeitung). Während der Prüfung werden weitere Antworten mit `409 not_accepting` abgelehnt.
* **Erneut fragen** erzeugt eine neue Instanz; späte Wiederholungen der alten sind veraltet.
* **Verbindungsabbruch:** Handy zeigt «Verbindung unterbrochen», versucht automatisch weiter und zeigt nach der Rückkehr den aktuellen Zustand. Desktop zeigt «Smartphone gerade nicht erreichbar» (kein Poll seit 12 s).

## 4. Kontrollierte Übernahme
Handy-Antwort → `answer_json` der Sitzung (Fallzustand **unverändert**) → Sozialarbeiterin prüft (Original, deutsche Bedeutung, Herkunft «Sprachbrücke», «wartet auf Bestätigung»)
→ **Übernehmen:** bestehender Pfad `add_message(… ANSWER, fact_id, origin="VOICE_BRIDGE", original_text, original_language)` → `analyze_pending` → Entscheidung neu → `sync` → nächste Frage auf dem Handy.
Strukturierte Antworten gehen als **stabile Werte** (`true/false`, Enum-Wert, ISO-Datum, Zahl) und werden serverseitig gegen die Faktdefinition geprüft; übersetzte Labels werden nie als Wert akzeptiert.
Sie werden als deutscher Standardtext («Ja», Datum, Enum-Label) an den bestehenden deterministischen Parser übergeben, es gibt keine Rückübersetzung und keinen KI-Aufruf.
Freitext: Original + Ursprungssprache bleiben erhalten (`case_messages.original_text/original_language`), deutsche Fassung ist als **maschinell übersetzt** markiert und korrigierbar; bei fehlgeschlagener Übersetzung muss die Sozialarbeiterin selbst eine deutsche Fassung eintragen.
«Weiss nicht» nutzt den bestehenden Weg (`answer_unknown`).

Herkunftsvermerk: im Verlauf «Via Sprachbrücke beantwortet, durch Sozialarbeiterin bestätigt»; im Fallbericht bei den betroffenen Zeilen «Angabe der ratsuchenden Person, via Sprachbrücke erfasst und durch die Sozialarbeiterin bestätigt».
Das bedeutet **keine** juristische Verifikation. Es gibt keine zweite Berichtsvorlage.

## 5. Übersetzung
* **Oberflächentexte** des Handys: statisch (de/en/ar/uk), kein Modellaufruf.
* **Fragen** (Text, Erklärung, Antwortoptionen): beim Auswählen der Frage übersetzt (`AIProvider.translate`), also bevor das Handy sie sieht; Cache in `translation_cache` (Schlüssel = Hash aus Sprachpaar und Text), Wiederholungen kosten nichts. Fakt-/Antwort-IDs bleiben unverändert.
* **Gemini:** eigener Prompt (`TRANSLATION_V1`): wortgetreu, keine Interpretation/Rechtsberatung, Negationen/Zahlen/Daten exakt; Ausgabe wird validiert (gleiche Anzahl, keine leeren Einträge, **alle Zahlen des Originals müssen erhalten sein**). Inhalte sind Daten, nie Anweisungen; der Client kann keinen Prompt beeinflussen.
* **Fehler:** schlägt die Übersetzung fehl, sieht das Handy **keine** Frage, sondern «… wird von der Sozialarbeiterin erklärt»; der Desktop zeigt den Fehler, «Übersetzung erneut versuchen» und den Hinweis, selbst zu erklären oder eine Dolmetschperson beizuziehen.
* **Mock-Provider:** markiert statt zu übersetzen (`[EN · Mock] …`), damit nie der Eindruck einer echten Übersetzung entsteht. Für die echte Demo `AI_PROVIDER=gemini` verwenden.
* Maschinelle Übersetzung ist bei rechtlich wichtigen Punkten **kein Ersatz** für qualifizierte Sprachmittlung.

## 6. Datenmodell (Migration `0005`)
`bridge_sessions` (Token-Hash, Status, Sprache, `rev`, Ablauf, aktuelle Frageinstanz + Snapshot + Übersetzung, ausstehende Antwort + `request_id`), `translation_cache`, `case_messages.origin/original_text/original_language`.
Keine zweite Fakten-DB, keine zweite Rule Engine, keine eigenen mobilen Fragen.

## 7. API
Sozialarbeiterin (`/api/cases/{id}/voice-bridge`): `GET` (Zustand), `POST` (starten; beendet eine ältere Sitzung), `/pause`, `/resume`, `/end`, `/answer/accept` (`corrected_value` | `corrected_text_de`), `/answer/reask`, `/skip`, `/retry-translation`.
Handy (`/api/bridge`, Header `X-Bridge-Token`): `GET /state`, `POST /language`, `POST /answer` (`instance_id`, `request_id`, `kind: value|unknown|text`, `value`).

## 8. Sicherheit
* QR = `…/bridge#t=<Token>`: 256-Bit-Zufallstoken (`secrets.token_urlsafe(32)`), **im URL-Fragment** (wird nie an einen Server gesendet, taucht in keinem Access-Log auf; die Seite entfernt es aus der Adresszeile, hält es für den Tab in `sessionStorage`). Kein Personenbezug im QR.
* Gespeichert wird nur der SHA-256-Hash; der Klartext (`join_token`) nur bis das Handy verbunden ist (damit ein neu geladener Desktop den QR neu zeichnen kann).
* Eine aktive Sitzung pro Fall (neuer Start macht den alten QR ungültig), Gültigkeit 120 min (`BRIDGE_TTL_MINUTES`), Widerruf durch «Sitzung beenden» oder Fallabschluss; danach `410`. Unbekannter Token `401`.
* Der Token erlaubt ausschliesslich die drei Handy-Endpunkte (keine Fallendpunkte, keine anderen Fälle, kein Schreiben in den Fall).
* **Netzwerkgrenze:** Anfragen mit nicht lokaler Quelle (Client-IP oder irgendein `X-Forwarded-For`-Hop) dürfen nur `/api/bridge/*` und `/api/health` nutzen (`RESTRICT_REMOTE_ACCESS`, Standard an). Im LAN-Modus ist nur der Vite-Server erreichbar; die API bleibt auf `localhost`.
* Keine Tokens oder Antworttexte in Logs (Token nur im Header/Fragment; Übersetzungsfehler loggen nur den Fehlertyp).
* Der Datenschutzhinweis (was übertragen wird, maschinelle Übersetzung) steht auf dem Handy vor der Sprachwahl und auf dem Desktop beim Aktivieren. Prototyp nur mit synthetischen Daten.

## 9. Lokale Zwei-Geräte-Demo
**Start:** `.\scripts\dev.ps1 -Lan` (optional `-ApiPort 8001 -WebPort 5174`, `-LanIp <Adresse>` falls die automatische Wahl nicht passt).
Das Skript
1. listet alle IPv4-Adressen mit Adaptername und Netzwerkprofil und wählt die des Adapters mit der **Default-Route** (virtuelle Adapter wie WSL/Hyper-V/Docker/VPN werden nie automatisch gewählt),
2. startet Vite mit `VITE_HOST=0.0.0.0` (lauscht im Netzwerk, `localhost:<Port>` funktioniert weiter) und die API weiterhin nur auf `127.0.0.1`,
3. gibt die gewählte Adresse als `BRIDGE_PUBLIC_BASE_URL` an die API weiter (der QR-Code verwendet genau diese Adresse),
4. prüft, dass der Webserver unter dieser Adresse antwortet, und zeigt, ob bereits eine passende eingehende Firewall-Regel existiert; sonst eine eng begrenzte Regel (nur dieser Port, nur das aktive Netzwerkprofil, nur `LocalSubnet`) zum Kopieren und den Befehl zum Entfernen.

**Ursache des früheren `ERR_CONNECTION_REFUSED`:** Vite war ohne `-Lan` gestartet und lauschte nur auf Loopback (`::1:5174`). Die LAN-Adresse (`172.20.10.4`, WLAN/iPhone-Hotspot) war richtig, aber auf diesem Port hörte dort niemand zu.

**QR-Adresse im Panel:** feste `BRIDGE_PUBLIC_BASE_URL` hat Vorrang; sonst bietet das Panel alle privaten IPv4-Adressen dieses Computers an (Default-Route zuerst), man kann eine wählen oder eine eigene Basisadresse eintragen (wird im Browser gemerkt). QR und angezeigter Link kommen aus derselben Variable. Es wird **nie** `localhost` in einen QR geschrieben; ohne bekannte Adresse erscheint eine Konfigurationshilfe statt eines QR-Codes.
Das Panel prüft per Browser, ob unter der Adresse ein Server antwortet («Der Server antwortet unter dieser Adresse» / «… antwortet kein Server»). Das beweist die Bindung des Servers, **nicht** die Firewall: erst wenn das Handy tatsächlich verbunden ist («Smartphone verbunden»), ist alles bestätigt. Nach 25 s ohne Verbindung erscheint die Fehlersuche.

**Bewusst nicht möglich über die Netzwerkadresse:** Die Desktop-App selbst. Öffnet man `http://<LAN-IP>:<Port>/` an einem anderen Gerät (oder am Desktop über die LAN-IP), lädt die Seite, aber alle API-Aufrufe ausser `/api/bridge/*` und `/api/health` werden mit `403` abgelehnt. Die Sozialarbeiterin arbeitet über `http://localhost:<Port>`.

**Smartphone-Test (ohne Fallakte-Zugriff):**
1. Computer und Smartphone im selben WLAN/Hotspot. Bei einem iPhone-Hotspot ist das Netz typisch `172.20.10.x`; der Computer muss mit diesem Hotspot verbunden sein.
2. `.\scripts\dev.ps1 -Lan` starten, im Browser `http://localhost:<Port>` öffnen, Fall öffnen, «Sprachbrücke aktivieren».
3. QR mit der Kamera scannen oder den Link im Handy-Browser öffnen, Sprache wählen. Der Desktop zeigt «Smartphone verbunden».
4. Falls die Seite nicht lädt: Adresse im Panel prüfen/ändern, Firewall-Regel aus der Skriptausgabe (admin) anlegen, Netz nach der Demo wieder aufräumen.
5. Ohne Smartphone: den Link in einem zweiten Browserfenster (anderes Profil) öffnen.
6. Für echte Übersetzungen `AI_PROVIDER=gemini` und genügend `AI_DAILY_REQUEST_LIMIT`.
Keine öffentliche Freigabe der Dev-Server, kein Tunnel, kein Port-Forwarding.

## 10. Einschränkungen
* Polling alle 2 s (kein Push); bei sehr vielen parallelen Sitzungen wäre SSE/WebSocket nötig.
* Mehrfachauswahl-Fragen existieren in der Wissensbasis nicht (unterstützt: ja/nein, Auswahl, Datum, Zahl, Text, «weiss nicht»).
* Sprachen fest: de, en, ar, uk; weitere erfordern statische UI-Texte (`features/bridge/i18n.ts`).
* Keine Authentifizierung der Sozialarbeiterin (lokaler Prototyp); die Netzwerkgrenze ersetzt keine Zugriffskontrolle.
* Kein HTTPS im Dev-Modus (Klartext im WLAN!): nur für synthetische Demodaten.
* Freitextübersetzung und Frageübersetzung durch Gemini sind nicht juristisch geprüft.

## 11. Tests
`apps/api/tests/test_voice_bridge.py` (32: ein QR/mehrere Fragen, Auto-Weiterschaltung, kontrollierte Übernahme, Freitext, stabile Werte, Überspringen, veraltet/doppelt, Reconnect, Pause, Ende/Ablauf/Token, keine Falldaten, Remote-Sperre,
Eskalation/Sicherheit, Sprachen/RTL, keine KI-Aufrufe durch Polling + Cache, Übersetzungsfehler, Fallbericht-Herkunft), `apps/web/src/test/bridge.test.tsx` (11), `apps/web/e2e/voice_bridge.spec.ts` (4, zwei getrennte Browser-Kontexte: Desktop + Handy, inkl. Arabisch/RTL und Reload).
Alle mit Mock-KI; kein echter Gemini-Aufruf.
