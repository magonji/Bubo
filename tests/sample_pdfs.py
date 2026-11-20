"""Small synthetic papers for the figure-extraction tests (no real papers in the repository)."""

import io
import math

import pymupdf
from PIL import Image, ImageDraw

BODY = ("Owls hunt by ear, and the prey they hunt can hear them. We review how three features of "
        "the wing feathers reduce the sound of flight, and measure flight noise in twelve birds. ") * 3


def _png(w: int, h: int, kind: str) -> bytes:
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    if kind == "plot":
        d.line([(40, h - 40), (w - 20, h - 40)], fill="black", width=3)
        d.line([(40, 20), (40, h - 40)], fill="black", width=3)
        pts = [(40 + x, h / 2 - math.sin(x / 40) * h / 4) for x in range(0, w - 60, 4)]
        d.line(pts, fill=(31, 119, 180), width=4)
    elif kind == "logo":
        d.rectangle([0, 0, w, h], fill=(20, 60, 120))
        d.ellipse([w / 3, h / 4, 2 * w / 3, 3 * h / 4], fill="white")
    else:   # a photo-like graphical abstract
        for y in range(h):
            d.line([(0, y), (w, y)], fill=(80 + y * 120 // h, 140, 200 - y * 100 // h))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def raster_paper() -> bytes:
    """Two pages: a captioned raster plot, an uncaptioned graphical abstract, a repeated logo
    in the header and a small icon."""
    doc = pymupdf.open()
    logo, icon = _png(330, 220, "logo"), _png(120, 90, "plot")
    for n in range(2):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(460, 50, 540, 103), stream=logo)      # on every page
        page.insert_textbox(pymupdf.Rect(60, 120, 535, 230), BODY, fontsize=10)
        if n == 0:
            page.insert_image(pymupdf.Rect(110, 250, 485, 500), stream=_png(900, 600, "plot"))
            page.insert_textbox(pymupdf.Rect(60, 512, 535, 560),
                                "Figure 1. Flight noise against frequency for barn owls.", fontsize=9)
            page.insert_image(pymupdf.Rect(60, 600, 100, 630), stream=icon)    # too small
        else:
            page.insert_image(pymupdf.Rect(120, 260, 470, 480), stream=_png(800, 500, "photo"))
        page.insert_textbox(pymupdf.Rect(60, 640, 535, 760), BODY, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def vector_paper() -> bytes:
    """One page, two columns: a plot drawn with paths and text labels in the left column,
    captioned 'Fig. 2 |', and a header rule across the page."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_line((50, 60), (545, 60), width=0.8)                          # header rule
    page.insert_textbox(pymupdf.Rect(50, 70, 290, 250), BODY, fontsize=9)
    page.insert_textbox(pymupdf.Rect(305, 70, 545, 760), BODY * 3, fontsize=9)
    # The plot: axes, ticks, a curve, and text labels outside the axes.
    x0, y0, x1, y1 = 85, 290, 280, 450
    page.draw_line((x0, y1), (x1, y1), width=1)
    page.draw_line((x0, y0), (x0, y1), width=1)
    for i in range(5):
        x = x0 + i * (x1 - x0) / 4
        page.draw_line((x, y1), (x, y1 + 4), width=0.8)
        page.insert_text((x - 3, y1 + 14), str(i * 5), fontsize=7)
    curve = [pymupdf.Point(x0 + t, y1 - 10 - 120 * math.exp(-t / 60)) for t in range(0, x1 - x0, 3)]
    page.draw_polyline(curve, color=(0.12, 0.47, 0.71), width=1.5)
    page.insert_text((150, y1 + 28), "Time (ms)", fontsize=8)
    page.insert_text((62, 400), "Signal", fontsize=8, rotate=90)
    page.insert_textbox(pymupdf.Rect(50, 488, 290, 530),
                        "Fig. 2 | Decay of the cochlear signal after a click.", fontsize=8)
    page.insert_textbox(pymupdf.Rect(50, 540, 290, 760), BODY, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data
