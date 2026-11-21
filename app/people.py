"""Following scientists by their ORCID iD, and a radar of their new publications.

A followed person's publications come from two public sources, merged by DOI:

* ORCID (pub.orcid.org): the person's own record, the authority on who they are and on the
  works they claim;
* OpenAlex (api.openalex.org): works matched to the ORCID iD, usually within days of
  publication, with their authors and journal. Some papers carry someone else's ORCID iD by
  mistake (ORCID's own example iD is a favourite), so an OpenAlex work only counts if the
  name printed on the paper for that iD contains the person's family name.

Every 12 hours (BUBO_RADAR_HOURS) a background thread looks at each person again. Works
discovered then, and published in the 60 days before, appear on the radar.
"""

import json
import logging
import re
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone

import httpx

from . import db
from .config import settings

log = logging.getLogger("bubo.people")

ORCID_API = "https://pub.orcid.org/v3.0"
OPENALEX_API = "https://api.openalex.org"
NEW_DAYS = 60                 # how recent a work must be to count as news
TIMEOUT = 20.0
ORCID_RE = re.compile(r"(\d{4})-?(\d{4})-?(\d{4})-?(\d{3}[\dX])", re.I)


class PeopleError(Exception):
    pass


# --------------------------------------------------------------------------- #
# ORCID iDs
# --------------------------------------------------------------------------- #

def normalise_orcid(text: str) -> str:
    """'https://orcid.org/0000-0002-1825-0097', '0000000218250097'… → '0000-0002-1825-0097'.
    Raises PeopleError if it is not a valid ORCID iD (the last character is a checksum)."""
    m = ORCID_RE.search((text or "").strip())
    if not m:
        raise PeopleError("That does not look like an ORCID iD (0000-0000-0000-0000)")
    digits = "".join(m.groups()).upper()
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    if digits[-1] != ("X" if check == 10 else str(check)):
        raise PeopleError("That ORCID iD is not valid: please check it")
    return "-".join(digits[i:i + 4] for i in range(0, 16, 4))


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #

def _client() -> httpx.Client:
    ua = "Bubo/0.1 (self-hosted reference manager)"
    if settings.contact_email:
        ua += f" (mailto:{settings.contact_email})"
    return httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": ua})


def _doi(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value.strip(), flags=re.I)
    return value.lower() or None


def _date(y, m=None, d=None) -> str | None:
    """An ISO date, as precise as known: '2024', '2024-05', '2024-05-17'."""
    try:
        if not y:
            return None
        parts = [f"{int(y):04d}"] + [f"{int(x):02d}" for x in (m, d) if x]
        return "-".join(parts[:3])
    except (TypeError, ValueError):
        return None


def _plain(text: str) -> str:
    """'Müller-Lüdenscheidt' → 'mullerludenscheidt': for comparing names."""
    text = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"[^a-z]", "", "".join(c for c in text if not unicodedata.combining(c)).lower())


def fetch_person(orcid: str) -> dict:
    """Name, family name and affiliation of an ORCID iD."""
    name, family, affiliation = "", None, None
    with _client() as c:
        try:
            r = c.get(f"{ORCID_API}/{orcid}/person", headers={"Accept": "application/json"})
            if r.status_code == 404:
                raise PeopleError("There is no ORCID record with that iD")
            r.raise_for_status()
            n = (r.json().get("name") or {})
            given = ((n.get("given-names") or {}).get("value") or "").strip()
            family = ((n.get("family-name") or {}).get("value") or "").strip()
            credit = ((n.get("credit-name") or {}).get("value") or "").strip()
            name = credit or " ".join(p for p in (given, family) if p)
            family = family or None
        except httpx.HTTPError as e:
            log.warning("ORCID person %s: %s", orcid, e)
        try:
            params = {"mailto": settings.contact_email} if settings.contact_email else {}
            r = c.get(f"{OPENALEX_API}/authors/orcid:{orcid}", params=params)
            if r.status_code == 200:
                a = r.json()
                name = name or a.get("display_name") or ""
                inst = a.get("last_known_institutions") or []
                affiliation = inst[0].get("display_name") if inst else None
        except httpx.HTTPError as e:
            log.warning("OpenAlex author %s: %s", orcid, e)
    if not name:
        raise PeopleError("Could not find a name for that ORCID iD; is the record public?")
    return {"name": name, "family": family or name.split()[-1], "affiliation": affiliation}


