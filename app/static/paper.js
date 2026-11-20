// The paper screen on phones (/paper/<id>): figures carousel, details, notes and related
// papers. Loaded after app.js and uses its helpers ($, api, state, icon, esc, toast…).
// On wider screens a /paper/<id> link simply selects the paper in the library.

const paper = { id: null, item: null, figures: [], index: 0, fromApp: false, poll: null, notesTimer: null };
const PAPER_PATH = /^\/paper\/(\d+)\/?$/;
const paperView = $("#paper");

Object.assign(ICONS, {
  "chevron-left": '<path d="M15 6l-6 6 6 6"/>',
  more: '<circle cx="12" cy="5.5" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="12" cy="18.5" r="1.2"/>',
  expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  share: '<path d="M12 15V3M7.5 7.5 12 3l4.5 4.5M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/>',
  "folder-plus": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M12 10.5v5M9.5 13h5"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m20.5 16-5-5-8 8.5"/>',
});

// --------------------------------------------------------------------------
// Opening, closing and the address bar
// --------------------------------------------------------------------------
async function openPaper(id) {
  if (!narrow.matches) return showItem(id);
  history.pushState({ bubo: "paper", id }, "", `/paper/${id}`);
  paper.fromApp = true;
  await renderPaper(id);
}

function closePaper() {
  if (history.state?.bubo === "paper" && paper.fromApp) return history.back();  // popstate hides it
  history.replaceState(null, "", "/");
  hidePaper();
}

function hidePaper() {
  clearTimeout(paper.poll);
  flushNotes();
  paper.id = null;
  paperView.classList.add("hidden");
  document.body.classList.remove("show-paper");
}

// The address decides: /paper/<id> shows that paper, anything else the library.
function syncPaperWithLocation() {
  const m = location.pathname.match(PAPER_PATH);
  if (m && narrow.matches) renderPaper(Number(m[1]), { keepPlace: Number(m[1]) === paper.id });
  else if (paper.id) hidePaper();
}
window.addEventListener("popstate", syncPaperWithLocation);

// Called once the library has loaded (see start() in app.js).
function routeFromLocation() {
  const m = location.pathname.match(PAPER_PATH);
  if (!m) return;
  if (narrow.matches) renderPaper(Number(m[1]));
  else { history.replaceState(null, "", "/"); showItem(Number(m[1])); }
}

narrow.addEventListener("change", () => {
  if (narrow.matches || !paper.id) return;
  const id = paper.id;
  history.replaceState(null, "", "/");
  hidePaper();
  showItem(id);
});

// After any change made elsewhere (refresh() in app.js), show the paper's new state.
function refreshPaper() {
  if (paper.id) renderPaper(paper.id, { keepPlace: true });
}

// --------------------------------------------------------------------------
// Rendering
// --------------------------------------------------------------------------
async function renderPaper(id, { keepPlace = false } = {}) {
  clearTimeout(paper.poll);
  let item, figs;
  try {
    [item, figs] = await Promise.all([api(`/api/items/${id}`), api(`/api/items/${id}/figures`)]);
  } catch (err) {
    // Deleted (here or elsewhere): go back to the library; say so only when opening it.
    if (!keepPlace) toast("That paper is no longer in your library", true);
    closePaper();
    return;
  }
  const scroll = keepPlace ? paperView.querySelector(".pv-scroll")?.scrollTop ?? 0 : 0;
  const sameFigures = keepPlace && paper.id === id && paper.figures.map((f) => f.id).join() === figs.figures.map((f) => f.id).join();
  paper.id = id;
  paper.item = item;
  paper.figures = figs.figures;
  if (!sameFigures) paper.index = Math.max(0, paper.figures.findIndex((f) => f.id === figs.cover_id));

  paperView.innerHTML = paperHTML(item, figs.status);
  paperView.classList.remove("hidden");
  document.body.classList.add("show-paper");
  paperView.querySelector(".pv-scroll").scrollTop = scroll;
  setupCarousel();
  setupAbstract();
  loadRelated(item);
  // Move focus into the new screen (for screen readers), without a visible ring.
  if (!keepPlace) paperView.querySelector(".pv-title").focus({ preventScroll: true });
  // Figures are still being extracted: look again shortly.
  if (figs.status === "pending") paper.poll = setTimeout(() => paper.id === id && renderPaper(id, { keepPlace: true }), 3000);
}

