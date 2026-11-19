"""Find the sentences of a PDF that contain a search, with their page numbers.

Matching follows the library search (SQLite FTS5 with ``remove_diacritics``): case- and
accent-insensitive, and each search word matches the start of a word ("learn" matches
"learning").
"""

import re
import unicodedata

import pymupdf

HL_START, HL_END = "\x02", "\x03"
MAX_HITS = 30
MAX_SNIPPET = 280

_SENTENCE_END = re.compile(r"(?<=[.!?])[\"”’)\]]*\s+(?=[\"“‘(\[]?[A-Z0-9])")


def _fold(ch: str) -> str:
    """Lower-case and strip accents from one character (may return 0–3 characters)."""
    return "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)).lower()


def terms(query: str) -> list[str]:
    seen = []
    for t in re.findall(r"\w+", query, re.UNICODE):
        f = "".join(_fold(c) for c in t)
        if f and f not in seen:
            seen.append(f)
    return seen


def _folded(text: str) -> tuple[str, list[int]]:
    """Folded text plus, for each folded character, its index in the original."""
    out, index = [], []
    for i, ch in enumerate(text):
        f = _fold(ch)
        out.append(f)
        index.extend([i] * len(f))
    return "".join(out), index


def _clean(text: str) -> str:
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)   # words hyphenated across lines
    return re.sub(r"\s+", " ", text).strip()


def _highlight(sentence: str, patterns: list[re.Pattern]) -> tuple[str, int]:
    """Wrap matches in markers; returns the text and how many distinct terms matched."""
    folded, index = _folded(sentence)
    spans, matched = [], set()
    for n, pat in enumerate(patterns):
        for m in pat.finditer(folded):
            start, end = m.start(1), m.end(1)
            spans.append((index[start], index[end - 1] + 1))
            matched.add(n)
    if not spans:
        return sentence, 0
    spans.sort()
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    # Trim long sentences to a window around the first match.
    lo, hi = 0, len(sentence)
    if hi > MAX_SNIPPET:
        first = merged[0][0]
        lo = max(0, first - MAX_SNIPPET // 3)
        hi = min(len(sentence), lo + MAX_SNIPPET)
        lo = max(0, min(lo, hi - MAX_SNIPPET))
    out, pos = [], lo
    for a, b in merged:
        if b <= lo or a >= hi:
            continue
        a, b = max(a, lo), min(b, hi)
        out += [sentence[pos:a], HL_START, sentence[a:b], HL_END]
        pos = b
    out.append(sentence[pos:hi])
    text = "".join(out).strip()
    return ("…" if lo > 0 else "") + text + ("…" if hi < len(sentence) else ""), len(matched)


def find(pdf_bytes: bytes, query: str) -> dict:
    """{"terms": [...], "total": sentences found, "hits": [{"page", "snippet"}]}."""
    words = terms(query)
    if not words:
        return {"terms": [], "total": 0, "hits": []}
    patterns = [re.compile(rf"(?<![^\W_])({re.escape(w)})", re.UNICODE) for w in words]
    found = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page_no, page in enumerate(doc, start=1):
            text = _clean(page.get_text())
            if not text:
                continue
            for sentence in _SENTENCE_END.split(text):
                snippet, n = _highlight(sentence, patterns)
                if n:
                    found.append((n, page_no, snippet))
    if not found:
        return {"terms": words, "total": 0, "hits": []}
    # With several search words, show the sentences that contain the most of them.
    best = max(n for n, _, _ in found)
    hits = [{"page": p, "snippet": s} for n, p, s in found if n == best]
    return {"terms": words, "total": len(hits), "hits": hits[:MAX_HITS]}
