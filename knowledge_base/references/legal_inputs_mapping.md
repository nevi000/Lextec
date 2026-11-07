# Zuordnung der Rechtsgrundlagen des Rechtsteams zu Quellen-IDs

_Generiert mit `python -m app.cli fedlex map-inputs`. Reine Dokumentation: Es werden keine Regeln aktiviert,
keine Triage-Schwellen oder Sicherheitsaktionen geändert. `verified: true` einer Organisation bedeutet nicht,
dass Kontakte heute neu geprüft wurden._

Zusammenfassung: INTERNATIONAL: 17, NOT_IN_KB: 19, RESOLVED: 12, UNRESOLVABLE: 9

| Fundstelle | Angabe des Rechtsteams | Status | Quellen-ID | Hinweis |
|---|---|---|---|---|
| `referral_rules.yaml/issue_rules[0]` | Art. 266a ff. OR | UNRESOLVABLE | - | Bereich/Sammelverweis/Freitext: bewusst nicht automatisch aufgelöst (Rechtsteam). |
| `referral_rules.yaml/issue_rules[0]` | Art. 266l-266o OR (Form, Familienwohnung, Nichtigkeit) | UNRESOLVABLE | - | Bereich/Sammelverweis/Freitext: bewusst nicht automatisch aufgelöst (Rechtsteam). |
| `referral_rules.yaml/issue_rules[0]` | Art. 271, 271a OR (Anfechtbarkeit) | UNRESOLVABLE | - | Gesetz nicht eindeutig (z. B. kantonales Recht / nur Name). |
| `referral_rules.yaml/issue_rules[0]` | Art. 273 Abs. 1 OR | RESOLVED | CH_OR_273_1 |  |
| `referral_rules.yaml/issue_rules[1]` | Art. 257d Abs. 1 OR (Wohnraum: Zahlungsfrist mind. 30 Tage) | RESOLVED | CH_OR_257D |  |
| `referral_rules.yaml/issue_rules[1]` | Art. 266n OR | RESOLVED | CH_OR_266N |  |
| `referral_rules.yaml/issue_rules[2]` | Art. 257d Abs. 2 OR | RESOLVED | CH_OR_257D |  |
| `referral_rules.yaml/issue_rules[2]` | Art. 272a Abs. 1 lit. a OR (keine Erstreckung) | RESOLVED | CH_OR_272A_1 |  |
| `referral_rules.yaml/issue_rules[2]` | Art. 273 OR | RESOLVED | CH_OR_273_1, CH_OR_273_2, CH_OR_273_3, CH_OR_273_4_5 |  |
| `referral_rules.yaml/issue_rules[3]` | Art. 272 OR | RESOLVED | CH_OR_272 |  |
| `referral_rules.yaml/issue_rules[3]` | Art. 272a OR (Ausschluss) | RESOLVED | CH_OR_272A_1 |  |
| `referral_rules.yaml/issue_rules[3]` | Art. 272b OR (max. 4 Jahre Wohnraum) | RESOLVED | CH_OR_272B |  |
| `referral_rules.yaml/issue_rules[3]` | Art. 273 Abs. 2 OR | RESOLVED | CH_OR_273_2 |  |
| `referral_rules.yaml/issue_rules[4]` | Art. 259a ff. OR | UNRESOLVABLE | - | Bereich/Sammelverweis/Freitext: bewusst nicht automatisch aufgelöst (Rechtsteam). |
| `referral_rules.yaml/issue_rules[4]` | Art. 259g-259i OR (Hinterlegung) | UNRESOLVABLE | - | Bereich/Sammelverweis/Freitext: bewusst nicht automatisch aufgelöst (Rechtsteam). |
| `referral_rules.yaml/issue_rules[5]` | Art. 257 ZPO (Rechtsschutz in klaren Faellen) | RESOLVED | CH_ZPO_257_1 |  |
| `referral_rules.yaml/issue_rules[5]` | kantonales Vollstreckungsrecht | UNRESOLVABLE | - | Bereich/Sammelverweis/Freitext: bewusst nicht automatisch aufgelöst (Rechtsteam). |
| `referral_rules.yaml/issue_rules[6]` | Art. 269d OR (amtliches Formular, Begruendung, Mitteilung mind. 10 Tage vor Kuendigungsfrist) | RESOLVED | CH_OR_269D |  |
| `referral_rules.yaml/issue_rules[6]` | Art. 270b OR | NOT_IN_KB | - | Art. 270b OR ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `referral_rules.yaml/issue_rules[7]` | Art. 257e OR | NOT_IN_KB | - | Art. 257e OR ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[INHUMAN_LIVING_CONDITIONS]` | Art. 3 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[INHUMAN_LIVING_CONDITIONS]` | Art. 8 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[INHUMAN_LIVING_CONDITIONS]` | Art. 7 BV (Menschenwuerde) | NOT_IN_KB | - | Art. 7 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[INHUMAN_LIVING_CONDITIONS]` | Art. 10 Abs. 3 BV | NOT_IN_KB | - | Art. 10 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[INHUMAN_LIVING_CONDITIONS]` | Art. 12 BV (Hilfe in Notlagen) | NOT_IN_KB | - | Art. 12 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[ABUSE_BY_STAFF_OR_OFFICIALS]` | Art. 3 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[ABUSE_BY_STAFF_OR_OFFICIALS]` | Art. 10 Abs. 3 BV | NOT_IN_KB | - | Art. 10 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[ABUSE_BY_STAFF_OR_OFFICIALS]` | Art. 312 StGB (Amtsmissbrauch) | NOT_IN_KB | - | Art. 312 StGB ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[ABUSE_BY_STAFF_OR_OFFICIALS]` | UN-Antifolterkonvention | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[UNLAWFUL_DEPRIVATION_OF_LIBERTY]` | Art. 5 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[UNLAWFUL_DEPRIVATION_OF_LIBERTY]` | Art. 31 BV | NOT_IN_KB | - | Art. 31 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[UNLAWFUL_DEPRIVATION_OF_LIBERTY]` | Art. 10 Abs. 2 BV | NOT_IN_KB | - | Art. 10 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[DENIAL_OF_EMERGENCY_AID_OR_CARE]` | Art. 12 BV | NOT_IN_KB | - | Art. 12 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[DENIAL_OF_EMERGENCY_AID_OR_CARE]` | Art. 3 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[DENIAL_OF_EMERGENCY_AID_OR_CARE]` | Art. 2 EMRK (bei Lebensgefahr) | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[DEATH_OR_SERIOUS_INJURY]` | Art. 2 EMRK (inkl. Untersuchungspflicht) | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[DEATH_OR_SERIOUS_INJURY]` | Art. 10 Abs. 1 BV | NOT_IN_KB | - | Art. 10 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[CHILD_RIGHTS_VIOLATION]` | Art. 11 BV | NOT_IN_KB | - | Art. 11 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[CHILD_RIGHTS_VIOLATION]` | Art. 19 BV (Grundschulunterricht) | NOT_IN_KB | - | Art. 19 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[CHILD_RIGHTS_VIOLATION]` | UN-Kinderrechtskonvention | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[CHILD_RIGHTS_VIOLATION]` | Art. 3, 8 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[DISCRIMINATION_BY_AUTHORITY]` | Art. 8 Abs. 2 BV | NOT_IN_KB | - | Art. 8 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[DISCRIMINATION_BY_AUTHORITY]` | Art. 14 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[DISCRIMINATION_BY_AUTHORITY]` | UN-Rassendiskriminierungskonvention | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[DISCRIMINATION_BY_AUTHORITY]` | Behindertengleichstellungsgesetz | UNRESOLVABLE | - | Bereich/Sammelverweis/Freitext: bewusst nicht automatisch aufgelöst (Rechtsteam). |
| `liability_flags.yaml/categories[FAMILY_AND_PRIVACY_INTERFERENCE]` | Art. 8 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[FAMILY_AND_PRIVACY_INTERFERENCE]` | Art. 13 BV | NOT_IN_KB | - | Art. 13 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[FAMILY_AND_PRIVACY_INTERFERENCE]` | Art. 14 BV | NOT_IN_KB | - | Art. 14 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[FAMILY_AND_PRIVACY_INTERFERENCE]` | nDSG / kantonales Datenschutzrecht | UNRESOLVABLE | - | Bereich/Sammelverweis/Freitext: bewusst nicht automatisch aufgelöst (Rechtsteam). |
| `liability_flags.yaml/categories[PROCEDURAL_DENIAL]` | Art. 29 BV (rechtliches Gehoer, Rechtsverzoegerung) | NOT_IN_KB | - | Art. 29 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[PROCEDURAL_DENIAL]` | Art. 29a BV | NOT_IN_KB | - | Art. 29a BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[PROCEDURAL_DENIAL]` | Art. 13 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[PROCEDURAL_DENIAL]` | Art. 6 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[AUTHORITY_INACTION]` | Art. 29 Abs. 1 BV | NOT_IN_KB | - | Art. 29 BV ist (noch) keine Quelle im Wissensbestand; kein Eintrag erfunden. |
| `liability_flags.yaml/categories[AUTHORITY_INACTION]` | Schutzpflichten aus Art. 2, 3, 8 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
| `liability_flags.yaml/categories[AUTHORITY_INACTION]` | Staatshaftung (VG / kantonale Haftungsgesetze) | UNRESOLVABLE | - | Bereich/Sammelverweis/Freitext: bewusst nicht automatisch aufgelöst (Rechtsteam). |
| `liability_flags.yaml/categories[FORCED_LABOUR]` | Art. 4 EMRK | INTERNATIONAL | - | Völkerrecht: nur mit eindeutiger amtlicher Schweizer Quelle (nicht automatisch). |
