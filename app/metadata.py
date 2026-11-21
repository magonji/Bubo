"""Metadata retrieval: Crossref (DOI), arXiv, Unpaywall and web pages."""

import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from html import unescape
from html.parser import HTMLParser
from urllib.parse import quote, urljoin

import httpx

from . import pdf
from .config import settings

TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MAX_PDF_BYTES = 200 * 1024 * 1024

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", re.I)
ARXIV_NEW_RE = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?![\d])")
ARXIV_OLD_RE = re.compile(r"\b([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?\b")
ARXIV_STAMP_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)",
                            re.I)


class MetadataError(Exception):
    pass


def _client() -> httpx.Client:
    ua = "Bubo/0.1 (self-hosted reference manager)"
    if settings.contact_email:
        ua += f" (mailto:{settings.contact_email})"
    return httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                        headers={"User-Agent": ua})


# --------------------------------------------------------------------------- #
# Identifiers
# --------------------------------------------------------------------------- #

def clean_doi(doi: str) -> str:
    doi = doi.strip()
    doi = re.sub(r"(?i)^(https?://(dx\.)?doi\.org/|doi:\s*)", "", doi)
    doi = doi.rstrip(".,;:")
    # Strip trailing brackets unless they are balanced within the DOI.
    while doi and doi[-1] in ")]}" and doi.count(doi[-1]) > doi.count({")": "(", "]": "[", "}": "{"}[doi[-1]]):
        doi = doi[:-1]
    return doi


def find_doi(text: str) -> str | None:
    m = DOI_RE.search(text)
    return clean_doi(m.group(1)) if m else None


def find_arxiv(text: str, strict: bool = False) -> str | None:
    """strict=True only accepts the 'arXiv:XXXX.XXXXX' form (the stamp on arXiv PDFs)."""
    m = ARXIV_STAMP_RE.search(text)
    if m:
        return m.group(1)
    if strict:
        return None
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:\.pdf)?(?:[?#\s]|$)", text, re.I)
    if m:
        return m.group(1)
    return None


PMID_URL_RE = re.compile(r"(?i)pubmed\.ncbi\.nlm\.nih\.gov/(\d{1,9})")


def classify(identifier: str) -> tuple[str, str]:
    """('doi' | 'arxiv' | 'pmid' | 'url', value). Bare numbers are taken as PubMed IDs."""
    s = identifier.strip()
    if re.match(r"(?i)^https?://", s):
        if re.search(r"(?i)arxiv\.org/(abs|pdf)/", s):
            return "arxiv", find_arxiv(s)
        if re.search(r"(?i)//(dx\.)?doi\.org/", s):
            return "doi", clean_doi(s)
        if m := PMID_URL_RE.search(s):
            return "pmid", m.group(1)
        return "url", s
    if m := re.fullmatch(r"(?i)(?:pmid:?\s*)?(\d{1,9})", s):
        return "pmid", m.group(1)
    if re.match(r"(?i)^(doi:\s*)?10\.\d{4,9}/\S+$", s):
        return "doi", clean_doi(s)
    s2 = re.sub(r"(?i)^arxiv:\s*", "", s)
    if ARXIV_NEW_RE.fullmatch(s2) or ARXIV_OLD_RE.fullmatch(s2):
        return "arxiv", s2
    raise MetadataError("Unrecognised identifier: please use a DOI, an arXiv ID, a PubMed ID or a URL")


# --------------------------------------------------------------------------- #
# Crossref
# --------------------------------------------------------------------------- #

CROSSREF_TYPES = {
    "journal-article": "article",
    "proceedings-article": "inproceedings",
    "book": "book", "monograph": "book", "edited-book": "book", "reference-book": "book",
    "book-chapter": "incollection", "book-section": "incollection", "book-part": "incollection",
    "dissertation": "phdthesis",
    "report": "techreport",
    "posted-content": "preprint",
}


def _strip_tags(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(re.sub(r"\s+", " ", s)).strip()
    s = re.sub(r"(?i)^abstract[\s.:]*", "", s)
    return s or None


def plain(s: str | None) -> str | None:
    """Text without HTML: Crossref and publishers' pages send names like "Organic &amp;
    Biomolecular Chemistry" (and now and then tags), which would otherwise be stored as such."""
    if not s:
        return s
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s))).strip() or None


