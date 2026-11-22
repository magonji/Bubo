import pymupdf
import pytest
from fastapi.testclient import TestClient

from app import bibtex, main, metadata

FAKE = {
    "item_type": "article",
    "title": "Deep Learning for Everything",
    "authors": [{"given": "Ada", "family": "Lovelace"}, {"given": "Alan", "family": "Turing"}],
    "year": 2021,
    "venue": "Journal of Testing",
    "volume": "3", "issue": "2", "pages": "10–20",
    "publisher": "Test Press",
    "doi": "10.1234/test.5678",
    "url": "https://doi.org/10.1234/test.5678",
    "abstract": "We test things.",
}


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def client(monkeypatch):
    calls = []

    def fake_crossref(doi):
        calls.append(doi)
        if doi.lower() != FAKE["doi"]:  # DOIs are case-insensitive, as in Crossref
            raise metadata.MetadataError("no")
        return dict(FAKE)

    monkeypatch.setattr(metadata, "fetch_crossref", fake_crossref)
    monkeypatch.setattr(metadata, "search_crossref_title", lambda t: None)
    monkeypatch.setattr(metadata, "unpaywall_pdf_url", lambda d: None)
    c = TestClient(main.app)
    c.calls = calls
    return c


def login(c):
    assert c.post("/api/login", json={"password": "wrong"}).status_code == 401
    assert c.post("/api/login", json={"password": "secret"}).status_code == 200


def test_requires_auth(client):
    assert client.get("/api/items").status_code == 401
    assert client.get("/").status_code == 200


def test_identifier_classification():
    assert metadata.classify("10.1000/xyz123") == ("doi", "10.1000/xyz123")
    assert metadata.classify("https://doi.org/10.1000/ABC(1)2") == ("doi", "10.1000/ABC(1)2")
    assert metadata.classify("arXiv:2101.00001v2") == ("arxiv", "2101.00001v2")
    assert metadata.classify("https://arxiv.org/abs/2101.00001") == ("arxiv", "2101.00001")
    assert metadata.classify("https://arxiv.org/pdf/2101.00001v1.pdf") == ("arxiv", "2101.00001v1")
    assert metadata.classify("hep-th/9901001") == ("arxiv", "hep-th/9901001")
    assert metadata.classify("https://example.com/paper")[0] == "url"
    assert metadata.find_doi("see doi:10.1145/3292500.3330701.") == "10.1145/3292500.3330701"
    with pytest.raises(metadata.MetadataError):
        metadata.classify("hola")


def test_full_flow(client):
    login(client)
    pdf_bytes = make_pdf("Deep Learning for Everything\nDOI: 10.1234/test.5678\nQuantum café")

    # Upload: the DOI is identified and the full text is indexed.
    r = client.post("/api/items/upload", files=[("files", ("paper.pdf", pdf_bytes, "application/pdf"))])
    res = r.json()["results"][0]
    assert res["status"] == "created" and res["identified"]
    item_id = res["id"]

    # Duplicate detected by file hash.
    r = client.post("/api/items/upload", files=[("files", ("copy.pdf", pdf_bytes, "application/pdf"))])
    assert r.json()["results"][0]["status"] == "duplicate"

    # Non-PDF rejected.
    r = client.post("/api/items/upload", files=[("files", ("x.pdf", b"hello", "application/pdf"))])
    assert r.json()["results"][0]["status"] == "error"

    item = client.get(f"/api/items/{item_id}").json()
    assert item["title"] == FAKE["title"] and item["has_file"] and item["citekey"] == "lovelace2021deep"

    # Full-text search (accent-insensitive) and author search.
    assert [i["id"] for i in client.get("/api/items", params={"q": "quantum cafe"}).json()] == [item_id]
    assert len(client.get("/api/items", params={"q": "turing"}).json()) == 1
    assert client.get("/api/items", params={"q": "nonexistent"}).json() == []

    # Collections and tags.
    cid = client.post("/api/collections", json={"name": "Thesis"}).json()["id"]
    sub = client.post("/api/collections", json={"name": "Chapter 1", "parent_id": cid}).json()["id"]
    assert client.patch(f"/api/collections/{cid}", json={"parent_id": sub}).status_code == 409
    assert client.post(f"/api/collections/{cid}/items", json={"item_ids": [item_id]}).status_code == 200
    r = client.patch(f"/api/items/{item_id}", json={"tags": ["ML", "read", "ml"], "notes": "secret note"})
    assert r.json()["tags"] == ["ML", "read"]
    assert len(client.get("/api/items", params={"collection": cid}).json()) == 1
    assert len(client.get("/api/items", params={"unfiled": True}).json()) == 0
    assert len(client.get("/api/items", params={"tag": "ml"}).json()) == 1
    # Editing metadata keeps the full text indexed; notes and tags are searchable too.
    assert len(client.get("/api/items", params={"q": "quantum"}).json()) == 1
    assert len(client.get("/api/items", params={"q": "secret"}).json()) == 1
    assert {t["name"] for t in client.get("/api/tags").json()} == {"ML", "read"}

    # PDF.
    r = client.get(f"/api/items/{item_id}/file")
    assert r.status_code == 200 and r.content == pdf_bytes
    assert "inline" in r.headers["content-disposition"]

    # Import by DOI: duplicate.
    r = client.post("/api/items/import", json={"identifier": "https://doi.org/10.1234/TEST.5678"})
    assert r.json()["status"] == "duplicate"

    # BibTeX.
    bib = client.get(f"/api/items/{item_id}/bibtex").text
    assert bib.startswith("@article{lovelace2021deep,")
    assert "author = {Lovelace, Ada and Turing, Alan}" in bib
    assert "title = {{Deep Learning for Everything}}" in bib
    assert "pages = {10--20}" in bib
    r = client.post("/api/export/bibtex", json={"ids": [item_id]})
    assert r.status_code == 200 and "@article" in r.text

    # Manual item + clashing citation key.
    other = client.post("/api/items", json={"title": "Another", "authors": [{"family": "Lovelace"}], "year": 2021}).json()
    assert client.patch(f"/api/items/{other['id']}", json={"citekey": "lovelace2021deep"}).status_code == 409

    # Deleting also removes the file and orphaned tags.
    assert client.delete(f"/api/items/{item_id}?permanent=true").status_code == 200
    assert client.get(f"/api/items/{item_id}").status_code == 404
    assert client.get("/api/tags").json() == []
    assert not list(main.settings.papers_dir.rglob("*.pdf"))


def test_unidentified_pdf_falls_back(client):
    login(client)
    data = make_pdf("A document without identifiers")
    res = client.post("/api/items/upload", files=[("files", ("my-notes.pdf", data, "application/pdf"))]).json()["results"][0]
    assert res["status"] == "created" and not res["identified"]
    assert client.get(f"/api/items/{res['id']}").json()["title"]


def test_arxiv_stamp_preferred_over_reference_doi(client, monkeypatch):
    login(client)
    seen = []
    monkeypatch.setattr(metadata, "fetch_arxiv", lambda a: seen.append(a) or {
        "item_type": "preprint", "title": "An arXiv paper", "authors": [{"given": "Grace", "family": "Hopper"}],
        "year": 2020, "arxiv_id": a})
    data = make_pdf("arXiv:2005.14165v4 [cs.CL] 22 Jul 2020\nAn arXiv paper\n[1] ref doi 10.9999/other")
    res = client.post("/api/items/upload", files=[("files", ("a.pdf", data, "application/pdf"))]).json()["results"][0]
    assert seen == ["2005.14165v4"]
    item = client.get(f"/api/items/{res['id']}").json()
    assert bibtex.entry(item).startswith("@misc{hopper2020arxiv,")
    assert "eprint = {2005.14165v4}" in bibtex.entry(item)


def test_annotations(client):
    login(client)
    data = make_pdf("Annotated paper\nDOI: 10.1234/test.5678\nhello target world")
    item_id = client.post("/api/items/upload", files=[("files", ("p.pdf", data, "application/pdf"))]
                          ).json()["results"][0]["id"]

    # PDF user-space rectangle of the word "target" (origin bottom-left, as PDF.js reports it).
    doc = pymupdf.open(stream=data)
    page = doc[0]
    r = page.search_for("target")[0]
    h = page.mediabox.height
    rect = [r.x0, h - r.y1, r.x1, h - r.y0]
    doc.close()

    hl = client.post(f"/api/items/{item_id}/annotations", json={
        "kind": "highlight", "color": "green", "page": 0, "rects": [rect], "text": "target",
        "comment": "Key passage about wombats"}).json()
    note = client.post(f"/api/items/{item_id}/annotations", json={
        "kind": "note", "page": 0, "rects": [[50, 50, 50, 50]], "comment": "Check the maths"}).json()
    assert hl["color"] == "green" and note["color"] == "yellow"

    # Validation: unknown colour, malformed rectangle, unknown item.
    assert client.post(f"/api/items/{item_id}/annotations", json={
        "kind": "highlight", "color": "mauve", "page": 0, "rects": [rect]}).status_code == 422
    assert client.post(f"/api/items/{item_id}/annotations", json={
        "kind": "highlight", "page": 0, "rects": [[1, 2, 3]]}).status_code == 422
    assert client.post("/api/items/9999/annotations", json={
        "kind": "note", "page": 0, "rects": [rect]}).status_code == 404

    assert client.get(f"/api/items/{item_id}").json()["annotation_count"] == 2
    assert [a["id"] for a in client.get(f"/api/items/{item_id}/annotations").json()] == [hl["id"], note["id"]]

    # Comments are searchable, and updates are reflected in the index.
    assert len(client.get("/api/items", params={"q": "wombats"}).json()) == 1
    r = client.patch(f"/api/annotations/{hl['id']}", json={"comment": "About platypuses", "color": "blue"})
    assert r.json()["comment"] == "About platypuses" and r.json()["color"] == "blue"
    assert client.get("/api/items", params={"q": "wombats"}).json() == []
    assert len(client.get("/api/items", params={"q": "platypuses"}).json()) == 1
    # Clearing a comment.
    assert client.patch(f"/api/annotations/{note['id']}", json={"comment": ""}).json()["comment"] is None

    # Export: the highlight lands on the word and the original file is untouched.
    r = client.get(f"/api/items/{item_id}/annotated.pdf")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    out = pymupdf.open(stream=r.content)
    out_page = out[0]
    annots = list(out_page.annots())
    kinds = sorted(a.type[1] for a in annots)
    assert kinds == ["Highlight", "Text"]
    highlight = next(a for a in annots if a.type[1] == "Highlight")
    assert "target" in out_page.get_textbox(highlight.rect)
    assert highlight.info["content"] == "About platypuses"
    out.close()
    assert client.get(f"/api/items/{item_id}/file").content == data

    # Deleting.
    assert client.delete(f"/api/annotations/{note['id']}").status_code == 200
    assert client.get(f"/api/items/{item_id}").json()["annotation_count"] == 1
    client.delete(f"/api/items/{item_id}?permanent=true")
    assert client.patch(f"/api/annotations/{hl['id']}", json={"color": "pink"}).status_code == 404


