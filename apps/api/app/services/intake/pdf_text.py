"""Local text extraction for the «Fallbeschreibung als PDF importieren» feature.

The PDF is only an alternative way to enter the free-text case description. Nothing is stored:
the bytes live in memory for the duration of the request, only the extracted text is returned
to the browser, which puts it into the normal description field. No OCR, no external service.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.errors import AppError

PDF_MAGIC = b"%PDF-"
MAX_TEXT_CHARS = 20000  # same limit as a normally entered message


class PdfImportError(AppError):
    status_code = 422
    code = "pdf_import_failed"


@dataclass(frozen=True)
class PdfText:
    text: str
    pages: int
    truncated: bool


def _tidy(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_case_text(data: bytes, *, max_bytes: int, max_pages: int) -> PdfText:
    if not data:
        raise PdfImportError("Die Datei ist leer.", code="pdf_empty")
    if len(data) > max_bytes:
        raise PdfImportError(
            f"Die Datei ist zu gross (maximal {max_bytes // (1024 * 1024)} MB).",
            code="pdf_too_large",
        )
    if not data.lstrip()[:1024].startswith(PDF_MAGIC) and PDF_MAGIC not in data[:1024]:
        raise PdfImportError(
            "Diese Datei ist kein PDF. Bitte wählen Sie eine PDF-Datei.", code="pdf_invalid_type"
        )
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # an empty user password is the only thing we try; we never ask for or guess passwords
            try:
                ok = reader.decrypt("")
            except Exception:  # noqa: BLE001
                ok = 0
            if not ok:
                raise PdfImportError(
                    "Dieses PDF ist passwortgeschützt. Bitte laden Sie eine ungeschützte Version hoch "
                    "oder kopieren Sie die Fallbeschreibung direkt in das Eingabefeld.",
                    code="pdf_encrypted",
                )
        pages = len(reader.pages)
        if pages > max_pages:
            raise PdfImportError(
                f"Das PDF hat zu viele Seiten ({pages}; maximal {max_pages}). "
                "Eine Fallbeschreibung sollte kurz sein.",
                code="pdf_too_many_pages",
            )
        parts: list[str] = []
        total = 0
        for page in reader.pages:
            chunk = page.extract_text() or ""
            parts.append(chunk)
            total += len(chunk)
            if total > MAX_TEXT_CHARS * 3:  # resource guard, stop reading further pages
                break
    except PdfImportError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, AttributeError, OSError, RecursionError):
        raise PdfImportError(
            "Das PDF ist beschädigt oder kann nicht gelesen werden. Bitte versuchen Sie ein anderes PDF.",
            code="pdf_corrupt",
        ) from None
    except Exception:  # noqa: BLE001 - parser errors vary; never leak details or content
        raise PdfImportError(
            "Beim Auslesen des PDFs ist ein Fehler aufgetreten. Bitte versuchen Sie ein anderes PDF.",
            code="pdf_extraction_failed",
        ) from None

    text = _tidy("\n\n".join(parts))
    if not text:
        raise PdfImportError(
            "Aus diesem PDF konnte kein Text ausgelesen werden. Bitte verwenden Sie ein PDF mit "
            "auswählbarem Text oder kopieren Sie Ihre Fallbeschreibung direkt in das Eingabefeld.",
            code="pdf_no_text",
        )
    truncated = len(text) > MAX_TEXT_CHARS
    if truncated:
        text = text[:MAX_TEXT_CHARS].rstrip()
    return PdfText(text=text, pages=pages, truncated=truncated)
