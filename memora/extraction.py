from __future__ import annotations

from io import BytesIO

from docx import Document
from pypdf import PdfReader

SUPPORTED_UPLOAD_TYPES = {
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def extract_text_from_upload(content_type: str | None, blob: bytes) -> str:
    if content_type == "text/plain":
        return _extract_text_from_plain(blob)

    if content_type == "application/pdf":
        return _extract_text_from_pdf(blob)

    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_text_from_docx(blob)

    raise ValueError("unsupported file type")


def _extract_text_from_plain(blob: bytes) -> str:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("could not decode uploaded text file") from exc

    cleaned = text.strip()
    if not cleaned:
        raise ValueError("uploaded file is empty")

    return cleaned


def _extract_text_from_pdf(blob: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(blob))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        raise ValueError("could not parse uploaded pdf") from exc

    combined = "\n".join(pages).strip()
    if not combined:
        raise ValueError("uploaded file has no readable text")

    return combined


def _extract_text_from_docx(blob: bytes) -> str:
    try:
        doc = Document(BytesIO(blob))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("could not parse uploaded docx") from exc

    combined = "\n".join(paragraph.text for paragraph in doc.paragraphs).strip()
    if not combined:
        raise ValueError("uploaded file has no readable text")

    return combined
