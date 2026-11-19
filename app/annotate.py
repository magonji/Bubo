"""Embed Bubo annotations into a copy of a PDF so other readers can see them."""

import pymupdf

# Shared with the web interface (app/static/viewer.js).
COLOURS = {
    "yellow": "#ffd400",
    "green": "#5fb236",
    "blue": "#2ea8e5",
    "pink": "#e56eee",
    "orange": "#f19837",
    "purple": "#a28ae5",
}


def _rgb(name: str) -> tuple[float, float, float]:
    h = COLOURS.get(name, COLOURS["yellow"]).lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def export(pdf_bytes: bytes, annotations: list[dict]) -> bytes:
    """Return a new PDF with each annotation added as a standard PDF annotation.

    Rectangles are stored in PDF user space (origin bottom-left, as reported by
    PDF.js); `page.transformation_matrix` maps them to PyMuPDF's unrotated,
    top-left coordinate system, which is what annotation methods expect.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    with doc:
        for a in annotations:
            if not 0 <= a["page"] < len(doc):
                continue
            page = doc[a["page"]]
            rects = []
            for x1, y1, x2, y2 in a["rects"]:
                r = pymupdf.Rect(x1, y1, x2, y2) * page.transformation_matrix
                r.normalize()
                rects.append(r)
            if not rects:
                continue
            colour = _rgb(a["color"])
            if a["kind"] == "highlight":
                annot = page.add_highlight_annot(quads=[r.quad for r in rects])
            else:
                annot = page.add_text_annot(rects[0].tl, a.get("comment") or "", icon="Note")
            annot.set_colors(stroke=colour)
            annot.set_info(content=a.get("comment") or "", title="Bubo")
            annot.update()
        return doc.tobytes(garbage=1, deflate=True)
