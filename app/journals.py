"""The journals in the library: a gallery of them, and a profile of each from OpenAlex.

Journals are not stored on their own: they are the venues of the papers, grouped by name
regardless of case and spacing. A journal's profile (publisher, ISSN, h-index, citations
per article, open access, home page) comes from OpenAlex when its page is opened, and is
kept for 30 days in the journals table.
"""

import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx

from . import people

log = logging.getLogger("bubo.journals")

PROFILE_DAYS = 30
COVERS = 4          # figures in a journal's mosaic


def key(name: str | None) -> str:
    return " ".join((name or "").lower().split())


def list_journals(conn) -> list[dict]:
    """Every venue in the library, with its papers counted and figures for its cover."""
    rows = conn.execute(
        "SELECT i.id, i.venue, i.venue_short, i.publisher, i.year, i.added_at, i.to_read_at, "
        "COALESCE((SELECT f.id || ':' || f.pdf_hash || ':' || IFNULL(f.fill, 0) FROM figures f WHERE f.id = i.cover_figure_id AND f.item_id = i.id), "
        " (SELECT f.id || ':' || f.pdf_hash || ':' || IFNULL(f.fill, 0) FROM figures f WHERE f.item_id = i.id ORDER BY f.idx LIMIT 1)) AS cover "
        "FROM items i WHERE i.venue IS NOT NULL AND trim(i.venue) != '' "
        "ORDER BY i.year DESC NULLS LAST, i.added_at DESC").fetchall()
    groups: dict[str, dict] = {}
    for r in rows:
        k = key(r["venue"])
        g = groups.setdefault(k, {"key": k, "names": Counter(), "short": Counter(), "publishers": Counter(),
                                  "papers": 0, "to_read": 0, "years": [], "covers": [], "last_added": ""})
        g["names"][r["venue"].strip()] += 1
        if r["venue_short"]:
            g["short"][r["venue_short"]] += 1
        if r["publisher"]:
            g["publishers"][r["publisher"]] += 1
        g["papers"] += 1
        g["to_read"] += bool(r["to_read_at"])
        if r["year"]:
            g["years"].append(r["year"])
        g["last_added"] = max(g["last_added"], r["added_at"])
        if r["cover"] and len(g["covers"]) < COVERS:
            fid, h, fill = r["cover"].split(":")
            g["covers"].append({"url": f"/api/figures/{fid}/thumb.webp?v={h[:8]}", "fill": fill == "1"})
    profiles = {r["key"]: json.loads(r["data"]) for r in conn.execute("SELECT key, data FROM journals")}
    out = []
    for k, g in groups.items():
        prof = profiles.get(k) or {}
        out.append({
            "key": k, "name": g["names"].most_common(1)[0][0],
            "short": g["short"].most_common(1)[0][0] if g["short"] else None,
            "publisher": prof.get("publisher") or (g["publishers"].most_common(1)[0][0] if g["publishers"] else None),
            "papers": g["papers"], "to_read": g["to_read"],
            "first_year": min(g["years"]) if g["years"] else None,
            "last_year": max(g["years"]) if g["years"] else None,
            "covers": g["covers"], "last_added": g["last_added"],
        })
    out.sort(key=lambda j: j["name"].lower())
    return out


def _fetch(name: str) -> dict:
    """OpenAlex's source with this exact name (ignoring case and accents), or {}."""
    with people._client() as c:
        r = c.get(f"{people.OPENALEX_API}/sources", params=people._openalex_params(search=name, **{"per-page": 5}))
        r.raise_for_status()
    want = people._plain(name)
    for s in r.json().get("results") or []:
        names = [s.get("display_name") or ""] + (s.get("alternate_titles") or []) + [s.get("abbreviated_title") or ""]
        if any(people._plain(n) == want for n in names if n):
            stats = s.get("summary_stats") or {}
            return {
                "openalex_id": (s.get("id") or "").rsplit("/", 1)[-1] or None,
                "display_name": s.get("display_name"),
                "publisher": s.get("host_organization_name"),
                "issn": s.get("issn_l") or ((s.get("issn") or [None])[0]),
                "type": s.get("type"),
                "homepage": s.get("homepage_url"),
                "is_oa": s.get("is_oa"), "in_doaj": s.get("is_in_doaj"),
                "works_count": s.get("works_count"), "cited_by": s.get("cited_by_count"),
                "h_index": stats.get("h_index"),
                "mean_citedness": round(stats["2yr_mean_citedness"], 1) if stats.get("2yr_mean_citedness") is not None else None,
                "country": s.get("country_code"),
            }
    return {}


def profile(conn, name: str, refresh: bool = False) -> dict:
    """A journal's profile, from the cache or (at most every 30 days) from OpenAlex."""
    k = key(name)
    row = conn.execute("SELECT data, checked_at FROM journals WHERE key = ?", (k,)).fetchone()
    stale = (datetime.now(timezone.utc) - timedelta(days=PROFILE_DAYS)).isoformat(timespec="seconds")
    if row and not refresh and row["checked_at"] >= stale:
        return json.loads(row["data"])
    try:
        data = _fetch(name)
    except (httpx.HTTPError, ValueError) as e:
        log.warning("OpenAlex source %r: %s", name, e)
        return json.loads(row["data"]) if row else {}
    conn.execute("INSERT INTO journals (key, data, checked_at) VALUES (?, ?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET data = excluded.data, checked_at = excluded.checked_at",
                 (k, json.dumps(data), datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()
    return data