def test_vendored_pdfjs_is_served(client):
    r = client.get("/static/vendor/pdfjs/pdf.min.mjs")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert client.get("/static/vendor/pdfjs/wasm/openjpeg.wasm").headers["content-type"] == "application/wasm"
    # The legacy build, for browsers without the latest JavaScript (older Safari).
    for f in ("pdf.min.mjs", "pdf.worker.min.mjs"):
        r = client.get(f"/static/vendor/pdfjs/legacy/{f}")
        assert r.status_code == 200 and "javascript" in r.headers["content-type"]


def pdf_files():
    root = main.settings.papers_dir
    return sorted(str(p.relative_to(root)) for p in root.rglob("*.pdf"))


def test_flat_readable_names(client, monkeypatch):
    login(client)
    from app import storage
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")

    thesis = client.post("/api/collections", json={"name": "Thesis"}).json()["id"]
    reading = client.post("/api/collections", json={"name": "Reading"}).json()["id"]
    data = make_pdf("Deep Learning for Everything\nDOI: 10.1234/test.5678")
    item_id = client.post("/api/items/upload", data={"collection_id": str(thesis)},
                          files=[("files", ("x.pdf", data, "application/pdf"))]).json()["results"][0]["id"]
    name = "Lovelace and Turing - 2021 - Deep Learning for Everything.pdf"
    assert pdf_files() == [name]
    assert client.get(f"/api/items/{item_id}").json()["file_path"] == name
    assert client.get(f"/api/items/{item_id}/file").content == data

    # Collections never move the file.
    client.patch(f"/api/items/{item_id}", json={"collections": [thesis, reading]})
    client.patch(f"/api/collections/{thesis}", json={"name": "My thesis"})
    client.delete(f"/api/collections/{reading}")
    assert pdf_files() == [name]

    # Editing metadata renames it (names stay valid on exFAT/NTFS).
    client.patch(f"/api/items/{item_id}", json={"title": 'A "new" title: part 1/2', "year": 2022})
    renamed = "Lovelace and Turing - 2022 - A new title - part 1 2.pdf"
    assert pdf_files() == [renamed]
    assert not (main.settings.papers_dir / ".incoming").exists()

    # Same name → numbered; names are compared case-insensitively.
    monkeypatch.setattr(metadata, "identify_pdf", lambda info, **kw: {
        "title": "a NEW title - part 1 2", "authors": [{"family": "lovelace"}, {"family": "turing"}],
        "year": 2022})
    client.post("/api/items/upload", files=[("files", ("y.pdf", make_pdf("Other"), "application/pdf"))])
    assert pdf_files() == [renamed, "lovelace and turing - 2022 - a NEW title - part 1 2 (2).pdf"]

    # Downloads use the readable name (UTF-8 safe).
    r = client.get(f"/api/items/{item_id}/file", params={"download": True})
    assert "Lovelace%20and%20Turing%20-%202022" in r.headers["content-disposition"]
    client.post(f"/api/items/{item_id}/annotations", json={"kind": "note", "page": 0, "rects": [[1, 1, 1, 1]]})
    r = client.get(f"/api/items/{item_id}/annotated.pdf")
    assert "%28annotated%29.pdf" in r.headers["content-disposition"]

    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")
    assert pdf_files() == []

    assert storage.clean_component(' CON ', 50, "x") == "_CON"
    assert storage.clean_component('What? <Really> | "yes"...', 50, "x") == "What Really yes"
    assert storage.base_name("", [], None) == "Untitled"
    three = [{"family": "Vaswani"}, {"family": "Shazeer"}, {"family": "Parmar"}]
    assert storage.base_name("Attention", three, 2017) == "Vaswani et al. - 2017 - Attention"
    assert storage.base_name("", three, None) == "Vaswani et al"  # trailing dot not allowed on exFAT


def test_older_layouts_are_migrated(client):
    login(client)
    from app import db, storage
    data, other = make_pdf("Legacy paper"), make_pdf("Foldered paper")
    legacy = main.settings.legacy_files_dir
    legacy.mkdir(exist_ok=True)
    (legacy / "0123456789abcdef0123456789abcdef.pdf").write_bytes(data)
    folder = main.settings.papers_dir / "Thesis" / "Chapter 1"
    folder.mkdir(parents=True)
    (folder / "Old name.pdf").write_bytes(other)
    (folder / ".DS_Store").write_bytes(b"junk")
    conn = db.connect()
    a = db.create_item(conn, {"title": "Old one", "authors": [{"family": "Curie"}], "year": 1903},
                       file={"name": "0123456789abcdef0123456789abcdef.pdf", "size": 1, "hash": "h1"})
    b = db.create_item(conn, {"title": "Foldered", "authors": [{"family": "Noether"}], "year": 1918},
                       file={"name": "Thesis/Chapter 1/Old name.pdf", "size": 1, "hash": "h2"})
    storage.sync_all(conn)
    conn.close()
    assert pdf_files() == ["Curie - 1903 - Old one.pdf", "Noether - 1918 - Foldered.pdf"]
    assert not legacy.exists() and not (main.settings.papers_dir / "Thesis").exists()
    assert client.get(f"/api/items/{a}/file").content == data
    assert client.get(f"/api/items/{b}/file").content == other
    client.delete(f"/api/items/{a}?permanent=true")
    client.delete(f"/api/items/{b}?permanent=true")


def test_refresh_preview_lists_changes_without_saving(client):
    login(client)
    item = client.post("/api/items", json={
        "title": "My own corrected title", "doi": "10.1234/TEST.5678", "year": 2021,
        "authors": [{"given": "Ada", "family": "Lovelace"}, {"given": "Alan", "family": " Turing "}],
        "pages": "10-20", "venue": "J. Test", "notes": "keep me"}).json()
    r = client.get(f"/api/items/{item['id']}/refresh-preview")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "Crossref"
    fields = {c["field"]: c for c in body["changes"]}
    # Equivalent values (DOI case, page dash, spacing in names) are not reported.
    assert "doi" not in fields and "pages" not in fields and "authors" not in fields and "year" not in fields
    assert fields["title"] == {"field": "title", "current": "My own corrected title",
                               "new": "Deep Learning for Everything"}
    assert fields["venue"]["new"] == "Journal of Testing"
    assert {"volume", "issue", "publisher", "abstract", "url"} <= set(fields)
    # Nothing was saved.
    assert client.get(f"/api/items/{item['id']}").json()["title"] == "My own corrected title"

    # Applying only some fields keeps the rest (and unrelated fields such as notes).
    picked = {f: fields[f]["new"] for f in ("venue", "volume")}
    after = client.patch(f"/api/items/{item['id']}", json=picked).json()
    assert after["title"] == "My own corrected title" and after["venue"] == "Journal of Testing"
    assert after["notes"] == "keep me"

    # Without DOI or arXiv ID there is nothing to refresh from.
    bare = client.post("/api/items", json={"title": "No identifiers"}).json()
    assert client.get(f"/api/items/{bare['id']}/refresh-preview").status_code == 422
    assert client.post(f"/api/items/{item['id']}/refresh").status_code in (404, 405)
    for i in (item, bare):
        client.delete(f"/api/items/{i['id']}?permanent=true")


def test_diff_never_blanks_fields():
    current = {"title": "A", "abstract": "Kept", "year": 2020}
    assert metadata.diff(current, {"title": "A", "abstract": "", "year": None}) == []
    assert metadata.diff({"year": "2020"}, {"year": 2020}) == []


def test_citations_and_settings(client):
    login(client)
    from app import citation
    assert client.get("/api/settings").json() == {"citation_style": "apa", "include_subcollections": False,
                                                  "new_items_to_read": False, "contact_email": "",
                                                  "contact_email_env": ""}
    item = client.post("/api/items", json={**{k: v for k, v in citation.EXAMPLE.items()}}).json()

    r = client.get(f"/api/items/{item['id']}/citation").json()
    assert r["style"] == "apa"
    assert r["text"] == ("LeCun, Y., Bengio, Y., & Hinton, G. (2015). Deep learning. Nature, 521(7553), "
                         "436–444. https://doi.org/10.1038/nature14539")
    assert "<i>Nature</i>, <i>521</i>(7553)" in r["html"] and "&amp;" in r["html"]

    # Changing the favourite style changes the default citation.
    assert client.patch("/api/settings", json={"citation_style": "ieee"}).json()["citation_style"] == "ieee"
    r = client.get(f"/api/items/{item['id']}/citation").json()
    assert r["text"] == ('Y. LeCun, Y. Bengio, and G. Hinton, “Deep learning,” Nature, vol. 521, no. 7553, '
                         'pp. 436–444, 2015, doi: 10.1038/nature14539.')
    assert client.patch("/api/settings", json={"citation_style": "nope"}).status_code == 422
    # An explicit style overrides the saved one.
    assert client.get(f"/api/items/{item['id']}/citation", params={"style": "vancouver"}).json()["text"] == (
        "LeCun Y, Bengio Y, Hinton G. Deep learning. Nature. 2015;521(7553):436–444. doi:10.1038/nature14539")

    styles = client.get("/api/citation-styles").json()
    assert [s["id"] for s in styles] == list(citation.STYLES)
    assert all(s["example"]["text"] for s in styles)
    client.patch("/api/settings", json={"citation_style": "apa"})
    client.delete(f"/api/items/{item['id']}?permanent=true")


