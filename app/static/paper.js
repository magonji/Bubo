// The paper sheet: figures carousel, details, notes and related papers. It is drawn in two
// places from the same code:
//   * "screen": the full-screen paper page on phones, at /paper/<id>;
//   * "pane":   the item pane on the right of the desktop library.
// Loaded after app.js and uses its helpers ($, api, state, icon, esc, toast, itemAction…).

Object.assign(ICONS, {
  "chevron-left": '<path d="M15 6l-6 6 6 6"/>',
  more: '<circle cx="12" cy="5.5" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="12" cy="18.5" r="1.2"/>',
  expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  share: '<path d="M12 15V3M7.5 7.5 12 3l4.5 4.5M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/>',
  "folder-plus": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M12 10.5v5M9.5 13h5"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m20.5 16-5-5-8 8.5"/>',
});

function createPaperView(root, mode) {
  const v = { root, mode, id: null, item: null, figures: [], people: [], index: 0, poll: null, notesTimer: null };
  const pane = mode === "pane";
  const q = (sel) => root.querySelector(`.pv ${sel}`);
  const scroller = () => (pane ? root : root.querySelector(".pv-scroll"));

  // ------------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------------
  async function render(id, { keepPlace = false, onGone = null } = {}) {
    clearTimeout(v.poll);
    let item, figs, matches;
    try {
      [item, figs, matches] = await Promise.all([api(`/api/items/${id}`), api(`/api/items/${id}/figures`),
        api(`/api/items/${id}/people`).then((r) => r.authors, () => [])]);
    } catch (err) {
      if (!keepPlace) toast("That paper is no longer in your library", true);
      onGone?.();
      return;
    }
    // Something else was shown meanwhile (another paper, the overview, the edit form).
    if (pane && (state.selected !== id || state.selectedIds.size > 1 || state.editing === id)) return;
    flushNotes();
    const scroll = keepPlace && v.id === id ? scroller()?.scrollTop ?? 0 : 0;
    const sameFigures = keepPlace && v.id === id && v.figures.map((f) => f.id).join() === figs.figures.map((f) => f.id).join();
    v.id = id;
    v.item = item;
    v.figures = figs.figures;
    v.people = matches || [];
    if (!sameFigures) v.index = Math.max(0, v.figures.findIndex((f) => f.id === figs.cover_id));

    root.innerHTML = sheetHTML(item, figs.status);
    if (scroller()) scroller().scrollTop = scroll;
    setupCarousel();
    setupAbstract();
    loadRelated(item);
    if (pane) {
      if (item.annotation_count) loadDetailAnnotations(item);       // app.js
      if (state.q && item.has_file) loadDetailMatches(item, state.q);
    }
    // Figures still being extracted: look again shortly.
    if (figs.status === "pending") v.poll = setTimeout(() => v.id === id && render(id, { keepPlace: true }), 3000);
  }

  function forget() {
    clearTimeout(v.poll);
    flushNotes();
    v.id = null;
  }

  function sheetHTML(i, figureStatus) {
    const back = $("#view-title").textContent || "My library";
    const venueYear = [i.venue, i.year].filter(Boolean).join(" · ");
    const canFind = !i.has_file && (i.doi || i.arxiv_id);
    const main = i.has_file ? ["open", "file", "Open PDF"] : canFind ? ["findpdf", "file-search", "Find PDF"] : ["attach", "paperclip", "Attach PDF"];
    const cols = state.collections.filter((c) => i.collections.includes(c.id));
    const doiUrl = i.doi ? `https://doi.org/${encodeURIComponent(i.doi).replace(/%2F/g, "/")}` : "";
    const date = (d) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
    const details = [
      i.venue && [{ inproceedings: "Conference", incollection: "Book", preprint: "Server", phdthesis: "University",
        mastersthesis: "University", techreport: "Institution" }[i.item_type] || "Journal",
        `<button type="button" class="pv-author-link" data-act="journal">${esc(i.venue)}</button>`],
      i.year && ["Year", i.year],
      i.volume && ["Volume", esc([i.volume, i.issue && `(${i.issue})`, i.pages && `, ${i.pages}`].filter(Boolean).join(""))],
      !i.volume && i.pages && ["Pages", esc(i.pages)],
      i.doi && ["DOI", `<a href="${esc(doiUrl)}" target="_blank" rel="noopener" class="pv-doi">${esc(i.doi)}</a>
        <button type="button" class="pv-mini" data-act="copy-doi" aria-label="Copy DOI">${icon("copy")}</button>`],
      i.arxiv_id && ["arXiv", `<a href="https://arxiv.org/abs/${esc(i.arxiv_id)}" target="_blank" rel="noopener">${esc(i.arxiv_id)}</a>`],
      i.url && !i.doi && ["Website", `<a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.url.replace(/^https?:\/\//, "").slice(0, 40))}</a>`],
      ["Added", date(i.added_at)],
      i.to_read_at && ["Reading list", `Since ${date(i.to_read_at)}`],
      ["PDF", i.has_file ? `Attached${i.file_size ? ` · ${fmtSize(i.file_size)}` : ""}` : "Not attached"],
      ...i.supplementary.map((s, n) => [n ? "" : "Supplementary",
        `<a href="/api/supplementary/${s.id}/file" target="_blank" rel="noopener">${esc(s.name)}</a>
         <button type="button" class="pv-mini" data-act="remove-supp" data-id="${s.id}" aria-label="Remove ${esc(s.name)}">${icon("x")}</button>`]),
    ].filter(Boolean);

    const menu = `
      <div class="menu-wrap">
        <button type="button" class="pv-icon" data-act="more" aria-label="More actions" aria-haspopup="menu" aria-expanded="false">${icon("more")}</button>
        <div class="menu pv-menu hidden" role="menu" aria-label="More actions">
          ${v.figures.length > 1 ? `<button type="button" role="menuitem" data-act="cover">${icon("image")} Set as cover figure</button>` : ""}
          <button type="button" role="menuitem" data-act="edit">${icon("pencil")} Edit details</button>
          <button type="button" role="menuitem" data-act="bib">${icon("braces")} Copy BibTeX</button>
          ${i.doi || i.arxiv_id ? `<button type="button" role="menuitem" data-act="refresh">${icon("refresh")} Refresh metadata</button>` : ""}
          ${i.has_file && i.annotation_count ? `<button type="button" role="menuitem" data-act="annotated">${icon("download")} Download with annotations</button>` : ""}
          ${i.has_file ? `<a role="menuitem" href="/api/items/${i.id}/file?download=true">${icon("download")} Download the PDF</a>` : ""}
          <button type="button" role="menuitem" data-act="attach">${icon("paperclip")} ${i.has_file ? "Replace PDF" : "Attach PDF"}</button>
          <button type="button" role="menuitem" data-act="supp">${icon("plus")} Add supplementary files</button>
          ${i.has_file ? `<button type="button" role="menuitem" data-act="refigure">${icon("refresh")} Extract figures again</button>` : ""}
          <div class="menu-sep" role="separator"></div>
          <button type="button" role="menuitem" data-act="delete" class="danger">${icon("trash")} Delete</button>
        </div>
      </div>`;
    const toread = `<button type="button" class="pv-icon${i.to_read ? " on" : ""}" data-act="toread" aria-pressed="${i.to_read}"
      aria-label="${i.to_read ? "On your reading list" : "Add to reading list"}" title="${i.to_read ? "On your reading list: click to remove" : "Add to reading list"}">${icon("bookmark")}</button>`;
    const bar = pane
      ? `<div class="pv-bar"><span class="pv-bar-title">${esc(TYPES[i.item_type] || "")}</span>${toread}${menu}</div>`
      : `<div class="pv-bar"><button type="button" class="pv-back" aria-label="Back to ${esc(back)}">${icon("chevron-left")}<span>${esc(back)}</span></button>${toread}${menu}</div>`;

    const body = `
      ${carouselHTML(i, figureStatus)}
      ${venueYear ? `<div class="pv-venue">${esc(venueYear)}</div>` : ""}
      <h1 class="pv-title" tabindex="-1">${esc(i.title) || "(untitled)"}</h1>
      ${authorsHTML(i)}
      <button type="button" class="pv-main primary" data-act="${main[0]}">${icon(main[1])} ${main[2]}</button>
      <div class="pv-actions${pane ? " two" : ""}">
        <button type="button" data-act="cite">${icon("quote")}<span>Cite</span></button>
        <button type="button" data-act="collections">${icon("folder-plus")}<span>Collection</span></button>
        ${pane ? "" : `<button type="button" data-act="share">${icon("share")}<span>Share</span></button>`}
      </div>
      ${pane ? `<div id="detail-matches"></div><div id="detail-annotations"></div>` : ""}
      ${i.abstract ? `<section class="pv-section"><h2>Abstract</h2>
        <p class="pv-abstract">${esc(i.abstract)}</p>
        <button type="button" class="pv-link pv-more hidden" data-act="abstract" aria-expanded="false">Read more</button></section>` : ""}
      <section class="pv-section"><h2>Details</h2>
        <dl class="pv-details">${details.map(([k, val]) => `<div><dt>${k}</dt><dd>${val}</dd></div>`).join("")}</dl></section>
      <section class="pv-section"><h2>Collections</h2>
        <div class="pv-chips">${cols.map((c) => `<button type="button" class="pv-chip" data-act="goto-collection" data-id="${c.id}">${esc(c.name)}</button>`).join("")}
          <button type="button" class="pv-chip pv-add" data-act="collections">${icon("plus")} Add</button></div></section>
      <section class="pv-section"><h2>Tags</h2>
        <div class="pv-chips">${i.tags.map((t) => `<button type="button" class="pv-chip" data-act="goto-tag" data-tag="${esc(t)}">${esc(t)}</button>`).join("")}
          <button type="button" class="pv-chip pv-add" data-act="add-tag">${icon("plus")} Add</button></div></section>
      <section class="pv-section"><h2><label for="pv-notes-${mode}">My notes</label></h2>
        <textarea class="pv-notes" id="pv-notes-${mode}" rows="4" placeholder="Add a note…">${esc(i.notes)}</textarea>
        <div class="pv-saved muted" aria-live="polite"></div></section>
      <section class="pv-section pv-related hidden"><h2>More in your library</h2><div class="pv-strip"></div></section>`;
    return `<div class="pv pv-${mode}">${bar}${pane ? body : `<div class="pv-scroll">${body}</div>`}</div>`;
  }

  // Authors you follow and who have a photo come first, with their portraits; everyone
  // else follows in the paper's order (people you follow link to their page).
  function authorsHTML(i) {
    if (!i.authors.length) return "";
    const faces = [], rest = [];
    i.authors.forEach((a, n) => {
      const m = v.people[n], name = [a.given, a.family].filter(Boolean).join(" ");
      if (m?.photo_url) faces.push({ name, m });
      else rest.push(m ? `<button type="button" class="pv-author-link" data-act="person" data-id="${m.id}">${esc(name)}</button>` : esc(name));
    });
    const SHORT = 6;
    const list = rest.length > SHORT
      ? `${rest.slice(0, SHORT).join(", ")}<span class="pv-more-authors" hidden>, ${rest.slice(SHORT).join(", ")}</span>
         <button type="button" class="pv-link pv-authors-more" data-act="authors" aria-expanded="false">and ${rest.length - SHORT} more</button>`
      : rest.join(", ");
    return `<div class="pv-authors">
      ${faces.length ? `<div class="pv-faces">${faces.map(({ name, m }) => `
        <button type="button" class="pv-face" data-act="person" data-id="${m.id}" title="${esc(m.name)}: their page">
          ${avatarHTML({ name: m.name, photo_url: m.photo_url }, "avatar-face")}<span>${esc(name)}</span></button>`).join("")}</div>` : ""}
      ${rest.length ? `<p class="pv-author-list">${list}</p>` : ""}
    </div>`;
  }

  function carouselHTML(i, status) {
    const figs = v.figures;
    if (!figs.length) {
      const note = status === "pending" ? "Extracting figures from the PDF…" : "";
      return `<div class="car car-empty"><div class="car-tile">${thumbHTML({ ...i, cover: null })}</div></div>
        ${note ? `<div class="car-nav"><span class="car-count">${note}</span></div>` : ""}`;
    }
    return `
    <div class="car" role="region" aria-roledescription="carousel" aria-label="Figures">
      <div class="car-track" tabindex="0">
        ${figs.map((f, n) => `<div class="car-slide" role="group" aria-roledescription="slide" aria-label="${n + 1} of ${figs.length}">
          <div class="car-tile"><img src="${esc(f.full)}" alt="${esc(f.label || `Figure ${n + 1}`)}" ${n === v.index ? "" : 'loading="lazy"'}
            width="${f.width}" height="${f.height}" decoding="async"></div></div>`).join("")}
      </div>
      ${figs.length > 1 ? `<button type="button" class="car-arrow car-prev" data-act="prev" aria-label="Previous figure">${icon("chevron-left")}</button>
        <button type="button" class="car-arrow car-next" data-act="next" aria-label="Next figure">${icon("chevron-right")}</button>` : ""}
      <button type="button" class="car-expand" data-act="expand"><span>${icon("expand")} Expand</span></button>
    </div>
    <div class="car-nav">
      ${figs.length > 1 && figs.length <= 9 ? `<div class="car-dots">${figs.map((f, n) => `<button type="button" data-act="dot" data-n="${n}" aria-label="Figure ${n + 1}"></button>`).join("")}</div>` : ""}
      <span class="car-count" aria-live="polite"></span>
      <button type="button" class="pv-link" data-act="all-figures">All figures</button>
    </div>
    <p class="car-caption"></p>`;
  }

  // ------------------------------------------------------------------------
  // Carousel, abstract and related papers
  // ------------------------------------------------------------------------
  function showFigure() {
    const n = v.index, f = v.figures[n];
    if (!f || !q(".car-count")) return;
    q(".car-count").textContent = `${f.label && /\d/.test(f.label) ? f.label : "Figure"} · ${n + 1} of ${v.figures.length}`;
    q(".car-caption").textContent = f.caption || "";
    root.querySelectorAll(".car-dots button").forEach((d, k) => d.setAttribute("aria-current", String(k === n)));
    q(".car-prev")?.toggleAttribute("disabled", n === 0);
    q(".car-next")?.toggleAttribute("disabled", n === v.figures.length - 1);
  }

  function setupCarousel() {
    const track = q(".car-track");
    if (!track) return;
    track.scrollLeft = v.index * track.clientWidth;
    let t;
    track.addEventListener("scroll", () => {
      clearTimeout(t);
      t = setTimeout(() => {
        const n = Math.round(track.scrollLeft / track.clientWidth);
        if (n !== v.index && v.figures[n]) { v.index = n; showFigure(); }
      }, 60);
    }, { passive: true });
    track.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); goTo(v.index + 1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); goTo(v.index - 1); }
    });
    showFigure();
  }

  function goTo(n, smooth = true) {
    const track = q(".car-track");
    if (!track || !v.figures[n]) return;
    track.scrollTo({ left: n * track.clientWidth, behavior: smooth ? "smooth" : "instant" });
    if (!smooth) { v.index = n; showFigure(); }
  }

  function setupAbstract() {
    const p = q(".pv-abstract");
    if (p && p.scrollHeight > p.clientHeight + 2) q(".pv-more").classList.remove("hidden");
  }

  // "More in your library": papers sharing a collection or a tag, otherwise recent ones.
  async function loadRelated(item) {
    const p = new URLSearchParams({ sort: "year" });
    if (item.collections.length) p.set("collection", item.collections[0]);
    else if (item.tags.length) p.set("tag", item.tags[0]);
    else p.set("sort", "added");
    let items;
    try { items = await api("/api/items?" + p); } catch { return; }
    if (v.id !== item.id || !q(".pv-strip")) return;
    items = items.filter((x) => x.id !== item.id).slice(0, 12);
    if (!items.length) return;
    q(".pv-strip").innerHTML = items.map((x) => `
      <a class="card" href="/paper/${x.id}" data-paper="${x.id}">
        <div class="thumb">${thumbHTML(x)}</div>
        <div class="c-title">${esc(x.title) || "(untitled)"}</div>
        <div class="c-meta">${esc([authorsShort(x.authors), x.year].filter(Boolean).join(" · "))}</div>
      </a>`).join("");
    q(".pv-related").classList.remove("hidden");
  }

  // ------------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------------
  root.addEventListener("click", async (e) => {
    if (!e.target.closest(".pv")) return;           // the pane also shows other things
    const related = e.target.closest(".pv-strip a[data-paper]");
    if (related) {
      e.preventDefault();
      const id = Number(related.dataset.paper);
      if (pane) return showItem(id);
      history.pushState({ bubo: "paper", id }, "", `/paper/${id}`);
      return render(id);
    }
    if (e.target.closest(".pv-back")) return closePaper();
    const el = e.target.closest("[data-act]");
    if (!el) {
      if (!e.target.closest(".menu-wrap")) closeMenu();
      return;
    }
    const i = v.item, act = el.dataset.act;
    if (act !== "more") closeMenu();
    switch (act) {
      case "more": return toggleMenu();
      case "toread": return setToRead([i.id], !i.to_read);
      case "open": return openViewer(i);
      case "findpdf": case "attach": case "bib": case "refresh": case "annotated": case "delete": case "cite":
        return itemAction(act, i);
      case "edit": return editDetails(i);
      case "supp": {
        const input = $("#supp-input");
        input.onchange = async () => {
          const files = [...input.files];
          input.value = "";
          if (files.length) await addSupplementary(i.id, files);
        };
        return input.click();
      }
      case "remove-supp": {
        const s = i.supplementary.find((x) => x.id === Number(el.dataset.id));
        if (!s || !confirm(`Remove “${s.name}” from this paper? The file is deleted.`)) return;
        try { await api(`/api/supplementary/${s.id}`, { method: "DELETE" }); toast("Supplementary file removed"); refresh(); }
        catch (err) { toast(err.message, true); }
        return;
      }
      case "refigure":
        try { await api(`/api/items/${i.id}/figures/extract`, { method: "POST" }); toast("Extracting the figures again…"); render(i.id, { keepPlace: true }); }
        catch (err) { toast(err.message, true); }
        return;
      case "cover": {
        const f = v.figures[v.index];
        try {
          await api(`/api/items/${i.id}/cover`, { method: "PUT", json: { figure_id: f.id } });
          toast(`${f.label || "This figure"} is now the cover`);
          refresh();
        } catch (err) { toast(err.message, true); }
        return;
      }
      case "prev": return goTo(v.index - 1);
      case "next": return goTo(v.index + 1);
      case "dot": return goTo(Number(el.dataset.n));
      case "expand": return openLightbox(v, "figure");
      case "all-figures": return openLightbox(v, "grid");
      case "authors": {
        const more = q(".pv-more-authors"), open = more.hidden;
        more.hidden = !open;
        el.setAttribute("aria-expanded", String(open));
        el.textContent = open ? "fewer" : `and ${more.textContent.split(",").filter((s) => s.trim()).length} more`;
        return;
      }
      case "person": {
        const p = (state.people || []).find((x) => x.id === Number(el.dataset.id));
        if (!pane) closePaper();
        return setView({ type: "person", id: Number(el.dataset.id), name: p?.name || el.textContent.trim() });
      }
      case "abstract": {
        const open = q(".pv-abstract").classList.toggle("open");
        el.setAttribute("aria-expanded", String(open));
        el.textContent = open ? "Read less" : "Read more";
        return;
      }
      case "copy-doi": copyText(i.doi); return toast("DOI copied");
      case "share": return sharePaper(i);
      case "collections": return chooseCollections(i);
      case "goto-collection": if (!pane) closePaper(); return setView({ type: "collection", id: Number(el.dataset.id) });
      case "goto-tag": if (!pane) closePaper(); return setView({ type: "tag", name: el.dataset.tag });
      case "journal": if (!pane) closePaper(); return openJournal(i.venue.trim());
      case "add-tag": {
        const name = prompt("Add a tag")?.trim();
        if (!name) return;
        try { await api(`/api/items/${i.id}`, { method: "PATCH", json: { tags: [...i.tags, name] } }); refresh(); }
        catch (err) { toast(err.message, true); }
        return;
      }
    }
  });

  function toggleMenu() {
    const menu = q(".pv-menu"), btn = q('[data-act="more"]');
    const open = menu.classList.toggle("hidden") === false;
    btn.setAttribute("aria-expanded", String(open));
    if (open) menu.querySelector("[role=menuitem]")?.focus();
  }
  function closeMenu() {
    const menu = q(".pv-menu");
    if (!menu || menu.classList.contains("hidden")) return;
    menu.classList.add("hidden");
    q('[data-act="more"]').setAttribute("aria-expanded", "false");
  }
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && q(".pv-menu") && !q(".pv-menu").classList.contains("hidden")) {
      e.stopPropagation();
      closeMenu();
      q('[data-act="more"]').focus();
    }
  });
  document.addEventListener("click", (e) => { if (!root.contains(e.target)) closeMenu(); });

  // Notes are saved as you type.
  root.addEventListener("input", (e) => {
    if (!e.target.matches(".pv-notes")) return;
    clearTimeout(v.notesTimer);
    q(".pv-saved").textContent = "";
    v.notesTimer = setTimeout(saveNotes, 800);
  });
  root.addEventListener("focusout", (e) => { if (e.target.matches?.(".pv-notes")) flushNotes(); });
  function flushNotes() {
    if (v.notesTimer) { clearTimeout(v.notesTimer); saveNotes(); }
  }
  async function saveNotes() {
    v.notesTimer = null;
    const box = q(".pv-notes");
    if (!box || !v.item || box.value === (v.item.notes || "")) return;
    const notes = box.value, item = v.item;
    try {
      await api(`/api/items/${item.id}`, { method: "PATCH", json: { notes } });
      item.notes = notes;
      const local = state.items.find((x) => x.id === item.id);
      if (local) local.notes = notes;
      if (q(".pv-saved") && v.item === item) q(".pv-saved").textContent = "Saved";
    } catch (err) { toast(err.message, true); }
  }

  return { render, forget, state: v, flushNotes, focusTitle: () => q(".pv-title")?.focus({ preventScroll: true }) };
}

