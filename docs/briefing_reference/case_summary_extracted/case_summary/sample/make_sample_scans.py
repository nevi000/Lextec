#!/usr/bin/env python3
"""Erzeugt fiktive Muster-'Scans' (Mietvertrag, Kuendigungsformular) fuer die Demo.
Alle Daten sind erfunden und als MUSTER gekennzeichnet."""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "scans"
OUT.mkdir(exist_ok=True)
W, H = 1240, 1754  # A4 @150 dpi
F = "/usr/share/fonts/truetype/dejavu/"
reg = lambda s: ImageFont.truetype(F + "DejaVuSerif.ttf", s)
bold = lambda s: ImageFont.truetype(F + "DejaVuSerif-Bold.ttf", s)
sans = lambda s: ImageFont.truetype(F + "DejaVuSans.ttf", s)


def page():
    img = Image.new("L", (W, H), 246)
    return img, ImageDraw.Draw(img)


def scanify(img, angle):
    random.seed(7)
    px = img.load()
    for _ in range(9000):
        x, y = random.randrange(W), random.randrange(H)
        px[x, y] = max(0, px[x, y] - random.randint(20, 70))
    img = img.filter(ImageFilter.GaussianBlur(0.6)).rotate(angle, fillcolor=232, resample=Image.BICUBIC)
    return img


def stamp(d):
    d.text((W - 360, 60), "MUSTER · FIKTIV", font=sans(30), fill=150)


def kv(d, y, k, v, x=110):
    d.text((x, y), k, font=reg(25), fill=60)
    d.text((x + 420, y), v, font=reg(25), fill=20)
    d.line((x + 415, y + 32, W - 110, y + 32), fill=170, width=1)
    return y + 52


# ---------- Mietvertrag ----------
img, d = page(); stamp(d)
d.text((110, 120), "MIETVERTRAG FÜR WOHNRÄUME", font=bold(44), fill=15)
d.text((110, 180), "Paritätischer Vertrag (Muster für Demo-Zwecke)", font=reg(24), fill=80)
y = 270
d.text((110, y), "1. Vertragsparteien", font=bold(28), fill=20); y += 55
y = kv(d, y, "Vermieterin", "Immobilien Beispiel AG, Verwaltung")
y = kv(d, y, "", "Beispielweg 3, 9000 St. Gallen")
y = kv(d, y, "Mieter", "Marco Meier und Lara Meier")
y = kv(d, y, "", "(solidarisch haftend)")
y += 20; d.text((110, y), "2. Mietobjekt", font=bold(28), fill=20); y += 55
y = kv(d, y, "Adresse", "Musterstrasse 12, 9000 St. Gallen")
y = kv(d, y, "Objekt", "4½-Zimmer-Wohnung, 2. OG links")
y = kv(d, y, "Nebenräume", "Kellerabteil Nr. 7")
y += 20; d.text((110, y), "3. Dauer und Kündigung", font=bold(28), fill=20); y += 55
y = kv(d, y, "Mietbeginn", "01.04.2019")
y = kv(d, y, "Vertragsdauer", "unbefristet")
y = kv(d, y, "Kündigungsfrist", "3 Monate")
y = kv(d, y, "Kündigungstermine", "ortsüblich (ausser 31.12.)")
y += 20; d.text((110, y), "4. Mietzins", font=bold(28), fill=20); y += 55
y = kv(d, y, "Nettomietzins / Monat", "CHF 1'640.–")
y = kv(d, y, "Akonto Nebenkosten", "CHF 210.–")
y = kv(d, y, "Bruttomietzins / Monat", "CHF 1'850.–")
y = kv(d, y, "Referenzzinssatz", "1.50 %  (Basis bei Vertragsschluss)")
y += 20; d.text((110, y), "5. Sicherheitsleistung", font=bold(28), fill=20); y += 55
y = kv(d, y, "Mietkaution", "CHF 4'920.– (Mietkautionskonto)")
y += 60
d.text((110, y), "St. Gallen, 12.02.2019", font=reg(25), fill=40)
d.text((110, y + 110), "Vermieterin ____________________", font=reg(25), fill=40)
d.text((680, y + 110), "Mieter ____________________", font=reg(25), fill=40)
d.text((110, H - 90), "Seite 1 von 4", font=sans(20), fill=110)
scanify(img, 0.5).save(OUT / "mietvertrag_s1.png", optimize=True)

# ---------- Kuendigungsformular ----------
img, d = page(); stamp(d)
d.text((110, 110), "Kanton St. Gallen", font=sans(24), fill=70)
d.text((110, 150), "Formular zur Mitteilung der Kündigung", font=bold(40), fill=15)
d.text((110, 200), "für Wohn- und Geschäftsräume (Art. 266l Abs. 2 OR) – MUSTER", font=reg(24), fill=70)
y = 300
y = kv(d, y, "Vermieterin", "Immobilien Beispiel AG")
y = kv(d, y, "An", "Herrn Marco Meier")
y = kv(d, y, "", "Musterstrasse 12, 9000 St. Gallen")
y = kv(d, y, "Mietobjekt", "4½-Zimmer-Wohnung, 2. OG links")
y += 20
y = kv(d, y, "Kündigung auf den", "31.01.2027")
y = kv(d, y, "Begründung", "Eigenbedarf (Sanierung geplant)")
y += 40
box = [
    "Rechtsbelehrung (Auszug, Muster):",
    "Wer die Kündigung anfechten will, muss dies innert 30 Tagen nach",
    "Empfang der Kündigung bei der Schlichtungsbehörde tun",
    "(Art. 273 Abs. 1 OR). Ein Erstreckungsbegehren ist innert",
    "derselben Frist zu stellen (Art. 273 Abs. 2 OR).",
]
d.rectangle((105, y - 10, W - 105, y + 40 * len(box) + 10), outline=120, width=2)
for i, line in enumerate(box):
    d.text((125, y + i * 40), line, font=reg(23), fill=40)
y += 40 * len(box) + 70
d.text((110, y), "St. Gallen, 09.10.2026", font=reg(25), fill=40)
d.text((110, y + 100), "Immobilien Beispiel AG  ____________________", font=reg(25), fill=40)
d.text((110, H - 90), "Zustellung: eingeschrieben", font=sans(20), fill=110)
scanify(img, -0.7).save(OUT / "kuendigung_s1.png", optimize=True)
print("ok", sorted(p.name for p in OUT.iterdir()))