function paperHTML(i, figureStatus) {
  const back = $("#view-title").textContent || "My library";
  const venueYear = [i.venue, i.year].filter(Boolean).join(" · ");
  const authorsAll = i.authors.map((a) => [a.given, a.family].filter(Boolean).join(" ")).join(", ");
  const canFind = !i.has_file && (i.doi || i.arxiv_id);
  const main = i.has_file ? ["open", "file", "Open PDF"] : canFind ? ["findpdf", "file-search", "Find PDF"] : ["attach", "paperclip", "Attach PDF"];
  const cols = state.collections.filter((c) => i.collections.includes(c.id));
  const doiUrl = i.doi ? `https://doi.org/${encodeURIComponent(i.doi).replace(/%2F/g, "/")}` : "";
  const details = [
    i.venue && ["Journal", esc(i.venue)],
    i.year && ["Year", i.year],
    i.volume && ["Volume", esc([i.volume, i.issue && `(${i.issue})`, i.pages && `, ${i.pages}`].filter(Boolean).join(""))],
    i.doi && ["DOI", `<a href="${esc(doiUrl)}" target="_blank" rel="noopener" class="pv-doi">${esc(i.doi)}</a>
      <button type="button" class="pv-mini" data-act="copy-doi" aria-label="Copy DOI">${icon("copy")}</button>`],
    i.arxiv_id && ["arXiv", `<a href="https://arxiv.org/abs/${esc(i.arxiv_id)}" target="_blank" rel="noopener">${esc(i.arxiv_id)}</a>`],
    ["Added", new Date(i.added_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })],
    ["PDF", i.has_file ? `Attached${i.file_size ? ` · ${fmtSize(i.file_size)}` : ""}` : "Not attached"],
    ...i.supplementary.map((s, n) => [n ? "" : "Supplementary",
      `<a href="/api/supplementary/${s.id}/file" target="_blank" rel="noopener">${esc(s.name)}</a>`]),
  ].filter(Boolean);

  return `
  <div class="pv-bar">
    <button type="button" class="pv-back" aria-label="Back to ${esc(back)}">${icon("chevron-left")}<span>${esc(back)}</span></button>
    <button type="button" class="pv-icon${i.to_read ? " on" : ""}" data-act="toread" aria-pressed="${i.to_read}"
      aria-label="${i.to_read ? "On your reading list" : "Add to reading list"}">${icon("bookmark")}</button>
    <div class="menu-wrap">
      <button type="button" class="pv-icon" data-act="more" aria-label="More actions" aria-haspopup="menu" aria-expanded="false">${icon("more")}</button>
      <div class="menu pv-menu hidden" role="menu" aria-label="More actions">
        ${paper.figures.length > 1 ? `<button type="button" role="menuitem" data-act="cover">${icon("image")} Set as cover figure</button>` : ""}
        <button type="button" role="menuitem" data-act="edit">${icon("pencil")} Edit details</button>
        <button type="button" role="menuitem" data-act="bib">${icon("braces")} Copy BibTeX</button>
        ${i.doi || i.arxiv_id ? `<button type="button" role="menuitem" data-act="refresh">${icon("refresh")} Refresh metadata</button>` : ""}
        ${i.has_file && i.annotation_count ? `<button type="button" role="menuitem" data-act="annotated">${icon("download")} Download with annotations</button>` : ""}
        <button type="button" role="menuitem" data-act="attach">${icon("paperclip")} ${i.has_file ? "Replace PDF" : "Attach PDF"}</button>
        <button type="button" role="menuitem" data-act="supp">${icon("plus")} Add supplementary files</button>
        ${i.has_file ? `<button type="button" role="menuitem" data-act="refigure">${icon("refresh")} Extract figures again</button>` : ""}
        <div class="menu-sep" role="separator"></div>
        <button type="button" role="menuitem" data-act="delete" class="danger">${icon("trash")} Delete</button>
      </div>
    </div>
  </div>
  <div class="pv-scroll">
    ${carouselHTML(i, figureStatus)}
    ${venueYear ? `<div class="pv-venue">${esc(venueYear)}</div>` : ""}
    <h1 class="pv-title" tabindex="-1">${esc(i.title) || "(untitled)"}</h1>
    ${i.authors.length ? `<div class="pv-authors"><span>${esc(authorsShort(i.authors))}</span>
      ${i.authors.length > 2 ? `<button type="button" class="pv-link" data-act="authors" aria-expanded="false" aria-controls="pv-all-authors">All authors</button>` : ""}</div>
      <p class="pv-all-authors" id="pv-all-authors" hidden>${esc(authorsAll)}</p>` : ""}
    <button type="button" class="pv-main primary" data-act="${main[0]}">${icon(main[1])} ${main[2]}</button>
    <div class="pv-actions">
      <button type="button" data-act="cite">${icon("quote")}<span>Cite</span></button>
      <button type="button" data-act="collections">${icon("folder-plus")}<span>Collection</span></button>
      <button type="button" data-act="share">${icon("share")}<span>Share</span></button>
    </div>
    ${i.abstract ? `<section class="pv-section"><h2>Abstract</h2>
      <p class="pv-abstract" id="pv-abstract">${esc(i.abstract)}</p>
      <button type="button" class="pv-link pv-more hidden" data-act="abstract" aria-expanded="false" aria-controls="pv-abstract">Read more</button></section>` : ""}
    <section class="pv-section"><h2>Details</h2>
      <dl class="pv-details">${details.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl></section>
    <section class="pv-section"><h2>Collections</h2>
      <div class="pv-chips">${cols.map((c) => `<button type="button" class="pv-chip" data-act="goto-collection" data-id="${c.id}">${esc(c.name)}</button>`).join("")}
        <button type="button" class="pv-chip pv-add" data-act="collections">${icon("plus")} Add</button></div></section>
    <section class="pv-section"><h2>Tags</h2>
      <div class="pv-chips">${i.tags.map((t) => `<button type="button" class="pv-chip" data-act="goto-tag" data-tag="${esc(t)}">${esc(t)}</button>`).join("")}
        <button type="button" class="pv-chip pv-add" data-act="add-tag">${icon("plus")} Add</button></div></section>
    <section class="pv-section"><h2><label for="pv-notes">My notes</label></h2>
      <textarea id="pv-notes" rows="4" placeholder="Add a note…">${esc(i.notes)}</textarea>
      <div class="pv-saved muted" id="pv-saved" aria-live="polite"></div></section>
    <section class="pv-section pv-related hidden"><h2>More in your library</h2><div class="pv-strip" id="pv-strip"></div></section>
  </div>`;
}

