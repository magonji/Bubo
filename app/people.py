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

Each person also has a profile: their current position from ORCID; citation figures and
research topics from OpenAlex (only when OpenAlex's author has the person's name); and,
for scientists with a Wikidata entry, a description, a Wikipedia link and a photo from
Wikimedia Commons, kept in <data>/people. A photo can also be uploaded by hand.
"""

import json
import logging
import re
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone

import io

import httpx
from PIL import Image, ImageOps

from . import db
from .config import settings

log = logging.getLogger("bubo.people")

ORCID_API = "https://pub.orcid.org/v3.0"
OPENALEX_API = "https://api.openalex.org"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
PROFILE_DAYS = 7              # how often a profile is looked up again
PHOTO_SIZE = (480, 600)       # portrait, 4:5
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

def _openalex_params(**params) -> dict:
    """Polite-pool email and, if configured, the user's own OpenAlex API key (without one,
    every OpenAlex request from the same IP address shares a small free daily budget)."""
    if settings.contact_email:
        params["mailto"] = settings.contact_email
    if settings.openalex_api_key:
        params["api_key"] = settings.openalex_api_key
    return params


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
            r = c.get(f"{OPENALEX_API}/authors/orcid:{orcid}", params=_openalex_params())
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


def _openalex_works(c: httpx.Client, orcid: str, family: str | None, full: bool = True) -> list[dict]:
    """The person's works on OpenAlex, newest first: up to 1,000 (full), or the latest 50,
    which is all the radar needs."""
    params = _openalex_params(filter=f"author.orcid:{orcid}", sort="publication_date:desc",
                              **({"per-page": 200, "cursor": "*"} if full else {"per-page": 50}))
    results = []
    for n in range(5 if full else 1):
        try:
            r = c.get(f"{OPENALEX_API}/works", params=params)
            r.raise_for_status()
        except httpx.HTTPError:
            if n == 0:
                raise
            break                          # keep the pages already fetched
        page = r.json()
        results += page.get("results") or []
        params["cursor"] = (page.get("meta") or {}).get("next_cursor")
        if not full or not params["cursor"] or not page.get("results"):
            break
    works = []
    for w in results:
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


def fetch_works(orcid: str, family: str | None = None, full: bool = True) -> list[dict]:
    """The person's works from ORCID and OpenAlex, merged by DOI (OpenAlex fills in authors
    and journals that ORCID summaries lack)."""
    merged: dict[str, dict] = {}
    errors = []
    with _client() as c:
        for name, fetch in (("ORCID", lambda c, o: _orcid_works(c, o)),
                            ("OpenAlex", lambda c, o: _openalex_works(c, o, family, full))):
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
# Profiles and photos
# --------------------------------------------------------------------------- #

def _name_matches(name: str | None, family: str | None) -> bool:
    return not family or (bool(name) and _plain(family) in _plain(name))


def fetch_profile(orcid: str, family: str | None) -> dict:
    """What can be found about a person besides their works. Every part is optional."""
    p: dict = {}
    with _client() as c:
        # Current position, from the person's own ORCID record.
        try:
            r = c.get(f"{ORCID_API}/{orcid}/employments", headers={"Accept": "application/json"})
            r.raise_for_status()
            current = []
            for g in r.json().get("affiliation-group") or []:
                for s in g.get("summaries") or []:
                    e = s.get("employment-summary") or {}
                    if e.get("end-date"):
                        continue
                    org = e.get("organization") or {}
                    current.append((org.get("name"), (org.get("address") or {}).get("country"), e.get("role-title")))
            if current:
                p["affiliation"], p["country"], p["role"] = current[0]
        except (httpx.HTTPError, ValueError) as e:
            log.warning("ORCID employments %s: %s", orcid, e)
        # Citation figures and topics, only if OpenAlex's author really is this person.
        try:
            r = c.get(f"{OPENALEX_API}/authors/orcid:{orcid}", params=_openalex_params())
            if r.status_code == 200 and _name_matches(r.json().get("display_name"), family):
                a = r.json()
                stats = a.get("summary_stats") or {}
                p.update(openalex_id=(a.get("id") or "").rsplit("/", 1)[-1] or None,
                         works_count=a.get("works_count"), cited_by=a.get("cited_by_count"),
                         h_index=stats.get("h_index"),
                         topics=json.dumps([t["display_name"] for t in (a.get("topics") or [])[:5]]))
                inst = a.get("last_known_institutions") or []
                if inst and "affiliation" not in p:
                    p["affiliation"], p["country"] = inst[0].get("display_name"), inst[0].get("country_code")
        except (httpx.HTTPError, ValueError) as e:
            log.warning("OpenAlex author %s: %s", orcid, e)
        # Description, Wikipedia and photo, for people on Wikidata.
        try:
            r = c.get(WIKIDATA_API, params={"action": "query", "list": "search", "format": "json",
                                            "srsearch": f"haswbstatement:P496={orcid}"})
            ids = [h["title"] for h in r.json()["query"]["search"]][:3]
            if ids:
                r = c.get(WIKIDATA_API, params={"action": "wbgetentities", "ids": "|".join(ids), "format": "json",
                                                "props": "claims|descriptions|sitelinks", "languages": "en"})
                entities = list(r.json().get("entities", {}).values())
                entities.sort(key=lambda e: not e.get("claims", {}).get("P18"))   # one with a photo first
                e = entities[0]
                p["wikidata_id"] = e.get("id")
                p["description"] = (e.get("descriptions", {}).get("en") or {}).get("value")
                p["wikipedia"] = (e.get("sitelinks", {}).get("enwiki") or {}).get("title")
                image = e.get("claims", {}).get("P18")
                if image:
                    file = image[0]["mainsnak"]["datavalue"]["value"]
                    p["photo_url"] = f"https://commons.wikimedia.org/wiki/Special:FilePath/{file}?width=600"
                    p["photo_credit"] = f"https://commons.wikimedia.org/wiki/File:{file.replace(' ', '_')}"
        except (httpx.HTTPError, ValueError, KeyError) as e:
            log.warning("Wikidata %s: %s", orcid, e)
    return p


def photo_dir():
    d = settings.data_dir / "people"
    d.mkdir(exist_ok=True)
    return d


def save_photo(person_id: int, data: bytes) -> str:
    """Store a photo as a 4:5 portrait (cropped towards the top, where faces usually are)."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        raise PeopleError("That file is not an image Bubo can read")
    img = ImageOps.fit(img, PHOTO_SIZE, Image.LANCZOS, centering=(0.5, 0.3))
    name = f"{person_id}.webp"
    img.save(photo_dir() / name, "WEBP", quality=84)
    return name