// ----------------------------------------------------------------------------
// Shared by both views
// ----------------------------------------------------------------------------

// "Edit details": the full form of every field (app.js). On the desktop it replaces the
// sheet in the pane, with a way back; on phones it slides over the paper screen.
function editDetails(i) {
  if (narrow.matches) { select(i); return showDetailPane(); }
  state.editing = i.id;
  renderEditForm(i);
}

// Share the DOI (or the paper's web page) with its citation: the /paper link itself only
// works for you, behind your password.
async function sharePaper(i) {
  const url = i.doi ? `https://doi.org/${i.doi}` : i.arxiv_id ? `https://arxiv.org/abs/${i.arxiv_id}` : i.url || "";
  let text = i.title;
  try { text = (await api(`/api/items/${i.id}/citation`)).text; } catch {}
  if (navigator.share) {
    try { await navigator.share({ title: i.title, text, ...(url ? { url } : {}) }); } catch { /* cancelled */ }
    return;
  }
  copyText(url ? `${text}\n${url}` : text);
  toast("Citation and link copied");
}

function chooseCollections(i) {
  const dlg = $("#pv-dialog");
  const byParent = {};
  for (const c of state.collections) (byParent[c.parent_id ?? "root"] ||= []).push(c);
  const rows = [];
  const walk = (parent, depth) => (byParent[parent] || []).forEach((c) => {
    rows.push(`<label class="pv-check" style="padding-left:${depth * 18}px"><input type="checkbox" value="${c.id}"
      ${i.collections.includes(c.id) ? "checked" : ""}> ${esc(c.name)}</label>`);
    walk(c.id, depth + 1);
  });
  walk("root", 0);
  dlg.innerHTML = `<form method="dialog">
    <h3 id="pv-dialog-title">Collections</h3>
    ${rows.length ? `<div class="pv-checks">${rows.join("")}</div>` : `<p class="muted">You have no collections yet. Create them from the sidebar.</p>`}
    <div class="dialog-buttons"><button type="button" data-close>Cancel</button>
      ${rows.length ? `<button type="submit" class="primary">Save</button>` : ""}</div></form>`;
  dlg.querySelector("[data-close]").addEventListener("click", () => dlg.close());
  dlg.querySelector("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const ids = [...dlg.querySelectorAll("input:checked")].map((x) => Number(x.value));
    dlg.close();
    try { await api(`/api/items/${i.id}`, { method: "PATCH", json: { collections: ids } }); toast("Collections saved"); refresh(); }
    catch (err) { toast(err.message, true); }
  });
  dlg.showModal();
}

