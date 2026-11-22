"""Text for scanned PDFs (pages that are only pictures), read with Tesseract through PyMuPDF.

A scanned paper has no text to search, to identify it by or to show matches from. When a PDF
is added, the first two pages of a scan are read at once, so the paper can be identified (see
pdf.analyze); the rest is read in a background thread, page by page, and goes into the
full-text index. The text of each page is kept in <data>/ocr/<item>-<pdf hash>.json for the
"matches in this paper" list. The PDF itself is never changed.

Scans already in the library are read too, one at a time, in the background. Tesseract and its
languages come with the Docker image (BUBO_OCR_LANGS chooses among those installed);
without Tesseract, nothing happens. BUBO_OCR=0 turns it off.
"""

import json
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

from . import db, storage
from .config import settings

log = logging.getLogger("bubo.ocr")

DPI = 300               # Tesseract reads small print well from 300 dpi
MIN_CHARS = 25          # a page with less text than this, and a picture, is a scan
MAX_PAGES = 80          # pages read per paper (a long scanned book is not read whole)
FIRST_PAGES = 2         # read at once when a scan is added, to identify it

_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")
_setup: dict = {}


def _tessdata() -> str | None:
    try:
        found = pymupdf.get_tessdata()
        if found and Path(found).is_dir():
            return str(found)
    except Exception:
        pass
    for pattern in ("/usr/share/tesseract-ocr/*/tessdata", "/usr/share/tessdata", "/opt/homebrew/share/tessdata",
                    "/usr/local/share/tessdata"):
        for p in sorted(Path("/").glob(pattern.lstrip("/")), reverse=True):
            if p.is_dir():
                return str(p)
    return None


def languages() -> str | None:
    """The Tesseract languages to read with ("eng+deu+spa+fra"), or None without OCR."""
    if "langs" in _setup:
        return _setup["langs"]
    langs = None
    if settings.ocr and shutil.which("tesseract") and (td := _tessdata()):
        installed = {p.stem for p in Path(td).glob("*.traineddata")}
        chosen = [lang for lang in settings.ocr_langs.split("+") if lang in installed]
        langs = "+".join(chosen or (["eng"] if "eng" in installed else [])) or None
        _setup["tessdata"] = td
    _setup["langs"] = langs
    return langs


def is_scanned(page) -> bool:
    return len(page.get_text().strip()) < MIN_CHARS and bool(page.get_images())


def page_text(page) -> str:
    """The text Tesseract reads on a page ("" if it cannot)."""
    langs = languages()
    if not langs:
        return ""
    try:
        tp = page.get_textpage_ocr(language=langs, dpi=DPI, full=True, tessdata=_setup.get("tessdata"))
        return page.get_text(textpage=tp)
    except Exception as e:
        log.warning("OCR of page %s: %s", page.number + 1, e)
        return ""


def needs_ocr(doc) -> bool:
    """Most of the first pages are pictures without text."""
    pages = [doc[i] for i in range(min(5, len(doc)))]
    return bool(pages) and sum(is_scanned(p) for p in pages) * 2 >= len(pages)


def read(doc, limit: int = MAX_PAGES) -> list[str]:
    """Every page's text (up to limit pages): Tesseract's for scanned pages, the PDF's otherwise."""
    return [page_text(p) if is_scanned(p) else p.get_text() for p in (doc[i] for i in range(min(limit, len(doc))))]


# --------------------------------------------------------------------------- #
# Kept text
# --------------------------------------------------------------------------- #

def _dir() -> Path:
    d = settings.data_dir / "ocr"
    d.mkdir(exist_ok=True)
    return d


def _path(item_id: int, file_hash: str) -> Path:
    return _dir() / f"{item_id}-{(file_hash or '')[:16]}.json"


def saved_pages(item_id: int, file_hash: str | None) -> list[str] | None:
    """The text read from a paper's scanned PDF, page by page, if there is any."""
    if not file_hash:
        return None
    try:
        return json.loads(_path(item_id, file_hash).read_text())
    except (OSError, ValueError):
        return None


def remove(item_id: int) -> None:
    for p in _dir().glob(f"{item_id}-*.json"):
        p.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# In the background
# --------------------------------------------------------------------------- #

def run(item_id: int) -> str | None:
    """Read a paper's scanned PDF and index its text. Returns the status saved: "done" (it
    was a scan, now read), "none" (not a scan) or None (nothing to do)."""
    from . import pdf
    if not languages():
        return None
    conn = db.connect()
    try:
        row = conn.execute("SELECT file_name, file_hash FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row or not row["file_name"]:
            return None
        try:
            doc = pymupdf.open(storage.abs_path(row["file_name"]))
        except Exception as e:
            log.warning("OCR: cannot open the PDF of item %s: %s", item_id, e)
            conn.execute("UPDATE items SET ocr_status = 'error' WHERE id = ?", (item_id,))
            conn.commit()
            return "error"
        with doc:
            if not needs_ocr(doc):
                status = "none"
            else:
                texts = read(doc)
                remove(item_id)
                _path(item_id, row["file_hash"]).write_text(json.dumps(texts, ensure_ascii=False))
                db.reindex(conn, item_id, fulltext="\n".join(texts)[:pdf.MAX_FULLTEXT])
                status = "done"
                log.info("OCR: read %s pages of item %s", len(texts), item_id)
        conn.execute("UPDATE items SET ocr_status = ? WHERE id = ?", (status, item_id))
        conn.commit()
        return status
    finally:
        conn.close()


def _run_safely(item_id: int) -> None:
    try:
        run(item_id)
    except Exception:
        log.exception("OCR of item %s failed", item_id)


def schedule(item_id: int) -> None:
    """A paper has a new PDF: read it in the background if it is a scan."""
    if languages():
        with _lock:
            _executor.submit(_run_safely, item_id)


def start_backlog() -> None:
    """Papers added before OCR (or while it was off): look at each PDF once, in the background."""
    if not languages():
        return

    def go():
        conn = db.connect()
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM items WHERE file_name IS NOT NULL AND ocr_status IS NULL "
                "AND deleted_at IS NULL ORDER BY id DESC")]
        finally:
            conn.close()
        for item_id in ids:
            _run_safely(item_id)

    with _lock:
        _executor.submit(go)
