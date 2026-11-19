"""BibTeX export."""

import re

ENTRY_TYPES = {
    "article": "article",
    "inproceedings": "inproceedings",
    "preprint": "misc",
    "book": "book",
    "incollection": "incollection",
    "phdthesis": "phdthesis",
    "mastersthesis": "mastersthesis",
    "techreport": "techreport",
    "misc": "misc",
}

VENUE_FIELD = {
    "article": "journal",
    "inproceedings": "booktitle",
    "incollection": "booktitle",
    "phdthesis": "school",
    "mastersthesis": "school",
    "techreport": "institution",
}


def _escape(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value)).strip()
    value = re.sub(r"(?<!\\)([&%#_$])", r"\\\1", value)
    # Unbalanced braces would break the entry, so drop them.
    if value.count("{") != value.count("}"):
        value = value.replace("{", "").replace("}", "")
    return value


def _authors(authors: list[dict]) -> str:
    names = []
    for a in authors:
        family, given = a.get("family", ""), a.get("given", "")
        names.append(f"{family}, {given}" if family and given else family or given)
    return " and ".join(names)


def entry(item: dict) -> str:
    t = item.get("item_type") or "misc"
    fields: list[tuple[str, str]] = []
    add = lambda k, v: fields.append((k, v)) if v not in (None, "") else None  # noqa: E731
    add("title", "{" + _escape(item.get("title") or "") + "}" if item.get("title") else None)
    add("author", _escape(_authors(item.get("authors") or [])))
    add("year", item.get("year"))
    add(VENUE_FIELD.get(t, "howpublished" if t == "misc" else "journal"),
        _escape(item["venue"]) if item.get("venue") else None)
    add("volume", item.get("volume"))
    add("number", item.get("issue"))
    add("pages", (item.get("pages") or "").replace("–", "--") or None)
    add("publisher", _escape(item["publisher"]) if item.get("publisher") else None)
    add("doi", item.get("doi"))
    if item.get("arxiv_id"):
        add("eprint", item["arxiv_id"])
        add("archivePrefix", "arXiv")
    add("url", item.get("url"))
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields)
    return f"@{ENTRY_TYPES.get(t, 'misc')}{{{item.get('citekey') or 'item' + str(item['id'])},\n{body}\n}}\n"


def export(items: list[dict]) -> str:
    return "\n".join(entry(i) for i in items)
