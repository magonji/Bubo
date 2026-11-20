"""Figures extracted from PDFs: thumbnails for the library and the figure carousel.

Two kinds of figure are found:

* Figures with a caption ("Figure 3.", "Fig. 3 |", "FIG. 3."): the drawings, images and
  short pieces of text (axis labels, panel letters) next to the caption are gathered into
  one region, which is rendered from the page. This covers vector figures (plots drawn as
  paths, very common in chemistry and physics) as well as raster ones, and never cuts off
  the labels around a plot.
* Embedded raster images that no caption claimed, such as a graphical abstract on the first
  page. Small images, images repeated on several pages (journal logos) and images with an
  extreme aspect ratio are ignored.

Each figure is saved as WebP in two sizes under ``<data>/figures/<item id>/<PDF hash>/``,
so a set of figures is reused for as long as the PDF does not change. Extraction runs in a
background thread when a PDF is added; ``python -m app.cli figures`` fills in the figures of
papers added before.
"""

import hashlib
import logging
import re
import shutil
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image

from . import db, storage
from .config import settings

log = logging.getLogger("bubo.figures")

SIZES = {"thumb": 400, "full": 1200}     # width in pixels
QUALITY = {"thumb": 78, "full": 84}
MAX_FIGURES = 30
MIN_PIXELS = (300, 200)                  # embedded images smaller than this are ignored
MAX_ASPECT = 4.0                         # nor are banners and slivers
MAX_GAP = 80                             # points between a figure and its caption, at most

# "Figure 1.", "Fig. 2 |", "FIG. 3:", "Figure S4 –". A sentence such as "Figure 1 shows…"
# does not match, because the number must be followed by punctuation or the end of a line.
CAPTION_RE = re.compile(
    r"^\s*(?:supplementary\s+|extended\s+data\s+)?(fig(?:ure)?\.?)\s*(S?\d+(?:\.\d+)?[a-z]?)\s*(?:[.:|—–-]|$)",
    re.I | re.M)


def root() -> Path:
    return settings.data_dir / "figures"


# --------------------------------------------------------------------------- #
# Finding figures in a PDF
# --------------------------------------------------------------------------- #

@dataclass
class Found:
    page: int                  # zero-based
    rect: pymupdf.Rect
    kind: str                  # "caption" (region above or below a caption) | "image"
    label: str = ""            # "Figure 3"
    caption: str = ""


def _clean_caption(text: str) -> str:
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1200]


def _is_prose(block) -> bool:
    """A block of running text (several long lines), as opposed to a label or a legend."""
    lines = [l for l in block[4].splitlines() if l.strip()]
    return len(lines) >= 2 and sum(len(l) for l in lines) / len(lines) >= 40


def _overlaps_x(a: pymupdf.Rect, x0: float, x1: float) -> bool:
    return a.x1 > x0 and a.x0 < x1


def _grow(seed: pymupdf.Rect, pool: list[pymupdf.Rect], gap: float) -> pymupdf.Rect:
    """Union of `seed` and every rectangle in `pool` reachable through gaps below `gap`."""
    region, used = pymupdf.Rect(seed), set()
    changed = True
    while changed:
        changed = False
        near = region + (-gap, -gap, gap, gap)
        for i, r in enumerate(pool):
            if i not in used and near.intersects(r):
                region |= r
                used.add(i)
                changed = True
    return region