// Full-screen figures: one at a time ("Expand") or all of them ("All figures").
let lightboxView = null;
function openLightbox(view, mode) {
  lightboxView = view;
  const dlg = $("#lightbox"), figs = view.figures;
  const head = `<div class="lb-bar"><span class="lb-title" id="lightbox-title">${mode === "grid" ? `All figures (${figs.length})` : ""}</span>
    <button type="button" class="pv-icon" data-lb="close" aria-label="Close">${icon("x")}</button></div>`;
  if (mode === "grid") {
    dlg.innerHTML = head + `<div class="lb-grid">${figs.map((f, n) => `
      <button type="button" class="lb-thumb" data-lb="pick" data-n="${n}" aria-label="${esc(f.label || `Figure ${n + 1}`)}">
        <span class="thumb"><span class="tile"><img src="${esc(f.thumb)}" alt="" loading="lazy" width="${f.thumb_width}" height="${f.thumb_height}"></span></span>
        <span class="lb-label">${esc(f.label || `Figure ${n + 1}`)} · p. ${f.page}</span></button>`).join("")}</div>`;
  } else {
    const f = figs[view.index];
    dlg.innerHTML = head + `<div class="lb-stage"><div class="lb-tile"><img src="${esc(f.full)}" alt="${esc(f.label || "Figure")}"></div></div>
      <div class="lb-foot">
        ${figs.length > 1 ? `<button type="button" class="car-arrow" data-lb="prev" aria-label="Previous figure" ${view.index ? "" : "disabled"}>${icon("chevron-left")}</button>` : ""}
        <p class="lb-caption"><b>${esc(f.label || "")}</b> ${esc((f.caption || "").replace(/^\s*(fig(ure)?\.?)\s*\S+\s*[.:|—–-]?\s*/i, ""))}</p>
        ${figs.length > 1 ? `<button type="button" class="car-arrow" data-lb="next" aria-label="Next figure" ${view.index < figs.length - 1 ? "" : "disabled"}>${icon("chevron-right")}</button>` : ""}
      </div>`;
    $("#lightbox-title").textContent = `${view.index + 1} of ${figs.length}`;
  }
  dlg.dataset.mode = mode;
  if (!dlg.open) dlg.showModal();
  dlg.querySelector('[data-lb="close"]').focus();
}