def test_citation_edge_cases():
    from app import citation
    many = [{"given": f"Given{i}", "family": f"Family{i}"} for i in range(25)]
    apa = citation.format({"title": "Big team?", "authors": many, "item_type": "misc"}, "apa")["text"]
    assert apa.startswith("Family0, G., ") and ", … Family24, G. (n.d.). " in apa
    assert "Big team?" in apa and "?." not in apa
    # No authors: APA moves the title to the author position.
    assert citation.format({"title": "Anonymous work", "year": 2001}, "apa")["text"] == "Anonymous work. (2001)."
    assert citation._initials("Jean-Paul") == "J.-P." and citation._initials("Aidan N.", dots=False) == "AN"
    for style in citation.STYLES:  # never crash on an almost empty item
        assert citation.format({}, style)["text"]



def test_subcollections_and_moving(client):
    login(client)
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")
    for c in client.get("/api/collections").json():
        client.delete(f"/api/collections/{c['id']}")
    new = lambda name, parent=None: client.post("/api/collections", json={"name": name, "parent_id": parent}).json()["id"]
    ml = new("ML")
    nlp = new("NLP", ml)
    trans = new("Transformers", nlp)
    other = new("Other")
    a = client.post("/api/items", json={"title": "A", "collections": [ml]}).json()["id"]
    b = client.post("/api/items", json={"title": "B", "collections": [trans]}).json()["id"]
    client.post("/api/items", json={"title": "C", "collections": [nlp, trans]})  # counted once

    ids = lambda **p: sorted(i["title"] for i in client.get("/api/items", params=p).json())
    assert ids(collection=ml) == ["A"]
    assert ids(collection=ml, subcollections=True) == ["A", "B", "C"]
    assert ids(collection=nlp, subcollections=True) == ["B", "C"]
    cols = {c["name"]: c for c in client.get("/api/collections").json()}
    assert (cols["ML"]["count"], cols["ML"]["total"]) == (1, 3)
    assert (cols["NLP"]["count"], cols["NLP"]["total"]) == (1, 2)
    assert (cols["Transformers"]["count"], cols["Transformers"]["total"]) == (2, 2)

    # Moving: into another collection, to the top level, and never into a descendant.
    assert client.patch(f"/api/collections/{nlp}", json={"parent_id": other}).status_code == 200
    assert ids(collection=ml, subcollections=True) == ["A"]
    assert ids(collection=other, subcollections=True) == ["B", "C"]
    assert client.patch(f"/api/collections/{nlp}", json={"parent_id": trans}).status_code == 409
    assert client.patch(f"/api/collections/{nlp}", json={"parent_id": nlp}).status_code == 409
    assert client.patch(f"/api/collections/{nlp}", json={"parent_id": None}).status_code == 200
    assert {c["name"]: c["parent_id"] for c in client.get("/api/collections").json()}["NLP"] is None

    assert client.patch("/api/settings", json={"include_subcollections": True}).json()["include_subcollections"]
    client.patch("/api/settings", json={"include_subcollections": False})
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")
    for c in client.get("/api/collections").json():
        client.delete(f"/api/collections/{c['id']}")


def make_pages(*pages: str) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def test_search_excerpts_and_page_matches(client, monkeypatch):
    login(client)
    from app import textsearch
    monkeypatch.setattr(metadata, "identify_pdf", lambda info, **kw: {"title": "Owls of Europe", "year": 2020})
    data = make_pages("Introduction. The eagle owl is large.\nIt hunts at night.",
                      "Methods. We ringed every Eurasian eagle owl we found.",
                      "Nothing to see here.")
    item_id = client.post("/api/items/upload", files=[("files", ("o.pdf", data, "application/pdf"))]
                          ).json()["results"][0]["id"]
    client.patch(f"/api/items/{item_id}", json={"notes": "Ask Marta about the ringing permits"})

    hit = next(i for i in client.get("/api/items", params={"q": "eagle owl"}).json() if i["id"] == item_id)
    assert hit["match"]["field"] == "fulltext"
    assert "\x02eagle\x03 \x02owl\x03" in hit["match"]["snippet"]
    # The notes win when they contain the search and the text does not.
    hit = next(i for i in client.get("/api/items", params={"q": "permits"}).json() if i["id"] == item_id)
    assert hit["match"]["field"] == "notes" and "\x02permits\x03" in hit["match"]["snippet"]
    # Matches in the title alone need no excerpt.
    hit = next(i for i in client.get("/api/items", params={"q": "Europe"}).json() if i["id"] == item_id)
    assert hit["match"] is None
    assert all(i.get("match") is None for i in client.get("/api/items").json())

    r = client.get(f"/api/items/{item_id}/text-matches", params={"q": "eagle owl"}).json()
    assert r["terms"] == ["eagle", "owl"] and r["total"] == 2
    assert [h["page"] for h in r["hits"]] == [1, 2]
    assert r["hits"][0]["snippet"] == "The \x02eagle\x03 \x02owl\x03 is large."
    # Prefixes, accents and case behave as in the library search.
    assert client.get(f"/api/items/{item_id}/text-matches", params={"q": "EURAS"}).json()["total"] == 1
    assert textsearch.terms("Café crème") == ["cafe", "creme"]
    assert client.get(f"/api/items/{item_id}/text-matches", params={"q": "zebra"}).json()["total"] == 0
    client.delete(f"/api/items/{item_id}?permanent=true")


def test_reading_list(client):
    login(client)
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")
    a = client.post("/api/items", json={"title": "Later", "to_read": True}).json()
    b = client.post("/api/items", json={"title": "Already read"}).json()
    assert a["to_read"] and a["to_read_at"] and not b["to_read"]
    assert [i["title"] for i in client.get("/api/items", params={"to_read": True}).json()] == ["Later"]
    assert client.get("/api/library-counts").json() == {"all": 2, "unfiled": 2, "to_read": 1, "journals": 0, "trash": 0}

    # Adding again keeps the original date; removing takes it off the list.
    again = client.patch(f"/api/items/{a['id']}", json={"to_read": True}).json()
    assert again["to_read_at"] == a["to_read_at"]
    client.patch(f"/api/items/{b['id']}", json={"to_read": True})
    assert client.get("/api/library-counts").json()["to_read"] == 2
    done = client.patch(f"/api/items/{a['id']}", json={"to_read": False}).json()
    assert not done["to_read"] and done["to_read_at"] is None
    assert [i["title"] for i in client.get("/api/items", params={"to_read": True}).json()] == ["Already read"]
    # Other edits leave the flag alone.
    assert client.patch(f"/api/items/{b['id']}", json={"title": "Renamed"}).json()["to_read"]
    for i in (a, b):
        client.delete(f"/api/items/{i['id']}?permanent=true")



def test_new_items_to_reading_list_and_queue_order(client, monkeypatch):
    login(client)
    import time
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")
    monkeypatch.setattr(metadata, "identify_pdf", lambda info, **kw: None)
    pdf_a, pdf_b = make_pdf("Paper A"), make_pdf("Paper B")
    r = client.post("/api/items/upload", data={"to_read": "true"},
                    files=[("files", ("a.pdf", pdf_a, "application/pdf"))]).json()["results"][0]
    assert client.get(f"/api/items/{r['id']}").json()["to_read"]
    plain = client.post("/api/items/upload", files=[("files", ("b.pdf", pdf_b, "application/pdf"))]).json()["results"][0]
    assert not client.get(f"/api/items/{plain['id']}").json()["to_read"]
    # Uploading a paper that is already in the library puts it on the list too.
    dup = client.post("/api/items/upload", data={"to_read": "true"},
                      files=[("files", ("b2.pdf", pdf_b, "application/pdf"))]).json()["results"][0]
    assert dup["status"] == "duplicate" and client.get(f"/api/items/{plain['id']}").json()["to_read"]

    # Importing by identifier.
    r = client.post("/api/items/import", json={"identifier": "10.1234/test.5678", "to_read": True}).json()
    assert r["status"] == "created" and r["item"]["to_read"]

    # Queue order: by the date each paper was put on the list.
    client.patch(f"/api/items/{plain['id']}", json={"to_read": False})
    time.sleep(1.1)
    client.patch(f"/api/items/{plain['id']}", json={"to_read": True})
    order = [i["id"] for i in client.get("/api/items", params={"to_read": True, "sort": "to_read"}).json()]
    assert order[-1] == plain["id"]
    order_desc = [i["id"] for i in client.get("/api/items", params={"to_read": True, "sort": "to_read_desc"}).json()]
    assert order_desc[0] == plain["id"]

    assert client.patch("/api/settings", json={"new_items_to_read": True}).json()["new_items_to_read"]
    client.patch("/api/settings", json={"new_items_to_read": False})
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")


def test_pubmed_ids(client, monkeypatch):
    login(client)
    assert metadata.classify("PMID: 25788094") == ("pmid", "25788094")
    assert metadata.classify("25788094") == ("pmid", "25788094")
    assert metadata.classify("https://pubmed.ncbi.nlm.nih.gov/25788094/") == ("pmid", "25788094")
    assert metadata._pubmed_name("van der Maaten LJ") == {"given": "L. J.", "family": "van der Maaten"}

    class Resp:
        status_code = 200
        def __init__(self, data): self._data = data
        def raise_for_status(self): pass
        def json(self): return self._data
    summary = {"result": {"111": {"title": "Owls at night.", "authors": [{"name": "Hoot A"}],
                                  "pubdate": "2019 Mar", "fulljournalname": "Journal of Owls",
                                  "volume": "4", "issue": "1", "pages": "1-9", "articleids": []}}}
    class FakeClient:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, params=None): return Resp(summary)
    monkeypatch.setattr(metadata, "_client", lambda: FakeClient())
    r = client.post("/api/items/import", json={"identifier": "PMID:111"}).json()
    item = r["item"]
    assert r["status"] == "created" and item["title"] == "Owls at night" and item["year"] == 2019
    assert item["authors"] == [{"given": "A.", "family": "Hoot"}] and item["pages"] == "1–9"
    assert item["url"] == "https://pubmed.ncbi.nlm.nih.gov/111/"
    client.delete(f"/api/items/{item['id']}?permanent=true")


