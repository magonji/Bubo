# <img src="app/static/owl.svg" alt="" width="40" align="top"> Bubo

A self-hosted reference manager: your papers and PDFs live on your own server, and you manage
them from the browser.

**Website, with screenshots: [magonji.github.io/Bubo](https://magonji.github.io/Bubo/)**

## Features

- **Home**, the page Bubo opens on: the library at a glance in the whole window but the
  sidebar. Its figures (papers, to read, new on the radar, journals, people) lead to each
  section, under them are the papers added most recently, your reading list, what is new on
  the radar, papers with incomplete metadata (with **Find** for each), your journals and the
  people you follow. In Settings, **Open Bubo on** chooses between Home, My library and the
  Radar. The owl in the header also leads home.
- **Add papers** with the **+ Add** button: one box accepts a DOI (or doi.org link), an arXiv ID,
  a PubMed ID or a publisher's URL and detects which it is; if an open-access PDF is available,
  it is downloaded automatically. The same dialog takes PDFs by drag and drop (or choose them),
  with a collection to file them in and each file's progress and result, and **Add manually**
  creates an entry for a paper without a PDF. Pasting a DOI, arXiv ID, `PMID:` or URL into the
  search box offers to add it instead of searching for it. Dropping PDFs anywhere on the window,
  or onto a collection in the sidebar, also opens the dialog. Bubo reads each PDF, looks for a
  DOI or an arXiv stamp and fills in the metadata from Crossref or arXiv. If it finds neither
  (older papers, scans), it searches Crossref as it would a reference, with the top of the
  first page (journal, year, title, authors) and with the file name when it reads "Authors -
  Year - Title", and only takes a result whose title is on that page, or in the file name,
  and whose year and first author match. Papers that are not online at all (many book
  chapters) get their title, authors and year from the file name. **Find metadata online**,
  in a paper's menu, does the same search for papers already in your library.
- **Scanned PDFs** (pages that are only pictures) are read with OCR (Tesseract, in English,
  German, Spanish and French): the first two pages at once, to identify the paper, and the
  rest in the background, so their text can be searched and its matches shown. Scans already
  in your library are read too, one at a time. The PDF itself is not changed.
- **Supplementary information**: keep any number of SI files with a paper (PDFs,
  spreadsheets, data, videos…). In the upload dialog each file can be declared as a paper or
  as supplementary information for another PDF in the same upload, for the paper open in the
  item pane, or for any paper in the library; files whose names look like SI ("SI", "ESI",
  "supplementary", "mmc1"…) and files that are not PDFs are marked as such automatically.
  They can also be added from the paper's pane. They are stored next to the paper as
  `… - SI.pdf`, `… - SI 2.xlsx`, and the text of SI PDFs is included in search.
- **Figures**: when a paper gets a PDF, Bubo finds its figures in the background: the drawings,
  images and labels next to each "Figure N" caption (vector plots keep their axes) and embedded
  images that no caption claims, ignoring logos and small images. They are kept with their
  captions as thumbnails for the phone layout and a figure carousel. Any figure can be made the
  paper's cover. For papers added earlier, run `python -m app.cli figures` (see below).
- **The paper's pane** on the right of the library shows the selected paper the same way as
  the phone's paper screen: its figures, journal and year, title, an Open PDF button, Cite and
  Collection, the abstract, details, collections, tags, notes saved as you type and related
  papers, plus the search matches and annotations. The ⋯ menu holds the other actions, and
  **Edit details** opens the form with every field.
- **On phones and tablets held upright** (screens up to 760 px, and touch screens up to
  1100 px such as an iPad in portrait) the library is a gallery of figure cards or a list with
  thumbnails under a compact header (the section and its count, a sort button that opens a
  sheet, the search box and the layout switch; the top row slides away as you scroll down),
  with a floating button to add papers. Each paper has its own screen at `/paper/<id>`: a carousel of its figures,
  the abstract, details with a copyable DOI, collections, tags, notes saved as you type and
  related papers, with buttons to open the PDF, cite, file and share it. Papers without figures
  get a cover coloured from the journal's name. Bubo can be added to the home screen, where it
  opens like an app with the owl as its icon. On a computer the table stays as it is.
- **People** shows everyone who wrote the papers in your library as a wall of portraits, like
  a library of books or films, with the people you follow first. Each author's ORCID iD is
  looked for in every way Bubo can: Crossref, OpenAlex (50 papers per request), the ORCID
  records that list the paper, and the iDs printed or linked in the PDF. An iD is only given
  to an author whose name matches it, as these records are sometimes wrong. This happens in
  the background when you add a paper and, once, for the whole library. Authors with no iD
  are told apart by family name and initial. A second layout shows People as a table (photo,
  name, family name, affiliation and h-index), sorted by any column.
- **Follow scientists** from a paper's author list (**Follow authors** on its sheet: tick
  whoever you want, and paste an iD Bubo did not find), from their page, or anyone by their
  ORCID iD (the **+** next to "Following" in the sidebar). Bubo lists each person's
  publications, from their ORCID record and from OpenAlex, with an **Add** button for those
  not yet in your library (by DOI they come in with full metadata and, when there is one, an
  open-access PDF). Every 12 hours it looks for new ones: publications from the last two
  months appear on the **Radar**, marked as new until you open it. OpenAlex sometimes credits
  a paper to the wrong ORCID iD, so its papers only count when the name printed on them
  matches the person's.