function lightboxGoTo(n) {
  const view = lightboxView, track = view.root.querySelector(".car-track");
  view.index = n;
  if (track) track.scrollTo({ left: n * track.clientWidth, behavior: "instant" });
}

$("#lightbox").addEventListener("click", (e) => {
  const el = e.target.closest("[data-lb]");
  if (!el || !lightboxView) return;
  const a = el.dataset.lb, dlg = $("#lightbox"), view = lightboxView;
  if (a === "close") return dlg.close();
  if (a === "pick") { dlg.close(); return lightboxGoTo(Number(el.dataset.n)); }
  if (a === "prev" || a === "next") {
    lightboxGoTo(Math.max(0, Math.min(view.figures.length - 1, view.index + (a === "next" ? 1 : -1))));
    openLightbox(view, "figure");
  }
});
$("#lightbox").addEventListener("keydown", (e) => {
  if ($("#lightbox").dataset.mode !== "figure") return;
  if (e.key === "ArrowRight") $('#lightbox [data-lb="next"]:not([disabled])')?.click();
  if (e.key === "ArrowLeft") $('#lightbox [data-lb="prev"]:not([disabled])')?.click();
});
// Swipe between figures in the full-screen view.
(() => {
  let x0 = null;
  const dlg = $("#lightbox");
  dlg.addEventListener("touchstart", (e) => { if (dlg.dataset.mode === "figure" && e.touches.length === 1) x0 = e.touches[0].clientX; }, { passive: true });
  dlg.addEventListener("touchend", (e) => {
    if (x0 == null) return;
    const dx = e.changedTouches[0].clientX - x0;
    x0 = null;
    if (Math.abs(dx) > 60) dlg.querySelector(`[data-lb="${dx < 0 ? "next" : "prev"}"]:not([disabled])`)?.click();
  });
})();