function carouselHTML(i, status) {
  const figs = paper.figures;
  if (!figs.length) {
    const note = status === "pending" ? "Extracting figures from the PDF…" : "";
    return `<div class="car car-empty"><div class="car-tile">${thumbHTML({ ...i, cover: null })}</div></div>
      ${note ? `<div class="car-nav"><span class="car-count">${note}</span></div>` : ""}`;
  }
  return `
  <div class="car" role="region" aria-roledescription="carousel" aria-label="Figures">
    <div class="car-track" tabindex="0">
      ${figs.map((f, n) => `<div class="car-slide" role="group" aria-roledescription="slide" aria-label="${n + 1} of ${figs.length}">
        <div class="car-tile"><img src="${esc(f.full)}" alt="${esc(f.label || `Figure ${n + 1}`)}" ${n === paper.index ? "" : 'loading="lazy"'}
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

// --------------------------------------------------------------------------
// Carousel
// --------------------------------------------------------------------------
function setupCarousel() {
  const track = paperView.querySelector(".car-track");
  if (!track) return;
  const show = () => {
    const n = paper.index, f = paper.figures[n];
    paperView.querySelector(".car-count").textContent = `${f.label && /\d/.test(f.label) ? f.label : "Figure"} · ${n + 1} of ${paper.figures.length}`
      .replace(/^Figure · /, "Figure ");
    paperView.querySelector(".car-caption").textContent = f.caption || "";
    paperView.querySelectorAll(".car-dots button").forEach((d, k) => d.setAttribute("aria-current", String(k === n)));
    paperView.querySelector(".car-prev")?.toggleAttribute("disabled", n === 0);
    paperView.querySelector(".car-next")?.toggleAttribute("disabled", n === paper.figures.length - 1);
  };
  track.scrollLeft = paper.index * track.clientWidth;
  let t;
  track.addEventListener("scroll", () => {
    clearTimeout(t);
    t = setTimeout(() => {
      const n = Math.round(track.scrollLeft / track.clientWidth);
      if (n !== paper.index && paper.figures[n]) { paper.index = n; show(); }
    }, 60);
  }, { passive: true });
  track.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { e.preventDefault(); goToFigure(paper.index + 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); goToFigure(paper.index - 1); }
  });
  show();
}

function goToFigure(n, smooth = true) {
  const track = paperView.querySelector(".car-track");
  if (!track || !paper.figures[n]) return;
  track.scrollTo({ left: n * track.clientWidth, behavior: smooth ? "smooth" : "instant" });
}

function setupAbstract() {
  const p = $("#pv-abstract");
  if (p && p.scrollHeight > p.clientHeight + 2) paperView.querySelector(".pv-more").classList.remove("hidden");
}

