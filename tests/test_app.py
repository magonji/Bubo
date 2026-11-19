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
    assert client.delete(f"/api/items/{item_id}").status_code == 200
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
    client.delete(f"/api/items/{item_id}")
    assert client.patch(f"/api/annotations/{hl['id']}", json={"color": "pink"}).status_code == 404


def test_vendored_pdfjs_is_served(client):
    r = client.get("/static/vendor/pdfjs/pdf.min.mjs")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert client.get("/static/vendor/pdfjs/wasm/openjpeg.wasm").headers["content-type"] == "application/wasm"


def pdf_files():
    root = main.settings.papers_dir
    return sorted(str(p.relative_to(root)) for p in root.rglob("*.pdf"))


def test_flat_readable_names(client, monkeypatch):
    login(client)
    from app import storage
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}")

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
    monkeypatch.setattr(metadata, "identify_pdf", lambda info: {
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
        client.delete(f"/api/items/{it['id']}")
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
    client.delete(f"/api/items/{a}")
    client.delete(f"/api/items/{b}")


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
        client.delete(f"/api/items/{i['id']}")


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
    client.delete(f"/api/items/{item['id']}")


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
        client.delete(f"/api/items/{it['id']}")
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
        client.delete(f"/api/items/{it['id']}")
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
    monkeypatch.setattr(metadata, "identify_pdf", lambda info: {"title": "Owls of Europe", "year": 2020})
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
    client.delete(f"/api/items/{item_id}")


def test_reading_list(client):
    login(client)
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}")
    a = client.post("/api/items", json={"title": "Later", "to_read": True}).json()
    b = client.post("/api/items", json={"title": "Already read"}).json()
    assert a["to_read"] and a["to_read_at"] and not b["to_read"]
    assert [i["title"] for i in client.get("/api/items", params={"to_read": True}).json()] == ["Later"]
    assert client.get("/api/library-counts").json() == {"all": 2, "unfiled": 2, "to_read": 1}

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
        client.delete(f"/api/items/{i['id']}")



def test_new_items_to_reading_list_and_queue_order(client, monkeypatch):
    login(client)
    import time
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}")
    monkeypatch.setattr(metadata, "identify_pdf", lambda info: None)
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
        client.delete(f"/api/items/{it['id']}")


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
    client.delete(f"/api/items/{item['id']}")


def test_find_pdf_and_overview(client, monkeypatch):
    login(client)
    for it in client.get("/api/items").json():
        client.delete(f"/api/items/{it['id']}")
    full = client.post("/api/items", json={"title": "Complete", "authors": [{"family": "A"}], "year": 2020,
                                           "item_type": "misc", "doi": "10.1/x", "to_read": True}).json()
    bare = client.post("/api/items", json={"title": "New item"}).json()
    ov = client.get("/api/overview").json()
    assert [i["title"] for i in ov["recent"]] == ["New item", "Complete"]
    assert [i["title"] for i in ov["to_read"]] == ["Complete"] and ov["to_read_total"] == 1
    assert [i["title"] for i in ov["incomplete"]] == ["New item"] and ov["incomplete_total"] == 1

    assert client.post(f"/api/items/{bare['id']}/find-pdf").status_code == 422
    monkeypatch.setattr(metadata, "find_pdf", lambda item: None)
    assert client.post(f"/api/items/{full['id']}/find-pdf").status_code == 404
    data = make_pdf("Found it")
    monkeypatch.setattr(metadata, "find_pdf", lambda item: data)
    found = client.post(f"/api/items/{full['id']}/find-pdf").json()
    assert found["has_file"] and client.get(f"/api/items/{full['id']}/file").content == data
    assert client.post(f"/api/items/{full['id']}/find-pdf").status_code == 409
    for i in (full, bare):
        client.delete(f"/api/items/{i['id']}")



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