def test_find_pdf_and_overview(client, monkeypatch):
    login(client)
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")
    full = client.post("/api/items", json={"title": "Complete", "authors": [{"family": "A"}], "year": 2020,
                                           "item_type": "misc", "doi": "10.1/x", "to_read": True}).json()
    bare = client.post("/api/items", json={"title": "New item"}).json()
    ov = client.get("/api/overview").json()
    assert [i["title"] for i in ov["recent"]] == ["New item", "Complete"]
    assert [i["title"] for i in ov["to_read"]] == ["Complete"] and ov["to_read_total"] == 1
    assert [i["title"] for i in ov["incomplete"]] == ["New item"] and ov["incomplete_total"] == 1
    assert ov["incomplete"][0]["missing"] == ["title", "authors", "year", "journal"]
    assert ov["counts"] == {"papers": 2, "with_pdf": 0, "to_read": 1, "collections": 0}

    assert client.post(f"/api/items/{bare['id']}/find-pdf").status_code == 422
    monkeypatch.setattr(metadata, "find_pdf", lambda item: None)
    assert client.post(f"/api/items/{full['id']}/find-pdf").status_code == 404
    data = make_pdf("Found it")
    monkeypatch.setattr(metadata, "find_pdf", lambda item: data)
    found = client.post(f"/api/items/{full['id']}/find-pdf").json()
    assert found["has_file"] and client.get(f"/api/items/{full['id']}/file").content == data
    assert client.post(f"/api/items/{full['id']}/find-pdf").status_code == 409
    for i in (full, bare):
        client.delete(f"/api/items/{i['id']}?permanent=true")



def test_contact_email_setting(client):
    login(client)
    from app.config import settings as cfg
    assert cfg.contact_email is None
    r = client.patch("/api/settings", json={"contact_email": "  owl@example.org "})
    assert r.json()["contact_email"] == "owl@example.org"
    assert cfg.contact_email == "owl@example.org"          # used straight away, no restart
    assert client.patch("/api/settings", json={"contact_email": "not an email"}).status_code == 422
    assert cfg.contact_email == "owl@example.org"
    # Clearing it falls back to BUBO_CONTACT_EMAIL (unset in the tests).
    assert client.patch("/api/settings", json={"contact_email": ""}).json()["contact_email"] == ""
    assert cfg.contact_email is None


def all_files():
    root = main.settings.papers_dir
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.is_file() and not p.name.startswith("."))


def test_supplementary_files(client):
    login(client)
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")
    paper = make_pdf("Main paper text")
    r = client.post("/api/items/upload", files=[("files", ("paper.pdf", paper, "application/pdf"))])
    item_id = r.json()["results"][0]["id"]
    client.patch(f"/api/items/{item_id}", json={
        "title": "Silent flight", "authors": [{"family": "Strix"}], "year": 2024})

    si = make_pdf("Supplementary figures about feather serrations")
    r = client.post(f"/api/items/{item_id}/supplementary",
                    files={"file": ("ncomms-s1.pdf", si, "application/pdf")})
    assert r.status_code == 200 and r.json()["status"] == "added"
    table = b"species,noise\nowl,18\n"
    r = client.post(f"/api/items/{item_id}/supplementary",
                    files={"file": ("Data S1.CSV", table, "text/csv")})
    item = r.json()["item"]
    assert [s["name"] for s in item["supplementary"]] == ["ncomms-s1.pdf", "Data S1.CSV"]
    assert all_files() == ["Strix - 2024 - Silent flight - SI 2.csv",
                           "Strix - 2024 - Silent flight - SI.pdf",
                           "Strix - 2024 - Silent flight.pdf"]
    first, second = (s["id"] for s in item["supplementary"])

    # The same file twice, or the paper's own PDF, is not added again.
    again = client.post(f"/api/items/{item_id}/supplementary",
                        files={"file": ("copy.pdf", si, "application/pdf")})
    assert again.json()["status"] == "duplicate"
    own = client.post(f"/api/items/{item_id}/supplementary",
                      files={"file": ("paper.pdf", paper, "application/pdf")})
    assert own.status_code == 409

    # The text of supplementary PDFs is searchable, and labelled as such.
    found = client.get("/api/items", params={"q": "serrations"}).json()
    assert [i["id"] for i in found] == [item_id]
    assert found[0]["match"]["field"] == "supplementary"

    # PDFs open in the browser; other files are downloaded, never rendered.
    r = client.get(f"/api/supplementary/{first}/file")
    assert r.content == si and r.headers["content-disposition"].startswith("inline")
    html = client.post(f"/api/items/{item_id}/supplementary",
                       files={"file": ("page.html", b"<script>alert(1)</script>", "text/html")})
    html_id = html.json()["item"]["supplementary"][-1]["id"]
    r = client.get(f"/api/supplementary/{html_id}/file")
    assert r.headers["content-disposition"].startswith("attachment")
    assert r.headers["content-type"] == "application/octet-stream"
    client.delete(f"/api/supplementary/{html_id}")

    # Files follow the paper's metadata, and the numbering closes up after a deletion.
    client.patch(f"/api/items/{item_id}", json={"title": "Quiet wings"})
    assert all_files() == ["Strix - 2024 - Quiet wings - SI 2.csv",
                           "Strix - 2024 - Quiet wings - SI.pdf",
                           "Strix - 2024 - Quiet wings.pdf"]
    item = client.delete(f"/api/supplementary/{first}").json()
    assert [s["id"] for s in item["supplementary"]] == [second]
    assert all_files() == ["Strix - 2024 - Quiet wings - SI.csv", "Strix - 2024 - Quiet wings.pdf"]
    assert client.get("/api/items", params={"q": "serrations"}).json() == []

    # Deleting the paper removes its supplementary files too.
    client.delete(f"/api/items/{item_id}?permanent=true")
    assert all_files() == []


def test_search_index_gains_supplementary_column():
    from app import db
    conn = db.connect()
    conn.execute("DROP TABLE items_fts")
    conn.execute("CREATE VIRTUAL TABLE items_fts USING fts5(title, authors, abstract, venue, "
                 "extra, fulltext, tokenize = 'unicode61 remove_diacritics 2')")
    conn.execute("INSERT INTO items_fts (rowid, title, authors, abstract, venue, extra, fulltext) "
                 "VALUES (999, 'Kept title', '', '', '', '', 'kept text')")
    conn.commit()
    conn.close()
    db.init_db()
    conn = db.connect()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(items_fts)")]
    assert cols[-1] == "supplementary"
    assert conn.execute("SELECT title FROM items_fts WHERE items_fts MATCH 'kept'").fetchone()[0] == "Kept title"
    conn.execute("DELETE FROM items_fts WHERE rowid = 999")
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #

def test_figures_found_in_raster_and_vector_papers():
    from app import figures
    from tests.sample_pdfs import raster_paper, vector_paper
    with pymupdf.open(stream=raster_paper(), filetype="pdf") as doc:
        found = figures.find_figures(doc)
        # The captioned plot and the graphical abstract; not the logo repeated on every
        # page, nor the small icon.
        assert [(f.page, f.kind, f.label) for f in found] == [(0, "caption", "Figure 1"), (1, "image", "")]
        assert found[0].caption.startswith("Figure 1. Flight noise")
        assert found[0].rect.contains(pymupdf.Rect(110, 250, 485, 500))
        assert found[0].rect.y1 < 512          # stops above the caption
    with pymupdf.open(stream=vector_paper(), filetype="pdf") as doc:
        (fig,) = figures.find_figures(doc)
        assert (fig.kind, fig.label) == ("caption", "Figure 2")
        # The axes, the curve and the labels outside the axes, including the rotated one…
        assert fig.rect.contains(pymupdf.Rect(85, 290, 280, 478)) and fig.rect.x0 < 56
        # …but not the body text above, the other column or the header rule.
        assert fig.rect.y0 > 250 and fig.rect.x1 < 300


def test_figures_api(client):
    from app import figures
    from tests.sample_pdfs import raster_paper, vector_paper
    login(client)
    r = client.post("/api/items/upload", files=[("files", ("owls.pdf", raster_paper(), "application/pdf"))])
    item_id = r.json()["results"][0]["id"]
    figures.wait()
    data = client.get(f"/api/items/{item_id}/figures").json()
    assert data["status"] == "done" and len(data["figures"]) == 2
    first, second = data["figures"]
    assert first["label"] == "Figure 1" and first["caption"].startswith("Figure 1.") and first["page"] == 1

    thumb = client.get(first["thumb"])
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/webp"
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(thumb.content)).width <= 400
    assert Image.open(io.BytesIO(client.get(first["full"]).content)).width <= 1200

    item = client.get(f"/api/items/{item_id}").json()
    assert item["figure_count"] == 2 and item["cover"]["id"] == first["id"]
    item = client.put(f"/api/items/{item_id}/cover", json={"figure_id": second["id"]}).json()
    assert item["cover"]["id"] == second["id"]
    assert client.put(f"/api/items/{item_id}/cover", json={"figure_id": 99999}).status_code == 404

    # A new PDF brings new figures, and the cover goes back to the first one.
    client.post(f"/api/items/{item_id}/file", files={"file": ("v.pdf", vector_paper(), "application/pdf")})
    figures.wait()
    item = client.get(f"/api/items/{item_id}").json()
    assert item["figure_count"] == 1 and item["cover"]["id"] != second["id"]
    assert client.get(first["thumb"]).status_code == 404
    assert len(list(figures.item_dir(item_id).iterdir())) == 1      # the old set is gone

    # A paper without figures, and deleting a paper.
    plain = client.post("/api/items/upload", files=[("files", ("p.pdf", make_pdf("Just text"), "application/pdf"))])
    plain_id = plain.json()["results"][0]["id"]
    figures.wait()
    p = client.get(f"/api/items/{plain_id}").json()
    assert p["figures_status"] == "none" and p["cover"] is None
    client.delete(f"/api/items/{item_id}?permanent=true")
    client.delete(f"/api/items/{plain_id}?permanent=true")
    assert not figures.item_dir(item_id).exists()