// "More in your library": papers sharing a collection or a tag, otherwise recent ones.
async function loadRelated(item) {
  const p = new URLSearchParams({ sort: "year" });
  if (item.collections.length) p.set("collection", item.collections[0]);
  else if (item.tags.length) p.set("tag", item.tags[0]);
  else p.set("sort", "added");
  let items;
  try { items = await api("/api/items?" + p); } catch { return; }
  if (paper.id !== item.id) return;
  items = items.filter((x) => x.id !== item.id).slice(0, 12);
  if (!items.length) return;
  $("#pv-strip").innerHTML = items.map((x) => `
    <a class="card" href="/paper/${x.id}" data-id="${x.id}">
      <div class="thumb">${thumbHTML(x)}</div>
      <div class="c-title">${esc(x.title) || "(untitled)"}</div>
      <div class="c-meta">${esc([authorsShort(x.authors), x.year].filter(Boolean).join(" · "))}</div>
    </a>`).join("");
  paperView.querySelector(".pv-related").classList.remove("hidden");
}

// --------------------------------------------------------------------------
// Actions
// --------------------------------------------------------------------------
paperView.addEventListener("click", async (e) => {
  const related = e.target.closest(".pv-strip a[data-id]");
  if (related) {
    e.preventDefault();
    const id = Number(related.dataset.id);
    history.pushState({ bubo: "paper", id }, "", `/paper/${id}`);
    return renderPaper(id);
  }
  if (e.target.closest(".pv-back")) return closePaper();
  const el = e.target.closest("[data-act]");
  if (!el) {
    if (!e.target.closest(".menu-wrap")) closePaperMenu();
    return;
  }
  const i = paper.item, act = el.dataset.act;
  if (act !== "more") closePaperMenu();
  switch (act) {
    case "more": return togglePaperMenu();
    case "toread": return setToRead([i.id], !i.to_read);
    case "open": return openViewer(i);
    case "findpdf": case "attach": case "bib": case "refresh": case "annotated": case "delete": case "cite":
      return itemAction(act, i);
    case "edit": select(i); return showDetailPane();
    case "supp": {
      const input = $("#supp-input");
      input.onchange = async () => {
        const files = [...input.files];
        input.value = "";
        if (files.length) await addSupplementary(i.id, files);
      };
      return input.click();
    }
    case "refigure":
      try { await api(`/api/items/${i.id}/figures/extract`, { method: "POST" }); toast("Extracting the figures again…"); renderPaper(i.id, { keepPlace: true }); }
      catch (err) { toast(err.message, true); }
      return;
    case "cover": {
      const f = paper.figures[paper.index];
      try {
        await api(`/api/items/${i.id}/cover`, { method: "PUT", json: { figure_id: f.id } });
        toast(`${f.label || "This figure"} is now the cover`);
        refresh();
      } catch (err) { toast(err.message, true); }
      return;
    }
    case "prev": return goToFigure(paper.index - 1);
    case "next": return goToFigure(paper.index + 1);
    case "dot": return goToFigure(Number(el.dataset.n));
    case "expand": return openLightbox("figure");
    case "all-figures": return openLightbox("grid");
    case "authors": {
      const p = $("#pv-all-authors"), open = p.hidden;
      p.hidden = !open;
      el.setAttribute("aria-expanded", String(open));
      el.textContent = open ? "Fewer authors" : "All authors";
      return;
    }
    case "abstract": {
      const open = $("#pv-abstract").classList.toggle("open");
      el.setAttribute("aria-expanded", String(open));
      el.textContent = open ? "Read less" : "Read more";
      return;
    }
    case "copy-doi": copyText(i.doi); return toast("DOI copied");
    case "share": return sharePaper(i);
    case "collections": return chooseCollections(i);
    case "goto-collection": closePaper(); return setView({ type: "collection", id: Number(el.dataset.id) });
    case "goto-tag": closePaper(); return setView({ type: "tag", name: el.dataset.tag });
    case "add-tag": {
      const name = prompt("Add a tag")?.trim();
      if (!name) return;
      try { await api(`/api/items/${i.id}`, { method: "PATCH", json: { tags: [...i.tags, name] } }); refresh(); }
      catch (err) { toast(err.message, true); }
      return;
    }
  }
});

