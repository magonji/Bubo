"""Maintenance commands, run inside the container:

    docker compose exec bubo python -m app.cli figures            # papers without figures yet
    docker compose exec bubo python -m app.cli figures --all      # extract every paper again
    docker compose exec bubo python -m app.cli figures --item 42
    docker compose exec bubo python -m app.cli journal-abbreviations

They can run while Bubo is running.
"""

import argparse
import os
import sys
import time

from . import db, figures, metadata
from .config import settings


def _drop_privileges() -> None:
    """`docker compose exec` runs as root: write files as the owner of the data folder,
    as the server does, so that it can manage them later."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        st = os.stat(settings.data_dir)
        if st.st_uid != 0:
            os.setgid(st.st_gid)
            os.setuid(st.st_uid)


def cmd_figures(args) -> None:
    conn = db.connect()
    if args.item:
        ids = [args.item]
    elif args.all:
        ids = [r[0] for r in conn.execute("SELECT id FROM items WHERE file_name IS NOT NULL ORDER BY id")]
    else:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM items WHERE file_name IS NOT NULL AND (figures_status IS NULL "
            "OR figures_status IN ('pending', 'error') OR figures_hash IS NOT file_hash) ORDER BY id")]
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


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Bubo maintenance commands")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("figures", help="extract the figures of papers that do not have them yet")
    p.add_argument("--all", action="store_true", help="extract the figures of every paper again")
    p.add_argument("--item", type=int, help="only this paper (its id)")
    p.set_defaults(func=cmd_figures)
    p = sub.add_parser("journal-abbreviations", help="fetch abbreviated journal names from Crossref")
    p.set_defaults(func=cmd_journal_abbreviations)
    args = parser.parse_args(argv)
    _drop_privileges()
    db.init_db()
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