def _caption_figures(page, graphics: list[pymupdf.Rect], text_blocks: list) -> list[Found]:
    """Figures identified by their captions on one page."""
    width = page.rect.width
    captions = [b for b in text_blocks if CAPTION_RE.match(b[4])]
    captions.sort(key=lambda b: b[1])
    found = []
    for n, cap in enumerate(captions):
        crect = pymupdf.Rect(cap[:4])
        # A caption narrower than most of the page belongs to one column of a two-column
        # layout, and so does its figure. A full-width figure may have wider gaps between
        # its panels.
        if crect.width < 0.6 * width:
            x0, x1, gap = crect.x0 - 20, crect.x1 + 20, 24
        else:
            x0, x1, gap = page.rect.x0, page.rect.x1, 48
        # Look above the caption first (the usual place), then below it.
        prev_bottom = max([pymupdf.Rect(c[:4]).y1 for c in captions[:n]
                           if _overlaps_x(pymupdf.Rect(c[:4]), x0, x1)], default=page.rect.y0)
        next_top = min([pymupdf.Rect(c[:4]).y0 for c in captions[n + 1:]
                        if _overlaps_x(pymupdf.Rect(c[:4]), x0, x1)], default=page.rect.y1)
        region = None
        above = [g for g in graphics if g.y1 <= crect.y1 and g.y0 < crect.y0 - 10
                 and g.y0 >= prev_bottom - 2 and _overlaps_x(g, x0, x1)]
        if above:
            seed = max(above, key=lambda g: min(g.y1, crect.y0))
            if crect.y0 - seed.y1 < MAX_GAP:
                region = _grow(seed, above, gap)
                region.y1 = min(region.y1, crect.y0 - 1)
        if region is None:
            below = [g for g in graphics if g.y0 >= crect.y1 - 4 and g.y1 <= next_top + 2
                     and _overlaps_x(g, x0, x1)]
            if below:
                seed = min(below, key=lambda g: g.y0)
                if seed.y0 - crect.y1 < MAX_GAP:
                    region = _grow(seed, below, gap)
        if region is None:
            continue
        # Add the short texts around the graphics (axis labels, legends, panel letters).
        # A block of body text sticks out of the figure's surroundings, so it is left out.
        for _ in range(2):
            near, around = region + (-24, -20, 24, 20), region + (-56, -48, 56, 48)
            for b in text_blocks:
                r = pymupdf.Rect(b[:4])
                if b is not cap and near.intersects(r) and around.contains(r) \
                        and not CAPTION_RE.match(b[4]) and not _is_prose(b) \
                        and not r.intersects(crect):
                    region |= r
        region = (region + (-6, -6, 6, 6)) & page.rect
        if region.width < 60 or region.height < 40 or region.get_area() < 0.015 * page.rect.get_area():
            continue
        m = CAPTION_RE.match(cap[4])
        found.append(Found(page.number, region, "caption", f"Figure {m.group(2)}",
                           _clean_caption(cap[4])))
    return found


def find_figures(doc: pymupdf.Document) -> list[Found]:
    # Images that appear on more than one page are logos, rules and decorations.
    pages_of: dict[int, set] = {}
    for page in doc:
        for img in page.get_images(full=True):
            pages_of.setdefault(img[0], set()).add(page.number)
    repeated = {x for x, p in pages_of.items() if len(p) > 1}

    found: list[Found] = []
    for page in doc:
        if len(found) >= MAX_FIGURES:
            break
        prect = page.rect
        margin = prect.height * 0.05     # running headers and footers
        images = [i for i in page.get_image_info(xrefs=True)
                  if i.get("xref") not in repeated and pymupdf.Rect(i["bbox"]).is_valid]
        try:
            clusters = page.cluster_drawings(x_tolerance=4, y_tolerance=4)
        except Exception:                # an unusual page should not stop the rest
            clusters = []
        graphics = [pymupdf.Rect(r) & prect for r in clusters]
        graphics = [r for r in graphics
                    if r.y0 > prect.y0 + margin and r.y1 < prect.y1 - margin
                    and not (r.width > 0.85 * prect.width and r.height < 3)   # rules
                    and r.width * r.height > 25]
        graphics += [pymupdf.Rect(i["bbox"]) & prect for i in images]
        text_blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]

        on_page = _caption_figures(page, graphics, text_blocks)
        # Embedded images that no captioned figure contains.
        for i in images:
            r = pymupdf.Rect(i["bbox"]) & prect
            if any(f.rect.contains(r) or (f.rect & r).get_area() > 0.5 * r.get_area() for f in on_page):
                continue
            w, h = i.get("width", 0), i.get("height", 0)
            if w < MIN_PIXELS[0] or h < MIN_PIXELS[1] or r.width < 0.15 * prect.width:
                continue
            if max(r.width / r.height, r.height / r.width) > MAX_ASPECT:
                continue
            on_page.append(Found(page.number, r, "image"))
        on_page.sort(key=lambda f: (_number(f.label), f.rect.y0, f.rect.x0))
        found.extend(on_page)
    return found[:MAX_FIGURES]


