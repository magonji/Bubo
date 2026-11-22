"""Text and metadata-hint extraction from PDFs using PyMuPDF."""

import hashlib
import re
from dataclasses import dataclass, field

import pymupdf

MAX_FULLTEXT = 3_000_000  # characters indexed per document


@dataclass
class PdfInfo:
    fulltext: str = ""
    pages: list[str] = field(default_factory=list)   # text of the first few pages
    meta_title: str | None = None
    meta_author: str | None = None
    meta_subject: str | None = None
    guessed_title: str | None = None
    scanned: bool = False             # pages that are only pictures (their text read by OCR)


def is_pdf(data: bytes) -> bool:
    return b"%PDF" in data[:1024]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _guess_title(page) -> str | None:
    """The title is usually the text set in the largest font on the first page."""
    spans = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if len(text) >= 2:
                    spans.append((round(span["size"], 1), span["bbox"][1], text))
    if not spans:
        return None
    biggest = max(s for s, _, _ in spans)
    parts = [t for s, y, t in sorted(spans, key=lambda x: x[1]) if s >= biggest - 0.5]
    title = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if 10 <= len(title) <= 300 and not re.match(r"(?i)^(arxiv|journal|proceedings)", title):
        return title
    return None


def analyze(data: bytes) -> PdfInfo:
    info = PdfInfo()
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        return info
    with doc:
        meta = doc.metadata or {}
        title = (meta.get("title") or "").strip()
        # Generic titles left by authoring tools (e.g. "Microsoft Word - doc1.docx") are useless.
        if title and not re.search(r"(?i)(\.docx?|\.tex|\.dvi|\.pdf|\.tmp|untitled|microsoft word)", title) \
                and not re.fullmatch(r"[\w-]*\d[\w-]*", title):      # "tjv7373", "doc1": a file's name
            info.meta_title = title
        author = (meta.get("author") or "").strip()
        info.meta_author = author if author and author.lower() not in ("unknown", "usuario", "user", "admin") else None
        info.meta_subject = (meta.get("subject") or "").strip() or None
        texts, total = [], 0
        for i, page in enumerate(doc):
            t = page.get_text()
            if i < 3:
                info.pages.append(t)
            if total < MAX_FULLTEXT:
                texts.append(t)
                total += len(t)
        # A scan: read its first pages now, to identify it (ocr.py reads the rest later).
        from . import ocr
        if len(doc) and ocr.languages() and ocr.needs_ocr(doc):
            info.scanned = True
            for i in range(min(ocr.FIRST_PAGES, len(doc))):
                if ocr.is_scanned(doc[i]):
                    t = ocr.page_text(doc[i])
                    if i < len(info.pages):
                        info.pages[i] = t
                    if i < len(texts):
                        texts[i] = t
        info.fulltext = "\n".join(texts)[:MAX_FULLTEXT]
        if len(doc):
            try:
                info.guessed_title = _guess_title(doc[0])
            except Exception:
                pass
    return info