// ----------------------------------------------------------------------------
// The phone screen: /paper/<id>
// ----------------------------------------------------------------------------
const PAPER_PATH = /^\/paper\/(\d+)\/?$/;
const paperView = $("#paper");
const screenView = createPaperView(paperView, "screen");
const paneView = createPaperView($("#detail"), "pane");
let paperFromApp = false;

async function openPaper(id) {
  if (!narrow.matches) return showItem(id);
  history.pushState({ bubo: "paper", id }, "", `/paper/${id}`);
  paperFromApp = true;
  await showPaperScreen(id);
}

async function showPaperScreen(id, keepPlace = false) {
  paperView.classList.remove("hidden");
  document.body.classList.add("show-paper");
  await screenView.render(id, { keepPlace, onGone: closePaper });
  if (!keepPlace) screenView.focusTitle();   // for screen readers, without a visible ring
}

function closePaper() {
  if (history.state?.bubo === "paper" && paperFromApp) return history.back();  // popstate hides it
  history.replaceState(null, "", "/");
  hidePaper();
}

function hidePaper() {
  screenView.forget();
  paperView.classList.add("hidden");
  paperView.innerHTML = "";
  document.body.classList.remove("show-paper");
}

// The address decides: /paper/<id> shows that paper, anything else the library.
function syncPaperWithLocation() {
  const m = location.pathname.match(PAPER_PATH);
  if (m && narrow.matches) showPaperScreen(Number(m[1]), Number(m[1]) === screenView.state.id);
  else if (screenView.state.id) hidePaper();
}
window.addEventListener("popstate", syncPaperWithLocation);

// Called once the library has loaded (see start() in app.js).
function routeFromLocation() {
  const m = location.pathname.match(PAPER_PATH);
  if (!m) return;
  if (narrow.matches) showPaperScreen(Number(m[1]));
  else { history.replaceState(null, "", "/"); showItem(Number(m[1])); }
}

narrow.addEventListener("change", () => {
  if (narrow.matches || !screenView.state.id) return;
  const id = screenView.state.id;
  history.replaceState(null, "", "/");
  hidePaper();
  showItem(id);
});

// After any change made elsewhere (refresh() in app.js), show the paper's new state.
function refreshPaper() {
  if (screenView.state.id) showPaperScreen(screenView.state.id, true);
}