def test_cli_fills_in_missing_figures(client, capsys):
    from app import cli, db, figures
    from tests.sample_pdfs import raster_paper
    login(client)
    r = client.post("/api/items/upload", files=[("files", ("o.pdf", raster_paper(), "application/pdf"))])
    item_id = r.json()["results"][0]["id"]
    figures.wait()
    conn = db.connect()            # as if the paper predated figure extraction
    conn.execute("DELETE FROM figures WHERE item_id = ?", (item_id,))
    conn.execute("UPDATE items SET figures_status = NULL, figures_hash = NULL WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    assert client.get(f"/api/items/{item_id}").json()["figure_count"] == 0
    cli.main(["figures"])
    assert client.get(f"/api/items/{item_id}").json()["figure_count"] == 2
    assert "2 figures" in capsys.readouterr().out
    client.delete(f"/api/items/{item_id}?permanent=true")


def test_paper_address_serves_the_app(client):
    r = client.get("/paper/123")
    assert r.status_code == 200 and "<title>Bubo</title>" in r.text and "/static/paper.js" in r.text
    assert client.get("/paper/not-a-number").status_code == 422


def test_bold_figure_labels_without_punctuation():
    from app import figures
    from tests.sample_pdfs import bold_label_paper
    with pymupdf.open(stream=bold_label_paper(), filetype="pdf") as doc:
        found = figures.find_figures(doc)
    assert [(f.kind, f.label) for f in found] == [("caption", "Figure 1")]
    assert found[0].caption.startswith("Fig. 1 Decay")
    assert found[0].rect.contains(pymupdf.Rect(150, 230, 450, 400)) and found[0].rect.y1 < 432


def test_figures_report_and_newer_versions(client, capsys):
    from app import cli, db, figures
    from tests.sample_pdfs import raster_paper
    login(client)
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")
    with_figs = client.post("/api/items/upload", files=[("files", ("a.pdf", raster_paper(), "application/pdf"))]).json()["results"][0]["id"]
    plain = client.post("/api/items/upload", files=[("files", ("b.pdf", make_pdf("Only words"), "application/pdf"))]).json()["results"][0]["id"]
    no_pdf = client.post("/api/items", json={"title": "Paper without a PDF"}).json()["id"]
    figures.wait()
    capsys.readouterr()
    cli.main(["figures", "--report"])
    out = capsys.readouterr().out
    assert "1 of 3 papers have figures." in out
    assert "No PDF attached" in out and f"[{no_pdf}] Paper without a PDF" in out
    assert "No figures found in the PDF (1)" in out and f"[{plain}]" in out
    assert f"[{with_figs}]" not in out

    # Papers where an older version found nothing are looked at again.
    conn = db.connect()
    conn.execute("UPDATE items SET figures_version = 1 WHERE id = ?", (plain,))
    conn.commit()
    conn.close()
    cli.main(["figures", "--report"])
    assert "by an older version" in capsys.readouterr().out
    cli.main(["figures"])
    out = capsys.readouterr().out
    assert "Done: 0 figures from 1 paper." in out
    cli.main(["figures"])
    assert "Every paper already has its figures." in capsys.readouterr().out
    for i in (with_figs, plain, no_pdf):
        client.delete(f"/api/items/{i}?permanent=true")


# --------------------------------------------------------------------------- #
# People and the radar
# --------------------------------------------------------------------------- #

def test_orcid_ids():
    from app import people
    assert people.normalise_orcid("https://orcid.org/0000-0002-1825-0097") == "0000-0002-1825-0097"
    assert people.normalise_orcid("000000021825009x".replace("x", "7")) == "0000-0002-1825-0097"
    assert people.normalise_orcid("0000-0000-1000-003x") == "0000-0000-1000-003X"   # checksum X
    for bad in ("0000-0002-1825-0098", "1234", ""):
        with pytest.raises(people.PeopleError):
            people.normalise_orcid(bad)


def test_following_people_and_the_radar(client, monkeypatch):
    from datetime import date, timedelta
    from app import people
    login(client)
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")
    recent = (date.today() - timedelta(days=10)).isoformat()
    works = [
        {"key": "doi:10.1234/test.5678", "doi": "10.1234/test.5678", "title": "Deep Learning for Everything",
         "authors": [{"given": "Ada", "family": "Lovelace"}], "venue": "Journal of Testing",
         "pub_date": recent, "type": "article", "url": None},
        {"key": "doi:10.1/old", "doi": "10.1/old", "title": "An old paper", "authors": [], "venue": None,
         "pub_date": "2015", "type": "article", "url": None},
    ]
    monkeypatch.setattr(people, "fetch_person", lambda o: {"name": "Ada Lovelace", "family": "Lovelace",
                                                           "affiliation": "Analytical Engines"})
    monkeypatch.setattr(people, "fetch_works", lambda o, family=None, full=True: list(works))
    monkeypatch.setattr(people, "fetch_profile", lambda o, family=None, **kw: {})

    assert client.post("/api/people", json={"orcid": "0000-0002-1825-0098"}).status_code == 422
    p = client.post("/api/people", json={"orcid": "https://orcid.org/0000-0002-1825-0097"}).json()
    assert (p["name"], p["orcid"], p["works"], p["unseen"]) == ("Ada Lovelace", "0000-0002-1825-0097", 2, 1)
    assert client.post("/api/people", json={"orcid": "0000-0002-1825-0097"}).status_code == 422   # already followed

    # On the radar: only the recent work.
    radar = client.get("/api/radar").json()
    assert [w["title"] for w in radar["works"]] == ["Deep Learning for Everything"] and radar["unseen"] == 1
    assert radar["works"][0]["people"] == ["Ada Lovelace"]

    # A new publication appears at the next look; an old one added to ORCID does not.
    works.append({"key": "openalex:W1", "doi": None, "title": "A brand new preprint", "authors": [],
                  "venue": None, "pub_date": date.today().isoformat(), "type": "preprint", "url": "https://example.org/w1"})
    works.append({"key": "doi:10.1/older", "doi": "10.1/older", "title": "Added to ORCID late", "authors": [],
                  "venue": None, "pub_date": "2010-01-01", "type": "article", "url": None})
    assert client.post(f"/api/people/{p['id']}/refresh").json()["new"] == 1
    radar = client.get("/api/radar").json()
    assert [w["title"] for w in radar["works"]] == ["A brand new preprint", "Deep Learning for Everything"]

    # Add to the library: by DOI through the usual import (here the fake Crossref)…
    dl = next(w for w in radar["works"] if w["doi"])
    r = client.post(f"/api/works/{dl['id']}/add", json={"to_read": True}).json()
    assert r["status"] == "created" and r["item"]["to_read"] and r["item"]["venue"] == "Journal of Testing"
    # …or, without a DOI, from what ORCID/OpenAlex gave.
    pre = next(w for w in radar["works"] if not w["doi"])
    r = client.post(f"/api/works/{pre['id']}/add").json()
    assert r["status"] == "created" and r["item"]["title"] == "A brand new preprint" and r["item"]["year"] == date.today().year
    assert client.post(f"/api/works/{pre['id']}/add").json()["status"] == "duplicate"
    listed = {w["title"]: w["in_library"] for w in client.get(f"/api/people/{p['id']}").json()["works_list"]}
    assert listed == {"Deep Learning for Everything": True, "A brand new preprint": True,
                      "An old paper": False, "Added to ORCID late": False}

    # Adding marked them as seen; dismissing takes one off the radar.
    assert client.get("/api/radar").json()["unseen"] == 0
    client.post(f"/api/radar/{pre['id']}/dismiss")
    assert [w["title"] for w in client.get("/api/radar").json()["works"]] == ["Deep Learning for Everything"]

    assert client.delete(f"/api/people/{p['id']}").json() == {"ok": True}
    r = client.get("/api/people").json()
    assert r["people"] == [] and r["radar_unseen"] == 0
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}?permanent=true")


def test_openalex_works_need_the_persons_name():
    """Papers that carry someone's ORCID iD by mistake are left out."""
    from app import people
    orcid = "0000-0002-1825-0097"
    def work(title, raw):
        return {"title": title, "doi": None, "id": f"https://openalex.org/W{abs(hash(title))}",
                "publication_date": "2026-01-01", "type": "article",
                "authorships": [{"raw_author_name": raw, "author": {"display_name": "Josiah Carberry",
                                                                    "orcid": f"https://orcid.org/{orcid}"}}]}
    class Fake:
        def get(self, url, params=None):
            class R:
                def raise_for_status(self): pass
                def json(self):
                    return {"results": [work("His paper", "Carberry, J."), work("Also his", "Jósiah CARBERRY"),
                                        work("Someone else's", "Meng Li")]}
            return R()
    titles = [w["title"] for w in people._openalex_works(Fake(), orcid, "Carberry")]
    assert titles == ["His paper", "Also his"]
    assert len(people._openalex_works(Fake(), orcid, None)) == 3      # no family name: keep all


