// Bubo PDF viewer: renders PDFs with PDF.js and stores highlights and notes
// on the server (they are never written into the original PDF).

// PDF.js uses very recent JavaScript (Map.getOrInsertComputed, Math.sumPrecise…). Browsers
// without it, such as Safari on iOS/iPadOS 17 and 18, get the "legacy" build of the same
// version, which adds what is missing.
const MODERN = typeof Map.prototype.getOrInsertComputed === "function" && typeof Math.sumPrecise === "function"
  && typeof Promise.try === "function" && typeof Promise.withResolvers === "function"
  && typeof Uint8Array.fromBase64 === "function" && typeof Uint8Array.prototype.toBase64 === "function"
  && typeof ArrayBuffer.prototype.transferToFixedLength === "function";
const BUILD = MODERN ? "/static/vendor/pdfjs/" : "/static/vendor/pdfjs/legacy/";
const pdfjsLib = await import(BUILD + "pdf.min.mjs");

const VENDOR = "/static/vendor/pdfjs/";
pdfjsLib.GlobalWorkerOptions.workerSrc = BUILD + "pdf.worker.min.mjs";

// Keep in sync with app/annotate.py.
const COLOURS = {
  yellow: "#ffd400", green: "#5fb236", blue: "#2ea8e5",
  pink: "#e56eee", orange: "#f19837", purple: "#a28ae5",
};
const COLOUR_LABELS = {
  yellow: "Yellow", green: "Green", blue: "Blue", pink: "Pink", orange: "Orange", purple: "Purple",
};
const MIN_SCALE = 0.25, MAX_SCALE = 5, MAX_CANVAS_PIXELS = 16_000_000;

const byId = (id) => document.getElementById(id);
const ui = {
  root: byId("viewer"), title: byId("viewer-title"), pages: byId("pages"),
  sidebar: byId("ann-sidebar"), popup: byId("sel-popup"), zoom: byId("zoom-level"),
  pageInput: byId("page-input"), pageCount: byId("page-count"), noteBtn: byId("note-mode"),
  colours: byId("colour-picker"), download: byId("viewer-download"),
  annotated: byId("viewer-annotated"),
};

const store = {
  get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
};

const S = {
  item: null, doc: null, loadingTask: null, token: 0, pages: [], annotations: [],
  scale: 1, fit: true, selected: null, pending: null, noteMode: false, observer: null,
  colour: COLOURS[store.get("hlColour")] ? store.get("hlColour") : "yellow", onClose: null,
};

// On a phone (as in app.js): one pane at a time.
const NARROW = window.matchMedia("(max-width: 760px), (hover: none) and (max-width: 1100px)");

// ---------------------------------------------------------------------------
// Opening and closing
// ---------------------------------------------------------------------------
async function open(item, { annotationId = null, onClose = null, page = null, terms = [] } = {}) {
  teardown();
  const token = ++S.token;
  S.item = item;
  S.terms = terms;
  S.scrollToHit = page ? page - 1 : null;
  S.onClose = onClose;
  S.fit = true;
  ui.title.textContent = item.title || "(untitled)";
  ui.download.href = `/api/items/${item.id}/file?download=true`;
  ui.annotated.href = `/api/items/${item.id}/annotated.pdf`;
  ui.pages.innerHTML = '<div class="viewer-msg">Loading PDF…</div>';
  // On a phone the annotations panel covers the page, so it starts closed.
  ui.sidebar.classList.toggle("hidden", NARROW.matches || store.get("annSidebar", "1") !== "1");
  ui.root.classList.remove("hidden");
  setNoteMode(false);
  renderColourPicker();

  try {
    S.loadingTask = pdfjsLib.getDocument({
      url: `/api/items/${item.id}/file`,
      cMapUrl: VENDOR + "cmaps/", cMapPacked: true,
      standardFontDataUrl: VENDOR + "standard_fonts/",
      wasmUrl: VENDOR + "wasm/", iccUrl: VENDOR + "iccs/",
    });
    const [doc, annotations] = await Promise.all([
      S.loadingTask.promise, api(`/api/items/${item.id}/annotations`),
    ]);
    if (token !== S.token) return;
    S.doc = doc;
    S.annotations = annotations;
    ui.pages.innerHTML = "";
    for (let i = 0; i < doc.numPages; i++) {
      const page = await doc.getPage(i + 1);
      if (token !== S.token) return;
      S.pages.push(createPage(i, page));
    }
    ui.pageCount.textContent = `of ${doc.numPages}`;
    ui.pageInput.max = doc.numPages;
    layout();
    renderSidebar();
    if (annotationId) focusAnnotation(annotationId, { scroll: true });
    else if (S.scrollToHit != null && S.pages[S.scrollToHit]) {
      ui.pages.scrollTop = S.pages[S.scrollToHit].div.offsetTop - 8;
    } else updatePageIndicator();
  } catch (err) {
    if (token !== S.token) return;
    console.error(err);
    ui.pages.innerHTML = `<div class="viewer-msg">Could not open the PDF: ${esc(err.message || err)}</div>`;
  }
}

