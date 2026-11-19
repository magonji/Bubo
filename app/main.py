"""HTTP API and web interface server for Bubo."""

import hmac
import re
import mimetypes
import time
from urllib.parse import quote
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from . import annotate, bibtex, citation, db, metadata, pdf, storage, textsearch
from .config import settings

STATIC = Path(__file__).parent / "static"

# PDF.js ships as ES modules and WebAssembly; make sure they get the right MIME types.
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")

if not settings.password:
    raise RuntimeError("Set the BUBO_PASSWORD environment variable before starting Bubo.")

app = FastAPI(title="Bubo", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="bubo_session",
    max_age=settings.session_days * 86400,
    same_site="lax",
    https_only=settings.secure_cookies,
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
db.init_db()
# Give readable names to PDFs from older layouts (or left half-way by a crash).
_startup_conn = db.connect()
storage.sync_all(_startup_conn)
# A contact email saved in Settings takes precedence over BUBO_CONTACT_EMAIL.
settings.contact_email = db.get_settings(_startup_conn).get("contact_email") or settings.env_contact_email
_startup_conn.close()

Conn = Annotated[object, Depends(db.get_db)]


def require_auth(request: Request) -> None:
    if not request.session.get("auth"):
        raise HTTPException(401, "Not authenticated")


Auth = Depends(require_auth)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

class Author(BaseModel):
    given: str = ""
    family: str = ""


class ItemIn(BaseModel):
    item_type: str | None = None
    title: str | None = None
    authors: list[Author] | None = None
    year: int | None = None
    venue: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    url: str | None = None
    abstract: str | None = None
    notes: str | None = None
    citekey: str | None = None
    tags: list[str] | None = None
    collections: list[int] | None = None
    to_read: bool | None = None   # on the reading list


class ImportIn(BaseModel):
    identifier: str
    collection_id: int | None = None
    to_read: bool = False   # also put the paper on the reading list


class CollectionIn(BaseModel):
    name: str | None = None
    parent_id: int | None = None


class ItemIds(BaseModel):
    item_ids: list[int]


class ExportIn(BaseModel):
    ids: list[int] | None = None


class LoginIn(BaseModel):
    password: str


CitationStyle = Literal[tuple(citation.STYLES)]


EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class SettingsIn(BaseModel):
    citation_style: CitationStyle | None = None
    # Sent to Unpaywall, Crossref and PubMed; "" clears it (falls back to BUBO_CONTACT_EMAIL).
    contact_email: str | None = Field(None, max_length=254)
    # Whether new papers (uploaded or added by identifier) go on the reading list.
    new_items_to_read: bool | None = None
    # Whether a collection's view also lists the items in its subcollections.
    include_subcollections: bool | None = None


DEFAULT_SETTINGS = {"citation_style": citation.DEFAULT_STYLE, "include_subcollections": False,
                    "new_items_to_read": False, "contact_email": ""}


def _settings(conn) -> dict:
    # "contact_email_env" tells the interface that BUBO_CONTACT_EMAIL provides a default.
    return {**DEFAULT_SETTINGS, **db.get_settings(conn), "contact_email_env": settings.env_contact_email or ""}


Colour = Literal[tuple(annotate.COLOURS)]
Rect = Annotated[list[float], Field(min_length=4, max_length=4)]


class AnnotationIn(BaseModel):
    kind: Literal["highlight", "note"]
    color: Colour = "yellow"
    page: int = Field(ge=0)
    rects: list[Rect] = Field(min_length=1, max_length=1000)
    text: str | None = Field(None, max_length=20000)
    comment: str | None = Field(None, max_length=50000)


class AnnotationPatch(BaseModel):
    color: Colour | None = None
    comment: str | None = Field(None, max_length=50000)


# --------------------------------------------------------------------------- #
# Files
# --------------------------------------------------------------------------- #

def _store_pdf(data: bytes) -> dict:
    return storage.save_new(data, pdf.sha256(data))


def _pdf_path_or_404(conn, item_id: int):
    name, _ = db.get_item_file(conn, item_id)
    path = storage.abs_path(name) if name else None
    if not path or not path.exists():
        raise HTTPException(404, "This item has no PDF")
    return path


def _content_disposition(kind: str, filename: str) -> str:
    ascii_name = filename.encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
    return f"{kind}; filename=\"{ascii_name}\"; filename*=utf-8''{quote(filename)}"


def _item_or_404(conn, item_id: int) -> dict:
    item = db.get_item(conn, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    return item


def _collection_ids(conn, cid: int | None) -> list[int]:
    return [cid] if cid is not None and db.collection_exists(conn, cid) else []


# --------------------------------------------------------------------------- #
# Interface and session
# --------------------------------------------------------------------------- #

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/login")
def login(body: LoginIn, request: Request):
    if not hmac.compare_digest(body.password.encode(), settings.password.encode()):
        time.sleep(1)  # slows down brute-force attempts
        raise HTTPException(401, "Incorrect password")
    request.session["auth"] = True
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me", dependencies=[Auth])
def me():
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #

@app.get("/api/items", dependencies=[Auth])
def list_items(conn: Conn, q: str | None = None, collection: int | None = None,
               tag: str | None = None, unfiled: bool = False, sort: str = "added",
               subcollections: bool = False, to_read: bool = False):
    return db.list_items(conn, q=q, collection_id=collection, tag=tag, unfiled=unfiled, sort=sort,
                         subcollections=subcollections, to_read=to_read)


@app.get("/api/library-counts", dependencies=[Auth])
def library_counts(conn: Conn):
    """Item counts for the fixed entries of the sidebar."""
    return db.library_counts(conn)


@app.get("/api/items/{item_id}", dependencies=[Auth])
def get_item(item_id: int, conn: Conn):
    return _item_or_404(conn, item_id)


@app.post("/api/items", dependencies=[Auth], status_code=201)
def create_item(body: ItemIn, conn: Conn):
    data = body.model_dump(exclude_none=True)
    tags, cols = data.pop("tags", None), data.pop("collections", None)
    data.pop("citekey", None)
    to_read = data.pop("to_read", False)
    item_id = db.create_item(conn, data, tags=tags, collection_ids=cols)
    if to_read:
        db.set_to_read(conn, item_id, True)
        conn.commit()
    return db.get_item(conn, item_id)


@app.patch("/api/items/{item_id}", dependencies=[Auth])
def update_item(item_id: int, body: ItemIn, conn: Conn):
    _item_or_404(conn, item_id)
    changes = body.model_dump(exclude_unset=True)
    try:
        db.update_item(conn, item_id, changes)
    except ValueError as e:
        raise HTTPException(409, str(e))
    storage.sync_item(conn, item_id)
    return db.get_item(conn, item_id)


@app.delete("/api/items/{item_id}", dependencies=[Auth])
def delete_item(item_id: int, conn: Conn):
    _item_or_404(conn, item_id)
    storage.delete(db.delete_item(conn, item_id))
    return {"ok": True}


@app.post("/api/items/upload", dependencies=[Auth])
def upload(conn: Conn, files: list[UploadFile] = File(...),
           collection_id: int | None = Form(None), to_read: bool = Form(False)):
    results = _upload(conn, files, collection_id)
    if to_read:  # new papers, and ones already in the library, go on the reading list
        _put_on_reading_list(conn, [r["id"] for r in results if r.get("id")])
    return {"results": results}


def _put_on_reading_list(conn, item_ids: list[int]) -> None:
    for item_id in item_ids:
        db.set_to_read(conn, item_id, True)
    conn.commit()


def _upload(conn, files: list[UploadFile], collection_id: int | None) -> list[dict]:
    results = []
    for f in files:
        data = f.file.read()
        name = f.filename or "document.pdf"
        if not pdf.is_pdf(data):
            results.append({"filename": name, "status": "error", "message": "Not a PDF"})
            continue
        file_hash = pdf.sha256(data)
        if dup := db.find_duplicate(conn, file_hash=file_hash):
            results.append({"filename": name, "status": "duplicate", "id": dup})
            continue
        info = pdf.analyze(data)
        meta = metadata.identify_pdf(info)
        identified = meta is not None
        meta = meta or metadata.fallback_meta(info, name)
        dup = db.find_duplicate(conn, doi=meta.get("doi"), arxiv_id=meta.get("arxiv_id"))
        if dup:
            existing = db.get_item(conn, dup)
            if not existing["has_file"]:
                db.set_file(conn, dup, _store_pdf(data), info.fulltext)
                storage.sync_item(conn, dup)
                results.append({"filename": name, "status": "attached", "id": dup})
            else:
                results.append({"filename": name, "status": "duplicate", "id": dup})
            continue
        item_id = db.create_item(conn, meta, file=_store_pdf(data), fulltext=info.fulltext,
                                 collection_ids=_collection_ids(conn, collection_id))
        storage.sync_item(conn, item_id)
        results.append({"filename": name, "status": "created", "id": item_id,
                        "identified": identified})
    return results


@app.post("/api/items/import", dependencies=[Auth])
def import_identifier(body: ImportIn, conn: Conn):
    result = _import(body, conn)
    if body.to_read:
        _put_on_reading_list(conn, [result["item"]["id"]])
        result["item"] = db.get_item(conn, result["item"]["id"])
    return result


def _import(body: ImportIn, conn) -> dict:
    try:
        kind, value = metadata.classify(body.identifier)
        dup = db.find_duplicate(conn, doi=value if kind == "doi" else None,
                                arxiv_id=value if kind == "arxiv" else None)
        if dup:
            return {"status": "duplicate", "item": db.get_item(conn, dup)}
        meta, pdf_bytes = metadata.resolve(body.identifier)
    except metadata.MetadataError as e:
        raise HTTPException(422, str(e))
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Error contacting the external service: {e}")
    if dup := db.find_duplicate(conn, doi=meta.get("doi"), arxiv_id=meta.get("arxiv_id")):
        return {"status": "duplicate", "item": db.get_item(conn, dup)}
    file, fulltext = None, ""
    if pdf_bytes:
        file, fulltext = _store_pdf(pdf_bytes), pdf.analyze(pdf_bytes).fulltext
    item_id = db.create_item(conn, meta, file=file, fulltext=fulltext,
                             collection_ids=_collection_ids(conn, body.collection_id))
    storage.sync_item(conn, item_id)
    return {"status": "created", "item": db.get_item(conn, item_id)}


@app.post("/api/items/{item_id}/file", dependencies=[Auth])
def attach_file(item_id: int, conn: Conn, file: UploadFile = File(...)):
    item = _item_or_404(conn, item_id)
    data = file.file.read()
    if not pdf.is_pdf(data):
        raise HTTPException(422, "Not a PDF")
    old, _ = db.get_item_file(conn, item_id)
    db.set_file(conn, item_id, _store_pdf(data), pdf.analyze(data).fulltext)
    storage.delete(old)
    storage.sync_item(conn, item_id)
    return db.get_item(conn, item["id"])


@app.get("/api/items/{item_id}/file", dependencies=[Auth])
def get_file(item_id: int, conn: Conn, download: bool = False):
    path = _pdf_path_or_404(conn, item_id)
    return FileResponse(path, media_type="application/pdf", filename=path.name,
                        content_disposition_type="attachment" if download else "inline")


@app.get("/api/items/{item_id}/annotated.pdf", dependencies=[Auth])
def get_annotated_file(item_id: int, conn: Conn):
    """Download a copy of the PDF with the annotations embedded."""
    path = _pdf_path_or_404(conn, item_id)
    data = annotate.export(path.read_bytes(), db.list_annotations(conn, item_id))
    filename = f"{path.stem} (annotated).pdf"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": _content_disposition("attachment", filename)})


@app.post("/api/items/{item_id}/find-pdf", dependencies=[Auth])
def find_pdf(item_id: int, conn: Conn):
    """Look for a free PDF (arXiv, Unpaywall, publisher page) and attach it if found."""
    item = _item_or_404(conn, item_id)
    if item["has_file"]:
        raise HTTPException(409, "This item already has a PDF")
    if not (item.get("doi") or item.get("arxiv_id")):
        raise HTTPException(422, "Add a DOI or arXiv ID first, so that a PDF can be looked up")
    data = metadata.find_pdf(item)
    if data is None:
        hint = "" if settings.contact_email else (
            " Adding a contact email in Settings enables Unpaywall, which finds many more.")
        raise HTTPException(404, "No open-access PDF found." + hint)
    db.set_file(conn, item_id, _store_pdf(data), pdf.analyze(data).fulltext)
    storage.sync_item(conn, item_id)
    return db.get_item(conn, item_id)


@app.get("/api/overview", dependencies=[Auth])
def overview(conn: Conn):
    """Shown in the item pane when nothing is selected."""
    items = db.list_items(conn, sort="added")
    incomplete = [i for i in items if db.is_incomplete(i)]
    to_read = db.list_items(conn, to_read=True, sort="to_read")
    return {"recent": items[:5], "to_read": to_read[:5], "to_read_total": len(to_read),
            "incomplete": incomplete[:5], "incomplete_total": len(incomplete)}


@app.get("/api/items/{item_id}/text-matches", dependencies=[Auth])
def text_matches(item_id: int, conn: Conn, q: str):
    """Sentences of the item's PDF that contain the search, with their page numbers."""
    path = _pdf_path_or_404(conn, item_id)
    return textsearch.find(path.read_bytes(), q)


@app.get("/api/items/{item_id}/annotations", dependencies=[Auth])
def list_annotations(item_id: int, conn: Conn):
    _item_or_404(conn, item_id)
    return db.list_annotations(conn, item_id)


@app.post("/api/items/{item_id}/annotations", dependencies=[Auth], status_code=201)
def create_annotation(item_id: int, body: AnnotationIn, conn: Conn):
    _item_or_404(conn, item_id)
    return db.get_annotation(conn, db.create_annotation(conn, item_id, body.model_dump()))


@app.patch("/api/annotations/{ann_id}", dependencies=[Auth])
def update_annotation(ann_id: int, body: AnnotationPatch, conn: Conn):
    if db.get_annotation(conn, ann_id) is None:
        raise HTTPException(404, "Annotation not found")
    db.update_annotation(conn, ann_id, body.model_dump(exclude_unset=True, exclude_none=True)
                         | ({"comment": body.comment} if "comment" in body.model_fields_set else {}))
    return db.get_annotation(conn, ann_id)


@app.delete("/api/annotations/{ann_id}", dependencies=[Auth])
def delete_annotation(ann_id: int, conn: Conn):
    db.delete_annotation(conn, ann_id)
    return {"ok": True}


@app.get("/api/items/{item_id}/refresh-preview", dependencies=[Auth])
def refresh_preview(item_id: int, conn: Conn):
    """Re-fetch the metadata (DOI first, then arXiv ID) and list what would change.

    Nothing is saved: the interface lets the user pick fields and applies them with PATCH.
    """
    item = _item_or_404(conn, item_id)
    try:
        if item.get("doi"):
            source, fetched = "Crossref", metadata.fetch_crossref(item["doi"])
        elif item.get("arxiv_id"):
            source, fetched = "arXiv", metadata.fetch_arxiv(item["arxiv_id"])
        else:
            raise HTTPException(422, "The item has neither a DOI nor an arXiv ID")
    except metadata.MetadataError as e:
        raise HTTPException(422, str(e))
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Error contacting the external service: {e}")
    return {"source": source, "changes": metadata.diff(item, fetched)}


@app.get("/api/items/{item_id}/bibtex", dependencies=[Auth], response_class=PlainTextResponse)
def item_bibtex(item_id: int, conn: Conn):
    return bibtex.entry(_item_or_404(conn, item_id))


@app.get("/api/items/{item_id}/citation", dependencies=[Auth])
def item_citation(item_id: int, conn: Conn, style: CitationStyle | None = None):
    """The item's reference in the given style (default: the one chosen in Settings)."""
    item = _item_or_404(conn, item_id)
    style = style or _settings(conn)["citation_style"]
    if style not in citation.STYLES:
        style = citation.DEFAULT_STYLE
    return {"style": style, "name": citation.STYLES[style], **citation.format(item, style)}


@app.get("/api/citation-styles", dependencies=[Auth])
def citation_styles():
    return [{"id": sid, "name": name, "example": citation.format(citation.EXAMPLE, sid)}
            for sid, name in citation.STYLES.items()]


@app.get("/api/settings", dependencies=[Auth])
def get_settings(conn: Conn):
    return _settings(conn)


@app.patch("/api/settings", dependencies=[Auth])
def update_settings(body: SettingsIn, conn: Conn):
    values = body.model_dump(exclude_none=True)
    if "contact_email" in values:
        email = values["contact_email"].strip()
        if email and not EMAIL_RE.fullmatch(email):
            raise HTTPException(422, "That does not look like an email address")
        values["contact_email"] = email
        settings.contact_email = email or settings.env_contact_email
    db.set_settings(conn, values)
    return _settings(conn)


@app.post("/api/export/bibtex", dependencies=[Auth])
def export_bibtex(body: ExportIn, conn: Conn):
    items = db.list_items(conn, ids=body.ids, sort="authors")
    return Response(bibtex.export(items), media_type="application/x-bibtex; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="bubo.bib"'})


# --------------------------------------------------------------------------- #
# Collections and tags
# --------------------------------------------------------------------------- #

@app.get("/api/collections", dependencies=[Auth])
def list_collections(conn: Conn):
    return db.list_collections(conn)


@app.post("/api/collections", dependencies=[Auth], status_code=201)
def create_collection(body: CollectionIn, conn: Conn):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(422, "The name cannot be empty")
    if body.parent_id is not None and not db.collection_exists(conn, body.parent_id):
        raise HTTPException(404, "Parent collection not found")
    return {"id": db.create_collection(conn, name, body.parent_id)}


@app.patch("/api/collections/{cid}", dependencies=[Auth])
def update_collection(cid: int, body: CollectionIn, conn: Conn):
    if not db.collection_exists(conn, cid):
        raise HTTPException(404, "Collection not found")
    fields = body.model_fields_set
    name = body.name.strip() if body.name else None
    if "name" in fields and not name:
        raise HTTPException(422, "The name cannot be empty")
    if "parent_id" in fields and body.parent_id is not None \
            and not db.collection_exists(conn, body.parent_id):
        raise HTTPException(404, "Parent collection not found")
    try:
        db.update_collection(conn, cid, name, body.parent_id, "parent_id" in fields)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.delete("/api/collections/{cid}", dependencies=[Auth])
def delete_collection(cid: int, conn: Conn):
    db.delete_collection(conn, cid)
    return {"ok": True}


@app.post("/api/collections/{cid}/items", dependencies=[Auth])
def add_to_collection(cid: int, body: ItemIds, conn: Conn):
    if not db.collection_exists(conn, cid):
        raise HTTPException(404, "Collection not found")
    db.add_to_collection(conn, cid, body.item_ids)
    return {"ok": True}


@app.delete("/api/collections/{cid}/items/{item_id}", dependencies=[Auth])
def remove_from_collection(cid: int, item_id: int, conn: Conn):
    db.remove_from_collection(conn, cid, item_id)
    return {"ok": True}


@app.get("/api/tags", dependencies=[Auth])
def list_tags(conn: Conn):
    return db.list_tags(conn)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}

