"""Human-readable PDF storage.

All PDFs are kept together in ``<data>/papers``, named after their metadata::

    papers/
    ├── LeCun et al. - 2015 - Deep learning.pdf
    └── Vaswani et al. - 2017 - Attention Is All You Need.pdf

Collections exist only inside Bubo; they do not affect where files live. Files are
renamed automatically when a paper's authors, year or title change, so the folder should
be treated as read-only.

Names are kept valid on exFAT/NTFS/FAT32 (no ``\\ / : * ? " < > |``, no trailing dots or
spaces, no reserved Windows names) and are compared case-insensitively.
"""

import json
import logging
import os
import re
import threading
import unicodedata
import uuid
from pathlib import Path

from .config import settings

log = logging.getLogger("bubo.storage")

STAGING = ".incoming"
JUNK = {".DS_Store", "Thumbs.db", "desktop.ini"}
# PDFs stored before readable names were introduced: <data>/files/<uuid>.pdf
LEGACY_RE = re.compile(r"[0-9a-f]{32}\.pdf")

# Renames are not atomic with respect to the database, so serialise them.
lock = threading.RLock()

_INVALID = re.compile(r'[\\/*?"<>|\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}


def root() -> Path:
    return settings.papers_dir


def abs_path(rel: str) -> Path:
    """Absolute path of a stored `file_name` (relative to the papers folder)."""
    if LEGACY_RE.fullmatch(rel):
        return settings.legacy_files_dir / rel
    return root() / rel


def is_in_place(rel: str | None) -> bool:
    """True once the file has its readable name (not staged or in the legacy folder)."""
    return bool(rel) and not rel.startswith(f"{STAGING}/") and not LEGACY_RE.fullmatch(rel)


def clean_component(name: str, max_len: int, fallback: str) -> str:
    name = unicodedata.normalize("NFC", name or "")
    name = name.replace(":", " -")
    name = _INVALID.sub(" ", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if len(name) > max_len:
        cut = name[:max_len]
        name = (cut.rsplit(" ", 1)[0] if " " in cut[max_len // 2:] else cut).strip(" .")
    if not name:
        name = fallback
    if name.split(".")[0].lower() in _RESERVED:
        name = "_" + name
    return name


def base_name(title: str, authors: list[dict], year: int | None) -> str:
    """'Vaswani et al. - 2017 - Attention Is All You Need' (Zotero-style)."""
    def family(a):
        return (a.get("family") or a.get("given") or "").strip()
    names = [family(a) for a in authors if family(a)]
    if len(names) > 2:
        lead = f"{names[0]} et al."
    elif len(names) == 2:
        lead = f"{names[0]} and {names[1]}"
    else:
        lead = names[0] if names else ""
    # "et al." keeps its full stop: only the ends of the whole name are trimmed.
    lead = re.sub(r"\s+", " ", _INVALID.sub(" ", lead.replace(":", " -"))).strip()[:60]
    parts = [lead, str(year) if year else "", clean_component(title, 120, "")]
    return clean_component(" - ".join(p for p in parts if p), 190, "Untitled")


def _unique(conn, base: str, item_id: int, current: str | None) -> str:
    taken = {r[0].lower() for r in conn.execute(
        "SELECT file_name FROM items WHERE id != ? AND file_name IS NOT NULL", (item_id,))}
    candidate, n = f"{base}.pdf", 2
    while True:
        same_file = current is not None and candidate.lower() == current.lower()
        if candidate.lower() not in taken and (same_file or not (root() / candidate).exists()):
            return candidate
        candidate, n = f"{base} ({n}).pdf", n + 1


def _prune(directory: Path) -> None:
    """Remove folders inside papers/ left empty by a move (ignoring OS clutter files)."""
    top = root().resolve()
    d = directory
    while True:
        try:
            d_res = d.resolve()
        except OSError:
            return
        if d_res == top or top not in d_res.parents:
            return
        try:
            entries = list(d.iterdir())
        except OSError:
            return
        if any(e.name not in JUNK and not e.name.startswith("._") for e in entries):
            return
        for e in entries:
            e.unlink(missing_ok=True)
        try:
            d.rmdir()
        except OSError:
            return
        d = d.parent


def save_new(data: bytes, sha256: str) -> dict:
    """Write an uploaded PDF to the staging area; `sync_item` then gives it its name."""
    staging = root() / STAGING
    staging.mkdir(parents=True, exist_ok=True)
    rel = f"{STAGING}/{uuid.uuid4().hex}.pdf"
    (root() / rel).write_bytes(data)
    return {"name": rel, "size": len(data), "hash": sha256}


def delete(rel: str | None) -> None:
    if not rel:
        return
    with lock:
        path = abs_path(rel)
        path.unlink(missing_ok=True)
        _prune(path.parent)


def sync_item(conn, item_id: int) -> None:
    """Rename the item's PDF to match its metadata. Commits the change."""
    with lock:
        row = conn.execute("SELECT file_name, title, authors, year FROM items WHERE id = ?",
                           (item_id,)).fetchone()
        if row is None or not row["file_name"]:
            return
        current = row["file_name"]
        src = abs_path(current)
        if not src.exists():
            log.warning("PDF for item %s is missing: %s", item_id, src)
            return
        base = base_name(row["title"], json.loads(row["authors"] or "[]"), row["year"])
        target = _unique(conn, base, item_id, current)
        if target == current:
            return
        dst = root() / target
        os.replace(src, dst)
        try:
            conn.execute("UPDATE items SET file_name = ? WHERE id = ?", (target, item_id))
            conn.commit()
        except Exception:
            os.replace(dst, src)
            raise
        _prune(src.parent)


def sync_all(conn) -> None:
    """Give every PDF its expected name and place (run at start-up).

    This also migrates older layouts: <data>/files/<uuid>.pdf and the short-lived
    per-collection subfolders of papers/.
    """
    with lock:
        for (item_id,) in conn.execute(
                "SELECT id FROM items WHERE file_name IS NOT NULL").fetchall():
            sync_item(conn, item_id)
        legacy = settings.legacy_files_dir
        if legacy.is_dir() and not any(legacy.iterdir()):
            legacy.rmdir()
