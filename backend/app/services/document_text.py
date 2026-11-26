"""Text extraction from uploaded documents, using local libraries only.

Digital PDFs and DOCX files are read directly. Scanned PDFs and images have no
text layer; they are reported as needing OCR, which arrives with the AI
provider integration in Phase 4. Nothing is guessed or invented here.
"""

import io
import logging
from dataclasses import dataclass

import docx
import pymupdf

from app.models.exam import ExtractionStatus
from app.services.uploads import DOCX, JPEG, PDF, PNG, FileKind

logger = logging.getLogger("gradepilot.extraction")

# Pages with fewer characters than this are treated as scanned images.
_MIN_CHARS_PER_PAGE = 25
_MAX_PAGES = 200


@dataclass
class ExtractionResult:
    status: ExtractionStatus
    text: str | None
    page_count: int | None
    message: str


def _extract_pdf(data: bytes) -> ExtractionResult:
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception:  # noqa: BLE001 - PyMuPDF raises several error types for bad files
        return ExtractionResult(ExtractionStatus.FAILED, None, None, "The PDF is corrupted or could not be opened.")

    with document:
        if document.needs_pass:
            return ExtractionResult(
                ExtractionStatus.FAILED, None, None, "The PDF is password-protected. Upload an unlocked copy."
            )
        page_count = document.page_count
        if page_count > _MAX_PAGES:
            return ExtractionResult(
                ExtractionStatus.FAILED, None, page_count, f"The PDF has more than {_MAX_PAGES} pages."
            )
        pages = [page.get_text("text", sort=True).strip() for page in document]

    text = "\n\n".join(page for page in pages if page)
    text_pages = sum(1 for page in pages if len(page) >= _MIN_CHARS_PER_PAGE)
    if text_pages == 0:
        return ExtractionResult(
            ExtractionStatus.NEEDS_OCR,
            None,
            page_count,
            "This PDF has no text layer (it looks scanned). Handwriting and scan recognition need an "
            "OCR-capable AI model, which is configured in a later phase. Add the questions manually for now.",
        )
    message = f"Extracted text from {text_pages} of {page_count} page(s)."
    if text_pages < page_count:
        message += " Some pages look scanned and were skipped."
    return ExtractionResult(ExtractionStatus.SUCCEEDED, text, page_count, message)


def _extract_docx(data: bytes) -> ExtractionResult:
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception:  # noqa: BLE001 - python-docx surfaces zip and XML errors
        return ExtractionResult(ExtractionStatus.FAILED, None, None, "The DOCX file is corrupted or could not be read.")

    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append("  ".join(dict.fromkeys(cells)))
    text = "\n".join(lines).strip()
    if not text:
        return ExtractionResult(ExtractionStatus.FAILED, None, None, "The document contains no text.")
    return ExtractionResult(ExtractionStatus.SUCCEEDED, text, None, "Extracted text from the document.")


def extract_text(data: bytes, kind: FileKind) -> ExtractionResult:
    if kind == PDF:
        return _extract_pdf(data)
    if kind == DOCX:
        return _extract_docx(data)
    if kind in (PNG, JPEG):
        return ExtractionResult(
            ExtractionStatus.NEEDS_OCR,
            None,
            1,
            "Images need an OCR-capable AI model to read, which is configured in a later phase. "
            "The file is stored; add the questions manually for now.",
        )
    return ExtractionResult(ExtractionStatus.FAILED, None, None, "Unsupported document type.")