- **A person's page** has their papers in your library (all their publications, for people
  you follow), their current position (from ORCID), citations, h-index and research topics
  (from OpenAlex), a short description and Wikipedia link (from Wikidata) and, for scientists
  with a picture on Wikimedia Commons, their photo; for anyone else you can add one yourself
  (the camera button), or Bubo shows their initials. All this is filled in in the background
  for every author OpenAlex or ORCID knows, so it is in People without opening anyone's page:
  OpenAlex and Wikidata are asked about 50 people at a time, ORCID one by one, and profiles
  are renewed every three days (`BUBO_PROFILE_DAYS`), so affiliations and h-indexes stay
  current.
  On a paper's sheet every author links to their page, authors with a photo appear with it,
  and the people you follow stand out.
- **Merge people** whose name is spelt differently on some papers (**Merge with…** on a
  person's page, which suggests likely duplicates): their papers, ORCID iD, photo and follow
  become one person's, under the name you choose, and Bubo remembers the other spelling for
  papers you add later. The papers' author lists stay as printed. People with different ORCID
  iDs cannot be merged.
- **My papers**: find yourself in People and choose **This is me**. The papers you are an
  author of then get an entry of their own in the sidebar and a row on the home page, with
  how often each has been cited (OpenAlex; sort by "Most cited"), their total and h-index,
  and your OpenAlex h-index. With your ORCID iD, the page also lists your publications that
  are not in your library yet, each with an Add button, or Ignore to stop listing it. The home page shows the latest
  works citing your papers, and which of them each cites (new ones marked). Citations and
  publications are checked again every 3 days (BUBO_PROFILE_DAYS).
- **Journals** gathers the journals your papers were published in as a shelf of covers, each
  made from the figures of your latest papers in it. A journal's page lists your papers in it
  under its publisher, h-index, citations per article and open-access status (from OpenAlex,
  looked up when you open the page and kept for 30 days). The journal on a paper's sheet
  links to it.
- **Trash**: deleted papers go to the trash (with an **Undo** button), keeping their PDF, notes,
  annotations and figures. From there you can restore them, delete them for good, or empty the
  trash; papers in it for more than 30 days are deleted for good. Adding a paper that is in
  the trash brings it back.
- **Find PDF** for papers without one (the dimmed icon in the PDF column, or the button in the
  item pane): looks on arXiv, Unpaywall (with `BUBO_CONTACT_EMAIL` set) and the publisher's page.
- **The order you choose** (by year, date added, title or author) is remembered between visits.
- **Library table** with a comfortable layout (authors and venue under the title) or a compact
  one, or the papers shown by their figures: a **gallery** of cards or a **list with figures**
  (the buttons next to the list's title; these layouts have an Order menu instead of column
  headings, and their cards can be selected and dragged like rows). Papers are listed newest
  first (by publication year); the table can be sorted by any column, including the date
  added, and has a reading-list column and icons for notes and PDFs. Shift-click selects a
  range and Cmd/Ctrl-click adds or removes papers, for bulk actions or for dragging several
  papers onto a collection at once. With nothing selected (click an empty part of the list,
  or press Escape), the pane closes and the list takes the whole width; the home page shows
  the library at a glance.
- A **reading list** for papers you want to read: add or remove a paper with the bookmark button
  in its pane, or drag papers onto "Reading list" in the sidebar. Papers on it are marked in the
  library list. New papers can go straight onto it: turn on "Put new papers on the reading
  list" in Settings (it also sets the default of the "Add to reading list" box in the upload
  dialog, which can be changed for a single upload). Like every list it shows the newest
  papers first; it can also work as a queue, ordered by when each paper was put on it
  (oldest or newest first), or be sorted by any column.