function teardown() {
  S.token++;
  S.observer?.disconnect();
  S.observer = null;
  for (const p of S.pages) cancelRender(p);
  S.loadingTask?.destroy();
  S.loadingTask = null;
  S.doc = null;
  S.pages = [];
  S.annotations = [];
  S.terms = [];
  S.scrollToHit = null;
  S.selected = null;
  S.pending = null;
  hidePopup();
  ui.pages.innerHTML = "";
  ui.sidebar.innerHTML = "";
}

function close() {
  if (ui.root.classList.contains("hidden")) return;
  flushComments();
  teardown();
  ui.root.classList.add("hidden");
  const cb = S.onClose;
  S.onClose = null;
  cb?.();
}

// ---------------------------------------------------------------------------
// Pages and rendering
// ---------------------------------------------------------------------------
function createPage(index, page) {
  const div = document.createElement("div");
  div.className = "pdf-page";
  div.dataset.index = index;
  div.innerHTML = '<div class="ann-layer"></div><div class="textLayer"></div><div class="note-layer"></div>';
  ui.pages.appendChild(div);
  const p = {
    index, page, div, base: page.getViewport({ scale: 1 }), viewport: null,
    annLayer: div.children[0], textDiv: div.children[1], noteLayer: div.children[2],
    state: "idle", task: null, textLayer: null, renderId: 0,
  };
  p.textDiv.addEventListener("pointerdown", () => p.textDiv.classList.add("selecting"));
  return p;
}

function fitScale() {
  const pad = parseFloat(getComputedStyle(ui.pages).paddingLeft) || 0;
  const avail = ui.pages.clientWidth - 2 * pad - 8;
  const widest = Math.max(...S.pages.map((p) => p.base.width));
  return clampScale(avail / widest);
}

const clampScale = (s) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

function layout(keepPosition = false) {
  if (!S.pages.length) return;
  const anchor = keepPosition ? scrollAnchor() : null;
  if (S.fit) S.scale = fitScale();
  S.observer?.disconnect();
  for (const p of S.pages) {
    cancelRender(p);
    p.viewport = p.page.getViewport({ scale: S.scale });
    const { width, height } = p.viewport;
    Object.assign(p.div.style, { width: `${width}px`, height: `${height}px` });
    p.div.style.setProperty("--total-scale-factor", S.scale * (p.viewport.userUnit || 1));
    renderAnnotations(p);
  }
  ui.zoom.textContent = `${Math.round(S.scale * 100)}%`;
  S.observer = new IntersectionObserver(onIntersect, { root: ui.pages, rootMargin: "150% 0px" });
  S.pages.forEach((p) => S.observer.observe(p.div));
  if (anchor) restoreAnchor(anchor);
}

function onIntersect(entries) {
  for (const e of entries) {
    const p = S.pages[Number(e.target.dataset.index)];
    if (e.isIntersecting) renderPage(p);
    else if (p.state !== "idle") cancelRender(p); // free memory for far-away pages
  }
}

function cancelRender(p) {
  p.renderId++;
  p.task?.cancel();
  p.textLayer?.cancel();
  p.task = p.textLayer = null;
  p.div.querySelector("canvas")?.remove();
  p.textDiv.replaceChildren();
  p.state = "idle";
}

