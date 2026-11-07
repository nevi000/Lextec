# Robuste Gemini-Analyse längerer Fallschilderungen

## Ursache des Fehlers «Die Gemini-Antwort entsprach nicht dem erwarteten Schema»
Belegt durch die Nutzungsprotokolle (`ai_usage`): zwei Aufrufe der Analyse des Falls «Demir» (Schimmel) endeten bei **2486 Ausgabe-Tokens** bei einem
Limit von **2500** (`AI_MAX_OUTPUT_TOKENS_PER_CALL`). Eine lange Schilderung ergibt viele Fakten mit Belegzitaten (~22 Fakten ≈ 2400 Tokens).
Gemini brach mit `finish_reason = MAX_TOKENS` ab, das JSON war mitten im Satz abgeschnitten, die Pydantic-Validierung schlug fehl (Strukturteil:
`facts[n].evidence_quote` bzw. das Array selbst; fehlende schliessende Klammern). Gemini lieferte also kein falsches Schema, sondern eine **unvollständige** Antwort,
und der Client erkannte das nicht als solche.

**Warum es lange dauerte:** Gemini generierte bis zum Limit (jeweils fast 2,5 k Tokens ≈ 15 s), der Client-Timeout lag bei 30 s und ein erneutes Analysieren wiederholte den identischen Aufruf mit demselben Ergebnis.

## Änderungen (nur Analysepipeline)
* `ai_max_output_tokens_per_call` 2500 → **4096**; `ai_timeout_seconds` 30 → **60**; neues `ai_max_output_tokens_retry` = 8192.
* `finish_reason` wird gelesen: `MAX_TOKENS` ist ein eigener Fehler (`ai_output_truncated`), das JSON wird **nie** repariert oder teilweise verwendet.
* **Höchstens ein gezielter Retry** pro Extraktion: bei Abschneiden mit höherem Limit und der Anweisung, kompakter zu antworten; bei Schemaverletzung mit den fehlerhaften **Feldpfaden** (nie Werte oder Falltext) als Hinweis. Danach ein klarer Fehler (`ai_output_truncated` bzw. `ai_schema_mismatch`). Transportfehler (503/Timeout) behalten ihren eigenen, begrenzten Retry (`AI_MAX_RETRIES=1`).
* Prompt `fact_extraction` 1.1: kürzeste wörtliche Belegzitate (prüft weiterhin, dass das Zitat in der Nachricht steht) → weniger Ausgabe-Tokens.
* Messung im Log (ohne Falltext): `gemini call function=… attempt=… api_ms=… in_tokens=… out_tokens=… finish=…` und `gemini parse ms=…`. Jeder Versuch steht weiterhin in `ai_usage`.
* Unverändert: strukturierte Ausgabe mit JSON-Schema (`response_json_schema`), Validierung gegen Katalog (ungültige Enum-Werte werden nie als Wert gespeichert, sondern «unklar»), Zitatprüfung, Rule Engine, Issues, Safety, Referral, Sprachbrücke, Briefing, UI.
* Die Eingabe bleibt bei jedem Fehler erhalten; «Erneut analysieren» ist möglich.

## Verifikation
* Mock-Tests (`tests/test_analysis_robustness.py`, 11): Abschneiden → ein Retry mit höherem Limit; zweimal abgeschnitten → klarer Fehler ohne dritten Aufruf; abgeschnittenes JSON wird nicht repariert; fehlendes Pflichtfeld → ein Retry mit Feldpfad, ohne Falltext; ungültiger Enum-Wert wird nicht gespeichert; Timeout (mit/ohne Erfolg, begrenzt); normale Antwort = genau 1 Aufruf; keine Datenverluste auf Service-Ebene.
* Ein echter Gemini-Aufruf mit dem Fall «Demir» (synthetisch, Wegwerf-Datenbank): 1 Aufruf, `finish=STOP`, 2406 Ausgabe-Tokens, 15,5 s, Issue 5 (Mängel) erkannt, 22 belegte Fakten, kein erfundener Mietzins-/Mahnungs-/Kündigungsfakt, Entscheidung durch die unveränderte Rule Engine.