def _orcid_works(c: httpx.Client, orcid: str) -> list[dict]:
    r = c.get(f"{ORCID_API}/{orcid}/works", headers={"Accept": "application/json"})
    r.raise_for_status()
    works = []
    for group in r.json().get("group") or []:
        summaries = group.get("work-summary") or []
        if not summaries:
            continue
        s = summaries[0]                       # the preferred version of the work
        ids = ((s.get("external-ids") or {}).get("external-id") or [])
        doi = next((_doi(x.get("external-id-value")) for x in ids
                    if (x.get("external-id-type") or "").lower() == "doi"), None)
        pd = s.get("publication-date") or {}
        val = lambda k: ((pd.get(k) or {}).get("value"))
        title = (((s.get("title") or {}).get("title") or {}).get("value") or "").strip()
        if not title:
            continue
        works.append({
            "key": f"doi:{doi}" if doi else f"orcid:{s.get('put-code')}",
            "doi": doi, "title": title, "authors": [],
            "venue": ((s.get("journal-title") or {}).get("value")),
            "pub_date": _date(val("year"), val("month"), val("day")),
            "type": s.get("type"), "url": ((s.get("url") or {}).get("value")),
        })
    return works


def _openalex_works(c: httpx.Client, orcid: str, family: str | None) -> list[dict]:
    params = {"filter": f"author.orcid:{orcid}", "sort": "publication_date:desc", "per-page": 200}
    if settings.contact_email:
        params["mailto"] = settings.contact_email
    r = c.get(f"{OPENALEX_API}/works", params=params)
    r.raise_for_status()
    works = []
    for w in r.json().get("results") or []:
        title = (w.get("title") or w.get("display_name") or "").strip()
        if not title:
            continue
        doi = _doi(w.get("doi"))
        # The name printed on the paper for this ORCID iD must contain the family name.
        if family:
            fam = _plain(family)
            names = [_plain(a.get("raw_author_name") or "") for a in w.get("authorships") or []
                     if ((a.get("author") or {}).get("orcid") or "").endswith(orcid)]
            if names and not any(fam and fam in n for n in names):
                continue
        authors = []
        for a in w.get("authorships") or []:
            full = ((a.get("author") or {}).get("display_name") or "").strip()
            if full:
                given, _, last = full.rpartition(" ")
                authors.append({"given": given, "family": last or full})
        source = ((w.get("primary_location") or {}).get("source") or {})
        works.append({
            "key": f"doi:{doi}" if doi else f"openalex:{w.get('id', '').rsplit('/', 1)[-1]}",
            "doi": doi, "title": title, "authors": authors,
            "venue": source.get("display_name"),
            "pub_date": w.get("publication_date") or _date(w.get("publication_year")),
            "type": w.get("type"),
            "url": (w.get("open_access") or {}).get("oa_url") or (f"https://doi.org/{doi}" if doi else w.get("id")),
        })
    return works


def fetch_works(orcid: str, family: str | None = None) -> list[dict]:
    """The person's works from ORCID and OpenAlex, merged by DOI (OpenAlex fills in authors
    and journals that ORCID summaries lack)."""
    merged: dict[str, dict] = {}
    errors = []
    with _client() as c:
        for name, fetch in (("ORCID", lambda c, o: _orcid_works(c, o)),
                            ("OpenAlex", lambda c, o: _openalex_works(c, o, family))):
            try:
                for w in fetch(c, orcid):
                    old = merged.get(w["key"])
                    if old is None:
                        merged[w["key"]] = w
                    else:
                        for k, v in w.items():
                            if v and not old.get(k):
                                old[k] = v
            except (httpx.HTTPError, ValueError) as e:
                errors.append(f"{name}: {e}")
    if errors and not merged:
        raise PeopleError("Could not reach ORCID or OpenAlex: " + "; ".join(errors))
    return list(merged.values())


# --------------------------------------------------------------------------- #
# Storing
# --------------------------------------------------------------------------- #