async function renderPage(p) {
  if (p.state !== "idle") return;
  p.state = "rendering";
  const id = ++p.renderId;
  const vp = p.viewport;
  let ratio = window.devicePixelRatio || 1;
  if (vp.width * vp.height * ratio * ratio > MAX_CANVAS_PIXELS) {
    ratio = Math.sqrt(MAX_CANVAS_PIXELS / (vp.width * vp.height));
  }
  const canvas = document.createElement("canvas");
  canvas.width = Math.floor(vp.width * ratio);
  canvas.height = Math.floor(vp.height * ratio);
  canvas.style.width = `${vp.width}px`;
  canvas.style.height = `${vp.height}px`;
  try {
    p.task = p.page.render({
      canvas, viewport: vp, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined,
    });
    await p.task.promise;
    if (p.renderId !== id) return;
    p.div.prepend(canvas);
    p.textLayer = new pdfjsLib.TextLayer({
      textContentSource: p.page.streamTextContent(), container: p.textDiv, viewport: vp,
    });
    await p.textLayer.render();
    if (p.renderId !== id) return;
    p.state = "done";
    markSearchHits(p);
  } catch (err) {
    if (err?.name !== "RenderingCancelledException" && err?.name !== "AbortException") console.error(err);
  }
}

// ---------------------------------------------------------------------------
// Search terms: highlighted in the text layer when the viewer was opened from a search
// ---------------------------------------------------------------------------
const fold = (ch) => ch.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();