def delete_photo(person_id: int) -> None:
    (photo_dir() / f"{person_id}.webp").unlink(missing_ok=True)


PROFILE_FIELDS = ["affiliation", "country", "role", "openalex_id", "works_count", "cited_by", "h_index",
                  "topics", "wikidata_id", "description", "wikipedia"]


def refresh_profile(conn, person_id: int) -> None:
    row = conn.execute("SELECT orcid, family_name, photo_source FROM people WHERE id = ?", (person_id,)).fetchone()
    if row is None:
        return
    p = fetch_profile(row["orcid"], row["family_name"])
    values = {k: p.get(k) for k in PROFILE_FIELDS if k in p}
    values["profile_checked"] = _now().isoformat(timespec="seconds")
    # A photo from Wikimedia Commons, unless one was uploaded (or removed) by hand.
    if p.get("photo_url") and row["photo_source"] not in ("upload", "removed"):
        try:
            with _client() as c:
                r = c.get(p["photo_url"])
                r.raise_for_status()
            values.update(photo=save_photo(person_id, r.content), photo_source="wikidata",
                          photo_credit=p.get("photo_credit"))
        except (httpx.HTTPError, PeopleError) as e:
            log.warning("Photo of person %s: %s", person_id, e)
    sets = ", ".join(f"{k} = ?" for k in values)
    conn.execute(f"UPDATE people SET {sets} WHERE id = ?", (*values.values(), person_id))
    conn.commit()


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
    try:
        refresh_profile(conn, cur.lastrowid)
    except Exception:                     # a profile is a nicety: never fail to follow for it
        log.exception("Profile of %s", orcid)
    return cur.lastrowid


def refresh_person(conn, person_id: int, full: bool = False) -> int:
    """Look for new works: the latest ones (what the radar needs), or all of them (full)."""
    row = conn.execute("SELECT orcid, family_name FROM people WHERE id = ?", (person_id,)).fetchone()
    if row is None:
        return 0
    try:
        works = fetch_works(row["orcid"], row["family_name"], full=full)
    except PeopleError as e:
        conn.execute("UPDATE people SET last_error = ? WHERE id = ?", (str(e), person_id))
        conn.commit()
        raise
    return store_works(conn, person_id, works)


def refresh_all(conn) -> int:
    new = 0
    stale = (_now() - timedelta(days=PROFILE_DAYS)).isoformat(timespec="seconds")
    for (pid, checked) in conn.execute("SELECT id, profile_checked FROM people ORDER BY id").fetchall():
        try:
            new += refresh_person(conn, pid)
        except PeopleError as e:
            log.warning("Radar: person %s: %s", pid, e)
        if not checked or checked < stale:
            try:
                refresh_profile(conn, pid)
            except Exception:
                log.exception("Profile of person %s", pid)
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
    out = []
    for r in conn.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM person_works w WHERE w.person_id = p.id) AS works, "
            "(SELECT COUNT(*) FROM person_works w WHERE w.person_id = p.id AND w.is_new = 1 "
            " AND w.dismissed_at IS NULL AND w.seen_at IS NULL) AS unseen, "
            "(SELECT COUNT(*) FROM person_works w WHERE w.person_id = p.id AND (w.item_id IS NOT NULL OR "
            " EXISTS (SELECT 1 FROM items i WHERE lower(i.doi) = w.doi))) AS in_library "
            "FROM people p ORDER BY lower(p.name)"):
        p = dict(r)
        p["topics"] = json.loads(p.get("topics") or "[]")
        p["photo_url"] = (f"/api/people/{p['id']}/photo?v={(p.get('profile_checked') or '')[:19]}{p.get('photo_source') or ''}"
                          if p.get("photo") else None)
        out.append(p)
    return out


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


def item_people(conn, item: dict) -> list[dict | None]:
    """For each author of a paper, the followed person they are (or None).

    An author is a followed person when the family names match and either the paper is
    among that person's publications (same DOI) or the first initials match too."""
    people = list_people(conn)
    if not people or not item.get("authors"):
        return [None] * len(item.get("authors") or [])
    doi = (item.get("doi") or "").lower()
    by_doi = {r[0] for r in conn.execute("SELECT person_id FROM person_works WHERE doi = ?", (doi,))} if doi else set()
    out = []
    for a in item["authors"]:
        family, given = _plain(a.get("family")), _plain(a.get("given"))
        match = None
        for p in people:
            if not family or _plain(p.get("family_name") or p["name"].split()[-1]) != family:
                continue
            p_given = _plain(p["name"].rsplit(" ", 1)[0]) if " " in p["name"] else ""
            if p["id"] in by_doi or (given and p_given and given[0] == p_given[0]):
                match = p
                break
        out.append(match and {"id": match["id"], "name": match["name"], "photo_url": match["photo_url"]})
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
