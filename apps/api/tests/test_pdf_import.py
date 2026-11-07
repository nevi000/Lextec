"""PDF import of a written case description: text extraction only, no storage, no AI call, same pipeline afterwards."""

from __future__ import annotations

import io

from pypdf import PdfWriter

from tests.conftest import new_case

URL = "/api/intake/pdf-text"
PDF = {"Content-Type": "application/pdf"}


def make_pdf(pages: list[str]) -> bytes:
    """Minimal text-based PDF (one Helvetica text line per page); Latin-1 text only."""
    objs: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    font_obj = 3 + 2 * n
    for i, text in enumerate(pages):
        content = (
            b"BT /F1 12 Tf 50 750 Td ("
            + text.encode("latin-1").replace(b"(", b"\\(").replace(b")", b"\\)")
            + b") Tj ET"
        )
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> >>".encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objs.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    )
    return out.getvalue()


def blank_pdf(pages: int = 1, password: str | None = None) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=200, height=200)
    if password:
        w.encrypt(password)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def post(client, data: bytes, headers=PDF):
    return client.post(URL, content=data, headers=headers)


def err(r) -> str:
    return r.json()["error"]["code"]


def test_valid_text_pdf_returns_the_text(client):
    text = "Meine Klientin hat gestern eine Mietzinserhoehung erhalten. Sie wohnt in Zuerich."
    r = post(client, make_pdf([text]))
    assert r.status_code == 200
    body = r.json()
    assert body["pages"] == 1 and not body["truncated"]
    assert "Mietzinserhoehung erhalten" in body["text"]


def test_umlauts_survive(client):
    r = post(client, make_pdf(["Kündigung der Wohnung in Zürich"]))
    assert r.status_code == 200
    assert "Kündigung der Wohnung in Zürich" in r.json()["text"]


def test_multi_page_description(client):
    r = post(client, make_pdf(["Erste Seite der Schilderung.", "Zweite Seite der Schilderung."]))
    body = r.json()
    assert body["pages"] == 2
    assert body["text"].index("Erste") < body["text"].index("Zweite")


def test_pdf_without_text_is_reported(client):
    r = post(client, blank_pdf())
    assert r.status_code == 422 and err(r) == "pdf_no_text"
    assert "kein Text ausgelesen" in r.json()["error"]["message"]


def test_page_with_only_whitespace_is_reported(client):
    assert err(post(client, make_pdf(["   "]))) == "pdf_no_text"


def test_empty_body(client):
    assert err(post(client, b"")) == "pdf_empty"


def test_not_a_pdf(client):
    r = post(client, b"PK\x03\x04 this is a zip", {"Content-Type": "application/pdf"})
    assert r.status_code == 422 and err(r) == "pdf_invalid_type"
    # the declared type does not matter, the content does
    assert err(post(client, b"hello world", {"Content-Type": "text/plain"})) == "pdf_invalid_type"


def test_corrupt_pdf(client):
    r = post(client, b"%PDF-1.4\n1 0 obj << /Broken\n garbage \x00\x01\x02")
    assert r.status_code == 422 and err(r) in {
        "pdf_corrupt",
        "pdf_no_text",
        "pdf_extraction_failed",
    }
    assert r.status_code != 500


def test_password_protected_pdf(client):
    r = post(client, blank_pdf(password="geheim"))
    assert r.status_code == 422 and err(r) == "pdf_encrypted"
    assert "passwortgeschützt" in r.json()["error"]["message"]


def test_too_large(client, ctx):
    limit = ctx.settings.pdf_import_max_bytes
    r = post(client, b"%PDF-1.4\n" + b"0" * (limit + 1))
    assert r.status_code == 422 and err(r) == "pdf_too_large"


def test_too_many_pages(client, ctx):
    n = ctx.settings.pdf_import_max_pages + 1
    r = post(client, blank_pdf(n))
    assert r.status_code == 422 and err(r) == "pdf_too_many_pages"


def test_text_is_capped_to_message_limit(client):
    r = post(client, make_pdf(["wort " * 6000]))  # 30000 characters on one line
    assert r.status_code == 200
    assert r.json()["truncated"] is True and len(r.json()["text"]) <= 20000


def test_import_stores_nothing_and_makes_no_ai_call(client, ctx):
    from sqlalchemy import func, select

    from app.models.tables import Case, CaseMessage

    def counts():
        with ctx.session_factory() as s:
            return (
                s.scalar(select(func.count()).select_from(Case)),
                s.scalar(select(func.count()).select_from(CaseMessage)),
            )

    before = counts()
    usage_before = client.get("/api/ai/usage").json()
    assert (
        post(client, make_pdf(["Meine Klientin hat eine Kuendigung erhalten."])).status_code == 200
    )
    assert counts() == before
    assert (
        client.get("/api/ai/usage").json() == usage_before
    )  # extraction never calls the AI provider


def test_pdf_has_no_database_model():
    from app.models import tables

    assert not [
        n
        for n in dir(tables)
        if "pdf" in n.lower() or "document" in n.lower() or "upload" in n.lower()
    ]


def test_extracted_text_runs_through_the_normal_pipeline(client):
    """Integration B: PDF text -> description -> same analysis as typed text -> Issue 7."""
    text = (
        "Meine Klientin hat gestern eine Mietzinserhöhung erhalten. Sie wohnt in Zürich und möchte wissen, "
        "ob sie diese überprüfen lassen soll."
    )
    extracted = post(client, make_pdf([text])).json()["text"]
    cid = new_case(client)["id"]
    r = client.post(
        f"/api/cases/{cid}/messages", json={"content": extracted, "kind": "DESCRIPTION"}
    )
    assert r.status_code == 201 and r.json()["analysis"]["status"] == "OK"
    ids = {i["issue_definition_id"] for i in client.get(f"/api/cases/{cid}").json()["issues"]}
    assert "CH_TENANCY_RENT_INCREASE" in ids
