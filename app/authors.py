"""Every author in the library is a person, and their ORCID iD is looked for in every way we can.

Each author of each paper is linked to a row of the people table (item_authors). People are
told apart by their ORCID iD when it is known, otherwise by family name and first initial
("name key"): two "J. Smith" without an iD are one person, which is the best a name can do.
Following someone (people.py) is a flag on their row.

An author's ORCID iD comes, in order, from:

1. Crossref, which gives it for some authors (kept in the paper's authors as "orcid");
2. OpenAlex, which matches authors of a DOI to iDs (asked for 50 papers at a time);
3. ORCID itself: the people who have the DOI in their record;
4. the PDF, whose author list often links to orcid.org.

OpenAlex and ORCID records are sometimes wrong (people claim papers they only cited), so an
iD is only given to an author whose family name and first initial match the name on it.

A background thread looks at papers added or edited since it last ran (items whose
authors_checked is NULL), including, once, every paper already in the library.
"""

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from . import db, people, storage
from .config import settings

log = logging.getLogger("bubo.authors")

BATCH = 50                       # papers per OpenAlex request
_wake = threading.Event()


# --------------------------------------------------------------------------- #
# Names
# --------------------------------------------------------------------------- #

def name_key(given: str | None, family: str | None) -> str | None:
    """'María', 'García-López' → 'garcialopez|m'."""
    fam = people._plain(family)
    if not fam:
        return None
    return f"{fam}|{people._plain(given)[:1]}"


def full_name(a: dict) -> str:
    return " ".join(p for p in ((a.get("given") or "").strip(), (a.get("family") or "").strip()) if p)


def same_person(a: dict, given: str | None, family: str | None) -> bool:
    """Whether an author of a paper can be the person with this given and family name."""
    fam_a, fam_b = people._plain(a.get("family")), people._plain(family)
    if not fam_a or not fam_b:
        return False
    if fam_a != fam_b and not (len(fam_a) > 3 and len(fam_b) > 3 and (fam_a in fam_b or fam_b in fam_a)):
        return False      # "van der Walt" / "Walt", "García López" / "García" still match
    ga, gb = people._plain(a.get("given")), people._plain(given)
    return not ga or not gb or ga[0] == gb[0]


# --------------------------------------------------------------------------- #
# Linking authors to people (no network)
# --------------------------------------------------------------------------- #

def _person_for(conn, a: dict) -> int | None:
    key = name_key(a.get("given"), a.get("family"))
    orcid = a.get("orcid")
    name = full_name(a)
    if not key and not orcid:
        return None
    if orcid:
        row = conn.execute("SELECT id FROM people WHERE orcid = ?", (orcid,)).fetchone()
        if row:
            return row["id"]
        # Someone known so far only by name becomes the person with this iD.
        row = conn.execute("SELECT id FROM people WHERE orcid IS NULL AND name_key = ? "
                           "ORDER BY followed DESC, id LIMIT 1", (key,)).fetchone() if key else None
        if row:
            conn.execute("UPDATE people SET orcid = ? WHERE id = ?", (orcid, row["id"]))
            return row["id"]
    else:
        rows = conn.execute("SELECT id, orcid FROM people WHERE name_key = ? ORDER BY id", (key,)).fetchall()
        with_id = [r for r in rows if r["orcid"]]
        without = [r for r in rows if not r["orcid"]]
        if len(with_id) == 1:
            return with_id[0]["id"]
        if without:
            return without[0]["id"]
    cur = conn.execute("INSERT INTO people (orcid, name, family_name, name_key, followed, added_at) "
                       "VALUES (?, ?, ?, ?, 0, ?)",
                       (orcid, name or a.get("family") or orcid, (a.get("family") or "").strip() or None,
                        key, db.now()))
    return cur.lastrowid


def _better_name(conn, person_id: int, a: dict) -> None:
    """Keep the fullest form of a name seen ("Mario" rather than "M.") for people known only
    from papers (the name of someone followed comes from ORCID)."""
    name = full_name(a)
    row = conn.execute("SELECT name, followed FROM people WHERE id = ?", (person_id,)).fetchone()
    if row and not row["followed"] and len(name) > len(row["name"] or ""):
        conn.execute("UPDATE people SET name = ? WHERE id = ?", (name, person_id))


