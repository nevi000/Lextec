"""Erzeugt knowledge_base/referrals/referral_rules.yaml (produktiv) aus der Law-Team-Datei v1.2.

    python scripts/kb/build_referral_v12.py

* Eingabe (unverändert): docs/legal_inputs/referral_rules (1).yaml  (Version 1.2, 07.11.2026)
* Sicherung der bisher produktiven Version: docs/legal_inputs/previous/referral_network_v1.1_integrated.yaml
* Die v1.2-Datei bleibt TEXTLICH erhalten (Kommentare, 160 Gemeindezeilen). Nur markierte Ergänzungen der
  Software-Integration (# INTEGRATION) werden wieder angefügt, die in v1.2 fehlen:
    - official_check bei 142 / 143 / 147 (am 07.11.2026 auf den offiziellen Seiten geprüft)
    - address_protected bei Frauenhäusern (Durchgangsheim ANKER = öffentliche Notunterkunft, Adresse darf erscheinen) (Schutzadresse wird nie ausgegeben)
    - issue_rules: Alias CH_TENANCY_TERMINATION_ARREARS -> CH_TENANCY_PAYMENT_DEFAULT (ID der implementierten Issue-Datei)
    - issue_rules CH_TENANCY_TERMINATION: weitere Anlaufstelle (secondary) Rechtsauskunft
    - signal_bindings (Regel-IDs / Sicherheitskategorien -> Signale), role_location_basis, municipality_aliases
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "legal_inputs" / "referral_rules (1).yaml"
OLD = ROOT / "knowledge_base" / "referrals" / "referral_network.yaml"
OUT = ROOT / "knowledge_base" / "referrals" / "referral_rules.yaml"
BACKUP = ROOT / "docs" / "legal_inputs" / "previous" / "referral_network_v1.1_integrated.yaml"


def main() -> None:
    if OLD.exists():
        BACKUP.parent.mkdir(parents=True, exist_ok=True)
        if not BACKUP.exists():
            shutil.copy2(OLD, BACKUP)
    text = SRC.read_text(encoding="utf-8")
    old_text = OLD.read_text(encoding="utf-8") if OLD.exists() else BACKUP.read_text(encoding="utf-8")

    def insert_in_org(org_id: str, line: str) -> None:
        nonlocal text
        m = re.search(rf"^  - id: {re.escape(org_id)}\n", text, re.M)
        assert m, org_id
        nxt = re.search(r"^  - id: |^\n|^# ----", text[m.end() :], re.M)
        pos = m.end() + (nxt.start() if nxt else len(text) - m.end())
        text = text[:pos] + line + "\n" + text[pos:]

    marks = {
        "dargebotene_hand_143": '    official_check: {url: "https://www.143.ch/", checked: "2026-11-07", result: "143 anrufen, Chat und Mail"}   # INTEGRATION',
        "pro_juventute_147": '    official_check: {url: "https://www.147.ch/", checked: "2026-11-07", result: "147 jederzeit telefonisch erreichbar"}   # INTEGRATION',
        "opferhilfe_142": '    official_check: {url: "https://www.opferhilfe-schweiz.ch/", checked: "2026-11-07", result: "142 national seit 1. Mai 2026; ausdruecklich keine Notrufnummer"}   # INTEGRATION',
        "frauenhaus_violetta": "    address_protected: true            # INTEGRATION: Schutzadresse wird nie ausgegeben",
        "frauenhaus_winterthur": "    address_protected: true            # INTEGRATION: Schutzadresse wird nie ausgegeben",
    }
    for oid, line in marks.items():
        insert_in_org(oid, line)

    # issue rules
    assert "  - issue_id: CH_TENANCY_TERMINATION_ARREARS\n" in text
    text = text.replace(
        "  - issue_id: CH_TENANCY_TERMINATION_ARREARS\n",
        "  - issue_id: CH_TENANCY_PAYMENT_DEFAULT  # INTEGRATION: v1.2-ID CH_TENANCY_TERMINATION_ARREARS = Issue 3 (Alias)\n",
    )
    anchor = "      primary: [schlichtungsbehoerde_miete, mieterverband]\n"
    i = text.index("  - issue_id: CH_TENANCY_TERMINATION\n")
    j = text.index(anchor, i) + len(anchor)
    text = (
        text[:j]
        + "      secondary: [unentgeltliche_rechtsauskunft]   # INTEGRATION: weitere Anlaufstelle (Rechtsauskunft Bezirksgericht)\n"
        + text[j:]
    )

    # signal_bindings: copy from the integrated v1.1 file (section 7)
    k = old_text.index("# ---------------------------------------------------------------------------\n# 7. INTEGRATION: SIGNAL-BINDUNGEN")
    bindings = old_text[k:]
    text = text.rstrip("\n") + "\n\n" + bindings.rstrip("\n") + "\n"
    text += """