def test_people_profiles_and_photos(client, monkeypatch):
    import io
    from PIL import Image
    from app import db, people
    login(client)
    def png(w, h, colour):
        buf = io.BytesIO(); Image.new("RGB", (w, h), colour).save(buf, "PNG"); return buf.getvalue()
    monkeypatch.setattr(people, "fetch_person", lambda o: {"name": "Martin Fenner", "family": "Fenner", "affiliation": None})
    monkeypatch.setattr(people, "fetch_works", lambda o, family=None, full=True: [])
    monkeypatch.setattr(people, "fetch_profile", lambda o, family=None, **kw: {
        "affiliation": "Front Matter", "country": "DE", "role": "Founder", "works_count": 1056, "cited_by": 6811,
        "h_index": 35, "topics": '["Open Access", "Scientometrics"]', "wikidata_id": "Q30532925",
        "description": "German researcher", "photo_url": "https://commons.example/photo.jpg",
        "photo_credit": "https://commons.example/File:photo.jpg"})
    class FakeClient:                       # the photo download from Wikimedia Commons
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url):
            class R:
                content = png(800, 600, "red")
                def raise_for_status(self): pass
            return R()
    monkeypatch.setattr(people, "_client", lambda: FakeClient())

    p = client.post("/api/people", json={"orcid": "0000-0003-1419-2405"}).json()
    assert (p["affiliation"], p["role"], p["h_index"], p["topics"]) == ("Front Matter", "Founder", 35, ["Open Access", "Scientometrics"])
    assert p["photo_source"] == "wikidata" and p["photo_url"]
    photo = client.get(p["photo_url"])
    assert photo.headers["content-type"] == "image/webp"
    assert Image.open(io.BytesIO(photo.content)).size == (480, 600)          # cropped to a portrait

    # An uploaded photo replaces it, and survives later profile updates.
    up = client.post(f"/api/people/{p['id']}/photo", files={"file": ("me.png", png(300, 300, "blue"), "image/png")}).json()
    assert up["photo_source"] == "upload"
    people.refresh_profile(db.connect(), p["id"])
    again = next(x for x in client.get("/api/people").json()["people"] if x["id"] == p["id"])
    assert again["photo_source"] == "upload"
    assert Image.open(io.BytesIO(client.get(again["photo_url"]).content)).getpixel((10, 10))[2] > 200   # still blue
    assert client.post(f"/api/people/{p['id']}/photo", files={"file": ("x.txt", b"not an image", "text/plain")}).status_code == 422

    # Removing it keeps Wikidata's from coming back.
    gone = client.delete(f"/api/people/{p['id']}/photo").json()
    assert gone["photo_url"] is None and gone["photo_source"] == "removed"
    people.refresh_profile(db.connect(), p["id"])
    assert next(x for x in client.get("/api/people").json()["people"] if x["id"] == p["id"])["photo_url"] is None
    client.delete(f"/api/people/{p['id']}")
    assert not (people.photo_dir() / f"{p['id']}.webp").exists()


def test_openalex_paging_is_frugal_and_keeps_what_it_has():
    import httpx
    from app import people
    calls = []
    def page(n):
        return {"meta": {"next_cursor": f"c{n}"}, "results": [
            {"title": f"Work {n}-{i}", "doi": f"10.1/{n}.{i}", "id": f"W{n}{i}", "publication_date": "2026-01-01",
             "authorships": []} for i in range(3)]}
    class Fake:
        def get(self, url, params=None):
            calls.append(dict(params))
            n = len(calls)
            class R:
                def raise_for_status(self):
                    if n == 3:                 # the free daily budget runs out on the third page
                        raise httpx.HTTPStatusError("401", request=None, response=None)
                def json(self): return page(n)
            return R()
    works = people._openalex_works(Fake(), "0000-0002-1825-0097", None, full=True)
    assert len(works) == 6 and len(calls) == 3                  # two pages kept
    calls.clear()
    people._openalex_works(Fake(), "0000-0002-1825-0097", None, full=False)
    assert len(calls) == 1 and calls[0]["per-page"] == 50 and "cursor" not in calls[0]


def test_every_author_is_a_person_and_can_be_followed(client, monkeypatch):
    from app import people
    login(client)
    names = {"0000-0002-1825-0097": ("Ada Lovelace", "Lovelace"), "0000-0001-5109-3700": ("Bertram Lovelace", "Lovelace")}
    monkeypatch.setattr(people, "fetch_person", lambda o: {"name": names[o][0], "family": names[o][1], "affiliation": None})
    monkeypatch.setattr(people, "fetch_works", lambda o, family=None, full=True: [])
    monkeypatch.setattr(people, "fetch_profile", lambda o, family=None, **kw: {})
    a = client.post("/api/items", json={"title": "One", "authors": [{"given": "A.", "family": "Babbage"},
                                                                     {"given": "Ada", "family": "Lovelace"}]}).json()
    b = client.post("/api/items", json={"title": "Two", "authors": [{"given": "Ada", "family": "Lovelace"},
                                                                     {"given": "Bert", "family": "Lovelace"}]}).json()
    everyone = {p["name"]: p for p in client.get("/api/people", params={"scope": "all"}).json()["people"]}
    assert set(everyone) == {"A. Babbage", "Ada Lovelace", "Bert Lovelace"}
    assert everyone["Ada Lovelace"]["papers"] == 2 and not everyone["Ada Lovelace"]["followed"]
    assert client.get("/api/people").json()["people"] == []                # nobody followed yet
    m = client.get(f"/api/items/{b['id']}/people").json()["authors"]
    assert m[0]["id"] == everyone["Ada Lovelace"]["id"] and m[1]["id"] == everyone["Bert Lovelace"]["id"]

    # Following needs an iD: one typed for an author without one.
    bert = everyone["Bert Lovelace"]["id"]
    assert client.post(f"/api/people/{bert}/follow", json={}).status_code == 422
    f = client.post(f"/api/people/{bert}/follow", json={"orcid": "0000-0001-5109-3700"}).json()
    assert f["id"] == bert and f["followed"] and f["orcid"] == "0000-0001-5109-3700" and f["name"] == "Bertram Lovelace"
    page = client.get(f"/api/people/{bert}").json()
    assert [i["title"] for i in page["items"]] == ["Two"]
    # Following Ada by her iD makes the author of both papers that person.
    ada = client.post("/api/people", json={"orcid": "0000-0002-1825-0097"}).json()
    assert ada["id"] == everyone["Ada Lovelace"]["id"] and ada["papers"] == 2
    assert {p["name"] for p in client.get("/api/people").json()["people"]} == {"Ada Lovelace", "Bertram Lovelace"}

    # Unfollowed, they stay as authors; without papers or a follow, people go.
    client.delete(f"/api/people/{bert}")
    assert not client.get(f"/api/people/{bert}").json()["followed"]
    client.delete(f"/api/people/{ada['id']}")
    for i in (a, b):
        client.delete(f"/api/items/{i['id']}?permanent=true")
    assert client.get("/api/people", params={"scope": "all"}).json()["people"] == []


def test_orcid_ids_go_only_to_authors_with_that_name():
    from app import authors
    paper = [{"given": "Stéfan J.", "family": "van der Walt"}, {"given": "Ralf", "family": "Gommers"},
             {"given": "C.", "family": "Harris"}]
    found = authors._assign(paper, [("Stéfan", "van der Walt", "0000-0001-9276-1891"),
                                    ("Ralf", "Gommers", "0000-0002-0300-3333"),
                                    ("Stephen", "Osewe", "0009-0009-0562-6196")])     # only cited it
    assert found == 2 and [a.get("orcid") for a in paper] == ["0000-0001-9276-1891", "0000-0002-0300-3333", None]
    # Two candidates for one name: neither is given.
    one = [{"given": "J.", "family": "Smith"}]
    assert authors._assign(one, [("John", "Smith", "0000-0002-1825-0097"), ("Jane", "Smith", "0000-0001-5109-3700")]) == 0
    # Edited author lists keep the iDs found for the same names.
    kept = authors.keep_orcids(paper, [{"given": "Ralf", "family": "Gommers"}, {"given": "New", "family": "Author"}])
    assert kept[0]["orcid"] == "0000-0002-0300-3333" and "orcid" not in kept[1]


def test_journals_gallery_and_profile(client, monkeypatch):
    from app import journals
    login(client)
    made = [client.post("/api/items", json={"title": t, "venue": v, "year": y}).json() for t, v, y in [
        ("One", "Journal of Owls", 2019), ("Two", "journal of  owls ", 2024), ("Three", "Annals of Hooting", 2021)]]
    js = {j["key"]: j for j in client.get("/api/journals").json()["journals"]}
    assert set(js) == {"journal of owls", "annals of hooting"}
    assert js["journal of owls"]["papers"] == 2 and (js["journal of owls"]["first_year"], js["journal of owls"]["last_year"]) == (2019, 2024)
    assert client.get("/api/library-counts").json()["journals"] == 2
    assert {i["title"] for i in client.get("/api/items", params={"venue": "JOURNAL OF OWLS"}).json()} == {"One", "Two"}
    calls = []
    monkeypatch.setattr(journals, "_fetch", lambda name: calls.append(name) or {"publisher": "Owl Press", "h_index": 12})
    assert client.get("/api/journals/profile", params={"name": "Journal of Owls"}).json()["h_index"] == 12
    client.get("/api/journals/profile", params={"name": "journal of owls"})
    assert calls == ["Journal of Owls"]                      # kept, not looked up again
    assert client.get("/api/journals").json()["journals"][1]["publisher"] == "Owl Press"
    for i in made:
        client.delete(f"/api/items/{i['id']}?permanent=true")


def test_photographs_fill_their_tile_and_margins_are_trimmed():
    import random
    from PIL import Image, ImageDraw, ImageFilter
    from app import figures
    random.seed(3)
    tex = Image.new("L", (300, 200), 90)
    d = ImageDraw.Draw(tex)
    for _ in range(50):
        x, y, r = random.randint(0, 300), random.randint(0, 200), random.randint(5, 25)
        d.ellipse([x - r, y - r, x + r, y + r], fill=random.randint(60, 230))
    tex = tex.filter(ImageFilter.GaussianBlur(2))
    tex.putdata([max(0, min(255, v + random.randint(-25, 25))) for v in tex.get_flattened_data()])
    photo = Image.new("RGB", (400, 300), "white")
    photo.paste(tex.convert("RGB"), (50, 50))                 # a micrograph with white margins
    box, fill = figures.analyse(photo)
    assert fill and box == (50, 50, 350, 250)                  # cropped flush
    plot = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(plot)
    d.line([(40, 260), (380, 260)], fill="black", width=2)
    d.line([(40, 20), (40, 260)], fill="black", width=2)
    d.line([(40 + x, 140 - 60 * ((x / 40) % 2)) for x in range(0, 340, 20)], fill=(31, 119, 180), width=3)
    assert figures.analyse(plot)[1] is False
    heat = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(heat)
    for i in range(10):
        for j in range(8):
            d.rectangle([60 + i * 30, 20 + j * 30, 89 + i * 30, 49 + j * 30], fill=(255 - i * 20, 255 - j * 25, 200))
    assert figures.analyse(heat)[1] is False                 # flat blocks of colour: a diagram


