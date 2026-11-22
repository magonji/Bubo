"""SQLite access: schema, items, collections, tags and FTS5 search."""

import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone

from . import storage
from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY,
    item_type    TEXT NOT NULL DEFAULT 'article',
    title        TEXT NOT NULL DEFAULT '',
    authors      TEXT NOT NULL DEFAULT '[]',   -- JSON: [{"given": .., "family": ..}]
    year         INTEGER,
    venue        TEXT,
    volume       TEXT,
    issue        TEXT,
    pages        TEXT,
    publisher    TEXT,
    doi          TEXT,
    arxiv_id     TEXT,
    url          TEXT,
    abstract     TEXT,
    citekey      TEXT UNIQUE,
    notes        TEXT,
    file_name    TEXT,
    file_size    INTEGER,
    file_hash    TEXT,
    added_at     TEXT NOT NULL,
    modified_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_doi ON items(lower(doi));
CREATE INDEX IF NOT EXISTS idx_items_arxiv ON items(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_items_hash ON items(file_hash);

CREATE TABLE IF NOT EXISTS collections (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    parent_id INTEGER REFERENCES collections(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS item_collections (
    item_id       INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, collection_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS item_tags (
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, tag_id)
);

CREATE TABLE IF NOT EXISTS annotations (
    id          INTEGER PRIMARY KEY,
    item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,              -- 'highlight' | 'note'
    color       TEXT NOT NULL,
    page        INTEGER NOT NULL,           -- zero-based page index
    rects       TEXT NOT NULL,              -- JSON [[x1, y1, x2, y2], ...] in PDF user space
    text        TEXT,                       -- highlighted text
    comment     TEXT,
    created_at  TEXT NOT NULL,
    modified_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_annotations_item ON annotations(item_id, page);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL      -- JSON
);

-- Supplementary information: any number of files per paper (PDFs, spreadsheets, ...).
CREATE TABLE IF NOT EXISTS supplementary (
    id            INTEGER PRIMARY KEY,
    item_id       INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    file_name     TEXT NOT NULL,            -- inside the papers folder, like items.file_name
    original_name TEXT NOT NULL,            -- the name it was uploaded with
    file_size     INTEGER,
    file_hash     TEXT,
    fulltext      TEXT,                     -- text of a PDF, for search
    added_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_supplementary_item ON supplementary(item_id);

-- Figures extracted from the PDF (see figures.py); the image files live in <data>/figures.
CREATE TABLE IF NOT EXISTS figures (
    id           INTEGER PRIMARY KEY,
    item_id      INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    pdf_hash     TEXT NOT NULL,             -- the PDF they were extracted from
    idx          INTEGER NOT NULL,          -- order in the paper
    page         INTEGER NOT NULL,          -- zero-based
    kind         TEXT NOT NULL,             -- 'caption' | 'image'
    label        TEXT,                      -- 'Figure 3'
    caption      TEXT,
    width        INTEGER, height INTEGER,   -- of the large image
    thumb_width  INTEGER, thumb_height INTEGER
);
CREATE INDEX IF NOT EXISTS idx_figures_item ON figures(item_id, idx);

-- Scientists followed by their ORCID iD (people.py) and their publications.
-- Every author in the library (authors.py), and whether you follow them (people.py).
CREATE TABLE IF NOT EXISTS people (
    id           INTEGER PRIMARY KEY,
    orcid        TEXT UNIQUE,               -- 0000-0002-1825-0097, when known
    name         TEXT NOT NULL,
    family_name  TEXT,                      -- to check OpenAlex's attributions
    name_key     TEXT,                      -- 'garcia|m': tells apart people without an iD
    followed     INTEGER NOT NULL DEFAULT 0,
    affiliation  TEXT,
    added_at     TEXT NOT NULL,
    last_checked TEXT,
    last_error   TEXT
);
CREATE TABLE IF NOT EXISTS item_authors (
    item_id   INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    pos       INTEGER NOT NULL,             -- position in the paper's author list
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, pos)
);
CREATE INDEX IF NOT EXISTS idx_item_authors_person ON item_authors(person_id);
-- Names merged into a person by hand (authors.merge): papers by them are that person's.
CREATE TABLE IF NOT EXISTS person_aliases (
    name_key  TEXT PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS person_works (
    id           INTEGER PRIMARY KEY,
    person_id    INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    work_key     TEXT NOT NULL,             -- 'doi:10.…', or an ORCID/OpenAlex id without a DOI
    doi          TEXT,                      -- lower case
    title        TEXT NOT NULL,
    authors      TEXT NOT NULL DEFAULT '[]',
    venue        TEXT,
    pub_date     TEXT,                      -- '2024', '2024-05' or '2024-05-17'
    type         TEXT,
    url          TEXT,
    first_seen   TEXT NOT NULL,
    is_new       INTEGER NOT NULL DEFAULT 0, -- on the radar
    seen_at      TEXT,                      -- looked at on the radar
    dismissed_at TEXT,                      -- taken off the radar
    item_id      INTEGER,                   -- added to the library (works without a DOI)
    UNIQUE (person_id, work_key)
);
CREATE INDEX IF NOT EXISTS idx_person_works_new ON person_works(is_new, dismissed_at);

-- Journals' profiles from OpenAlex, by lower-cased name (journals.py).
CREATE TABLE IF NOT EXISTS journals (
    key        TEXT PRIMARY KEY,
    data       TEXT NOT NULL,      -- JSON
    checked_at TEXT NOT NULL
);
"""

FTS_SCHEMA = """CREATE VIRTUAL TABLE IF NOT EXISTS {name} USING fts5(
    title, authors, abstract, venue, extra, fulltext, supplementary,
    tokenize = 'unicode61 remove_diacritics 2'
)"""

META_FIELDS = [
    "item_type", "title", "authors", "year", "venue", "venue_short", "volume", "issue",
    "pages", "publisher", "doi", "arxiv_id", "url", "abstract", "notes",
]
ITEM_TYPES = [
    "article", "inproceedings", "preprint", "book", "incollection",
    "phdthesis", "mastersthesis", "techreport", "misc",
]
SORTS = {
    "added": "i.added_at DESC, i.id DESC",
    "added_asc": "i.added_at ASC, i.id ASC",
    # Publication year, the default order: newest papers first, then the most recently added.
    "year": "i.year DESC NULLS LAST, i.added_at DESC, i.id DESC",
    "year_asc": "i.year ASC NULLS LAST, i.added_at ASC, i.id ASC",
    "title": "lower(i.title) ASC",
    "title_desc": "lower(i.title) DESC",
    "authors": "lower(json_extract(i.authors, '$[0].family')) ASC NULLS LAST",
    "authors_desc": "lower(json_extract(i.authors, '$[0].family')) DESC NULLS LAST",
    "venue": "lower(i.venue) ASC NULLS LAST",
    "venue_desc": "lower(i.venue) DESC NULLS LAST",
    # Reading list: the order in which papers were put on it.
    "to_read": "i.to_read_at ASC, i.id ASC",
    "to_read_desc": "i.to_read_at DESC, i.id DESC",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = connect()
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    conn.execute(FTS_SCHEMA.format(name="items_fts"))
    fts_columns = {r["name"] for r in conn.execute("PRAGMA table_info(items_fts)")}
    # Whether a figure is a photograph that may fill its tile (figures.analyse; NULL: not looked at).
    if "fill" not in {r["name"] for r in conn.execute("PRAGMA table_info(figures)")}:
        conn.execute("ALTER TABLE figures ADD COLUMN fill INTEGER")
    # Profiles of followed people (people.py), added after the table itself.
    people_columns = {r["name"] for r in conn.execute("PRAGMA table_info(people)")}
    for column in ["family_name", "name_key", "followed INTEGER NOT NULL DEFAULT 0", "country", "role", "openalex_id", "works_count INTEGER", "cited_by INTEGER",
                   "h_index INTEGER", "topics", "wikidata_id", "description", "wikipedia", "photo",
                   "photo_source", "photo_credit", "profile_checked", "photo_looked", "name_fixed INTEGER"]:
        name, _, kind = column.partition(" ")
        if name not in people_columns:
            conn.execute(f"ALTER TABLE people ADD COLUMN {name} {kind or 'TEXT'}")
    if "supplementary" not in fts_columns:
        # Libraries created before supplementary files: rebuild the index with the new column.
        conn.execute(FTS_SCHEMA.format(name="items_fts_new"))
        conn.execute(
            "INSERT INTO items_fts_new (rowid, title, authors, abstract, venue, extra, fulltext, "
            "supplementary) SELECT rowid, title, authors, abstract, venue, extra, fulltext, '' "
            "FROM items_fts")
        conn.execute("DROP TABLE items_fts")
        conn.execute("ALTER TABLE items_fts_new RENAME TO items_fts")
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(items)")}
    for column, kind in [
        ("to_read_at", "TEXT"),           # when it was put on the reading list (NULL: not on it)
        ("venue_short", "TEXT"),          # abbreviated journal name, e.g. "Nat. Commun."
        ("figures_status", "TEXT"),       # NULL | pending | done | none | error
        ("figures_hash", "TEXT"),         # hash of the PDF the figures come from
        ("cover_figure_id", "INTEGER"),   # chosen thumbnail (NULL: the first figure)
        ("figures_version", "INTEGER"),   # figures.VERSION that produced them
        ("authors_checked", "TEXT"),      # when authors' ORCID iDs were looked for (authors.py)
        ("authors_openalex", "TEXT"),     # when authors' OpenAlex ids were looked for (authors.py)
        ("deleted_at", "TEXT"),           # in the trash since (NULL: in the library)
    ]:
        if column not in columns:
            conn.execute(f"ALTER TABLE items ADD COLUMN {column} {kind}")
    conn.commit()
    _unescape_stored(conn)
    _people_for_all_authors(conn)
    conn.close()


def _people_for_all_authors(conn) -> None:
    """Libraries from before every author was a person: people were only those followed, and
    their ORCID iD was required. Rebuild the table with the iD optional, then link every
    paper's authors (the background thread then looks for their iDs)."""
    from . import authors
    notnull = {r["name"]: r["notnull"] for r in conn.execute("PRAGMA table_info(people)")}
    if notnull.get("orcid"):
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(people)")]
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")
        # SQLite's way: a new table, the rows copied, the old one dropped and the new renamed
        # (so person_works keeps pointing at "people").
        ddl = re.search(r"CREATE TABLE IF NOT EXISTS people \(.*?\n\);", SCHEMA, re.S).group(0)
        conn.execute(ddl.replace("EXISTS people (", "EXISTS people_new (", 1))
        new_cols = {r["name"] for r in conn.execute("PRAGMA table_info(people_new)")}
        for c in cols:
            if c not in new_cols:
                conn.execute(f"ALTER TABLE people_new ADD COLUMN {c}")
        listed = ", ".join(cols)
        conn.execute(f"INSERT INTO people_new ({listed}) SELECT {listed} FROM people")
        conn.execute("UPDATE people_new SET followed = 1")      # everyone there was followed
        conn.execute("DROP TABLE people")
        conn.execute("ALTER TABLE people_new RENAME TO people")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_people_key ON people(name_key)")
    for r in conn.execute("SELECT id, name, family_name FROM people WHERE name_key IS NULL").fetchall():
        given = r["name"][: -len(r["family_name"])].strip() if r["family_name"] and r["name"].endswith(r["family_name"]) else r["name"].rsplit(" ", 1)[0]
        conn.execute("UPDATE people SET name_key = ? WHERE id = ?",
                     (authors.name_key(given, r["family_name"] or r["name"].split()[-1]), r["id"]))
    if conn.execute("SELECT 1 FROM items LIMIT 1").fetchone() and not conn.execute("SELECT 1 FROM item_authors LIMIT 1").fetchone():
        authors.link_all(conn)
    # Profiles taken from the wrong one of several OpenAlex profiles with the same ORCID iD
    # (before the choice by the person's papers): look at everyone's again, once.
    if conn.execute("SELECT 1 FROM settings WHERE key = '_profiles_chosen_by_papers'").fetchone() is None:
        conn.execute("UPDATE people SET profile_checked = NULL WHERE orcid IS NOT NULL")
        conn.execute("INSERT INTO settings (key, value) VALUES ('_profiles_chosen_by_papers', 'true')")
    conn.commit()


def get_db():
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #

def authors_to_text(authors: list[dict]) -> str:
    return "; ".join(
        " ".join(p for p in (a.get("given"), a.get("family")) if p) for a in authors
    )


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


STOPWORDS = {"a", "an", "the", "on", "of", "in", "for", "to", "and", "with"}


def make_citekey(conn: sqlite3.Connection, item: dict, exclude_id: int | None = None) -> str:
    authors = item.get("authors") or []
    family = authors[0].get("family", "") if authors else ""
    base = re.sub(r"[^a-z]", "", _ascii(family).lower()) or "anon"
    base += str(item.get("year") or "")
    words = [w for w in re.findall(r"[a-z0-9]+", _ascii(item.get("title") or "").lower())
             if w not in STOPWORDS]
    if words:
        base += words[0]
    key, n = base, 0
    while True:
        row = conn.execute("SELECT id FROM items WHERE citekey = ?", (key,)).fetchone()
        if row is None or row["id"] == exclude_id:
            return key
        key = base + chr(ord("a") + n) if n < 26 else f"{base}{n}"
        n += 1


def fts_query(q: str) -> str | None:
    tokens = re.findall(r"\w+", q, re.UNICODE)
    if not tokens:
        return None
    return " ".join(f'"{t}"*' for t in tokens)


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #

def _row_to_item(row: sqlite3.Row, tags: list[str], collections: list[int],
                 supplementary: list[dict], figures: list) -> dict:
    item = dict(row)
    item["annotation_count"] = item.pop("annotation_count", 0) or 0
    item["to_read"] = bool(item.get("to_read_at"))
    item["authors"] = json.loads(item["authors"] or "[]")
    file_name = item.pop("file_name")
    item["has_file"] = bool(file_name)
    # Name inside the papers folder, once the file has been given its readable name.
    item["file_path"] = file_name if storage.is_in_place(file_name) else None
    item.pop("primary_collection_id", None)  # left over from the per-collection folder layout
    item.pop("file_hash", None)
    item["tags"] = sorted(tags, key=str.lower)
    item["collections"] = collections
    item["supplementary"] = supplementary
    # The thumbnail: the figure chosen as cover, otherwise the first one.
    item.pop("figures_hash", None)
    item.pop("figures_version", None)
    cover = next((f for f in figures if f["id"] == item["cover_figure_id"]), figures[0] if figures else None)
    item["figure_count"] = len(figures)
    item["cover"] = cover and {
        "id": cover["id"], "width": cover["thumb_width"], "height": cover["thumb_height"], "fill": bool(cover["fill"]),
        "url": f"/api/figures/{cover['id']}/thumb.webp?v={cover['pdf_hash'][:8]}",
    }
    return item


def _relations(conn, ids: list[int]) -> tuple[dict, dict, dict, dict]:
    tags: dict[int, list[str]] = {i: [] for i in ids}
    cols: dict[int, list[int]] = {i: [] for i in ids}
    supp: dict[int, list[dict]] = {i: [] for i in ids}
    figs: dict[int, list] = {i: [] for i in ids}
    if not ids:
        return tags, cols, supp, figs
    marks = ",".join("?" * len(ids))
    for r in conn.execute(
        f"SELECT it.item_id, t.name FROM item_tags it JOIN tags t ON t.id = it.tag_id "
        f"WHERE it.item_id IN ({marks})", ids):
        tags[r[0]].append(r[1])
    for r in conn.execute(
        f"SELECT item_id, collection_id FROM item_collections WHERE item_id IN ({marks}) "
        f"ORDER BY rowid", ids):
        cols[r[0]].append(r[1])
    for r in conn.execute(
        f"SELECT id, item_id, file_name, original_name, file_size, added_at FROM supplementary "
        f"WHERE item_id IN ({marks}) ORDER BY id", ids):
        supp[r["item_id"]].append({
            "id": r["id"], "name": r["original_name"], "size": r["file_size"],
            "added_at": r["added_at"],
            "file_path": r["file_name"] if storage.is_in_place(r["file_name"]) else None,
        })
    for r in conn.execute(
        f"SELECT id, item_id, pdf_hash, thumb_width, thumb_height, fill FROM figures "
        f"WHERE item_id IN ({marks}) ORDER BY idx", ids):
        figs[r["item_id"]].append(r)
    return tags, cols, supp, figs


_ANN_COUNT = "(SELECT COUNT(*) FROM annotations a WHERE a.item_id = i.id) AS annotation_count"


def get_item(conn, item_id: int) -> dict | None:
    row = conn.execute(f"SELECT i.*, {_ANN_COUNT} FROM items i WHERE i.id = ?",
                       (item_id,)).fetchone()
    if row is None:
        return None
    tags, cols, supp, figs = _relations(conn, [item_id])
    return _row_to_item(row, tags[item_id], cols[item_id], supp[item_id], figs[item_id])


def get_item_file(conn, item_id: int) -> tuple[str | None, str | None]:
    row = conn.execute("SELECT file_name, citekey FROM items WHERE id = ?", (item_id,)).fetchone()
    return (row["file_name"], row["citekey"]) if row else (None, None)


# A venue's name lower-cased, trimmed and with runs of spaces collapsed (as journals.key does).
def venue_key_sql(col: str = "venue") -> str:
    return (f"lower(trim(replace(replace(replace(replace({col}, char(10), ' '), char(9), ' '), "
            "'   ', ' '), '  ', ' ')))")


def list_items(conn, q: str | None = None, collection_id: int | None = None,
               tag: str | None = None, unfiled: bool = False, sort: str = "year",
               ids: list[int] | None = None, subcollections: bool = False,
               to_read: bool = False, venue: str | None = None, trash: bool = False) -> list[dict]:
    # Papers in the trash are listed only in the trash.
    where, params = [f"i.deleted_at IS {'NOT ' if trash else ''}NULL"], []
    if venue:
        # A journal: the same name, regardless of case and spacing (see journals.key).
        where.append(f"{venue_key_sql('i.venue')} = ?")
        params.append(" ".join(venue.lower().split()))
    if q:
        fq = fts_query(q)
        if fq:
            where.append("i.id IN (SELECT rowid FROM items_fts WHERE items_fts MATCH ?)")
            params.append(fq)
    if collection_id is not None and subcollections:
        # The collection and all its descendants, at any depth.
        where.append("i.id IN (WITH RECURSIVE sub(id) AS (SELECT ? UNION "
                     "SELECT c.id FROM collections c JOIN sub ON c.parent_id = sub.id) "
                     "SELECT item_id FROM item_collections WHERE collection_id IN sub)")
        params.append(collection_id)
    elif collection_id is not None:
        where.append("i.id IN (SELECT item_id FROM item_collections WHERE collection_id = ?)")
        params.append(collection_id)
    if unfiled:
        where.append("i.id NOT IN (SELECT item_id FROM item_collections)")
    if to_read:
        where.append("i.to_read_at IS NOT NULL")
    if tag:
        where.append("i.id IN (SELECT it.item_id FROM item_tags it JOIN tags t "
                     "ON t.id = it.tag_id WHERE t.name = ? COLLATE NOCASE)")
        params.append(tag)
    if ids is not None:
        if not ids:
            return []
        where.append(f"i.id IN ({','.join('?' * len(ids))})")
        params.extend(ids)
    sql = f"SELECT i.*, {_ANN_COUNT} FROM items i"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY " + ("i.deleted_at DESC" if trash else SORTS.get(sort, SORTS["year"]))
    rows = conn.execute(sql, params).fetchall()
    tags, cols, supp, figs = _relations(conn, [r["id"] for r in rows])
    items = [_row_to_item(r, tags[r["id"]], cols[r["id"]], supp[r["id"]], figs[r["id"]])
             for r in rows]
    fq = fts_query(q) if q else None
    if fq and items:
        matches = search_snippets(conn, fq)
        for item in items:
            item["match"] = matches.get(item["id"])
    return items


HL_START, HL_END = "\x02", "\x03"   # highlight markers in snippets (rendered as <mark>)

# Columns of items_fts that get a snippet, in order of preference. Matches in the title
# or authors are already visible in the list, so they need none.
_SNIPPET_COLUMNS = [(5, "fulltext", 32), (2, "abstract", 32), (4, "notes", 24),
                    (6, "supplementary", 32)]


def clean_snippet(text: str) -> str:
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)   # words hyphenated across lines
    return re.sub(r"\s+", " ", text).strip()


def search_snippets(conn, fts: str) -> dict[int, dict]:
    """For each matching item, a short highlighted excerpt and the field it comes from."""
    cols = ", ".join(f"snippet(items_fts, {c}, '{HL_START}', '{HL_END}', '…', {n})"
                     for c, _, n in _SNIPPET_COLUMNS)
    out = {}
    marked = re.compile(f"{HL_START}(.*?){HL_END}", re.S)
    for row in conn.execute(f"SELECT rowid, {cols} FROM items_fts WHERE items_fts MATCH ?", (fts,)):
        best, best_terms = None, 0
        # Prefer the field whose excerpt contains the most distinct search terms; ties go to
        # the earlier field in _SNIPPET_COLUMNS.
        for (_, field, _), snippet in zip(_SNIPPET_COLUMNS, row[1:]):
            terms = len({m.lower() for m in marked.findall(snippet or "")})
            if terms > best_terms:
                best, best_terms = {"field": field, "snippet": clean_snippet(snippet)}, terms
        if best:
            out[row[0]] = best
    return out


def find_duplicate(conn, doi: str | None = None, arxiv_id: str | None = None,
                   file_hash: str | None = None) -> int | None:
    """The paper already in the library with this PDF, DOI or arXiv ID. Adding a paper that
    is in the trash takes it out of the trash."""
    found = _find_duplicate(conn, doi, arxiv_id, file_hash)
    if found and conn.execute("SELECT deleted_at FROM items WHERE id = ?", (found,)).fetchone()["deleted_at"]:
        restore_item(conn, found)
    return found


def _find_duplicate(conn, doi: str | None, arxiv_id: str | None, file_hash: str | None) -> int | None:
    if file_hash:
        r = conn.execute("SELECT id FROM items WHERE file_hash = ?", (file_hash,)).fetchone()
        if r:
            return r["id"]
    if doi:
        r = conn.execute("SELECT id FROM items WHERE lower(doi) = lower(?)", (doi,)).fetchone()
        if r:
            return r["id"]
    if arxiv_id:
        base = re.sub(r"v\d+$", "", arxiv_id)
        r = conn.execute("SELECT id FROM items WHERE arxiv_id = ? OR arxiv_id LIKE ?",
                         (base, base + "v%")).fetchone()
        if r:
            return r["id"]
    return None


def _clean(meta: dict) -> dict:
    out = {}
    for k in META_FIELDS:
        if k not in meta:
            continue
        v = meta[k]
        if k == "authors":
            v = json.dumps([{"given": (a.get("given") or "").strip(),
                             "family": (a.get("family") or "").strip(),
                             **({"orcid": a["orcid"]} if a.get("orcid") else {}),
                             **({"openalex": a["openalex"]} if a.get("openalex") else {})}
                            for a in (v or []) if a.get("given") or a.get("family")],
                           ensure_ascii=False)
        elif k == "year":
            try:
                v = int(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                v = None
        elif k == "item_type":
            v = v if v in ITEM_TYPES else "misc"
        elif isinstance(v, str):
            v = v.strip() or None
            if k == "title":
                v = v or ""
        out[k] = v
    return out


def create_item(conn, meta: dict, file: dict | None = None, fulltext: str | None = None,
                tags: list[str] | None = None, collection_ids: list[int] | None = None) -> int:
    data = _clean(meta)
    data.setdefault("title", "")
    data.setdefault("item_type", "article")
    ts = now()
    data["added_at"] = data["modified_at"] = ts
    if file:
        data.update(file_name=file["name"], file_size=file["size"], file_hash=file["hash"])
    data["citekey"] = make_citekey(conn, {**meta, "authors": meta.get("authors") or []})
    cols = ", ".join(data)
    cur = conn.execute(f"INSERT INTO items ({cols}) VALUES ({','.join('?' * len(data))})",
                       list(data.values()))
    item_id = cur.lastrowid
    if tags:
        set_tags(conn, item_id, tags, do_reindex=False)
    if collection_ids:
        set_collections(conn, item_id, collection_ids)
    reindex(conn, item_id, fulltext=fulltext or "")
    from . import authors
    authors.link_item(conn, item_id)
    conn.commit()
    authors.kick()
    return item_id


def update_item(conn, item_id: int, changes: dict) -> None:
    from . import authors
    if changes.get("authors") is not None:
        old = conn.execute("SELECT authors FROM items WHERE id = ?", (item_id,)).fetchone()
        changes = {**changes, "authors": authors.keep_orcids(json.loads(old["authors"] or "[]") if old else [],
                                                            [dict(a) for a in changes["authors"]])}
    data = _clean(changes)
    if "authors" in data or "doi" in data:
        data["authors_checked"] = None      # look for the authors' iDs again
    if "citekey" in changes:
        key = re.sub(r"[^\w:\-.]", "", changes.get("citekey") or "")
        if key:
            clash = conn.execute("SELECT id FROM items WHERE citekey = ? AND id != ?",
                                 (key, item_id)).fetchone()
            if clash:
                raise ValueError(f"The citation key '{key}' already exists")
            data["citekey"] = key
    if data:
        data["modified_at"] = now()
        sets = ", ".join(f"{k} = ?" for k in data)
        conn.execute(f"UPDATE items SET {sets} WHERE id = ?", [*data.values(), item_id])
    if "tags" in changes:
        set_tags(conn, item_id, changes["tags"] or [], do_reindex=False)
    if "collections" in changes:
        set_collections(conn, item_id, changes["collections"] or [])
    if "to_read" in changes:
        set_to_read(conn, item_id, bool(changes["to_read"]))
    reindex(conn, item_id)
    if "authors" in data:
        authors.link_item(conn, item_id)
    conn.commit()
    if "authors_checked" in data:
        authors.kick()


def set_file(conn, item_id: int, file: dict, fulltext: str) -> None:
    conn.execute("UPDATE items SET file_name = ?, file_size = ?, file_hash = ?, modified_at = ? "
                 "WHERE id = ?", (file["name"], file["size"], file["hash"], now(), item_id))
    reindex(conn, item_id, fulltext=fulltext)
    conn.commit()


TRASH_DAYS = 30


def trash_item(conn, item_id: int) -> None:
    """Move a paper to the trash: it leaves every list, but keeps its PDF, notes and figures.
    Its authors stay linked to it (so they come back as they were), but do not count, or
    appear among the people in the library, unless they have other papers or are followed."""
    conn.execute("UPDATE items SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL", (now(), item_id))
    conn.commit()


def restore_item(conn, item_id: int) -> None:
    conn.execute("UPDATE items SET deleted_at = NULL WHERE id = ?", (item_id,))
    conn.commit()


def expired_trash(conn, days: int = TRASH_DAYS) -> list[int]:
    """Papers in the trash for longer than `days`."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    return [r[0] for r in conn.execute(
        "SELECT id FROM items WHERE deleted_at IS NOT NULL AND deleted_at < ?", (cutoff,))]


def delete_item(conn, item_id: int) -> list[str]:
    """Delete the item and return the names of its files (PDF and supplementary) so the
    caller can remove them."""
    row = conn.execute("SELECT file_name FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        return []
    files = [row["file_name"]] if row["file_name"] else []
    files += [r[0] for r in conn.execute(
        "SELECT file_name FROM supplementary WHERE item_id = ?", (item_id,))]
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.execute("DELETE FROM items_fts WHERE rowid = ?", (item_id,))
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM item_tags)")
    from . import authors
    authors.drop_orphans(conn)
    conn.commit()
    return files


# --------------------------------------------------------------------------- #
# Supplementary information
# --------------------------------------------------------------------------- #

def add_supplementary(conn, item_id: int, file: dict, original_name: str,
                      fulltext: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO supplementary (item_id, file_name, original_name, file_size, file_hash, "
        "fulltext, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (item_id, file["name"], original_name, file["size"], file["hash"], fulltext, now()))
    conn.execute("UPDATE items SET modified_at = ? WHERE id = ?", (now(), item_id))
    reindex(conn, item_id)
    conn.commit()
    return cur.lastrowid


def get_supplementary(conn, supp_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM supplementary WHERE id = ?", (supp_id,)).fetchone()


def find_supplementary(conn, item_id: int, file_hash: str) -> int | None:
    row = conn.execute("SELECT id FROM supplementary WHERE item_id = ? AND file_hash = ?",
                       (item_id, file_hash)).fetchone()
    return row["id"] if row else None


def delete_supplementary(conn, supp_id: int) -> tuple[int, str] | None:
    """Delete the record; return (item id, file name) so the caller can remove the file."""
    row = get_supplementary(conn, supp_id)
    if row is None:
        return None
    conn.execute("DELETE FROM supplementary WHERE id = ?", (supp_id,))
    reindex(conn, row["item_id"])
    conn.commit()
    return row["item_id"], row["file_name"]


_ENTITY = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")


def _unescape_stored(conn) -> None:
    """Names saved with HTML entities by earlier versions ("Organic &amp; Biomolecular
    Chemistry", as Crossref sends them) are stored as plain text (once; cheap after that)."""
    from html import unescape
    fix = lambda v: unescape(v) if v and _ENTITY.search(v) else v
    for r in conn.execute("SELECT id, title, venue, venue_short, publisher, authors FROM items "
                          "WHERE title || IFNULL(venue, '') || IFNULL(venue_short, '') || IFNULL(publisher, '') "
                          "|| IFNULL(authors, '') LIKE '%&%;%'").fetchall():
        new = {k: fix(r[k]) for k in ("title", "venue", "venue_short", "publisher")}
        authors = json.loads(r["authors"] or "[]")
        authors = [{k: fix(v) if isinstance(v, str) else v for k, v in a.items()} for a in authors]
        if any(new[k] != r[k] for k in new) or json.dumps(authors) != json.dumps(json.loads(r["authors"] or "[]")):
            conn.execute("UPDATE items SET title = ?, venue = ?, venue_short = ?, publisher = ?, authors = ? WHERE id = ?",
                         (new["title"], new["venue"], new["venue_short"], new["publisher"], json.dumps(authors), r["id"]))
            reindex(conn, r["id"])
    for r in conn.execute("SELECT id, title, venue FROM person_works WHERE title || IFNULL(venue, '') LIKE '%&%;%'").fetchall():
        if fix(r["title"]) != r["title"] or fix(r["venue"]) != r["venue"]:
            conn.execute("UPDATE person_works SET title = ?, venue = ? WHERE id = ?", (fix(r["title"]), fix(r["venue"]), r["id"]))
    conn.commit()


def reindex(conn, item_id: int, fulltext: str | None = None) -> None:
    if fulltext is None:
        r = conn.execute("SELECT fulltext FROM items_fts WHERE rowid = ?", (item_id,)).fetchone()
        fulltext = r[0] if r else ""
    item = get_item(conn, item_id)
    conn.execute("DELETE FROM items_fts WHERE rowid = ?", (item_id,))
    annotations = " ".join(
        " ".join(filter(None, (r["text"], r["comment"])))
        for r in conn.execute("SELECT text, comment FROM annotations WHERE item_id = ?", (item_id,)))
    extra = " ".join(filter(None, [item.get("doi"), item.get("arxiv_id"), item.get("citekey"),
                                   item.get("notes"), " ".join(item["tags"]), annotations]))
    supplementary = "\n".join(r[0] for r in conn.execute(
        "SELECT fulltext FROM supplementary WHERE item_id = ? AND fulltext != '' ORDER BY id",
        (item_id,)))
    conn.execute(
        "INSERT INTO items_fts (rowid, title, authors, abstract, venue, extra, fulltext, "
        "supplementary) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (item_id, item["title"], authors_to_text(item["authors"]), item.get("abstract") or "",
         item.get("venue") or "", extra, fulltext, supplementary))


# --------------------------------------------------------------------------- #
# Tags
# --------------------------------------------------------------------------- #

def set_tags(conn, item_id: int, names: list[str], do_reindex: bool = True) -> None:
    clean = []
    for n in names:
        n = n.strip()
        if n and n.lower() not in {c.lower() for c in clean}:
            clean.append(n[:100])
    conn.execute("DELETE FROM item_tags WHERE item_id = ?", (item_id,))
    for n in clean:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (n,))
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (n,)).fetchone()[0]
        conn.execute("INSERT OR IGNORE INTO item_tags VALUES (?, ?)", (item_id, tag_id))
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM item_tags)")
    if do_reindex:
        reindex(conn, item_id)


def list_tags(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT t.name, COUNT(it.item_id) AS count FROM tags t "
        "JOIN item_tags it ON it.tag_id = t.id JOIN items i ON i.id = it.item_id AND i.deleted_at IS NULL "
        "GROUP BY t.id ORDER BY lower(t.name)")
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Collections
# --------------------------------------------------------------------------- #

def list_collections(conn) -> list[dict]:
    """Collections with `count` (items directly inside) and `total` (distinct items in the
    collection or any of its subcollections)."""
    rows = [dict(r) for r in conn.execute(
        "SELECT c.id, c.name, c.parent_id, COUNT(i.id) AS count FROM collections c "
        "LEFT JOIN item_collections ic ON ic.collection_id = c.id "
        "LEFT JOIN items i ON i.id = ic.item_id AND i.deleted_at IS NULL "
        "GROUP BY c.id ORDER BY lower(c.name)")]
    members: dict[int, set[int]] = {r["id"]: set() for r in rows}
    for item_id, cid in conn.execute("SELECT ic.item_id, ic.collection_id FROM item_collections ic "
                                     "JOIN items i ON i.id = ic.item_id AND i.deleted_at IS NULL"):
        members[cid].add(item_id)
    children: dict[int, list[int]] = {}
    for r in rows:
        if r["parent_id"] in members:
            children.setdefault(r["parent_id"], []).append(r["id"])
    totals: dict[int, set[int]] = {}

    def total(cid: int, depth: int = 0) -> set[int]:
        if cid not in totals:
            items = set(members[cid])
            if depth < 100:
                for child in children.get(cid, []):
                    items |= total(child, depth + 1)
            totals[cid] = items
        return totals[cid]

    for r in rows:
        r["total"] = len(total(r["id"]))
    return rows


def collection_exists(conn, cid: int) -> bool:
    return conn.execute("SELECT 1 FROM collections WHERE id = ?", (cid,)).fetchone() is not None


def create_collection(conn, name: str, parent_id: int | None) -> int:
    cur = conn.execute("INSERT INTO collections (name, parent_id) VALUES (?, ?)",
                       (name.strip(), parent_id))
    conn.commit()
    return cur.lastrowid


def update_collection(conn, cid: int, name: str | None, parent_id: int | None,
                      set_parent: bool) -> None:
    if name is not None:
        conn.execute("UPDATE collections SET name = ? WHERE id = ?", (name.strip(), cid))
    if set_parent:
        # Prevent cycles: the new parent cannot be a descendant of the collection.
        p = parent_id
        while p is not None:
            if p == cid:
                raise ValueError("A collection cannot be placed inside itself")
            r = conn.execute("SELECT parent_id FROM collections WHERE id = ?", (p,)).fetchone()
            p = r["parent_id"] if r else None
        conn.execute("UPDATE collections SET parent_id = ? WHERE id = ?", (parent_id, cid))
    conn.commit()


def delete_collection(conn, cid: int) -> None:
    conn.execute("DELETE FROM collections WHERE id = ?", (cid,))
    conn.commit()


def set_collections(conn, item_id: int, cids: list[int]) -> None:
    # Only add/remove what changed, so the order in which collections were added is kept.
    wanted = [c for c in dict.fromkeys(cids) if collection_exists(conn, c)]
    existing = [r[0] for r in conn.execute(
        "SELECT collection_id FROM item_collections WHERE item_id = ?", (item_id,))]
    for cid in existing:
        if cid not in wanted:
            conn.execute("DELETE FROM item_collections WHERE item_id = ? AND collection_id = ?",
                         (item_id, cid))
    for cid in wanted:
        if cid not in existing:
            conn.execute("INSERT INTO item_collections VALUES (?, ?)", (item_id, cid))


def add_to_collection(conn, cid: int, item_ids: list[int]) -> None:
    for iid in item_ids:
        conn.execute("INSERT OR IGNORE INTO item_collections "
                     "SELECT ?, ? WHERE EXISTS (SELECT 1 FROM items WHERE id = ?)",
                     (iid, cid, iid))
    conn.commit()


def remove_from_collection(conn, cid: int, item_id: int) -> None:
    conn.execute("DELETE FROM item_collections WHERE collection_id = ? AND item_id = ?",
                 (cid, item_id))
    conn.commit()


# --------------------------------------------------------------------------- #
# Annotations
# --------------------------------------------------------------------------- #

def _row_to_annotation(row: sqlite3.Row) -> dict:
    a = dict(row)
    a["rects"] = json.loads(a["rects"])
    return a


def list_annotations(conn, item_id: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM annotations WHERE item_id = ? ORDER BY page, id",
                        (item_id,))
    return [_row_to_annotation(r) for r in rows]


def get_annotation(conn, ann_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM annotations WHERE id = ?", (ann_id,)).fetchone()
    return _row_to_annotation(row) if row else None


def create_annotation(conn, item_id: int, data: dict) -> int:
    ts = now()
    cur = conn.execute(
        "INSERT INTO annotations (item_id, kind, color, page, rects, text, comment, "
        "created_at, modified_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (item_id, data["kind"], data["color"], data["page"], json.dumps(data["rects"]),
         (data.get("text") or "").strip() or None, (data.get("comment") or "").strip() or None,
         ts, ts))
    reindex(conn, item_id)
    conn.commit()
    return cur.lastrowid


def update_annotation(conn, ann_id: int, changes: dict) -> None:
    fields = {k: changes[k] for k in ("color", "comment") if k in changes}
    if "comment" in fields:
        fields["comment"] = (fields["comment"] or "").strip() or None
    if not fields:
        return
    fields["modified_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE annotations SET {sets} WHERE id = ?", [*fields.values(), ann_id])
    item_id = conn.execute("SELECT item_id FROM annotations WHERE id = ?", (ann_id,)).fetchone()[0]
    reindex(conn, item_id)
    conn.commit()


def delete_annotation(conn, ann_id: int) -> None:
    row = conn.execute("SELECT item_id FROM annotations WHERE id = ?", (ann_id,)).fetchone()
    if row is None:
        return
    conn.execute("DELETE FROM annotations WHERE id = ?", (ann_id,))
    reindex(conn, row["item_id"])
    conn.commit()



# --------------------------------------------------------------------------- #
# Settings (library-wide preferences)
# --------------------------------------------------------------------------- #

def get_settings(conn) -> dict:
    """The user's settings (keys starting with "_" are Bubo's own notes, such as migrations done)."""
    return {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM settings")
            if not r["key"].startswith("_")}


def set_settings(conn, values: dict) -> None:
    for key, value in values.items():
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, json.dumps(value)))
    conn.commit()