# ---------------------------------------------------------------------------
# 8. INTEGRATION: ORTSBEZUG JE ROLLE
#    Nicht jede Stelle richtet sich nach demselben Ort. property = Gemeinde des Mietobjekts (Schlichtungsbehoerde,
#    Rechtsauskunft Miete, Mieterverband); residence = Wohnsitzgemeinde der Klientin (Sozialdienst, Notunterkunft, KESB,
#    kjz, Opferberatung ...). Ist keine abweichende Wohnsitzgemeinde erfasst, gilt die Gemeinde des Mietobjekts
#    (mit Hinweis). Rollen ohne Eintrag: property.
# ---------------------------------------------------------------------------
role_location_basis:
  schlichtungsbehoerde_miete: property
  unentgeltliche_rechtsauskunft: property
  mieterverband: property
  ombudsstelle: property
  sozialdienst_gemeinde: residence
  notunterkunft: residence
  kesb: residence
  kjz: residence
  opferhilfe_kantonal: residence
  frauenhaus: residence
  frauenzentrale_kantonal: residence
  schuldenberatung: residence

# ---------------------------------------------------------------------------
# 9. INTEGRATION: ORTSTEIL-ALIASE (-> politische Gemeinde)
#    Nur eindeutige Zuordnungen. status: law_team = Beispiel aus dem Kommentar von v1.2 (Abschnitt 1b);
#    quartier = Stadtquartier bzw. Ortsteil, der verwaltungsmaessig zur genannten Gemeinde gehoert (Software-Ergaenzung,
#    vom Law-Team zu bestaetigen). Mehrdeutige Namen (z. B. nur "Affoltern", "Seen") sind bewusst NICHT aufgefuehrt.
#    Alias-Treffer werden im Fall als solche gekennzeichnet; die BFS-Nummer kommt aus dem Gemeindeeintrag.
# ---------------------------------------------------------------------------
municipality_aliases:
  Glattbrugg: {municipality: "ZH:Opfikon", status: law_team}
  Effretikon: {municipality: "ZH:Illnau-Effretikon", status: law_team}
  Oerlikon: {municipality: "ZH:Zürich", status: quartier}
  Altstetten: {municipality: "ZH:Zürich", status: quartier}
  Schwamendingen: {municipality: "ZH:Zürich", status: quartier}
  Höngg: {municipality: "ZH:Zürich", status: quartier}
  Wipkingen: {municipality: "ZH:Zürich", status: quartier}
  Albisrieden: {municipality: "ZH:Zürich", status: quartier}
  Leimbach: {municipality: "ZH:Zürich", status: quartier}
  Seebach: {municipality: "ZH:Zürich", status: quartier}
  Witikon: {municipality: "ZH:Zürich", status: quartier}
  Wollishofen: {municipality: "ZH:Zürich", status: quartier}
  Enge: {municipality: "ZH:Zürich", status: quartier}
  Fluntern: {municipality: "ZH:Zürich", status: quartier}
  Hirslanden: {municipality: "ZH:Zürich", status: quartier}
  Töss: {municipality: "ZH:Winterthur", status: quartier}
  Wülflingen: {municipality: "ZH:Winterthur", status: quartier}
  Oberwinterthur: {municipality: "ZH:Winterthur", status: quartier}
  Veltheim: {municipality: "ZH:Winterthur", status: quartier}
  Hegi: {municipality: "ZH:Winterthur", status: quartier}
  Kollbrunn: {municipality: "ZH:Zell (ZH)", status: quartier}
  Rikon: {municipality: "ZH:Zell (ZH)", status: quartier}
  Kemptthal: {municipality: "ZH:Lindau", status: quartier}
  Tagelswangen: {municipality: "ZH:Lindau", status: quartier}
"""
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"geschrieben: {OUT} ({len(text.splitlines())} Zeilen)")


if __name__ == "__main__":
    main()