def test_html_entities_in_names_are_decoded(client):
    from app import db, metadata
    m = metadata._crossref_to_meta({"type": "journal-article", "title": ["Nitrones &amp; minoxidil"],
        "container-title": ["Organic &amp; Biomolecular Chemistry"], "short-container-title": ["Org. Biomol. Chem."],
        "publisher": "Royal Society of Chemistry (RSC)", "author": [{"given": "Mar&#237;a", "family": "Garc&iacute;a"}]})
    assert m["venue"] == "Organic & Biomolecular Chemistry" and m["title"] == "Nitrones & minoxidil"
    assert m["authors"] == [{"given": "María", "family": "García"}]
    # Names stored with entities by earlier versions are fixed when the library opens.
    login(client)
    item = client.post("/api/items", json={"title": "Old", "venue": "Organic &amp; Biomolecular Chemistry"}).json()
    db.init_db()
    assert client.get(f"/api/items/{item['id']}").json()["venue"] == "Organic & Biomolecular Chemistry"
    assert [i["id"] for i in client.get("/api/items", params={"q": "Biomolecular"}).json()] == [item["id"]]
    client.delete(f"/api/items/{item['id']}?permanent=true")



def test_deleted_papers_go_to_the_trash(client):
    login(client)
    item = client.post("/api/items", json={"title": "Trashed", "doi": "10.9999/trash", "venue": "Bin Studies",
                                           "authors": [{"given": "Tess", "family": "Trash"}]}).json()
    client.put(f"/api/items/{item['id']}", json={"tags": ["rubbish"]})
    # An author with a photo (as when their page found one on Wikimedia Commons).
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (60, 80), "teal").save(buf, "PNG")
    tess_id = client.get(f"/api/items/{item['id']}/people").json()["authors"][0]["id"]
    client.post(f"/api/people/{tess_id}/photo", files={"file": ("t.png", buf.getvalue(), "image/png")})
    assert client.delete(f"/api/items/{item['id']}").json() == {"ok": True}
    # Gone from the library, tags, journals and people; kept in the trash.
    assert item["id"] not in [i["id"] for i in client.get("/api/items").json()]
    assert [i["id"] for i in client.get("/api/items", params={"trash": "true"}).json()] == [item["id"]]
    counts = client.get("/api/library-counts").json()
    assert counts["trash"] == 1 and counts["journals"] == 0
    assert "rubbish" not in [t["name"] for t in client.get("/api/tags").json()]
    assert "Tess Trash" not in [p["name"] for p in client.get("/api/people", params={"scope": "all"}).json()["people"]]
    assert client.get("/api/people").json()["everyone"] == 0
    assert client.get(f"/api/items/{item['id']}").json()["deleted_at"]
    # Restored, everything comes back: the same person, with their photo.
    client.post(f"/api/items/{item['id']}/restore")
    assert item["id"] in [i["id"] for i in client.get("/api/items").json()]
    tess = next(p for p in client.get("/api/people", params={"scope": "all"}).json()["people"] if p["name"] == "Tess Trash")
    assert tess["id"] == tess_id and tess["photo_url"]
    # Adding a paper that is in the trash takes it out of the trash.
    client.delete(f"/api/items/{item['id']}")
    r = client.post("/api/items/import", json={"identifier": "10.9999/trash"}).json()
    assert r["status"] == "duplicate" and r["item"]["id"] == item["id"] and not r["item"]["deleted_at"]
    # Deleting from the trash, or emptying it, is for good.
    client.delete(f"/api/items/{item['id']}")
    assert client.post("/api/trash/empty").json() == {"deleted": 1}
    assert client.get(f"/api/items/{item['id']}").status_code == 404
    assert client.get(f"/api/people/{tess_id}").status_code == 404        # gone, with their photo
    assert client.get("/api/library-counts").json()["trash"] == 0


def test_trash_is_emptied_after_30_days(client):
    from app import db, main
    login(client)
    item = client.post("/api/items", json={"title": "Old rubbish"}).json()
    client.delete(f"/api/items/{item['id']}")
    conn = db.connect()
    conn.execute("UPDATE items SET deleted_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (item["id"],))
    conn.commit()
    assert main.purge_expired_trash(conn) == 1
    conn.close()
    assert client.get(f"/api/items/{item['id']}").status_code == 404


def test_people_you_follow_stay_when_their_papers_are_deleted(client):
    from app import db
    login(client)
    item = client.post("/api/items", json={"title": "Only paper", "authors": [{"given": "Fay", "family": "Followed"},
                                                                            {"given": "Nell", "family": "Notfollowed"}]}).json()
    fay, nell = [a["id"] for a in client.get(f"/api/items/{item['id']}/people").json()["authors"]]
    conn = db.connect()
    conn.execute("UPDATE people SET followed = 1, orcid = '0000-0002-1825-0097' WHERE id = ?", (fay,))
    conn.commit()
    conn.close()
    names = lambda: {p["name"] for p in client.get("/api/people", params={"scope": "all"}).json()["people"]}
    client.delete(f"/api/items/{item['id']}")                    # to the trash
    assert names() == {"Fay Followed"}
    client.delete(f"/api/items/{item['id']}")                    # for good
    assert names() == {"Fay Followed"} and client.get(f"/api/people/{nell}").status_code == 404
    client.delete(f"/api/people/{fay}")
    assert names() == set()


def test_every_authors_profile_is_filled_in_the_background(client, monkeypatch):
    import io
    from PIL import Image
    from app import db, people
    login(client)
    item = client.post("/api/items", json={"title": "Famous", "authors": [
        {"given": "Ada", "family": "Lovelace"}, {"given": "Bo", "family": "Plain"}, {"given": "Cy", "family": "Noid"}]}).json()
    conn = db.connect()
    ada, bo, cy = [a["id"] for a in client.get(f"/api/items/{item['id']}/people").json()["authors"]]
    conn.execute("UPDATE people SET orcid = '0000-0002-1825-0097' WHERE id = ?", (ada,))
    conn.execute("UPDATE people SET orcid = '0000-0001-5109-3700' WHERE id = ?", (bo,))
    conn.execute("UPDATE people SET openalex_id = 'A99' WHERE id = ?", (cy,))       # known to OpenAlex only
    conn.commit()
    buf = io.BytesIO(); Image.new("RGB", (300, 400), "navy").save(buf, "JPEG")
    calls = []
    class Resp:
        def __init__(self, data=None, content=b""): self._d, self.content = data, content
        def raise_for_status(self): pass
        def json(self): return self._d
    def author(oid, name, orcid, h):
        return {"id": f"https://openalex.org/{oid}", "display_name": name, "orcid": orcid and f"https://orcid.org/{orcid}",
                "works_count": 10, "cited_by_count": 100 * h, "summary_stats": {"h_index": h}, "topics": [{"display_name": "Engines"}],
                "last_known_institutions": [{"display_name": "Somewhere", "country_code": "GB"}]}
    class Fake:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, params=None, **kw):
            calls.append(url)
            if url.endswith("/authors") and params["filter"].startswith("orcid:"):
                assert params["filter"] == "orcid:0000-0002-1825-0097|0000-0001-5109-3700"
                return Resp({"results": [author("A1", "Ada Lovelace", "0000-0002-1825-0097", 12),
                                         author("A2", "Someone Else", "0000-0001-5109-3700", 50)]})   # wrong name: ignored
            if url.endswith("/authors"):
                assert params["filter"] == "openalex:A99"
                return Resp({"results": [author("A99", "Cy Noid", None, 7)]})
            if url.endswith("/employments"):
                if "1825" in url:
                    return Resp({"affiliation-group": [{"summaries": [{"employment-summary": {
                        "organization": {"name": "Analytical Society", "address": {"country": "GB"}}, "role-title": "Countess"}}]}]})
                return Resp({"affiliation-group": []})
            if params and params.get("list") == "search":
                return Resp({"query": {"search": [{"title": "Q7259"}]}})
            if params and params.get("action") == "wbgetentities":
                return Resp({"entities": {"Q7259": {"claims": {
                    "P496": [{"mainsnak": {"datavalue": {"value": "0000-0002-1825-0097"}}}],
                    "P18": [{"mainsnak": {"datavalue": {"value": "Ada Lovelace portrait.jpg"}}}]},
                    "descriptions": {"en": {"value": "English mathematician"}}, "sitelinks": {"enwiki": {"title": "Ada Lovelace"}}}}})
            return Resp(content=buf.getvalue())          # the photo itself
    monkeypatch.setattr(people, "_client", lambda: Fake())
    monkeypatch.setattr(people.time, "sleep", lambda s: None)
    assert people.fill_profiles(conn) == 2
    everyone = {p["id"]: p for p in client.get("/api/people", params={"scope": "all"}).json()["people"]}
    a = client.get(f"/api/people/{ada}").json()
    assert a["h_index"] == 12 and a["affiliation"] == "Analytical Society" and a["role"] == "Countess"
    assert a["description"] == "English mathematician" and a["wikipedia"] == "Ada Lovelace" and a["photo_url"]
    assert everyone[bo]["h_index"] is None                                          # OpenAlex's was someone else
    assert everyone[cy]["h_index"] == 7 and everyone[cy]["affiliation"] == "Somewhere"
    n = len(calls)
    assert people.fill_profiles(conn) == 0 and len(calls) == n       # not asked again for a while
    conn.close()
    client.delete(f"/api/items/{item['id']}?permanent=true")