def _number(label: str) -> tuple:
    """Sort key for 'Figure 3', 'Figure 1.2', 'Figure S4' (unlabelled figures go last)."""
    m = re.search(r"(S?)(\d+)(?:\.(\d+))?", label)
    return (bool(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else (True, 10**6, 0)


def render(page, rect: pymupdf.Rect) -> Image.Image:
    """The region at (at least) twice its size, on white, as a PIL image."""
    zoom = min(5.0, max(2.0, SIZES["full"] / max(rect.width, 1)))
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _save(img: Image.Image, path: Path, size: str) -> tuple[int, int]:
    w = SIZES[size]
    if img.width > w:
        img = img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
    img.save(path, "WEBP", quality=QUALITY[size], method=4)
    return img.width, img.height


# --------------------------------------------------------------------------- #
# Storing figures
# --------------------------------------------------------------------------- #

def item_dir(item_id: int) -> Path:
    return root() / str(item_id)


def file_path(item_id: int, pdf_hash: str, idx: int, size: str) -> Path:
    return item_dir(item_id) / pdf_hash[:16] / f"{idx}-{size}.webp"


def remove_files(item_id: int) -> None:
    shutil.rmtree(item_dir(item_id), ignore_errors=True)


def extract_item(conn, item_id: int, force: bool = False) -> int | None:
    """Extract (or re-use) the figures of one paper. Returns how many were found, or None
    if there was nothing to do."""
    row = conn.execute("SELECT file_name, file_hash, figures_hash, figures_status FROM items "
                       "WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        return None
    if not row["file_name"]:
        conn.execute("DELETE FROM figures WHERE item_id = ?", (item_id,))
        conn.execute("UPDATE items SET figures_status = NULL, figures_hash = NULL, "
                     "cover_figure_id = NULL WHERE id = ?", (item_id,))
        conn.commit()
        remove_files(item_id)
        return None
    path = storage.abs_path(row["file_name"])
    data = path.read_bytes()
    pdf_hash = row["file_hash"] or hashlib.sha256(data).hexdigest()
    if not force and row["figures_hash"] == pdf_hash and row["figures_status"] in ("done", "none"):
        return None

    out = item_dir(item_id) / pdf_hash[:16]
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for idx, f in enumerate(find_figures(doc)):
            img = render(doc[f.page], f.rect)
            fw, fh = _save(img, out / f"{idx}-full.webp", "full")
            tw, th = _save(img, out / f"{idx}-thumb.webp", "thumb")
            rows.append((item_id, pdf_hash, idx, f.page, f.kind, f.label, f.caption, fw, fh, tw, th))
    conn.execute("DELETE FROM figures WHERE item_id = ?", (item_id,))
    conn.executemany(
        "INSERT INTO figures (item_id, pdf_hash, idx, page, kind, label, caption, width, height, "
        "thumb_width, thumb_height) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    conn.execute("UPDATE items SET figures_hash = ?, figures_status = ?, cover_figure_id = NULL "
                 "WHERE id = ?", (pdf_hash, "done" if rows else "none", item_id))
    conn.commit()
    # Figures of an earlier PDF of the same paper.
    for d in item_dir(item_id).iterdir():
        if d.is_dir() and d.name != pdf_hash[:16]:
            shutil.rmtree(d, ignore_errors=True)
    return len(rows)


def as_dict(r) -> dict:
    v = r["pdf_hash"][:8]
    return {
        "id": r["id"], "index": r["idx"], "page": r["page"] + 1, "kind": r["kind"],
        "label": r["label"] or "", "caption": r["caption"] or "",
        "width": r["width"], "height": r["height"],
        "thumb_width": r["thumb_width"], "thumb_height": r["thumb_height"],
        "thumb": f"/api/figures/{r['id']}/thumb.webp?v={v}",
        "full": f"/api/figures/{r['id']}/full.webp?v={v}",
    }


def list_figures(conn, item_id: int) -> list[dict]:
    return [as_dict(r) for r in conn.execute(
        "SELECT * FROM figures WHERE item_id = ? ORDER BY idx", (item_id,))]


# --------------------------------------------------------------------------- #
# Background extraction
# --------------------------------------------------------------------------- #

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="figures")
_pending: list[Future] = []
_lock = threading.Lock()


def _run(item_id: int, force: bool) -> None:
    conn = db.connect()
    try:
        extract_item(conn, item_id, force=force)
    except Exception:
        log.exception("Could not extract the figures of item %s", item_id)
        conn.execute("UPDATE items SET figures_status = 'error' WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()


def schedule(conn, item_id: int, force: bool = False) -> None:
    """Extract the figures of a paper in the background (after its PDF was added)."""
    conn.execute("UPDATE items SET figures_status = 'pending' WHERE id = ? AND file_name IS NOT NULL",
                 (item_id,))
    conn.commit()
    with _lock:
        _pending[:] = [f for f in _pending if not f.done()]
        _pending.append(_executor.submit(_run, item_id, force))


def wait() -> None:
    """Block until every scheduled extraction has finished (for tests and the CLI)."""
    with _lock:
        pending = list(_pending)
    for f in pending:
        f.result()