function markSearchHits(p) {
  if (!S.terms?.length) return;
  const patterns = S.terms.map((t) =>
    new RegExp(`(?<![\\p{L}\\p{N}])${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "gu"));
  for (const span of p.textDiv.querySelectorAll("span")) {
    if (span.querySelector("span") || !span.textContent) continue;
    const text = span.textContent;
    let folded = "";
    const index = [];
    [...text].forEach((ch, i) => { const f = fold(ch); folded += f; for (let k = 0; k < f.length; k++) index.push(i); });
    const chars = [...text];
    const ranges = [];
    for (const re of patterns) {
      for (const m of folded.matchAll(re)) ranges.push([index[m.index], index[m.index + m[0].length - 1] + 1]);
    }
    if (!ranges.length) continue;
    ranges.sort((a, b) => a[0] - b[0]);
    let html = "", pos = 0;
    for (const [a, b] of ranges) {
      if (a < pos) continue;
      html += esc(chars.slice(pos, a).join("")) + `<mark class="search-hit">${esc(chars.slice(a, b).join(""))}</mark>`;
      pos = b;
    }
    span.innerHTML = html + esc(chars.slice(pos).join(""));
  }
  if (S.scrollToHit === p.index) {
    S.scrollToHit = null;
    p.textDiv.querySelector("mark.search-hit")?.scrollIntoView({ block: "center" });
  }
}

// ---------------------------------------------------------------------------
// Coordinates: annotations are stored in PDF user space (origin bottom-left).
// ---------------------------------------------------------------------------
function toCss(p, [x1, y1, x2, y2]) {
  const [ax, ay] = p.viewport.convertToViewportPoint(x1, y1);
  const [bx, by] = p.viewport.convertToViewportPoint(x2, y2);
  return { l: Math.min(ax, bx), t: Math.min(ay, by), r: Math.max(ax, bx), b: Math.max(ay, by) };
}

function toPdf(p, { l, t, r, b }) {
  const [ax, ay] = p.viewport.convertToPdfPoint(l, t);
  const [bx, by] = p.viewport.convertToPdfPoint(r, b);
  const round = (n) => Math.round(n * 100) / 100;
  return [Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by)].map(round);
}

function mergeRects(rects) {
  rects.sort((a, b) => a.t - b.t || a.l - b.l);
  const out = [];
  for (const r of rects) {
    const h = r.b - r.t;
    const line = out.find((o) => {
      const overlap = Math.min(o.b, r.b) - Math.max(o.t, r.t);
      return overlap > Math.min(o.b - o.t, h) * 0.5 && r.l <= o.r + h * 0.6 && r.r >= o.l - h * 0.6;
    });
    if (line) {
      line.l = Math.min(line.l, r.l); line.t = Math.min(line.t, r.t);
      line.r = Math.max(line.r, r.r); line.b = Math.max(line.b, r.b);
    } else out.push({ ...r });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Drawing annotations
// ---------------------------------------------------------------------------
function renderAnnotations(p) {
  p.annLayer.replaceChildren();
  p.noteLayer.replaceChildren();
  for (const a of S.annotations) {
    if (a.page !== p.index) continue;
    if (a.kind === "highlight") {
      for (const rect of a.rects) {
        const c = toCss(p, rect);
        const el = document.createElement("div");
        el.className = "hl" + (a.id === S.selected ? " selected" : "");
        el.dataset.id = a.id;
        Object.assign(el.style, {
          left: `${c.l}px`, top: `${c.t}px`, width: `${c.r - c.l}px`, height: `${c.b - c.t}px`,
        });
        el.style.setProperty("--c", COLOURS[a.color]);
        p.annLayer.appendChild(el);
      }
    } else {
      const c = toCss(p, a.rects[0]);
      const el = document.createElement("button");
      el.className = "note-pin" + (a.id === S.selected ? " selected" : "");
      el.dataset.id = a.id;
      el.title = a.comment || "Note";
      el.innerHTML = icon("note");
      Object.assign(el.style, { left: `${c.l}px`, top: `${c.t}px` });
      el.style.setProperty("--c", COLOURS[a.color]);
      el.addEventListener("click", (e) => { e.stopPropagation(); focusAnnotation(a.id, { sidebar: true }); });
      p.noteLayer.appendChild(el);
    }
  }
}

function redrawPage(index) {
  const p = S.pages[index];
  if (p) renderAnnotations(p);
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
function sortedAnnotations() {
  const top = (a) => Math.max(...a.rects.map((r) => r[3]));
  const left = (a) => Math.min(...a.rects.map((r) => r[0]));
  return [...S.annotations].sort((a, b) => a.page - b.page || top(b) - top(a) || left(a) - left(b));
}

function renderSidebar() {
  const list = sortedAnnotations();
  ui.sidebar.innerHTML = `<div class="ann-head">Annotations <span class="muted">${list.length || ""}</span></div>` +
    (list.length ? list.map(cardHtml).join("") :
      `<div class="ann-empty muted">No annotations yet.<br><br>Select some text to highlight it,
       or use <b>Note</b> to pin a comment anywhere on a page.</div>`);
}

function cardHtml(a) {
  const swatches = Object.keys(COLOURS).map((c) =>
    `<button class="swatch mini-swatch${c === a.color ? " on" : ""}" data-colour="${c}"
      title="${COLOUR_LABELS[c]}" style="--c:${COLOURS[c]}"></button>`).join("");
  return `<div class="ann-card${a.id === S.selected ? " selected" : ""}" data-id="${a.id}" style="--c:${COLOURS[a.color]}">
    <div class="ann-meta"><span>Page ${a.page + 1} · ${a.kind === "note" ? "Note" : "Highlight"}</span>
      <span class="ann-tools">${swatches}<button class="ann-del" title="Delete annotation" aria-label="Delete annotation">${icon("x")}</button></span></div>
    ${a.text ? `<blockquote>${esc(a.text)}</blockquote>` : ""}
    <textarea rows="${a.comment ? 3 : 1}" placeholder="Add a comment…">${esc(a.comment || "")}</textarea>
  </div>`;
}

function cardFor(id) {
  return ui.sidebar.querySelector(`.ann-card[data-id="${id}"]`);
}

ui.sidebar.addEventListener("click", async (e) => {
  const card = e.target.closest(".ann-card");
  if (!card) return;
  const id = Number(card.dataset.id);
  if (e.target.closest(".ann-del")) return deleteAnnotation(id);
  const colour = e.target.closest(".swatch")?.dataset.colour;
  if (colour) return updateAnnotation(id, { color: colour });
  if (e.target.tagName !== "TEXTAREA") focusAnnotation(id, { scroll: true });
  else select(id);
});

const commentTimers = new Map();
ui.sidebar.addEventListener("input", (e) => {
  if (e.target.tagName !== "TEXTAREA") return;
  const id = Number(e.target.closest(".ann-card").dataset.id);
  e.target.rows = Math.max(e.target.rows, Math.min(10, e.target.value.split("\n").length + 1));
  clearTimeout(commentTimers.get(id));
  commentTimers.set(id, setTimeout(() => saveComment(id, e.target.value), 700));
});
ui.sidebar.addEventListener("focusout", (e) => {
  if (e.target.tagName !== "TEXTAREA") return;
  const id = Number(e.target.closest(".ann-card")?.dataset.id);
  if (commentTimers.has(id)) saveComment(id, e.target.value);
});

function flushComments() {
  for (const [id] of commentTimers) {
    const ta = cardFor(id)?.querySelector("textarea");
    if (ta) saveComment(id, ta.value);
  }
}

async function saveComment(id, value) {
  clearTimeout(commentTimers.get(id));
  commentTimers.delete(id);
  const a = S.annotations.find((x) => x.id === id);
  if (!a || (a.comment || "") === value.trim()) return;
  try {
    const updated = await api(`/api/annotations/${id}`, { method: "PATCH", json: { comment: value } });
    Object.assign(a, updated);
    S.pages[a.page] && renderAnnotations(S.pages[a.page]);
  } catch (err) { toast(`Comment not saved: ${err.message}`, true); }
}

// ---------------------------------------------------------------------------
// Creating, updating and deleting annotations
// ---------------------------------------------------------------------------
async function createAnnotations(parts, { kind = "highlight", focusComment = false } = {}) {
  const created = [];
  try {
    for (const part of parts) {
      created.push(await api(`/api/items/${S.item.id}/annotations`, {
        json: { kind, color: S.colour, page: part.page, rects: part.rects, text: part.text || null },
      }));
    }
  } catch (err) { toast(`Annotation not saved: ${err.message}`, true); }
  if (!created.length) return;
  S.annotations.push(...created);
  new Set(created.map((a) => a.page)).forEach(redrawPage);
  renderSidebar();
  select(created[0].id, { sidebar: true });
  if (focusComment) cardFor(created[0].id)?.querySelector("textarea")?.focus();
}

async function updateAnnotation(id, changes) {
  try {
    const updated = await api(`/api/annotations/${id}`, { method: "PATCH", json: changes });
    const a = S.annotations.find((x) => x.id === id);
    Object.assign(a, updated);
    redrawPage(a.page);
    renderSidebar();
  } catch (err) { toast(err.message, true); }
}

async function deleteAnnotation(id) {
  const a = S.annotations.find((x) => x.id === id);
  if (!a) return;
  if (a.comment && !confirm("Delete this annotation and its comment?")) return;
  try {
    await api(`/api/annotations/${id}`, { method: "DELETE" });
    S.annotations = S.annotations.filter((x) => x.id !== id);
    if (S.selected === id) S.selected = null;
    redrawPage(a.page);
    renderSidebar();
  } catch (err) { toast(err.message, true); }
}

function select(id, { sidebar = false } = {}) {
  const prev = S.annotations.find((x) => x.id === S.selected);
  S.selected = id;
  if (prev) redrawPage(prev.page);
  const a = S.annotations.find((x) => x.id === id);
  if (a && a.page !== prev?.page) redrawPage(a.page);
  ui.sidebar.querySelectorAll(".ann-card").forEach((c) =>
    c.classList.toggle("selected", Number(c.dataset.id) === id));
  if (sidebar && id != null) {
    if (ui.sidebar.classList.contains("hidden")) toggleSidebar(true);
    cardFor(id)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

function focusAnnotation(id, { scroll = false, sidebar = true } = {}) {
  const a = S.annotations.find((x) => x.id === id);
  if (!a) return;
  select(id, { sidebar });
  if (scroll) {
    const p = S.pages[a.page];
    const c = toCss(p, a.rects[0]);
    ui.pages.scrollTo({ top: p.div.offsetTop + c.t - ui.pages.clientHeight / 3, behavior: "smooth" });
  }
}

// ---------------------------------------------------------------------------
// Text selection → highlight popup
// ---------------------------------------------------------------------------
function selectionParts(range) {
  const parts = [];
  for (const p of S.pages) {
    if (p.state !== "done" || !range.intersectsNode(p.textDiv)) continue;
    const r = range.cloneRange();
    if (!p.textDiv.contains(range.startContainer)) r.setStart(p.textDiv, 0);
    if (!p.textDiv.contains(range.endContainer)) r.setEnd(p.textDiv, p.textDiv.childNodes.length);
    const box = p.div.getBoundingClientRect();
    const rects = mergeRects([...r.getClientRects()]
      .filter((c) => c.width > 0.5 && c.height > 0.5 && c.height < box.height * 0.2)
      .map((c) => ({ l: c.left - box.left, t: c.top - box.top, r: c.right - box.left, b: c.bottom - box.top }))
      .filter((c) => c.r > 0 && c.b > 0 && c.l < box.width && c.t < box.height));
    const text = r.toString().replace(/\s+/g, " ").trim();
    if (rects.length && text) parts.push({ page: p.index, rects: rects.map((c) => toPdf(p, c)), text });
  }
  return parts;
}

function checkSelection() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || !sel.rangeCount || S.noteMode) return hidePopup();
  const range = sel.getRangeAt(0);
  if (!ui.pages.contains(range.commonAncestorContainer)) return hidePopup();
  const parts = selectionParts(range);
  if (!parts.length) return hidePopup();
  S.pending = parts;
  const rects = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
  const last = rects[rects.length - 1] || range.getBoundingClientRect();
  ui.popup.classList.remove("hidden");
  const w = ui.popup.offsetWidth, h = ui.popup.offsetHeight;
  let top = last.bottom + 8;
  if (top + h > window.innerHeight - 8) top = Math.max(8, last.top - h - 8);
  ui.popup.style.top = `${top}px`;
  ui.popup.style.left = `${Math.min(window.innerWidth - w - 8, Math.max(8, last.right - w / 2))}px`;
}

function hidePopup() {
  ui.popup.classList.add("hidden");
  S.pending = null;
}

function renderPopup() {
  ui.popup.innerHTML = Object.keys(COLOURS).map((c) =>
    `<button class="swatch" data-colour="${c}" title="Highlight in ${COLOUR_LABELS[c].toLowerCase()}"
      style="--c:${COLOURS[c]}"></button>`).join("") +
    `<button class="popup-comment" title="Highlight and add a comment">${icon("comment")} Comment</button>`;
}

ui.popup.addEventListener("pointerdown", (e) => e.preventDefault()); // keep the selection
ui.popup.addEventListener("click", (e) => {
  const parts = S.pending;
  if (!parts) return;
  const colour = e.target.closest(".swatch")?.dataset.colour;
  const comment = e.target.closest(".popup-comment");
  if (!colour && !comment) return;
  if (colour) setColour(colour);
  window.getSelection()?.removeAllRanges();
  hidePopup();
  createAnnotations(parts, { focusComment: !!comment });
});

document.addEventListener("pointerup", () => {
  S.pages.forEach((p) => p.textDiv.classList.remove("selecting"));
  if (!ui.root.classList.contains("hidden")) setTimeout(checkSelection, 0);
});
// On touch screens the selection is adjusted with handles, which send no pointer
// events, so offer the highlight colours once the selection has settled.
let selTimer;
document.addEventListener("selectionchange", () => {
  const sel = window.getSelection();
  if (S.pending && (!sel || sel.isCollapsed)) hidePopup();
  if (ui.root.classList.contains("hidden") || !sel || sel.isCollapsed) return;
  clearTimeout(selTimer);
  selTimer = setTimeout(checkSelection, 350);
});

// Click on a page: add a note (in note mode) or select the highlight under the pointer.
ui.pages.addEventListener("click", (e) => {
  const div = e.target.closest(".pdf-page");
  if (!div) return;
  const p = S.pages[Number(div.dataset.index)];
  const box = div.getBoundingClientRect();
  const x = e.clientX - box.left, y = e.clientY - box.top;
  if (S.noteMode) {
    setNoteMode(false);
    createAnnotations([{ page: p.index, rects: [toPdf(p, { l: x, t: y, r: x, b: y })] }],
      { kind: "note", focusComment: true });
    return;
  }
  if (!window.getSelection()?.isCollapsed) return;
  const hit = [...S.annotations].reverse().find((a) => a.page === p.index && a.kind === "highlight" &&
    a.rects.some((r) => { const c = toCss(p, r); return x >= c.l && x <= c.r && y >= c.t && y <= c.b; }));
  if (hit) select(hit.id, { sidebar: true });
  else if (S.selected != null) select(null);
});

// ---------------------------------------------------------------------------
// Toolbar
// ---------------------------------------------------------------------------
function renderColourPicker() {
  ui.colours.innerHTML = Object.keys(COLOURS).map((c) =>
    `<button class="swatch${c === S.colour ? " on" : ""}" data-colour="${c}"
      title="${COLOUR_LABELS[c]} (colour for new annotations)" style="--c:${COLOURS[c]}"></button>`).join("");
  renderPopup();
}

function setColour(c) {
  S.colour = c;
  store.set("hlColour", c);
  renderColourPicker();
}

ui.colours.addEventListener("click", (e) => {
  const c = e.target.closest(".swatch")?.dataset.colour;
  if (c) setColour(c);
});

function setNoteMode(on) {
  S.noteMode = on;
  ui.noteBtn.classList.toggle("on", on);
  ui.pages.classList.toggle("note-mode", on);
}
ui.noteBtn.addEventListener("click", () => setNoteMode(!S.noteMode));

function toggleSidebar(force) {
  const show = force ?? ui.sidebar.classList.contains("hidden");
  ui.sidebar.classList.toggle("hidden", !show);
  if (!NARROW.matches) store.set("annSidebar", show ? "1" : "0");
  if (S.fit) layout(true);
}
byId("sidebar-toggle").addEventListener("click", () => toggleSidebar());

function zoom(factor) {
  S.fit = false;
  S.scale = clampScale(S.scale * factor);
  layout(true);
}
byId("zoom-in").addEventListener("click", () => zoom(1.2));
byId("zoom-out").addEventListener("click", () => zoom(1 / 1.2));
byId("zoom-fit").addEventListener("click", () => { S.fit = true; layout(true); });
byId("viewer-close").addEventListener("click", close);

function scrollAnchor() {
  const p = currentPage();
  if (!p) return null;
  return { index: p.index, frac: (ui.pages.scrollTop - p.div.offsetTop) / p.div.offsetHeight };
}
function restoreAnchor({ index, frac }) {
  const p = S.pages[index];
  ui.pages.scrollTop = p.div.offsetTop + frac * p.div.offsetHeight;
}

function currentPage() {
  const mid = ui.pages.scrollTop + ui.pages.clientHeight / 2;
  return S.pages.find((p) => p.div.offsetTop + p.div.offsetHeight + 12 >= mid) || S.pages[S.pages.length - 1];
}

function updatePageIndicator() {
  const p = currentPage();
  if (p && document.activeElement !== ui.pageInput) ui.pageInput.value = p.index + 1;
}

let scrollFrame = 0;
ui.pages.addEventListener("scroll", () => {
  cancelAnimationFrame(scrollFrame);
  scrollFrame = requestAnimationFrame(updatePageIndicator);
  if (S.pending) hidePopup();
});

ui.pageInput.addEventListener("change", () => {
  const n = Math.min(S.pages.length, Math.max(1, Number(ui.pageInput.value) || 1));
  ui.pages.scrollTop = S.pages[n - 1].div.offsetTop - 8;
});

let resizeTimer;
window.addEventListener("resize", () => {
  if (ui.root.classList.contains("hidden") || !S.fit) return;
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => layout(true), 150);
});

document.addEventListener("keydown", (e) => {
  if (ui.root.classList.contains("hidden")) return;
  const typing = e.target.matches("input, textarea, select");
  if (e.key === "Escape") {
    if (S.noteMode) return setNoteMode(false);
    if (S.pending) { window.getSelection()?.removeAllRanges(); return hidePopup(); }
    if (typing) return e.target.blur();
    return close();
  }
  if (typing) return;
  if ((e.key === "Delete" || e.key === "Backspace") && S.selected != null) {
    e.preventDefault();
    deleteAnnotation(S.selected);
  } else if (e.key === "+" || e.key === "=") { e.preventDefault(); zoom(1.2); }
  else if (e.key === "-") { e.preventDefault(); zoom(1 / 1.2); }
  else if (e.key === "0") { S.fit = true; layout(true); }
  else if (e.key === "n") setNoteMode(!S.noteMode);
});

window.BuboViewer = { open, close, COLOURS };