- Nested **collections**, **tags** and **notes**. Drag papers onto a collection to add them;
  drag a collection onto another to move it inside, or onto the "Collections" heading to move
  it back to the top level. "Include subcollections" makes a collection also list the papers
  in its subcollections.
- **Full-text search** across titles, authors, abstracts, notes, annotations and the contents
  of the PDFs (SQLite FTS5; accent-insensitive, words match by prefix). Each result shows the
  sentence where the search was found, and the item pane lists every matching sentence of the
  PDF with its page number: clicking one opens the viewer at that page with the words highlighted.
- Built-in **PDF viewer** with **highlights and notes**: select text to highlight it in one of six
  colours, add a comment to any highlight, or pin a note anywhere on a page. Annotations are stored
  on the server (the original PDF is never modified), appear in the item's detail pane, are
  included in search, and can be exported as a copy of the PDF with standard PDF annotations
  embedded, readable in any other PDF reader.
- **Copy citation** in your favourite style (APA 7, Chicago author-date, MLA 9, Harvard, IEEE or
  Vancouver, chosen in Settings). It is copied with formatting, so italics survive pasting
  into a word processor, and as plain text.
- **BibTeX**: copy a single item's entry, or export the papers in the current view to a `.bib`
  file from the menu (the three-line button at the top right, which also holds Settings and Sign out).
- **Refresh metadata** from Crossref or arXiv with a field-by-field comparison: tick the fields
  to replace, so manual corrections are never overwritten by surprise.
- Duplicate detection (by file, DOI and arXiv ID).

Keyboard shortcuts: `/` or Cmd/Ctrl+K focuses the search box, `↑`/`↓` move the selection, `Enter` opens the
PDF. In the viewer: `+`/`-` zoom, `0` fits to width, `N` adds a note, `Delete` removes the
selected annotation and `Esc` closes it.

## Deploying with Docker

The image is built by GitHub Actions and published as `ghcr.io/magonji/bubo`, for both
x86-64 and ARM (such as a Raspberry Pi), so the server needs only two files:

```bash
mkdir bubo && cd bubo
src=https://raw.githubusercontent.com/magonji/Bubo/main
curl -fsSLO $src/docker-compose.yml
curl -fsSL $src/.env.example -o .env
nano .env                         # set BUBO_PASSWORD and BUBO_DATA_DIR
mkdir -p /path/to/your/data       # the data folder must exist (see below)
docker compose up -d
```

Open `http://localhost:2826`.