function togglePaperMenu() {
  const menu = paperView.querySelector(".pv-menu"), btn = paperView.querySelector('[data-act="more"]');
  const open = menu.classList.toggle("hidden") === false;
  btn.setAttribute("aria-expanded", String(open));
  if (open) menu.querySelector("[role=menuitem]")?.focus();
}
function closePaperMenu() {
  const menu = paperView.querySelector(".pv-menu");
  if (!menu || menu.classList.contains("hidden")) return;
  menu.classList.add("hidden");
  paperView.querySelector('[data-act="more"]').setAttribute("aria-expanded", "false");
}
paperView.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !paperView.querySelector(".pv-menu")?.classList.contains("hidden")) {
    closePaperMenu();
    paperView.querySelector('[data-act="more"]').focus();
  }
});

// Notes are saved as you type.
paperView.addEventListener("input", (e) => {
  if (e.target.id !== "pv-notes") return;
  clearTimeout(paper.notesTimer);
  $("#pv-saved").textContent = "";
  paper.notesTimer = setTimeout(saveNotes, 800);
});
paperView.addEventListener("focusout", (e) => { if (e.target.id === "pv-notes") flushNotes(); });
function flushNotes() {
  if (paper.notesTimer) { clearTimeout(paper.notesTimer); saveNotes(); }
}
async function saveNotes() {
  paper.notesTimer = null;
  const box = $("#pv-notes");
  if (!box || !paper.item || box.value === (paper.item.notes || "")) return;
  const notes = box.value;
  try {
    await api(`/api/items/${paper.item.id}`, { method: "PATCH", json: { notes } });
    paper.item.notes = notes;
    if ($("#pv-saved")) $("#pv-saved").textContent = "Saved";
  } catch (err) { toast(err.message, true); }
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
    <div class="dialog-buttons"><button type="button" value="cancel" data-close>Cancel</button>
      ${rows.length ? `<button type="submit" class="primary" value="save">Save</button>` : ""}</div></form>`;
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

// --------------------------------------------------------------------------
// Full-screen figures: one at a time ("Expand") or all of them ("All figures")
// --------------------------------------------------------------------------
function openLightbox(mode) {
  const dlg = $("#lightbox"), figs = paper.figures;
  const head = `<div class="lb-bar"><span class="lb-title" id="lightbox-title">${mode === "grid" ? `All figures (${figs.length})` : ""}</span>
    <button type="button" class="pv-icon" data-lb="close" aria-label="Close">${icon("x")}</button></div>`;
  if (mode === "grid") {
    dlg.innerHTML = head + `<div class="lb-grid">${figs.map((f, n) => `
      <button type="button" class="lb-thumb" data-lb="pick" data-n="${n}" aria-label="${esc(f.label || `Figure ${n + 1}`)}">
        <span class="thumb"><span class="tile"><img src="${esc(f.thumb)}" alt="" loading="lazy" width="${f.thumb_width}" height="${f.thumb_height}"></span></span>
        <span class="lb-label">${esc(f.label || `Figure ${n + 1}`)} · p. ${f.page}</span></button>`).join("")}</div>`;
  } else {
    const f = figs[paper.index];
    dlg.innerHTML = head + `<div class="lb-stage"><div class="lb-tile"><img src="${esc(f.full)}" alt="${esc(f.label || "Figure")}"></div></div>
      <div class="lb-foot">
        ${figs.length > 1 ? `<button type="button" class="car-arrow" data-lb="prev" aria-label="Previous figure" ${paper.index ? "" : "disabled"}>${icon("chevron-left")}</button>` : ""}
        <p class="lb-caption"><b>${esc(f.label || "")}</b> ${esc((f.caption || "").replace(/^\s*(fig(ure)?\.?)\s*\S+\s*[.:|—–-]?\s*/i, ""))}</p>
        ${figs.length > 1 ? `<button type="button" class="car-arrow" data-lb="next" aria-label="Next figure" ${paper.index < figs.length - 1 ? "" : "disabled"}>${icon("chevron-right")}</button>` : ""}
      </div>`;
    $("#lightbox-title").textContent = `${paper.index + 1} of ${figs.length}`;
  }
  dlg.dataset.mode = mode;
  if (!dlg.open) dlg.showModal();
  dlg.querySelector('[data-lb="close"]').focus();
}

$("#lightbox").addEventListener("click", (e) => {
  const el = e.target.closest("[data-lb]");
  if (!el) return;
  const a = el.dataset.lb, dlg = $("#lightbox");
  if (a === "close") return dlg.close();
  if (a === "pick") { dlg.close(); paper.index = Number(el.dataset.n); goToFigure(paper.index, false); return; }
  if (a === "prev" || a === "next") {
    paper.index = Math.max(0, Math.min(paper.figures.length - 1, paper.index + (a === "next" ? 1 : -1)));
    goToFigure(paper.index, false);
    openLightbox("figure");
  }
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
