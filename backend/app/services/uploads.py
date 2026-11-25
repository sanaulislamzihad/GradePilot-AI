"""Upload validation that does not trust the client.

The file type is decided from the file's own bytes (magic numbers), and must
agree with the extension. Images are fully decoded to reject corrupt or
malformed files before anything else touches them.
"""

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.errors import AppError

_CHUNK = 1024 * 1024
# Guards against zip bombs disguised as Word documents.
_MAX_DOCX_UNCOMPRESSED = 100 * 1024 * 1024


@dataclass(frozen=True)
class FileKind:
    name: str
    extensions: tuple[str, ...]
    content_type: str


PDF = FileKind("pdf", (".pdf",), "application/pdf")
PNG = FileKind("png", (".png",), "image/png")
JPEG = FileKind("jpeg", (".jpg", ".jpeg"), "image/jpeg")
DOCX = FileKind(
    "docx", (".docx",), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

KINDS_BY_FORMAT = {"pdf": PDF, "png": PNG, "jpg": JPEG, "jpeg": JPEG, "docx": DOCX}


@dataclass(frozen=True)
class ValidatedFile:
    data: bytes
    kind: FileKind
    extension: str
    original_filename: str
    sha256: str


def _sniff(data: bytes) -> FileKind | None:
    if data.startswith(b"%PDF-"):
        return PDF
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "word/document.xml" in archive.namelist():
                    return DOCX
        except zipfile.BadZipFile:
            return None
    return None


def _safe_filename(name: str | None) -> str:
    base = PurePath((name or "upload").replace("\\", "/")).name
    cleaned = "".join(ch for ch in base if ch.isprintable() and ch not in '<>:"|?*').strip()
    return (cleaned or "upload")[:200]


async def read_validated(upload: UploadFile, allowed: set[str], max_bytes: int) -> ValidatedFile:
    """Read an upload, enforcing size, extension and content-type rules."""
    filename = _safe_filename(upload.filename)
    extension = PurePath(filename).suffix.lower()
    allowed_kinds = {KINDS_BY_FORMAT[fmt] for fmt in allowed}
    allowed_extensions = sorted({ext for kind in allowed_kinds for ext in kind.extensions})

    if extension not in allowed_extensions:
        raise AppError(415, f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}")

    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(_CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise AppError(413, f"File is too large. The limit is {max_bytes // (1024 * 1024)} MB.")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise AppError(400, "The uploaded file is empty")

    kind = _sniff(data)
    if kind is None or kind not in allowed_kinds or extension not in kind.extensions:
        raise AppError(415, "The file content does not match its extension or is not a supported format")

    if kind == DOCX:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(info.file_size for info in archive.infolist()) > _MAX_DOCX_UNCOMPRESSED:
                raise AppError(400, "The document expands to an unreasonable size and was rejected")

    if kind in (PNG, JPEG):
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise AppError(400, "The image is corrupted or could not be read") from None

    return ValidatedFile(
        data=data,
        kind=kind,
        extension=extension,
        original_filename=filename,
        sha256=hashlib.sha256(data).hexdigest(),
    )
