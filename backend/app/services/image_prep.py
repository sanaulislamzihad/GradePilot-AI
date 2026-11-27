"""Turn uploaded scripts into page images a vision model can read well.

Photos are rotated upright from their EXIF orientation, converted to grayscale,
contrast-enhanced (CLAHE) and scaled down to a sensible size. Scanned PDFs are
rendered page by page.
"""

import io
from dataclasses import dataclass

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageOps

from app.providers.base import AIImage

MAX_SIDE = 2000
PDF_DPI = 150
MIN_TEXT_CHARS = 25


@dataclass
class PageImage:
    page: int  # 1-based, across all files of the submission
    image: AIImage


def enhance(data: bytes) -> AIImage:
    with Image.open(io.BytesIO(data)) as source:
        upright = ImageOps.exif_transpose(source).convert("L")
        array = np.array(upright)
    height, width = array.shape[:2]
    scale = min(1.0, MAX_SIDE / max(height, width))
    if scale < 1.0:
        array = cv2.resize(array, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    array = clahe.apply(array)
    ok, encoded = cv2.imencode(".jpg", array, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("Could not encode the page image")
    return AIImage("image/jpeg", encoded.tobytes())


def pdf_page_texts(data: bytes) -> list[str]:
    with pymupdf.open(stream=data, filetype="pdf") as document:
        return [page.get_text("text", sort=True).strip() for page in document]


def pdf_has_text_layer(texts: list[str]) -> bool:
    return bool(texts) and all(len(text) >= MIN_TEXT_CHARS for text in texts)


def render_pdf(data: bytes, first_page: int = 1) -> list[PageImage]:
    pages: list[PageImage] = []
    with pymupdf.open(stream=data, filetype="pdf") as document:
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(dpi=PDF_DPI)
            pages.append(PageImage(first_page + index, enhance(pixmap.tobytes("png"))))
    return pages