# --------------------------------------------------------------------------- #
# Reading list
# --------------------------------------------------------------------------- #

def set_to_read(conn, item_id: int, on: bool) -> None:
    if on:  # keep the original date if it is already on the list
        conn.execute("UPDATE items SET to_read_at = COALESCE(to_read_at, ?) WHERE id = ?",
                     (now(), item_id))
    else:
        conn.execute("UPDATE items SET to_read_at = NULL WHERE id = ?", (item_id,))


def library_counts(conn) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS all_items, "
        "SUM(id NOT IN (SELECT item_id FROM item_collections)) AS unfiled, "
        "SUM(to_read_at IS NOT NULL) AS to_read, "
        f"COUNT(DISTINCT CASE WHEN trim(venue) != '' THEN {venue_key_sql()} END) AS journals "
        "FROM items WHERE deleted_at IS NULL").fetchone()
    trash = conn.execute("SELECT COUNT(*) FROM items WHERE deleted_at IS NOT NULL").fetchone()[0]
    return {"all": row["all_items"], "unfiled": row["unfiled"] or 0, "to_read": row["to_read"] or 0,
            "journals": row["journals"] or 0, "trash": trash}


def missing_details(item: dict) -> list[str]:
    """Details a reference needs that the item lacks (shown in the overview so they get fixed)."""
    missing = []
    if not item.get("title") or item["title"] == "New item":
        missing.append("title")
    if not item.get("authors"):
        missing.append("authors")
    if not item.get("year"):
        missing.append("year")
    if item.get("item_type") in ("article", "inproceedings", "incollection") and not item.get("venue"):
        missing.append("journal" if item.get("item_type") == "article" else "venue")
    return missing


def is_incomplete(item: dict) -> bool:
    return bool(missing_details(item))
