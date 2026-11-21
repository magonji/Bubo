"""Maintenance commands, run inside the container:

    docker compose exec bubo python -m app.cli figures            # papers without figures yet
    docker compose exec bubo python -m app.cli figures --all      # extract every paper again
    docker compose exec bubo python -m app.cli figures --item 42
    docker compose exec bubo python -m app.cli figures --report   # papers without a figure, and why
    docker compose exec bubo python -m app.cli journal-abbreviations

They can run while Bubo is running.
"""

import argparse
import os
import sys
import time

from . import db, figures, metadata, storage

REASONS = {
    "no-pdf": "No PDF attached: add one, or use Find PDF",
    None: "Not looked at yet: run 'python -m app.cli figures'",
    "pending": "Being extracted now, or interrupted: run 'python -m app.cli figures'",
    "error": "Extraction failed: run 'python -m app.cli figures' to try again and see the error",
    "none": "No figures found in the PDF",
    "old": "No figures found by an older version: run 'python -m app.cli figures' to look again",
}
from .config import settings


def _drop_privileges() -> None:
    """`docker compose exec` runs as root: write files as the owner of the data folder,
    as the server does, so that it can manage them later."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        st = os.stat(settings.data_dir)
        if st.st_uid != 0:
            os.setgid(st.st_gid)
            os.setuid(st.st_uid)


def figures_report(conn) -> None:
    rows = conn.execute(
        "SELECT i.id, i.title, i.venue, i.file_name, i.figures_status, i.figures_version FROM items i "
        "WHERE NOT EXISTS (SELECT 1 FROM figures f WHERE f.item_id = i.id) ORDER BY i.id").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    groups: dict = {}
    for r in rows:
        if not r["file_name"]:
            key = "no-pdf"
        elif r["figures_status"] == "none" and (r["figures_version"] or 0) < figures.VERSION:
            key = "old"
        else:
            key = r["figures_status"]
        groups.setdefault(key, []).append(r)
    print(f"{total - len(rows)} of {total} papers have figures.")
    for key in ("no-pdf", None, "pending", "error", "old", "none"):
        if key not in groups:
            continue
        print(f"\n{REASONS[key]} ({len(groups[key])}):")
        for r in groups[key]:
            venue = f" ({r['venue']})" if r["venue"] else ""
            print(f"  [{r['id']}] {(r['title'] or '(untitled)')[:80]}{venue}")


def cmd_figures(args) -> None:
    conn = db.connect()
    if args.report:
        return figures_report(conn)
    if args.item:
        ids = [args.item]
    elif args.all:
        ids = [r[0] for r in conn.execute("SELECT id FROM items WHERE file_name IS NOT NULL ORDER BY id")]
    else:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM items WHERE file_name IS NOT NULL AND (figures_status IS NULL "
            "OR figures_status IN ('pending', 'error') OR figures_hash IS NOT file_hash "
            "OR (figures_status = 'none' AND IFNULL(figures_version, 0) < ?)) ORDER BY id",
            (figures.VERSION,))]
    if not ids:
        print("Every paper already has its figures.")
        return
    total = 0
    for n, item_id in enumerate(ids, 1):
        title = (conn.execute("SELECT title FROM items WHERE id = ?", (item_id,)).fetchone() or [""])[0]
        try:
            count = figures.extract_item(conn, item_id, force=True)
        except Exception as e:     # one broken PDF should not stop the rest
            conn.execute("UPDATE items SET figures_status = 'error' WHERE id = ?", (item_id,))
            conn.commit()
            print(f"[{n}/{len(ids)}] {title[:70]}: failed ({e})")
            continue
        total += count or 0
        print(f"[{n}/{len(ids)}] {title[:70]}: {count or 0} figure{'s' if count != 1 else ''}")
    print(f"Done: {total} figures from {len(ids)} paper{'s' if len(ids) != 1 else ''}.")


def cmd_journal_abbreviations(args) -> None:
    """Fetch the abbreviated journal name from Crossref for papers with a DOI."""
    conn = db.connect()
    rows = conn.execute("SELECT id, doi, title FROM items WHERE doi IS NOT NULL AND doi != '' "
                        "AND (venue_short IS NULL OR venue_short = '') ORDER BY id").fetchall()
    if not rows:
        print("Every paper with a DOI already has its journal abbreviation.")
        return
    found = 0
    for n, r in enumerate(rows, 1):
        try:
            short = metadata.fetch_crossref(r["doi"]).get("venue_short")
        except Exception as e:
            print(f"[{n}/{len(rows)}] {r['title'][:70]}: failed ({e})")
            continue
        if short:
            conn.execute("UPDATE items SET venue_short = ? WHERE id = ?", (short, r["id"]))
            conn.commit()
            found += 1
        print(f"[{n}/{len(rows)}] {r['title'][:70]}: {short or 'none on Crossref'}")
        time.sleep(0.2)            # be gentle with Crossref
    print(f"Done: {found} of {len(rows)} papers now have an abbreviation.")


def cmd_find_metadata(args) -> None:
    """Look online for papers without a DOI or arXiv ID (older papers, scans) and, with
    --apply, take what is found."""
    conn = db.connect()
    rows = conn.execute("SELECT id, file_name FROM items WHERE IFNULL(doi, '') = '' AND IFNULL(arxiv_id, '') = '' "
                        "AND deleted_at IS NULL ORDER BY id").fetchall()
    if not rows:
        print("Every paper has a DOI or an arXiv ID.")
        return
    found = 0
    for n, r in enumerate(rows, 1):
        item = db.get_item(conn, r["id"])
        data = None
        if r["file_name"]:
            try:
                data = storage.abs_path(r["file_name"]).read_bytes()
            except OSError:
                pass
        label = f"[{n}/{len(rows)}] {(item['title'] or '(untitled)')[:60]}"
        try:
            meta = metadata.find_for_item(item, data)
        except Exception as e:
            print(f"{label}: failed ({e})")
            continue
        if not meta:
            print(f"{label}: not found online")
            continue
        found += 1
        changes = metadata.diff(item, meta)
        print(f"{label}: found {meta.get('doi') or ''} “{(meta.get('title') or '')[:70]}” ({meta.get('year') or '?'})")
        if args.apply and changes:
            db.update_item(conn, r["id"], {c["field"]: c["new"] for c in changes})
            storage.sync_item(conn, r["id"])
        time.sleep(1)              # be gentle with Crossref
    verb = "updated" if args.apply else "found (run again with --apply to take them)"
    print(f"Done: {found} of {len(rows)} papers {verb}.")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Bubo maintenance commands")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("figures", help="extract the figures of papers that do not have them yet")
    p.add_argument("--all", action="store_true", help="extract the figures of every paper again")
    p.add_argument("--item", type=int, help="only this paper (its id)")
    p.add_argument("--report", action="store_true", help="list the papers without a figure, and why")
    p.set_defaults(func=cmd_figures)
    p = sub.add_parser("journal-abbreviations", help="fetch abbreviated journal names from Crossref")
    p.set_defaults(func=cmd_journal_abbreviations)
    p = sub.add_parser("find-metadata", help="look online for papers without a DOI (older papers, scans)")
    p.add_argument("--apply", action="store_true", help="take what is found (otherwise, only list it)")
    p.set_defaults(func=cmd_find_metadata)
    args = parser.parse_args(argv)
    _drop_privileges()
    db.init_db()
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