**Updating:** `docker compose pull && docker compose up -d`. The library in the data folder is
kept, and the database is upgraded automatically if needed. After updating from a version
without figure extraction, run `docker compose exec bubo python -m app.cli figures` once to
find the figures of the papers you already have (see [Maintenance commands](#maintenance-commands)).

The `latest` tag follows the main branch and is rebuilt a few minutes after each change. Every
build is also tagged with its commit (for example `sha-3b6e58d`), and releases tagged
`vX.Y.Z` get `X.Y.Z` and `X.Y` tags. To stay on one of them, change the `image:` line in
`docker-compose.yml`; the [package page](https://github.com/magonji/Bubo/pkgs/container/bubo)
lists the available tags.

If you set Bubo up earlier by cloning the repository, run `git pull` once to get the new
`docker-compose.yml`, then `docker compose pull && docker compose up -d`.

To build the image yourself instead (for example after changing the code), clone the
repository, replace `image:` with `build: .` in `docker-compose.yml` and run
`docker compose up -d --build`.

### Where your data lives

Set `BUBO_DATA_DIR` in `.env` to the folder on the server that should hold the library
(`./data` next to `docker-compose.yml` by default). It looks like this:

```
<BUBO_DATA_DIR>/
├── library.db          # SQLite database: metadata, collections, tags, annotations, search index
├── papers/             # all the PDFs, in one folder
│   ├── Brown et al. - 2020 - Language Models are Few-Shot Learners.pdf
│   ├── Brown et al. - 2020 - Language Models are Few-Shot Learners - SI.pdf
│   ├── Krizhevsky et al. - 2012 - ImageNet Classification with Deep Convolutional Neural Networks.pdf
│   └── Vaswani et al. - 2017 - Attention Is All You Need.pdf
├── figures/            # figures extracted from the PDFs (WebP), one folder per paper
└── .secret_key         # session key generated on first start-up
```

- Files are named `First author(s) - Year - Title.pdf`; clashing names get ` (2)`, ` (3)`…
- Collections and tags exist only inside Bubo, so a paper can be in any number of
  collections without being copied or moved.
- Files are renamed automatically when you edit a paper's authors, year or title.
  Annotations are kept in `library.db`, never in the PDFs.
- **Treat `papers/` as read-only.** Browse and copy from it freely, but rename or delete papers
  from within Bubo, otherwise it will lose track of the files.
- Names are kept valid on exFAT, NTFS and FAT32 (characters such as `: ? * " < > |` are
  replaced) and are compared case-insensitively.

**Backups:** copying the data folder is enough (ideally with the container stopped, or use
`sqlite3 library.db ".backup backup.db"` while it is running).

### Using an external disk

1. Mount the disk at a fixed path and create a folder for Bubo on it, e.g.
   `/mnt/external/bubo`, then set `BUBO_DATA_DIR=/mnt/external/bubo` in `.env`.
2. **ext4 / btrfs / xfs:** nothing else to do. On start-up the container hands the folder to the
   user it runs as.
3. **exFAT / NTFS / FAT32:** these have no Unix permissions; the owner of every file is set by
   the mount options. Mount the disk with the uid/gid Bubo runs as (1000 by default).
   Find the disk's UUID with `sudo blkid`, then add a line like this to `/etc/fstab`:

   ```
   UUID=XXXX-XXXX  /mnt/external  exfat  defaults,nofail,uid=1000,gid=1000,umask=022  0  0
   ```

   (for NTFS use `ntfs3` instead of `exfat`). Then run `sudo mount -a`. If the disk is
   already mounted with another uid, you can instead set `PUID`/`PGID` in `.env` to match it.

If the data folder does not exist (for example because the disk is not mounted), Docker
refuses to start the container rather than silently creating an empty library on the
internal disk. Once the disk is mounted, run `docker compose up -d` again (or rely on
`restart: unless-stopped`).

### Permissions

The container starts as root only to prepare the data folder, then runs Bubo as an
unprivileged user:

- `PUID`/`PGID` in `.env` choose that user. If they are empty, the owner of the data folder
  is used, or 1000 if the folder belongs to root.
- If the folder belongs to someone else and the filesystem allows it, it is handed over to
  that user. If Bubo still cannot write to it, the container stops with a message
  explaining what to change.

### HTTPS

`docker-compose.yml` only publishes the port on `127.0.0.1`. To reach it from elsewhere, put it
behind an HTTPS reverse proxy and add `BUBO_SECURE_COOKIES=true` to `.env`. With Caddy:

```
papers.yourdomain.com {
    reverse_proxy 127.0.0.1:2826
}
```

If you use nginx, raise `client_max_body_size` (e.g. `200m`) so that large PDFs can be uploaded.

### Configuration (`.env`)

| Variable | Description |
|---|---|
| `BUBO_PASSWORD` | Sign-in password (required). |
| `BUBO_DATA_DIR` | Data folder on the host (default `./data`). Must exist. |
| `BUBO_PORT` | Port on `127.0.0.1` for the web interface (default 2826). |
| `PUID` / `PGID` | User and group Bubo runs as (default: owner of the data folder). |
| `BUBO_CONTACT_EMAIL` | Optional. Enables open-access PDF lookup via Unpaywall and is sent to Crossref and PubMed to use their polite pools. It can also be set in Settings, which takes precedence. |
| `BUBO_SECURE_COOKIES` | `true` when served over HTTPS. |
| `BUBO_SESSION_DAYS` | Session length in days (default 30). |
| `BUBO_RADAR_HOURS` | How often to look for new publications by the people you follow (default 12; 0 turns it off; "Check now" still works). |
| `BUBO_OCR` | `1` (default) reads the text of scanned PDFs; `0` turns it off. |
| `BUBO_OCR_LANGS` | The languages to read scans in, among those in the image (default `eng+deu+spa+fra`). |
| `BUBO_PROFILE_DAYS` | How often, in days, the authors' affiliations, h-indexes, topics and photos are looked at again (default `3`). |
| `BUBO_ORCID_LOOKUP` | `1` (default) looks for the ORCID iDs of the authors of your papers in the background; `0` turns it off. |
| `BUBO_OPENALEX_API_KEY` | Optional. Without a key, OpenAlex lets all requests from your IP address share a small free daily budget; Bubo asks for little, but a [free key](https://openalex.org/settings/api) gives you your own. |
| `BUBO_SECRET` | Optional session key; otherwise one is generated in `data/.secret_key`. |

### Maintenance commands

Run them inside the container, while Bubo is running if you like:

```bash
docker compose exec bubo python -m app.cli figures                 # papers without figures yet
docker compose exec bubo python -m app.cli figures --all           # extract every paper's figures again
docker compose exec bubo python -m app.cli figures --report        # papers without a figure, and why
docker compose exec bubo python -m app.cli journal-abbreviations   # "Nat. Commun." etc., from Crossref
docker compose exec bubo python -m app.cli find-metadata           # look online for papers without a DOI
docker compose exec bubo python -m app.cli find-metadata --apply   # …and take what is found
```

`find-metadata` looks for every paper without a DOI or arXiv ID as **Find metadata online**
does, and lists what it finds; with `--apply` it takes it (and renames the PDFs to match).

The first fills in the figures of papers added before figure extraction existed, and looks
again at papers where an older version of Bubo found none; new papers get theirs
automatically. `--report` lists the papers that have no figure and the reason: no PDF, not
looked at yet, an error, or no figures found (for instance a scanned PDF without text). The second asks Crossref for the abbreviated journal name of papers with a
DOI (new papers get it when they are added); it is shown in the phone list.

## Licence

Bubo is free software, released under the [GNU Affero General Public License v3.0](LICENSE)
(AGPL-3.0). You may use, study, change and share it. If you run a modified version for other
people over a network, you must offer them its source code; the "Source code" link in the menu
points to this repository, so change it if you publish a modified copy elsewhere.

Bundled third-party components keep their own licences: [PDF.js](https://github.com/mozilla/pdf.js)
(Apache-2.0, `app/static/vendor/pdfjs/LICENSE`) and the Fraunces and Inter fonts (SIL Open
Font License, `app/static/fonts/`). Bubo uses [PyMuPDF](https://pymupdf.readthedocs.io/), which
is also licensed under the AGPL-3.0, and [Pillow](https://python-pillow.org/) (MIT-CMU licence).

## Development

```bash
uv venv .venv && uv pip install -p .venv -r requirements-dev.txt
BUBO_PASSWORD=demo BUBO_DATA=./data .venv/bin/uvicorn app.main:app --reload
.venv/bin/python -m pytest -q
```

Layout:

- `app/main.py`: HTTP API (FastAPI) and sessions
- `app/db.py`: SQLite schema, items, collections, tags and search
- `app/metadata.py`: Crossref, arXiv, Unpaywall and web-page metadata extraction
- `app/pdf.py`: text and metadata hints from PDFs (PyMuPDF)
- `app/bibtex.py`: BibTeX export
- `app/annotate.py`: embeds annotations into an exported copy of a PDF
- `app/storage.py`: the `papers/` folder (readable names, renames, migration of older layouts)
- `app/figures.py`: finds figures in PDFs and stores them as WebP thumbnails (PyMuPDF, Pillow)
- `app/cli.py`: maintenance commands
- `app/authors.py`: every author as a person, and looking for their ORCID iDs
- `app/ocr.py`: reading the text of scanned PDFs with Tesseract
- `app/people.py`: following scientists by ORCID iD, profiles and the radar (ORCID, OpenAlex and Wikidata APIs)
- `docker-entrypoint.sh`: data-folder permissions, then drops privileges
- `app/static/`: web interface (plain HTML/CSS/JS, no build step); `viewer.js` is the PDF viewer
  and `paper.js` the paper screen on phones; `people.js` shows people, the people you follow and the radar
- `app/static/fonts/`: Fraunces (the name, titles on phones) and Inter (the phone layout),
  both under the SIL Open Font License
- `app/static/vendor/pdfjs/`: [PDF.js](https://github.com/mozilla/pdf.js) 6.4.299 (Apache-2.0),
  bundled so that the server needs no external CDN. `legacy/` holds the same version's legacy
  build, which the viewer uses in browsers without the latest JavaScript (such as Safari on
  iOS and iPadOS 17 and 18)

Annotation rectangles are stored in PDF user-space coordinates, so they stay aligned at any zoom
level and survive exporting.