def test_merging_people_whose_names_are_misspelt(client):
    import io
    from PIL import Image
    from app import db
    login(client)
    one = client.post("/api/items", json={"title": "One", "authors": [{"given": "Mario", "family": "González-Jiménez"}]}).json()
    two = client.post("/api/items", json={"title": "Two", "authors": [{"given": "M.", "family": "Gonzales-Jimenez"},
                                                                    {"given": "Ana", "family": "Other"}]}).json()
    good = client.get(f"/api/items/{one['id']}/people").json()["authors"][0]["id"]
    bad = client.get(f"/api/items/{two['id']}/people").json()["authors"][0]["id"]
    assert good != bad
    # Bubo suggests the misspelt one, not someone else.
    assert [p["id"] for p in client.get(f"/api/people/{good}/similar").json()["people"]] == [bad]
    # The misspelt one has a photo and an iD; merged, the person keeps both, and the name chosen.
    buf = io.BytesIO(); Image.new("RGB", (60, 80), "olive").save(buf, "PNG")
    client.post(f"/api/people/{bad}/photo", files={"file": ("p.png", buf.getvalue(), "image/png")})
    conn = db.connect()
    conn.execute("UPDATE people SET orcid = '0000-0002-1825-0097' WHERE id = ?", (bad,))
    conn.commit()
    p = client.post(f"/api/people/{good}/merge", json={"other_id": bad, "name": "Mario González-Jiménez"}).json()
    assert p["id"] == good and p["papers"] == 2 and p["orcid"] == "0000-0002-1825-0097" and p["photo_url"]
    assert p["name"] == "Mario González-Jiménez"
    assert client.get(f"/api/people/{bad}").status_code == 404
    # The papers keep their author lists as printed.
    assert client.get(f"/api/items/{two['id']}").json()["authors"][0]["family"] == "Gonzales-Jimenez"
    # A later paper with the misspelt name, or the paper edited, is the merged person's.
    three = client.post("/api/items", json={"title": "Three", "authors": [{"given": "M.", "family": "Gonzales-Jimenez"}]}).json()
    assert client.get(f"/api/items/{three['id']}/people").json()["authors"][0]["id"] == good
    client.put(f"/api/items/{two['id']}", json={"authors": [{"given": "M.", "family": "Gonzales-Jimenez"}]})
    assert client.get(f"/api/items/{two['id']}/people").json()["authors"][0]["id"] == good
    assert client.get(f"/api/people/{good}").json()["name"] == "Mario González-Jiménez"     # the name stays
    # Two people with different iDs are not merged.
    ana = client.get(f"/api/items/{one['id']}/people").json()["authors"]
    other = next(a for a in client.get("/api/people", params={"scope": "all"}).json()["people"] if a["name"] == "Ana Other")
    conn.execute("UPDATE people SET orcid = '0000-0001-5109-3700' WHERE id = ?", (other["id"],))
    conn.commit()
    conn.close()
    r = client.post(f"/api/people/{good}/merge", json={"other_id": other["id"]})
    assert r.status_code == 409 and "different ORCID" in r.json()["detail"]
    for i in (one, two, three):
        client.delete(f"/api/items/{i['id']}?permanent=true")


def test_papers_without_a_doi_found_by_first_page_and_file_name(monkeypatch):
    from app import metadata, pdf
    assert metadata.parse_filename("Beake et al - 1994 - The kinetics and mechanism of oxidation of hydroquinone.pdf") == {
        "families": ["Beake"], "year": 1994, "title": "The kinetics and mechanism of oxidation of hydroquinone", "et_al": True}
    assert metadata.parse_filename("Curie and Curie - 1898 - On a new radioactive substance.pdf")["families"] == ["Curie", "Curie"]
    assert metadata.parse_filename("s41586-020-2649-2.pdf") == {}
    first = ("J. CHEM. SOC. PERKIN TRANS. 2 1994 957 The Kinetics and Mechanism of Oxidation of Hydroquinone and\n"
             "Chlorohydroquinone in the Presence of Nitrous Acid\nBen D. Beake, Roy B. Moodie and John P. B. Sandall")
    right = {"title": "The kinetics and mechanism of oxidation of hydroquinone and chlorohydroquinone in the presence of nitrous acid",
             "year": 1994, "authors": [{"given": "Ben D.", "family": "Beake"}], "doi": "10.1039/p29940000957"}
    same_author = {"title": "Nitration and oxidation of 4-methoxyphenol by nitrous acid in aqueous acid solution",
                   "year": 1994, "authors": [{"given": "B. D.", "family": "Beake"}], "doi": "10.1039/p29940000335"}
    hints = metadata.parse_filename("Beake et al - 1994 - The kinetics and mechanism of oxidation of hydroquinone and chlorohydroquinone.pdf")
    assert metadata.plausible(right, first, hints) and not metadata.plausible(same_author, first, hints)
    assert not metadata.plausible({**right, "year": 2004}, first, hints)               # another year
    queries = []
    def fake_search(q, text="", h=None):
        queries.append(q)
        return right if metadata.plausible(right, text, h) else None
    monkeypatch.setattr(metadata, "search_crossref_citation", fake_search)
    monkeypatch.setattr(metadata, "search_crossref_title", lambda t: None)
    info = pdf.PdfInfo(pages=[first])
    assert metadata.identify_pdf(info, filename="Beake et al - 1994 - The kinetics.pdf")["doi"] == "10.1039/p29940000957"
    assert queries[0].startswith("J. CHEM. SOC.")                                         # the top of the first page
    # Not online at all: the file name, with the given name printed on the first page.
    info = pdf.PdfInfo(pages=["Nitrosation of amino acids as a precursor of alkylation mechanisms.\nJulio Casado\nSalamanca"])
    fb = metadata.fallback_meta(info, "Casado - 2007 - Nitrosation of amino acids as a precursor of alkylation mechanisms.pdf")
    assert fb["title"] == "Nitrosation of amino acids as a precursor of alkylation mechanisms" and fb["year"] == 2007
    assert fb["authors"] == [{"given": "Julio", "family": "Casado"}]


def test_the_openalex_profile_with_the_persons_papers_is_chosen(client):
    """OpenAlex can have two profiles with one ORCID iD (one mixed with someone else's
    papers): the one named on the person's papers in the library wins, not the last listed."""
    import json as _json
    from app import db, people
    login(client)
    items = [client.post("/api/items", json={"title": f"Paper {n}", "doi": f"10.9999/mine.{n}",
                                             "authors": [{"given": "Mario", "family": "González-Jiménez"}]}).json() for n in range(3)]
    conn = db.connect()
    pid = client.get(f"/api/items/{items[0]['id']}/people").json()["authors"][0]["id"]
    # Two papers name the big profile for him, one the small one (as OpenAlex's matching did).
    for n, it in enumerate(items):
        conn.execute("UPDATE items SET authors = ? WHERE id = ?", (_json.dumps(
            [{"given": "Mario", "family": "González-Jiménez", "openalex": "A_BIG" if n < 2 else "A_SMALL"}]), it["id"]))
    conn.commit()
    big = {"id": "https://openalex.org/A_BIG", "works_count": 57}
    small = {"id": "https://openalex.org/A_SMALL", "works_count": 6}
    assert people.pick_openalex_profile(None, conn, pid, [big, small])["id"].endswith("A_BIG")
    assert people.pick_openalex_profile(None, conn, pid, [small, big])["id"].endswith("A_BIG")
    # No evidence in the library (and no DOIs to ask about): the one with more works.
    conn.execute("UPDATE items SET authors = ?, doi = NULL WHERE id IN (?, ?, ?)",
                 (_json.dumps([{"given": "Mario", "family": "González-Jiménez"}]), *[i["id"] for i in items]))
    conn.commit()
    assert people.pick_openalex_profile(None, conn, pid, [small, big])["id"].endswith("A_BIG")
    conn.close()
    for it in items:
        client.delete(f"/api/items/{it['id']}?permanent=true")


def test_older_titles_with_series_joined_names_and_abstract_journals(monkeypatch):
    from app import metadata, pdf
    # A scan with no text: only the file name helps.
    hints = metadata.parse_filename("Opgenorth et al - 1974 - Reaktion aromatischer Diazoniumsalze mit Nitritionen.pdf")
    paper = {"title": "Aromatische Diazoverbindungen, V 1) Reaktion aromatischer Diazoniumsalze mit Nitritionen 2)",
             "year": 1974, "authors": [{"given": "H.-J.", "family": "Opgenorth"}], "doi": "10.1002/jlac.197419740821"}
    assert metadata.plausible(paper, "", hints)                                    # the title after its series
    vliet = metadata.parse_filename("van der Vliet et al - 1995 - Tyrosine modification by reactive nitrogen species.pdf")
    assert metadata.plausible({"title": "Tyrosine Modification by Reactive Nitrogen Species: A Closer Look", "year": 1995,
                               "authors": [{"given": "A.", "family": "Vandervliet"}]}, "", vliet)   # "Vandervliet"
    assert not metadata.plausible({"title": "Tyrosine Modification by Reactive Nitrogen Species: A Closer Look", "year": 1995,
                                   "authors": [{"given": "A.", "family": "Smith"}]}, "", vliet)
    # The paper itself is preferred to ChemInform's abstract of it.
    class R:
        def json(self):
            return {"message": {"items": [
                {"title": ["ChemInform Abstract: AROMATISCHE DIAZOVERBINDUNGEN 5. MITT. REAKTION AROMATISCHER DIAZONIUMSALZE MIT NITRITIONEN"],
                 "author": [{"family": "OPGENORTH"}], "issued": {"date-parts": [[1974]]}, "DOI": "10.1002/chin.197445179", "type": "journal-article"},
                {"title": [paper["title"]], "author": [{"family": "Opgenorth"}], "issued": {"date-parts": [[1974]]},
                 "DOI": paper["doi"], "type": "journal-article"}]}}
    monkeypatch.setattr(metadata, "_search", lambda url, params: R())
    assert metadata.search_crossref_citation("Opgenorth 1974 Reaktion aromatischer Diazoniumsalze", "", hints)["doi"] == paper["doi"]
    # A PDF whose own title is a file's name is not searched with it.
    import pymupdf
    doc = pymupdf.open(); doc.new_page(); doc.set_metadata({"title": "tjv7373.PDF", "author": "Unknown"})
    info = pdf.analyze(doc.tobytes())
    assert info.meta_title is None and info.meta_author is None
