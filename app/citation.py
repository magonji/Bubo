"""Formatted reference-list citations in common styles.

Each formatter turns an item into a list of segments ``(text, italic)``, which are
rendered as plain text and as HTML (so italics survive pasting into a word processor).
Titles are used as stored: no automatic sentence- or title-casing, which cannot be done
reliably (proper nouns, acronyms).
"""

import html
import re

Segments = list[tuple[str, bool]]

STYLES = {
    "apa": "APA 7th edition",
    "chicago": "Chicago 17th edition (author-date)",
    "mla": "MLA 9th edition",
    "harvard": "Harvard (Cite Them Right)",
    "ieee": "IEEE",
    "vancouver": "Vancouver",
}
DEFAULT_STYLE = "apa"

# Used to show what each style looks like in the settings dialog.
EXAMPLE = {
    "item_type": "article",
    "title": "Deep learning",
    "authors": [{"given": "Yann", "family": "LeCun"}, {"given": "Yoshua", "family": "Bengio"},
                {"given": "Geoffrey", "family": "Hinton"}],
    "year": 2015, "venue": "Nature", "volume": "521", "issue": "7553", "pages": "436–444",
    "publisher": "Springer Nature", "doi": "10.1038/nature14539",
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _initials(given: str, dots: bool = True, spaced: bool = True) -> str:
    """'Aidan N.' → 'A. N.'; 'Jean-Paul' → 'J.-P.'; dots=False → 'AN' (Vancouver)."""
    out = []
    for word in re.split(r"\s+", (given or "").strip()):
        if not word:
            continue
        parts = [p for p in word.split("-") if p]
        if dots:
            out.append("-".join(p[0].upper() + "." for p in parts))
        else:
            out.append("".join(p[0].upper() for p in parts))
    return (" " if spaced and dots else "").join(out)


def _family(a: dict) -> str:
    return (a.get("family") or a.get("given") or "").strip()


def _join(names: list[str], sep: str = ", ", last: str = ", and ", pair: str = " and ") -> str:
    if len(names) <= 1:
        return "".join(names)
    if len(names) == 2:
        return names[0] + pair + names[1]
    return sep.join(names[:-1]) + last + names[-1]


def _end(text: str, mark: str = ".") -> str:
    """Append punctuation unless the text already ends with some."""
    text = text.rstrip()
    return text if not text or text[-1] in ".?!" else text + mark


def _link(item: dict) -> str:
    if item.get("doi"):
        return f"https://doi.org/{item['doi']}"
    if item.get("arxiv_id"):
        return f"https://arxiv.org/abs/{re.sub(r'v[0-9]+$', '', item['arxiv_id'])}"
    return item.get("url") or ""


def _is_preprint(item: dict) -> bool:
    return item.get("item_type") == "preprint"


def _venue(item: dict) -> str:
    if _is_preprint(item) and not item.get("venue"):
        return "arXiv" if item.get("arxiv_id") else ""
    return item.get("venue") or ""


def _pages(item: dict) -> str:
    return (item.get("pages") or "").replace("--", "–").replace("-", "–")


def _thesis_kind(item: dict) -> str:
    return "Doctoral dissertation" if item.get("item_type") == "phdthesis" else "Master's thesis"


# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #

def apa(item: dict) -> Segments:
    authors = item.get("authors") or []
    names = [f"{_family(a)}, {_initials(a.get('given', ''))}".rstrip(", ") if a.get("given")
             else _family(a) for a in authors]
    if len(names) > 20:
        who = ", ".join(names[:19]) + ", … " + names[-1]
    else:
        who = _join(names, ", ", ", & ", ", & ")
    year = f"({item['year']})" if item.get("year") else "(n.d.)"
    title = item.get("title") or "Untitled"
    t, venue, pages, link = item.get("item_type"), _venue(item), _pages(item), _link(item)
    seg: Segments = []
    if who:
        seg += [(f"{_end(who)} {year}. ", False)]
    else:  # no author: the title moves into the author position
        seg += [(f"{_end(title)} {year}. ", False)]
        title = ""
    if t == "article" and venue:
        if title:
            seg.append((f"{_end(title)} ", False))
        seg.append((venue, True))
        if item.get("volume"):
            seg += [(", ", False), (item["volume"], True)]
        if item.get("issue"):
            seg.append((f"({item['issue']})", False))
        if pages:
            seg.append((f", {pages}", False))
        seg.append((". ", False))
    elif t in ("inproceedings", "incollection") and venue:
        if title:
            seg.append((f"{_end(title)} ", False))
        seg += [("In ", False), (venue, True)]
        seg.append((f" (pp. {pages}). " if pages else ". ", False))
        if item.get("publisher"):
            seg.append((f"{_end(item['publisher'])} ", False))
    else:
        if title:
            seg.append((title, True))
        if _is_preprint(item):
            seg.append((" [Preprint]", False))
        elif t in ("phdthesis", "mastersthesis"):
            school = f", {venue}" if venue else ""
            seg.append((f" [{_thesis_kind(item)}{school}]", False))
        seg.append((". " if title and not title.rstrip()[-1:] in "?!" else " ", False))
        source = venue if _is_preprint(item) else item.get("publisher") or (
            venue if t in ("techreport", "book", "misc") else "")
        if source:
            seg.append((f"{_end(source)} ", False))
    if link:
        seg.append((link, False))
    return seg


def chicago(item: dict) -> Segments:
    authors = item.get("authors") or []
    names = []
    for i, a in enumerate(authors[:7] if len(authors) > 10 else authors):
        given, family = (a.get("given") or "").strip(), _family(a)
        names.append(f"{family}, {given}" if i == 0 and given else f"{given} {family}".strip())
    who = _join(names) + (", et al" if len(authors) > 10 else "")
    year = str(item.get("year") or "n.d.")
    title = item.get("title") or "Untitled"
    t, venue, pages, link = item.get("item_type"), _venue(item), _pages(item), _link(item)
    seg: Segments = [(f"{_end(who)} {year}. " if who else f"{year}. ", False)]
    if t == "article" and venue:
        seg += [(f"“{_end(title)}” ", False), (venue, True)]
        if item.get("volume"):
            seg.append((f" {item['volume']}", False))
        if item.get("issue"):
            seg.append((f" ({item['issue']})", False))
        seg.append((f": {pages}. " if pages else ". ", False))
    elif t in ("inproceedings", "incollection") and venue:
        seg += [(f"“{_end(title)}” In ", False), (venue, True)]
        seg.append((f", {pages}. " if pages else ". ", False))
        if item.get("publisher"):
            seg.append((f"{_end(item['publisher'])} ", False))
    elif _is_preprint(item):
        seg.append((f"“{_end(title)}” ", False))
        if venue:
            seg.append((f"{_end(venue)} ", False))
    elif t in ("phdthesis", "mastersthesis"):
        kind = "PhD diss." if t == "phdthesis" else "Master's thesis"
        seg.append((f"“{_end(title)}” {kind}" + (f", {venue}. " if venue else ". "), False))
    else:
        seg += [(title, True), (". " if title.rstrip()[-1:] not in "?!" else " ", False)]
        if item.get("publisher"):
            seg.append((f"{_end(item['publisher'])} ", False))
    if link:
        seg.append((f"{link}.", False))
    return seg


def mla(item: dict) -> Segments:
    authors = item.get("authors") or []
    def inverted(a):
        given = (a.get("given") or "").strip()
        return f"{_family(a)}, {given}" if given else _family(a)
    def direct(a):
        return f"{(a.get('given') or '').strip()} {_family(a)}".strip()
    if len(authors) >= 3:
        who = f"{inverted(authors[0])}, et al"
    elif len(authors) == 2:
        who = f"{inverted(authors[0])}, and {direct(authors[1])}"
    else:
        who = inverted(authors[0]) if authors else ""
    title = item.get("title") or "Untitled"
    t, venue, pages, link = item.get("item_type"), _venue(item), _pages(item), _link(item)
    seg: Segments = [(f"{_end(who)} ", False)] if who else []
    container = t in ("article", "inproceedings", "incollection", "preprint") and venue
    if container:
        seg += [(f"“{_end(title)}” ", False), (venue, True)]
        details = []
        if item.get("volume"):
            details.append(f"vol. {item['volume']}")
        if item.get("issue"):
            details.append(f"no. {item['issue']}")
        if t != "article" and item.get("publisher"):
            details.append(item["publisher"])
        if item.get("year"):
            details.append(str(item["year"]))
        if pages:
            details.append(f"{'pp.' if '–' in pages else 'p.'} {pages}")
        seg.append(((", " + ", ".join(details)) if details else "", False))
    else:
        seg.append((title, True))
        details = [d for d in (item.get("publisher"), str(item["year"]) if item.get("year") else "") if d]
        seg.append(((". " + ", ".join(details)) if details else "", False))
    seg.append((f", {link}." if link else ".", False))
    return seg


def harvard(item: dict) -> Segments:
    authors = item.get("authors") or []
    names = [f"{_family(a)}, {_initials(a.get('given', ''), spaced=False)}".rstrip(", ")
             if a.get("given") else _family(a) for a in authors]
    who = f"{names[0]} et al." if len(names) >= 4 else _join(names, ", ", " and ", " and ")
    year = f"({item['year']})" if item.get("year") else "(no date)"
    title = item.get("title") or "Untitled"
    t, venue, pages, link = item.get("item_type"), _venue(item), _pages(item), _link(item)
    seg: Segments = [(f"{who} {year} " if who else f"{year} ", False)]
    if t == "article" and venue:
        seg += [(f"‘{title}’, ", False), (venue, True)]
        if item.get("volume"):
            seg.append((f", {item['volume']}", False))
        if item.get("issue"):
            seg.append((f"({item['issue']})", False))
        seg.append((f", pp. {pages}. " if pages else ". ", False))
    elif t in ("inproceedings", "incollection", "preprint") and venue:
        seg += [(f"‘{title}’, ", False), ("in " if t != "preprint" else "", False),
                (venue, True), (f", pp. {pages}. " if pages else ". ", False)]
    else:
        seg += [(title, True), (". " if title.rstrip()[-1:] not in "?!" else " ", False)]
        if item.get("publisher"):
            seg.append((f"{_end(item['publisher'])} ", False))
    if link:
        seg.append((f"Available at: {link}.", False))
    return seg


def ieee(item: dict) -> Segments:
    authors = item.get("authors") or []
    names = [f"{_initials(a.get('given', ''))} {_family(a)}".strip() for a in authors]
    who = f"{names[0]} et al." if len(names) > 6 else _join(names, ", ", ", and ", " and ")
    title = item.get("title") or "Untitled"
    t, venue, pages = item.get("item_type"), _venue(item), _pages(item)
    year = str(item.get("year") or "")
    pp = f"{'pp.' if '–' in pages else 'p.'} {pages}" if pages else ""
    doi = f"doi: {item['doi']}" if item.get("doi") else ""
    seg: Segments = [(f"{who}, " if who else "", False)]
    if t == "article" and venue:
        seg += [(f"“{title},” ", False), (venue, True)]
        parts = [f"vol. {item['volume']}" if item.get("volume") else "",
                 f"no. {item['issue']}" if item.get("issue") else "", pp, year, doi]
        seg.append(("".join(f", {p}" for p in parts if p) + ".", False))
    elif t in ("inproceedings", "incollection") and venue:
        seg += [(f"“{title},” in ", False), (venue, True)]
        parts = [year, pp, doi]
        seg.append(("".join(f", {p}" for p in parts if p) + ".", False))
    elif _is_preprint(item):
        seg.append((f"“{title},” ", False))
        rest = [year]
        if item.get("arxiv_id"):
            rest.append(f"arXiv:{item['arxiv_id']}")
        elif venue:
            rest.append(venue)
        seg.append((", ".join(r for r in rest if r) + ".", False))
    else:
        seg += [(title, True), (". ", False)]
        rest = [r for r in (item.get("publisher") or venue, year) if r]
        seg.append((", ".join(rest) + "." if rest else "", False))
        if doi:
            seg.append((f" {doi}.", False))
    return seg


def vancouver(item: dict) -> Segments:
    authors = item.get("authors") or []
    names = [f"{_family(a)} {_initials(a.get('given', ''), dots=False)}".strip() for a in authors]
    who = ", ".join(names[:6]) + (", et al" if len(names) > 6 else "")
    title = item.get("title") or "Untitled"
    t, venue, pages = item.get("item_type"), _venue(item), _pages(item)
    year = str(item.get("year") or "")
    seg: Segments = [(f"{_end(who)} " if who else "", False), (f"{_end(title)} ", False)]
    if t == "article" and venue:
        cite = f"{_end(venue)} {year}"
        if item.get("volume"):
            cite += f";{item['volume']}"
        if item.get("issue"):
            cite += f"({item['issue']})"
        if pages:
            cite += f":{pages}"
        seg.append((f"{cite}.", False))
    elif t in ("inproceedings", "incollection") and venue:
        seg.append((f"In: {_end(venue)} " + "; ".join(p for p in (item.get("publisher"), year) if p)
                    + (f". p. {pages}." if pages else "."), False))
    elif _is_preprint(item):
        seg[-1] = (f"{title} [Preprint]. ", False)
        seg.append((f"{venue}; {year}." if venue else f"{year}.", False))
    else:
        seg.append(("; ".join(p for p in (item.get("publisher"), year) if p) + ".", False))
    link = _link(item)
    if item.get("doi"):
        seg.append((f" doi:{item['doi']}", False))
    elif link:
        seg.append((f" Available from: {link}", False))
    return seg


FORMATTERS = {"apa": apa, "chicago": chicago, "mla": mla, "harvard": harvard,
              "ieee": ieee, "vancouver": vancouver}


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"\.\.(?!\.)", ".", text)
    return text.strip()


def format(item: dict, style: str) -> dict:
    """Return {"text": plain text, "html": HTML with <i> for italics}."""
    segments = [(t, i) for t, i in FORMATTERS[style](item) if t]
    text = _tidy("".join(t for t, _ in segments))
    parts = []
    for t, italic in segments:
        e = html.escape(t)
        parts.append(f"<i>{e}</i>" if italic else e)
    return {"text": text, "html": _tidy("".join(parts))}