def link_item(conn, item_id: int) -> None:
    """Link the authors of a paper to people (creating them), and drop people left without
    papers who are not followed."""
    row = conn.execute("SELECT authors FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.execute("DELETE FROM item_authors WHERE item_id = ?", (item_id,))
    if row:
        for pos, a in enumerate(json.loads(row["authors"] or "[]")):
            pid = _person_for(conn, a)
            if pid:
                _better_name(conn, pid, a)
                conn.execute("INSERT OR IGNORE INTO item_authors (item_id, pos, person_id) VALUES (?, ?, ?)",
                             (item_id, pos, pid))
    drop_orphans(conn)


def drop_orphans(conn) -> None:
    """People you do not follow who are no longer an author of any paper (not even one in
    the trash) go, with their photo."""
    for (pid,) in conn.execute(
            "SELECT id FROM people WHERE followed = 0 "
            "AND id NOT IN (SELECT person_id FROM item_authors)").fetchall():
        conn.execute("DELETE FROM people WHERE id = ?", (pid,))
        people.delete_photo(pid)


def merge_by_name(conn) -> None:
    """People known only by name whose name matches exactly one person with an ORCID iD are
    that person."""
    rows = conn.execute(
        "SELECT p.id, q.id AS target FROM people p JOIN people q ON q.name_key = p.name_key "
        "AND q.orcid IS NOT NULL WHERE p.orcid IS NULL AND p.followed = 0 "
        "AND (SELECT COUNT(*) FROM people r WHERE r.name_key = p.name_key AND r.orcid IS NOT NULL) = 1").fetchall()
    for r in rows:
        conn.execute("UPDATE OR IGNORE item_authors SET person_id = ? WHERE person_id = ?", (r["target"], r["id"]))
        conn.execute("DELETE FROM item_authors WHERE person_id = ?", (r["id"],))
        conn.execute("DELETE FROM people WHERE id = ? AND photo IS NULL", (r["id"],))   # a photo of their own: kept


def link_all(conn) -> None:
    for (item_id,) in conn.execute("SELECT id FROM items").fetchall():
        link_item(conn, item_id)
    merge_by_name(conn)
    conn.commit()


def keep_orcids(old: list[dict], new: list[dict]) -> list[dict]:
    """An edited author list keeps the iDs already found for the same names."""
    known = {(people._plain(a.get("given")), people._plain(a.get("family"))): a["orcid"]
             for a in old if a.get("orcid")}
    for a in new:
        if not a.get("orcid"):
            orcid = known.get((people._plain(a.get("given")), people._plain(a.get("family"))))
            if orcid:
                a["orcid"] = orcid
    return new


# --------------------------------------------------------------------------- #
# Looking for ORCID iDs
# --------------------------------------------------------------------------- #

def _orcid(value: str | None) -> str | None:
    try:
        return people.normalise_orcid(value) if value else None
    except people.PeopleError:
        return None


def _assign(authors: list[dict], candidates: list[tuple[str, str, str]]) -> int:
    """Give each author without an iD the one candidate (given, family, orcid) that matches
    their name. Returns how many were given one."""
    taken = {a["orcid"] for a in authors if a.get("orcid")}
    found = 0
    for a in authors:
        if a.get("orcid"):
            continue
        match = {o for g, f, o in candidates if o not in taken and same_person(a, g, f)}
        if len(match) == 1:
            a["orcid"] = match.pop()
            taken.add(a["orcid"])
            found += 1
    return found


def _split(name: str) -> tuple[str, str]:
    given, _, family = (name or "").strip().rpartition(" ")
    return given, family or name


def from_openalex(c: httpx.Client, dois: list[str]) -> dict[str, list[tuple[str, str, str]]]:
    """For each DOI, the authors OpenAlex knows an iD for: (given, family, orcid). An author
    counts only when the name printed on the paper and OpenAlex's name for the iD agree."""
    out: dict[str, list] = {}
    if not dois:
        return out
    r = c.get(f"{people.OPENALEX_API}/works", params=people._openalex_params(
        filter="doi:" + "|".join(dois), select="doi,authorships", **{"per-page": BATCH}))
    r.raise_for_status()
    for w in r.json().get("results") or []:
        doi = people._doi(w.get("doi"))
        for au in w.get("authorships") or []:
            orcid = _orcid((au.get("author") or {}).get("orcid"))
            printed = au.get("raw_author_name") or ""
            known = (au.get("author") or {}).get("display_name") or ""
            if not orcid or not printed:
                continue
            g, f = _split(printed)
            kg, kf = _split(known)
            if same_person({"given": g, "family": f}, kg, kf):
                out.setdefault(doi, []).append((g, f, orcid))
    return out


def from_orcid_search(c: httpx.Client, query: str) -> list[tuple[str, str, str]]:
    r = c.get(f"{people.ORCID_API}/expanded-search/", params={"q": query, "rows": 100},
              headers={"Accept": "application/json"})
    r.raise_for_status()
    return [(x.get("given-names") or "", x.get("family-names") or "", _orcid(x.get("orcid-id")))
            for x in r.json().get("expanded-result") or [] if _orcid(x.get("orcid-id"))]


def orcids_in_pdf(path) -> list[str]:
    """ORCID iDs printed or linked on the first pages of a PDF."""
    import pymupdf
    found = []
    try:
        with pymupdf.open(path) as doc:
            for page in list(doc)[:3]:
                texts = [l.get("uri") or "" for l in page.get_links()]
                texts.append(page.get_text())
                for t in texts:
                    for m in re.finditer(r"orcid\.org/(\S{16,19})|(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", t, re.I):
                        o = _orcid(m.group(0))
                        if o and o not in found:
                            found.append(o)
    except Exception as e:      # a broken PDF is no reason to stop
        log.warning("ORCID iDs in %s: %s", path, e)
    return found


def resolve(conn, item_ids: list[int]) -> int:
    """Look for the ORCID iDs of the authors of these papers, save them and link the authors
    again. Returns how many iDs were found."""
    rows = [r for r in (conn.execute("SELECT id, doi, authors, file_name FROM items WHERE id = ?", (i,)).fetchone()
                        for i in item_ids) if r]
    papers = [{"id": r["id"], "doi": people._doi(r["doi"]), "file": r["file_name"],
               "authors": json.loads(r["authors"] or "[]")} for r in rows]
    found = 0
    missing = lambda p: any(not a.get("orcid") for a in p["authors"])
    with people._client() as c:
        dois = [p["doi"] for p in papers if p["doi"] and missing(p)]
        try:
            by_doi = from_openalex(c, dois)
        except (httpx.HTTPError, ValueError) as e:
            log.warning("OpenAlex authors: %s", e)
            by_doi = {}
        for p in papers:
            found += _assign(p["authors"], by_doi.get(p["doi"], []))
        for p in papers:
            if p["doi"] and missing(p):
                try:
                    found += _assign(p["authors"], from_orcid_search(c, f'doi-self:"{p["doi"]}"'))
                except (httpx.HTTPError, ValueError) as e:
                    log.warning("ORCID search for %s: %s", p["doi"], e)
                time.sleep(0.3)
            if p["file"] and missing(p):
                ids = [o for o in orcids_in_pdf(storage.abs_path(p["file"]))
                       if o not in {a.get("orcid") for a in p["authors"]}]
                if ids:
                    try:
                        cands = from_orcid_search(c, " OR ".join(f"orcid:{o}" for o in ids[:20]))
                        found += _assign(p["authors"], cands)
                    except (httpx.HTTPError, ValueError) as e:
                        log.warning("ORCID names for a PDF's iDs: %s", e)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for p in papers:
        conn.execute("UPDATE items SET authors = ?, authors_checked = ? WHERE id = ?",
                     (json.dumps(p["authors"], ensure_ascii=False), stamp, p["id"]))
        link_item(conn, p["id"])
    merge_by_name(conn)
    conn.commit()
    return found


# --------------------------------------------------------------------------- #
# In the background
# --------------------------------------------------------------------------- #

def kick() -> None:
    """New or edited papers are waiting (cheap: the thread does the work)."""
    _wake.set()


def run_pending(conn) -> int:
    """Look at every paper waiting, BATCH at a time. Returns how many iDs were found."""
    found = 0
    while True:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM items WHERE authors_checked IS NULL AND deleted_at IS NULL ORDER BY id DESC LIMIT ?", (BATCH,))]
        if not ids:
            return found
        found += resolve(conn, ids)
        time.sleep(1)


def start() -> None:
    if not settings.orcid_lookup:
        return

    def loop():
        time.sleep(5)
        while True:
            _wake.clear()
            conn = db.connect()
            try:
                n = run_pending(conn)
                if n:
                    log.info("Found %s ORCID iDs of authors", n)
            except Exception:
                log.exception("Looking for authors' ORCID iDs failed")
            finally:
                conn.close()
            _wake.wait(600)

    threading.Thread(target=loop, name="authors", daemon=True).start()