def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_recent(pub_date: str | None, today: date | None = None) -> bool:
    """Published in the last NEW_DAYS days (a date given only as a year or a month counts
    from its last day)."""
    if not pub_date:
        return False
    today = today or _now().date()
    parts = [int(p) for p in pub_date.split("-")]
    try:
        if len(parts) == 3:
            d = date(*parts)
        elif len(parts) == 2:
            d = (date(parts[0] + parts[1] // 12, parts[1] % 12 + 1, 1) - timedelta(days=1))
        else:
            d = date(parts[0], 12, 31)
    except ValueError:
        return False
    return today - timedelta(days=NEW_DAYS) <= d <= today + timedelta(days=30)


def store_works(conn, person_id: int, works: list[dict]) -> int:
    """Save works not seen before; returns how many of them are news for the radar."""
    seen_at = _now().isoformat(timespec="seconds")
    known = {r[0] for r in conn.execute("SELECT work_key FROM person_works WHERE person_id = ?", (person_id,))}
    new = 0
    for w in works:
        if w["key"] in known:
            # Fill in details that a later fetch found (authors, journal, date).
            conn.execute(
                "UPDATE person_works SET authors = CASE WHEN authors = '[]' THEN ? ELSE authors END, "
                "venue = COALESCE(venue, ?), pub_date = COALESCE(pub_date, ?), url = COALESCE(url, ?) "
                "WHERE person_id = ? AND work_key = ?",
                (json.dumps(w["authors"], ensure_ascii=False), w["venue"], w["pub_date"], w["url"],
                 person_id, w["key"]))
            continue
        # News: a recent work not seen before (on the first look, the recent ones).
        is_new = is_recent(w["pub_date"])
        new += is_new
        conn.execute(
            "INSERT INTO person_works (person_id, work_key, doi, title, authors, venue, pub_date, "
            "type, url, first_seen, is_new) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (person_id, w["key"], w["doi"], w["title"], json.dumps(w["authors"], ensure_ascii=False),
             w["venue"], w["pub_date"], w["type"], w["url"], seen_at, int(is_new)))
    conn.execute("UPDATE people SET last_checked = ?, last_error = NULL WHERE id = ?", (seen_at, person_id))
    conn.commit()
    return new


def follow(conn, text: str) -> int:
    orcid = normalise_orcid(text)
    row = conn.execute("SELECT id FROM people WHERE orcid = ?", (orcid,)).fetchone()
    if row:
        raise PeopleError("You already follow that person")
    person = fetch_person(orcid)
    works = fetch_works(orcid, person["family"])
    cur = conn.execute("INSERT INTO people (orcid, name, family_name, affiliation, added_at) VALUES (?, ?, ?, ?, ?)",
                       (orcid, person["name"], person["family"], person["affiliation"],
                        _now().isoformat(timespec="seconds")))
    store_works(conn, cur.lastrowid, works)
    return cur.lastrowid


def refresh_person(conn, person_id: int) -> int:
    row = conn.execute("SELECT orcid, family_name FROM people WHERE id = ?", (person_id,)).fetchone()
    if row is None:
        return 0
    try:
        works = fetch_works(row["orcid"], row["family_name"])
    except PeopleError as e:
        conn.execute("UPDATE people SET last_error = ? WHERE id = ?", (str(e), person_id))
        conn.commit()
        raise
    return store_works(conn, person_id, works)


def refresh_all(conn) -> int:
    new = 0
    for (pid,) in conn.execute("SELECT id FROM people ORDER BY id").fetchall():
        try:
            new += refresh_person(conn, pid)
        except PeopleError as e:
            log.warning("Radar: person %s: %s", pid, e)
        time.sleep(1)                      # be gentle with the APIs
    return new


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

def _library_dois(conn) -> dict[str, int]:
    return {r[0]: r[1] for r in conn.execute(
        "SELECT lower(doi), id FROM items WHERE doi IS NOT NULL AND doi != ''")}


def _work_dict(r, library: dict[str, int]) -> dict:
    w = dict(r)
    w["authors"] = json.loads(w["authors"] or "[]")
    w["is_new"] = bool(w["is_new"])
    w["item_id"] = library.get(w["doi"]) if w["doi"] else w.get("item_id")
    w["in_library"] = bool(w["item_id"])
    return w


def list_people(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT p.*, (SELECT COUNT(*) FROM person_works w WHERE w.person_id = p.id) AS works, "
        "(SELECT COUNT(*) FROM person_works w WHERE w.person_id = p.id AND w.is_new = 1 "
        " AND w.dismissed_at IS NULL AND w.seen_at IS NULL) AS unseen "
        "FROM people p ORDER BY lower(p.name)")]


def person_works(conn, person_id: int) -> list[dict]:
    library = _library_dois(conn)
    rows = conn.execute("SELECT * FROM person_works WHERE person_id = ? "
                        "ORDER BY pub_date DESC NULLS LAST, lower(title)", (person_id,))
    return [_work_dict(r, library) for r in rows]


def radar(conn) -> list[dict]:
    """News from everyone followed, newest first; a work by two followed people appears once."""
    library = _library_dois(conn)
    rows = conn.execute(
        "SELECT w.*, p.name AS person_name, p.id AS person FROM person_works w "
        "JOIN people p ON p.id = w.person_id WHERE w.is_new = 1 AND w.dismissed_at IS NULL "
        "ORDER BY w.pub_date DESC NULLS LAST, w.first_seen DESC")
    out, by_key = [], {}
    for r in rows:
        w = _work_dict(r, library)
        if w["work_key"] in by_key:
            by_key[w["work_key"]]["people"].append(w["person_name"])
            continue
        w["people"] = [w["person_name"]]
        by_key[w["work_key"]] = w
        out.append(w)
    return out


def radar_unseen(conn) -> int:
    return conn.execute(
        "SELECT COUNT(DISTINCT work_key) FROM person_works WHERE is_new = 1 AND dismissed_at IS NULL "
        "AND seen_at IS NULL").fetchone()[0]


# --------------------------------------------------------------------------- #
# Background radar
# --------------------------------------------------------------------------- #

def start_radar() -> None:
    hours = settings.radar_hours
    if hours <= 0:
        return

    def loop():
        time.sleep(60)                     # let the server start first
        while True:
            conn = db.connect()
            try:
                n = refresh_all(conn)
                if n:
                    log.info("Radar: %s new publications", n)
            except Exception:
                log.exception("Radar check failed")
            finally:
                conn.close()
            time.sleep(hours * 3600)

    threading.Thread(target=loop, name="radar", daemon=True).start()