def _orcid(value: str | None) -> str | None:
    m = re.search(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", value or "", re.I)
    return m.group(1).upper() if m else None


def _crossref_to_meta(m: dict) -> dict:
    year = None
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (m.get(key) or {}).get("date-parts") or [[None]]
        if parts and parts[0] and parts[0][0]:
            year = parts[0][0]
            break
    authors = [{"given": plain(a.get("given")) or "", "family": plain(a.get("family") or a.get("name")) or "",
                **({"orcid": o} if (o := _orcid(a.get("ORCID"))) else {})}
               for a in m.get("author") or m.get("editor") or []]
    title = " ".join(m.get("title") or [""])
    subtitle = " ".join(m.get("subtitle") or [])
    if subtitle and subtitle.lower() not in title.lower():
        title = f"{title}: {subtitle}"
    return {
        "item_type": CROSSREF_TYPES.get(m.get("type"), "misc"),
        "title": _strip_tags(title) or "",
        "authors": authors,
        "year": year,
        "venue": plain((m.get("container-title") or [None])[0]),
        "venue_short": plain((m.get("short-container-title") or [None])[0]),
        "volume": m.get("volume"),
        "issue": m.get("issue"),
        "pages": (m.get("page") or "").replace("-", "–") or None,
        "publisher": plain(m.get("publisher")),
        "doi": m.get("DOI"),
        "url": m.get("URL"),
        "abstract": _strip_tags(m.get("abstract")),
    }


def fetch_crossref(doi: str) -> dict:
    with _client() as c:
        r = c.get(f"https://api.crossref.org/works/{quote(doi, safe='/')}")
    if r.status_code == 404:
        raise MetadataError(f"DOI not found in Crossref: {doi}")
    r.raise_for_status()
    return _crossref_to_meta(r.json()["message"])


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def search_crossref_title(title: str) -> dict | None:
    """Search by title, accepting a result only if the title is a near-exact match."""
    with _client() as c:
        r = c.get("https://api.crossref.org/works",
                  params={"query.bibliographic": title, "rows": 5})
    r.raise_for_status()
    target = _norm_title(title)
    for m in r.json()["message"].get("items", []):
        cand = _norm_title(" ".join(m.get("title") or []))
        if cand and SequenceMatcher(None, target, cand).ratio() >= 0.92:
            return _crossref_to_meta(m)
    return None


# --------------------------------------------------------------------------- #
# arXiv
# --------------------------------------------------------------------------- #

ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _split_name(name: str) -> dict:
    name = re.sub(r"\s+", " ", name).strip()
    if "," in name:
        family, given = [p.strip() for p in name.split(",", 1)]
        return {"given": given, "family": family}
    parts = name.split(" ")
    # Common particles ("van", "de la", ...) belong to the surname.
    i = len(parts) - 1
    while i > 0 and parts[i - 1].lower() in {"van", "von", "de", "del", "der", "da", "di", "la", "le"}:
        i -= 1
    return {"given": " ".join(parts[:i]), "family": " ".join(parts[i:])}


def fetch_arxiv(arxiv_id: str) -> dict:
    with _client() as c:
        r = c.get("https://export.arxiv.org/api/query",
                  params={"id_list": arxiv_id, "max_results": 1})
    r.raise_for_status()
    root = ET.fromstring(r.text)
    entry = root.find("a:entry", ATOM)
    if entry is None or entry.find("a:title", ATOM) is None:
        raise MetadataError(f"arXiv ID not found: {arxiv_id}")
    def txt(path):
        el = entry.find(path, ATOM)
        return re.sub(r"\s+", " ", el.text).strip() if el is not None and el.text else None
    entry_id = txt("a:id") or ""
    m = re.search(r"arxiv\.org/abs/(.+)$", entry_id)
    full_id = m.group(1) if m else arxiv_id
    published = txt("a:published") or ""
    return {
        "item_type": "preprint",
        "title": txt("a:title") or "",
        "authors": [_split_name(a.findtext("a:name", "", ATOM))
                    for a in entry.findall("a:author", ATOM)],
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "venue": txt("arxiv:journal_ref"),
        "doi": txt("arxiv:doi"),
        "arxiv_id": full_id,
        "url": f"https://arxiv.org/abs/{re.sub(r'v[0-9]+$', '', full_id)}",
        "abstract": txt("a:summary"),
    }


# --------------------------------------------------------------------------- #
# PubMed
# --------------------------------------------------------------------------- #

def _pubmed_name(name: str) -> dict:
    """PubMed lists authors as 'LeCun Y' or 'van der Maaten LJ'."""
    parts = name.strip().rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isupper() and len(parts[1]) <= 4:
        return {"given": " ".join(f"{c}." for c in parts[1]), "family": parts[0]}
    return {"given": "", "family": name.strip()}


def fetch_pubmed(pmid: str) -> dict:
    """Metadata for a PubMed ID: from Crossref when PubMed knows the DOI, else from PubMed."""
    params = {"db": "pubmed", "id": pmid, "retmode": "json", "tool": "bubo"}
    if settings.contact_email:
        params["email"] = settings.contact_email
    with _client() as c:
        r = c.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", params=params)
    r.raise_for_status()
    rec = r.json().get("result", {}).get(pmid)
    if not rec or rec.get("error"):
        raise MetadataError(f"PubMed ID not found: {pmid}")
    doi = next((a["value"] for a in rec.get("articleids", []) if a.get("idtype") == "doi"), None)
    if doi:
        try:
            meta = fetch_crossref(doi)
            meta.setdefault("url", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
            return meta
        except (MetadataError, httpx.HTTPError, KeyError, ValueError):
            pass
    year = re.search(r"(19|20)\d{2}", rec.get("pubdate") or rec.get("epubdate") or "")
    return {
        "item_type": "article",
        "title": (rec.get("title") or "").rstrip("."),
        "authors": [_pubmed_name(a["name"]) for a in rec.get("authors", []) if a.get("name")],
        "year": int(year.group(0)) if year else None,
        "venue": rec.get("fulljournalname") or rec.get("source"),
        "volume": rec.get("volume") or None,
        "issue": rec.get("issue") or None,
        "pages": (rec.get("pages") or "").replace("-", "–") or None,
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


# --------------------------------------------------------------------------- #
# Web pages and PDFs
# --------------------------------------------------------------------------- #

class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta: dict[str, list[str]] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            content = a.get("content")
            if name and content:
                self.meta.setdefault(name, []).append(content.strip())
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def download_pdf(url: str) -> bytes | None:
    try:
        with _client() as c, c.stream("GET", url) as r:
            if r.status_code != 200:
                return None
            chunks, size = [], 0
            for chunk in r.iter_bytes():
                size += len(chunk)
                if size > MAX_PDF_BYTES:
                    return None
                chunks.append(chunk)
        data = b"".join(chunks)
        return data if pdf.is_pdf(data) else None
    except httpx.HTTPError:
        return None


def unpaywall_pdf_url(doi: str) -> str | None:
    if not settings.contact_email:
        return None
    try:
        with _client() as c:
            r = c.get(f"https://api.unpaywall.org/v2/{quote(doi, safe='/')}",
                      params={"email": settings.contact_email})
        if r.status_code != 200:
            return None
        best = r.json().get("best_oa_location") or {}
        return best.get("url_for_pdf")
    except (httpx.HTTPError, ValueError):
        return None


def _meta_from_html(meta: dict[str, list[str]], page_title: str, url: str) -> dict:
    first = lambda *keys: next((meta[k][0] for k in keys if meta.get(k)), None)  # noqa: E731
    date = first("citation_publication_date", "citation_date", "dc.date",
                 "article:published_time") or ""
    year = re.search(r"(19|20)\d{2}", date)
    return {
        "item_type": "article" if meta.get("citation_journal_title") else "misc",
        "title": plain(first("citation_title", "dc.title", "og:title") or page_title.strip()) or "",
        "authors": [_split_name(plain(a)) for a in
                    meta.get("citation_author") or meta.get("dc.creator") or [] if plain(a)],
        "year": int(year.group(0)) if year else None,
        "venue": plain(first("citation_journal_title", "citation_conference_title", "og:site_name")),
        "volume": first("citation_volume"),
        "issue": first("citation_issue"),
        "pages": "–".join(filter(None, [first("citation_firstpage"), first("citation_lastpage")]))
                 or None,
        "publisher": plain(first("citation_publisher", "dc.publisher")),
        "url": url,
        "abstract": first("citation_abstract", "dc.description", "description"),
    }


# --------------------------------------------------------------------------- #
# Comparing stored and fetched metadata
# --------------------------------------------------------------------------- #

# Fields offered when refreshing metadata, in display order. The arXiv ID is never
# replaced: it identifies the version the user added.
REFRESH_FIELDS = ["item_type", "title", "authors", "year", "venue", "venue_short", "volume", "issue",
                  "pages", "publisher", "doi", "url", "abstract"]


def _norm(field: str, value):
    if field == "authors":
        return [(re.sub(r"\s+", " ", a.get("given") or "").strip(),
                 re.sub(r"\s+", " ", a.get("family") or "").strip()) for a in value or []]
    if field == "year":
        return int(value) if value not in (None, "") else None
    if value is None:
        return ""
    value = re.sub(r"\s+", " ", str(value)).strip()
    if field == "pages":
        value = value.replace("--", "–").replace("-", "–")
    if field == "doi":
        value = value.lower()
    return value


def diff(current: dict, fetched: dict) -> list[dict]:
    """Fields where the fetched metadata has a value that differs from the stored one."""
    changes = []
    for field in REFRESH_FIELDS:
        new = fetched.get(field)
        if new in (None, "", []):
            continue  # never offer to blank a field
        if _norm(field, new) != _norm(field, current.get(field)):
            changes.append({"field": field, "current": current.get(field), "new": new})
    return changes


# --------------------------------------------------------------------------- #
# High-level workflows
# --------------------------------------------------------------------------- #

def identify_pdf(info: pdf.PdfInfo) -> dict | None:
    """Try to work out a PDF's metadata from its contents."""
    first = info.pages[0] if info.pages else ""
    rest = "\n".join(info.pages[1:2])
    candidates: list[tuple[str, str]] = []
    if info.meta_subject and (d := find_doi(info.meta_subject)):
        candidates.append(("doi", d))
    if a := find_arxiv(first, strict=True):
        candidates.append(("arxiv", a))
    if d := find_doi(first):
        candidates.append(("doi", d))
    if a := find_arxiv(rest, strict=True):
        candidates.append(("arxiv", a))
    if d := find_doi(rest):
        candidates.append(("doi", d))
    for kind, value in candidates:
        try:
            return fetch_crossref(value) if kind == "doi" else fetch_arxiv(value)
        except (MetadataError, httpx.HTTPError, ET.ParseError, KeyError, ValueError):
            continue
    for title in filter(None, [info.meta_title, info.guessed_title]):
        try:
            if found := search_crossref_title(title):
                return found
        except (httpx.HTTPError, KeyError, ValueError):
            pass
    return None


def fallback_meta(info: pdf.PdfInfo, filename: str) -> dict:
    title = info.meta_title or info.guessed_title or re.sub(r"\.pdf$", "", filename, flags=re.I)
    authors = []
    if info.meta_author:
        authors = [_split_name(a) for a in re.split(r"\s*(?:;|,| and )\s*", info.meta_author) if a]
    return {"item_type": "misc", "title": title, "authors": authors}


def resolve(identifier: str) -> tuple[dict, bytes | None]:
    """Return (metadata, PDF bytes or None) for a DOI, arXiv ID or URL."""
    kind, value = classify(identifier)
    pdf_urls: list[str] = []
    pdf_bytes = None

    if kind == "arxiv":
        meta = fetch_arxiv(value)
        pdf_urls.append(f"https://arxiv.org/pdf/{meta['arxiv_id']}")
    elif kind == "doi":
        meta = fetch_crossref(value)
    elif kind == "pmid":
        meta = fetch_pubmed(value)
    else:
        with _client() as c:
            r = c.get(value)
        r.raise_for_status()
        final_url = str(r.url)
        if pdf.is_pdf(r.content):
            pdf_bytes = r.content
            meta = identify_pdf(pdf.analyze(pdf_bytes)) or fallback_meta(
                pdf.analyze(pdf_bytes), final_url.rsplit("/", 1)[-1])
            meta.setdefault("url", final_url)
        else:
            parser = _MetaParser()
            parser.feed(r.text)
            m = parser.meta
            doi = next((clean_doi(v[0]) for k in ("citation_doi", "prism.doi", "dc.identifier")
                        if (v := m.get(k)) and DOI_RE.search(v[0])), None)
            arxiv_id = (m.get("citation_arxiv_id") or [None])[0] or find_arxiv(final_url)
            doi = doi or find_doi(final_url)
            meta = None
            for k, v in (("arxiv", arxiv_id), ("doi", doi)):
                if not v:
                    continue
                try:
                    meta = fetch_arxiv(v) if k == "arxiv" else fetch_crossref(v)
                    break
                except (MetadataError, httpx.HTTPError, ET.ParseError):
                    pass
            if meta is None:
                meta = _meta_from_html(m, parser.title, final_url)
                if doi:
                    meta["doi"] = doi
            if meta.get("arxiv_id"):
                pdf_urls.append(f"https://arxiv.org/pdf/{meta['arxiv_id']}")
            for u in m.get("citation_pdf_url", []):
                pdf_urls.append(urljoin(final_url, u))

    if pdf_bytes is None and meta.get("doi") and (u := unpaywall_pdf_url(meta["doi"])):
        pdf_urls.append(u)
    for u in pdf_urls:
        if pdf_bytes is not None:
            break
        pdf_bytes = download_pdf(u)
    return meta, pdf_bytes


def landing_page_pdf_url(doi: str) -> str | None:
    """The PDF link a publisher advertises (citation_pdf_url) on the DOI's landing page."""
    try:
        with _client() as c:
            r = c.get(f"https://doi.org/{quote(doi, safe='/')}")
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            return None
        parser = _MetaParser()
        parser.feed(r.text)
        url = (parser.meta.get("citation_pdf_url") or [None])[0]
        return urljoin(str(r.url), url) if url else None
    except httpx.HTTPError:
        return None


def find_pdf(item: dict) -> bytes | None:
    """Look for a freely available PDF of an item: arXiv, Unpaywall, then the publisher's page."""
    candidates = []
    if item.get("arxiv_id"):
        candidates.append(lambda: f"https://arxiv.org/pdf/{item['arxiv_id']}")
    if item.get("doi"):
        candidates.append(lambda: unpaywall_pdf_url(item["doi"]))
        candidates.append(lambda: landing_page_pdf_url(item["doi"]))
    for get_url in candidates:
        url = get_url()
        if url and (data := download_pdf(url)):
            return data
    return None
