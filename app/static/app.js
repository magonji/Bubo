"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
// Simple stroke icons (24×24, drawn in the current text colour).
const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M5 20h14"/>',
  pencil: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  library: '<path d="M4 4h4v16H4zM10 4h4v16h-4zM16.5 5.2l3.4-.9 3.1 15-3.4.9z"/>',
  inbox: '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5.5 5h13L21 13v6H3v-6z"/>',
  bookmark: '<path d="M6 4h12v17l-6-4.2L6 21z"/>',
  "bookmark-check": '<path d="M6 4h12v17l-6-4.2L6 21z"/><path d="M9.2 10.2l2 2 3.6-3.6"/>',
  note: '<path d="M5 4h14v10l-6 6H5z"/><path d="M13 20v-6h6"/>',
  comment: '<path d="M4 5h16v11H9l-5 4z"/>',
  "book-open": '<path d="M3 5.5C5.5 4 8.5 4 12 6c3.5-2 6.5-2 9-.5V19c-2.5-1.5-5.5-1.5-9 .5-3.5-2-6.5-2-9-.5z"/><path d="M12 6v13.5"/>',
  paperclip: '<path d="M20 11.5l-7.8 7.8a5 5 0 0 1-7.1-7.1l8.1-8.1a3.4 3.4 0 0 1 4.8 4.8l-8.1 8.1a1.7 1.7 0 0 1-2.4-2.4l7.4-7.4"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5M5 20h14"/>',
  quote: '<path d="M10 7H6a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h3v1a3 3 0 0 1-3 3M20 7h-4a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h3v1a3 3 0 0 1-3 3"/>',
  braces: '<path d="M8 4H7a2 2 0 0 0-2 2v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4a2 2 0 0 0 2 2h1M16 4h1a2 2 0 0 1 2 2v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4a2 2 0 0 1-2 2h-1"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.6-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16M20 20v-4h-4"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  sidebar: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  "arrow-left": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  code: '<path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/>',
  "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  "file-search": '<path d="M13 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h4"/><path d="M13 3v5h5v2"/><circle cx="16.5" cy="16.5" r="3"/><path d="M21 21l-2.4-2.4"/>',
  "rows-1": '<path d="M4 6h16M4 10h16M4 14h16M4 18h16"/>',
  sort: '<path d="M8 20V4M4 8l4-4 4 4M16 4v16M12 16l4 4 4-4"/>',
  radar: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12l5.5-5.5"/><circle cx="12" cy="12" r="1"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  grid: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.2"/>',
  list: '<rect x="4" y="5" width="5" height="5" rx="1"/><rect x="4" y="14" width="5" height="5" rx="1"/><path d="M12 7.5h8M12 16.5h8"/>',
  "rows-2": '<path d="M4 5h16M4 8.5h10M4 13h16M4 16.5h10"/>',
  "arrow-up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
  "arrow-down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  "chevron-right": '<path d="M9 6l6 6-6 6"/>',
  "chevron-down": '<path d="M6 9l6 6 6-6"/>',
};
function icon(name) {
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
}
document.querySelectorAll("i[data-icon]").forEach((el) => { el.outerHTML = icon(el.dataset.icon); });

// Search excerpts arrive with \x02…\x03 around the matched words.
const highlight = (s) => esc(s).replace(/\x02/g, "<mark>").replace(/\x03/g, "</mark>");
const MATCH_LABELS = { fulltext: "Full text", abstract: "Abstract", notes: "Notes and annotations",
  supplementary: "Supplementary information" };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const TYPES = {
  article: "Journal article", inproceedings: "Conference paper", preprint: "Preprint",
  book: "Book", incollection: "Book chapter", phdthesis: "PhD thesis",
  mastersthesis: "Master's thesis", techreport: "Technical report", misc: "Other",
};

const state = {
  items: [], collections: [], tags: [],
  view: { type: "all" },          // all | unfiled | collection | tag
  q: "", sort: "year", selected: null,   // newest papers first expanded: new Set(),
  selectedIds: new Set(), anchor: null,        // multiple selection (Shift / Cmd / Ctrl)
  density: "comfortable",
  settings: { include_subcollections: false, new_items_to_read: false },
  sortToRead: "year",
};
const sortKey = () => (state.view.type === "toread" ? state.sortToRead : state.sort);
function setSortKey(value) {
  if (state.view.type === "toread") state.sortToRead = value;
  else state.sort = value;
  try {
    localStorage.setItem("sort", state.sort);
    localStorage.setItem("sortToRead", state.sortToRead);
  } catch {}
}
try {
  state.sort = localStorage.getItem("sort") || state.sort;
  state.sortToRead = localStorage.getItem("sortToRead") || state.sortToRead;
} catch {}
try { state.expanded = new Set(JSON.parse(localStorage.getItem("expanded") || "[]")); } catch {}
try {
  const saved = localStorage.getItem("density");
  state.density = ["compact", "gallery", "figures"].includes(saved) ? saved : "comfortable";
} catch {}

// --------------------------------------------------------------------------
// API
// --------------------------------------------------------------------------
async function api(path, opts = {}) {
  const init = { credentials: "same-origin", ...opts };
  if (opts.json !== undefined) {
    init.body = JSON.stringify(opts.json);
    init.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    init.method = opts.method || "POST";
  }
  const res = await fetch(path, init);
  if (res.status === 401 && path !== "/api/login") { showLogin(); throw new Error("Not authenticated"); }
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res.text();
}

function toast(msg, err = false, ms = 4000) {
  const el = document.createElement("div");
  el.className = "toast" + (err ? " err" : "");
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), ms);
  return el;
}

// --------------------------------------------------------------------------
// Login
// --------------------------------------------------------------------------
function showLogin() {
  document.querySelectorAll("dialog[open]").forEach((d) => d.close());
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  $("#login-password").focus();
}

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-error").textContent = "";
  try {
    await api("/api/login", { json: { password: $("#login-password").value } });
    $("#login-password").value = "";
    start();
  } catch (err) { $("#login-error").textContent = err.message; }
});

async function signOut() {
  await api("/api/logout", { method: "POST" });
  showLogin();
}

// --------------------------------------------------------------------------
// Data loading
// --------------------------------------------------------------------------
async function loadSidebar() {
  let people;
  [state.collections, state.tags, state.counts, people] = await Promise.all(
    [api("/api/collections"), api("/api/tags"), api("/api/library-counts"), api("/api/people")]);
  state.people = people.people;
  state.radarUnseen = people.radar_unseen;
  renderSidebar();
}

async function loadItems() {
  // A followed person's publications, or the radar (people.js).
  if (["person", "radar", "people"].includes(state.view.type)) return loadWorks();
  leaveWorksView();
  const p = new URLSearchParams({ sort: sortKey() });
  if (state.q) p.set("q", state.q);
  if (state.view.type === "collection") {
    p.set("collection", state.view.id);
    if (state.settings.include_subcollections) p.set("subcollections", "true");
  }
  if (state.view.type === "unfiled") p.set("unfiled", "true");
  if (state.view.type === "toread") p.set("to_read", "true");
  if (state.view.type === "tag") p.set("tag", state.view.name);
  state.items = await api("/api/items?" + p);
  renderItems();
}

async function refresh() {
  await Promise.all([loadSidebar(), loadItems()]);
  const present = new Set(state.items.map((i) => i.id));
  state.selectedIds = new Set([...state.selectedIds].filter((id) => present.has(id)));
  if (!present.has(state.selected)) state.selected = [...state.selectedIds].at(-1) ?? null;
  renderSelection();
  if (typeof refreshPaper === "function") refreshPaper();   // paper.js
}

// The item pane: one item, several (bulk actions) or none (library overview).
function renderSelection() {
  if (!state.selectedIds.size) hideDetailPane();
  $$("#items tr, #cards [data-id]").forEach((el) => el.classList.toggle("selected", state.selectedIds.has(Number(el.dataset.id))));
  if (state.selectedIds.size > 1) return renderMulti();
  renderDetail(state.items.find((i) => i.id === state.selected) || null);
}

// --------------------------------------------------------------------------
// Sidebar
// --------------------------------------------------------------------------
function renderSidebar() {
  $$(".side-item[data-view]").forEach((el) =>
    el.classList.toggle("active", state.view.type === el.dataset.view));
  const counts = state.counts || {};
  $("#count-all").textContent = counts.all || "";
  $("#count-unfiled").textContent = counts.unfiled || "";
  $("#count-toread").textContent = counts.to_read || "";

  const byParent = {};
  for (const c of state.collections) (byParent[c.parent_id ?? "root"] ||= []).push(c);
  const box = $("#collections");
  box.innerHTML = "";
  const walk = (parent, depth) => {
    for (const c of byParent[parent] || []) {
      const kids = byParent[c.id]?.length;
      const open = state.expanded.has(c.id);
      const el = document.createElement("div");
      el.className = "side-item" + (state.view.type === "collection" && state.view.id === c.id ? " active" : "");
      el.style.paddingLeft = 12 + depth * 14 + "px";
      el.dataset.cid = c.id;
      el.innerHTML = `<span class="twisty">${kids ? icon(open ? "chevron-down" : "chevron-right") : ""}</span>
        ${icon("folder")}<span class="name">${esc(c.name)}</span><span class="count"
          title="${c.total} in total${c.total !== c.count ? ` (${c.count} directly in this collection)` : ""}">${c.total || ""}</span>
        <span class="actions"><button data-a="sub" title="New subcollection">${icon("plus")}</button>
        <button data-a="rename" title="Rename">${icon("pencil")}</button><button data-a="del" title="Delete">${icon("x")}</button></span>`;
      el.addEventListener("click", (e) => {
        const a = e.target.closest("[data-a]")?.dataset.a;
        if (a) return collectionAction(a, c);
        if (e.target.closest(".twisty") && kids) {
          open ? state.expanded.delete(c.id) : state.expanded.add(c.id);
          try { localStorage.setItem("expanded", JSON.stringify([...state.expanded])); } catch {}
          return renderSidebar();
        }
        setView({ type: "collection", id: c.id, name: c.name });
      });
      el.draggable = true;
      el.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("text/x-bubo-collection", String(c.id));
        e.dataTransfer.effectAllowed = "move";
        draggedCollection = c.id;
      });
      el.addEventListener("dragend", () => { draggedCollection = null; });
      el.addEventListener("dragover", (e) => {
        // A collection cannot go into itself or one of its own subcollections.
        if (draggedCollection != null && isSelfOrDescendant(c.id, draggedCollection)) return;
        e.preventDefault();
        el.classList.add("drop-target");
      });
      el.addEventListener("dragleave", () => el.classList.remove("drop-target"));
      el.addEventListener("drop", async (e) => {
        e.preventDefault(); e.stopPropagation();
        el.classList.remove("drop-target");
        const moved = Number(e.dataTransfer.getData("text/x-bubo-collection"));
        const ids = draggedItemIds(e);
        if (moved) {
          if (!isSelfOrDescendant(c.id, moved)) {
            state.expanded.add(c.id);
            moveCollection(moved, c.id);
          }
        } else if (ids.length) {
          await api(`/api/collections/${c.id}/items`, { json: { item_ids: ids } });
          toast(`${ids.length > 1 ? `${ids.length} papers` : "Added"} to “${c.name}”`);
          refresh();
        } else if (e.dataTransfer.files.length) {
          resetWindowDrag();
          openUploadDialog(e.dataTransfer.files, c.id);
        }
      });
      box.appendChild(el);
      if (kids && open) walk(c.id, depth + 1);
    }
  };
  walk("root", 0);
  if (!state.collections.length) box.innerHTML = `<div class="side-item muted">No collections</div>`;

  const current = state.view.type === "collection" && state.collections.find((c) => c.id === state.view.id);
  const hasChildren = current && state.collections.some((c) => c.parent_id === current.id);
  $("#sub-toggle").classList.toggle("hidden", !hasChildren);
  $("#include-sub").checked = !!state.settings.include_subcollections;

  $("#tags").innerHTML = state.tags.map((t) =>
    `<span class="tag${state.view.type === "tag" && state.view.name === t.name ? " active" : ""}"
       data-tag="${esc(t.name)}">${esc(t.name)} <span class="muted">${t.count}</span></span>`).join("")
    || `<span class="muted tags-empty">Add tags from any paper's details.</span>`;
  if (typeof renderPeople === "function") renderPeople();   // people.js
}

$("#tags").addEventListener("click", (e) => {
  const t = e.target.closest(".tag");
  if (!t) return;
  const name = t.dataset.tag;
  setView(state.view.type === "tag" && state.view.name === name ? { type: "all" } : { type: "tag", name });
});

$$(".side-item[data-view]").forEach((el) =>
  el.addEventListener("click", () => setView({ type: el.dataset.view })));

async function setToRead(ids, on) {
  try {
    await Promise.all(ids.map((id) => api(`/api/items/${id}`, { method: "PATCH", json: { to_read: on } })));
    toast(on ? "Added to your reading list" : "Removed from your reading list");
    refresh();
  } catch (err) { toast(err.message, true); }
}

const toReadEntry = $("#side-toread");
const isItemDrag = (e) => [...(e.dataTransfer?.types || [])].includes("text/x-bubo-item");
toReadEntry.addEventListener("dragover", (e) => {
  if (!isItemDrag(e)) return;
  e.preventDefault();
  toReadEntry.classList.add("drop-target");
});
toReadEntry.addEventListener("dragleave", () => toReadEntry.classList.remove("drop-target"));
toReadEntry.addEventListener("drop", (e) => {
  toReadEntry.classList.toggle("drop-target", false);
  const ids = draggedItemIds(e);
  if (!ids.length) return;
  e.preventDefault();
  e.stopPropagation();
  setToRead(ids, true);
});

// Items dragged from the list: several when the drag starts on a selected row.
function draggedItemIds(e) {
  try {
    const many = e.dataTransfer.getData("text/x-bubo-items");
    if (many) return JSON.parse(many).map(Number);
  } catch {}
  const one = Number(e.dataTransfer.getData("text/x-bubo-item"));
  return one ? [one] : [];
}

$("#add-collection").addEventListener("click", () => collectionAction("new"));

let draggedCollection = null;

function isSelfOrDescendant(cid, ancestor) {
  for (let c = state.collections.find((x) => x.id === cid), i = 0; c && i < 100; i++) {
    if (c.id === ancestor) return true;
    c = state.collections.find((x) => x.id === c.parent_id);
  }
  return false;
}

async function moveCollection(cid, parentId) {
  const c = state.collections.find((x) => x.id === cid);
  if (!c || c.parent_id === parentId) return;
  try {
    await api(`/api/collections/${cid}`, { method: "PATCH", json: { parent_id: parentId } });
    try { localStorage.setItem("expanded", JSON.stringify([...state.expanded])); } catch {}
    const parent = state.collections.find((x) => x.id === parentId);
    toast(parent ? `Moved “${c.name}” into “${parent.name}”` : `Moved “${c.name}” to the top level`);
    refresh();
  } catch (err) { toast(err.message, true); }
}

// Dropping a collection on the "Collections" heading moves it to the top level.
const collectionsHead = $("#collections-head");
collectionsHead.addEventListener("dragover", (e) => {
  if (draggedCollection == null) return;
  e.preventDefault();
  collectionsHead.classList.add("drop-target");
});
collectionsHead.addEventListener("dragleave", () => collectionsHead.classList.remove("drop-target"));
collectionsHead.addEventListener("drop", (e) => {
  const moved = Number(e.dataTransfer.getData("text/x-bubo-collection"));
  collectionsHead.classList.remove("drop-target");
  if (!moved) return;
  e.preventDefault();
  moveCollection(moved, null);
});

$("#include-sub").addEventListener("change", async (e) => {
  state.settings.include_subcollections = e.target.checked;
  renderSidebar();
  loadItems();
  try { await api("/api/settings", { method: "PATCH", json: { include_subcollections: e.target.checked } }); }
  catch (err) { toast(err.message, true); }
});

async function collectionAction(action, c) {
  try {
    if (action === "new" || action === "sub") {
      const name = prompt(action === "sub" ? `New subcollection inside “${c.name}”:` : "Collection name:");
      if (!name?.trim()) return;
      await api("/api/collections", { json: { name, parent_id: c?.id ?? null } });
      if (c) state.expanded.add(c.id);
    } else if (action === "rename") {
      const name = prompt("New name:", c.name);
      if (!name?.trim()) return;
      await api(`/api/collections/${c.id}`, { method: "PATCH", json: { name } });
    } else if (action === "del") {
      if (!confirm(`Delete the collection “${c.name}” and its subcollections? The items themselves will not be deleted.`)) return;
      await api(`/api/collections/${c.id}`, { method: "DELETE" });
      if (state.view.type === "collection" && state.view.id === c.id) state.view = { type: "all" };
    }
    refresh();
  } catch (err) { toast(err.message, true); }
}

function setView(view) {
  state.view = view;
  renderSidebar();
  loadItems();
  closeDrawer();
}

// --------------------------------------------------------------------------
// Narrow screens (phones): one pane at a time. The sidebar is a drawer and the
// item pane covers the list; the back button (or the browser's) returns to it.
// --------------------------------------------------------------------------
const narrow = window.matchMedia("(max-width: 760px), (hover: none) and (max-width: 1100px)");
const TOUCH = window.matchMedia("(hover: none)").matches;
const SEARCH_PLACEHOLDER = $("#search").placeholder;
const fitPlaceholder = () => { $("#search").placeholder = narrow.matches ? "Search your library" : SEARCH_PLACEHOLDER; };
fitPlaceholder();

function openDrawer() {
  document.body.classList.add("show-side");
  $("#side-backdrop").hidden = false;
  $("#side-btn").setAttribute("aria-expanded", "true");
}
function closeDrawer() {
  if (!document.body.classList.contains("show-side")) return;
  document.body.classList.remove("show-side");
  $("#side-backdrop").hidden = true;
  $("#side-btn").setAttribute("aria-expanded", "false");
}
$("#side-btn").addEventListener("click", () =>
  document.body.classList.contains("show-side") ? closeDrawer() : openDrawer());
$("#side-backdrop").addEventListener("click", closeDrawer);

function showDetailPane() {
  if (!narrow.matches || document.body.classList.contains("show-detail")) return;
  // Opened with "Edit details" from the paper screen, it goes back there.
  $("#detail-back-label").textContent = document.body.classList.contains("show-paper")
    ? "Paper" : $("#view-title").textContent || "Library";
  document.body.classList.add("show-detail");
  $("#detail").scrollTop = 0;
  history.pushState({ bubo: "detail" }, "");
}
function hideDetailPane(fromHistory = false) {
  if (!document.body.classList.contains("show-detail")) return;
  document.body.classList.remove("show-detail");
  if (!fromHistory && history.state?.bubo === "detail") history.back();
}
$("#detail-back").addEventListener("click", () => hideDetailPane());
window.addEventListener("popstate", () => hideDetailPane(true));
narrow.addEventListener("change", () => {
  fitPlaceholder();
  renderCards();
  if (!narrow.matches) { closeDrawer(); hideDetailPane(); }
});

// --------------------------------------------------------------------------
// Item list
// --------------------------------------------------------------------------
function authorsShort(a) {
  if (!a?.length) return "";
  if (a.length === 1) return a[0].family || a[0].given;
  if (a.length === 2) return `${a[0].family} and ${a[1].family}`;
  return `${a[0].family} et al.`;
}

function sectionTitle() {
  const v = state.view;
  return { all: "My library", unfiled: "Unfiled items", toread: "Reading list",
    collection: v.name, tag: `Tag: ${v.name}`, radar: "Radar", person: v.name, people: "People" }[v.type];
}
function viewTitle() {
  return state.q ? `${sectionTitle()} — “${state.q}”` : sectionTitle();
}

const fullAuthors = (a) => (a || []).map((x) => [x.given, x.family].filter(Boolean).join(" ")).join(", ");
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "");

// What goes in the Publication column: never empty for a preprint.
function venueLabel(i) {
  if (i.venue) return i.venue;
  if (i.item_type === "preprint" || i.arxiv_id) return i.arxiv_id ? "arXiv" : "Preprint";
  return "";
}

const COLUMNS = {
  status: { head: () => icon("bookmark"), title: "Reading list", width: "34px", icon: true },
  title: { head: () => "Title", sort: "title" },
  authors: { head: () => "Authors", sort: "authors", width: "15%" },
  year: { head: () => "Year", sort: "year", width: "58px" },
  venue: { head: () => "Publication", sort: "venue", width: "15%" },
  added: { head: () => "Added", sort: "added", width: "116px" },
  notes: { head: () => icon("note"), title: "Notes and annotations", width: "30px", icon: true },
  pdf: { head: () => icon("file"), title: "PDF", width: "34px", icon: true },
};
const LAYOUTS = {
  comfortable: ["status", "title", "year", "added", "notes", "pdf"],
  compact: ["status", "title", "authors", "year", "venue", "added", "notes", "pdf"],
};

function renderHead() {
  const cols = LAYOUTS[state.density] || LAYOUTS.comfortable;
  const sort = sortKey(), base = sort.replace(/_(asc|desc)$/, "");
  // "year" and "added" sort descending by default; everything else ascending.
  const desc = ["year", "added"].includes(base) ? !sort.endsWith("_asc") : sort.endsWith("_desc");
  $("#items-cols").innerHTML = cols.map((c) =>
    `<col class="col-${c}"${COLUMNS[c].width ? ` style="width:${COLUMNS[c].width}"` : ""}>`).join("");
  $("#items-head").innerHTML = `<tr>${cols.map((c) => {
    const col = COLUMNS[c], sorted = col.sort && col.sort === base;
    return `<th class="col-${c}${col.icon ? " icon-col" : ""}${sorted ? " sorted" : ""}"
      ${col.sort ? `data-sort="${col.sort}" aria-sort="${sorted ? (desc ? "descending" : "ascending") : "none"}"` : ""}
      ${col.title ? `title="${col.title}" aria-label="${col.title}"` : ""}>${col.head()}${
      sorted ? `<span class="sort-arrow">${icon(desc ? "arrow-down" : "arrow-up")}</span>` : ""}</th>`;
  }).join("")}</tr>`;
  $$(".density [data-density]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.density === state.density)));
  $("#items-table").classList.toggle("comfortable", state.density !== "compact");
}

function cell(c, i) {
  const authors = authorsShort(i.authors), venue = venueLabel(i);
  switch (c) {
    case "status":
      return `<td class="col-status icon-col status" title="${i.to_read ? "On your reading list: click to remove" : "Add to reading list"}">${
        i.to_read ? icon("bookmark-check") : `<span class="off">${icon("bookmark")}</span>`}</td>`;
    case "title":
      if (state.density === "comfortable") {
        const meta = [authors && `<span title="${esc(fullAuthors(i.authors))}">${esc(authors)}</span>`, venue && esc(venue)]
          .filter(Boolean).join(" · ");
        return `<td class="col-title" title="${esc(i.title)}"><div class="t">${esc(i.title) || '<span class="muted">(untitled)</span>'}</div>${
          meta ? `<div class="meta">${meta}</div>` : ""}</td>`;
      }
      return `<td class="col-title" title="${esc(i.title)}">${esc(i.title) || '<span class="muted">(untitled)</span>'}</td>`;
    case "authors": return `<td class="col-authors" title="${esc(fullAuthors(i.authors))}">${esc(authors)}</td>`;
    case "year": return `<td class="col-year">${i.year ?? ""}</td>`;
    case "venue": return `<td class="col-venue" title="${esc(venue)}">${esc(venue)}</td>`;
    case "added": return `<td class="col-added" title="${esc(new Date(i.added_at).toLocaleString("en-GB"))}">${fmtDate(i.added_at)}</td>`;
    case "notes": {
      const parts = [i.notes && "Has notes",
        i.annotation_count && `${i.annotation_count} annotation${i.annotation_count > 1 ? "s" : ""}`].filter(Boolean);
      return `<td class="col-notes icon-col notes"${parts.length ? ` title="${parts.join(", ")}"` : ""}>${parts.length ? icon("note") : ""}</td>`;
    }
    case "pdf": {
      const si = i.supplementary.length
        ? ` (and ${i.supplementary.length} supplementary file${i.supplementary.length > 1 ? "s" : ""})` : "";
      return i.has_file
        ? `<td class="col-pdf icon-col pdf" title="Open PDF${si}">${icon("file")}</td>`
        : `<td class="col-pdf icon-col pdf" title="Find PDF${si}"><span class="missing">${icon("file-search")}</span></td>`;
    }
  }
  return "";
}

function renderItems() {
  $("#view-title").textContent = viewTitle();
  $("#count").textContent = `${state.items.length} item${state.items.length === 1 ? "" : "s"}`;
  // A different section, search or order starts at the top, with the whole header showing
  // (refreshes of the same list keep their place).
  const listKey = JSON.stringify([state.view, state.q, sortKey()]);
  if (listKey !== state.listKey) {
    state.listKey = listKey;
    $(".table-wrap").scrollTop = 0;
    $(".topbar").classList.remove("collapsed", "scrolled");
  }
  // Phones: the section in the header, with the number of papers shown (search included).
  $("#m-title").textContent = sectionTitle();
  $("#m-count").textContent = String(state.items.length);
  $("#m-count").setAttribute("aria-label", `${state.items.length} item${state.items.length === 1 ? "" : "s"}`);
  $("#empty").classList.toggle("hidden", state.items.length > 0);
  renderHead();
  const cols = LAYOUTS[state.density] || LAYOUTS.comfortable;
  $("#items").innerHTML = state.items.map((i) => {
    const sel = state.selectedIds.has(i.id) ? " selected" : "";
    return `<tr data-id="${i.id}" draggable="true" class="item-row${sel}">${cols.map((c) => cell(c, i)).join("")}</tr>${i.match ? `
    <tr data-id="${i.id}" class="snippet-row${sel}">
      <td colspan="${cols.length}"><span class="match-field">${MATCH_LABELS[i.match.field] || ""}</span>
        <span class="snippet">${highlight(i.match.snippet)}</span></td>
    </tr>` : ""}`;
  }).join("");
  $("#items-table").classList.toggle("with-snippets", state.items.some((i) => i.match));
  renderCards();
  const queue = state.view.type === "toread";
  $("#toread-order").classList.toggle("hidden", !queue || (!!cardMode() && !narrow.matches));
  if (queue) {
    const sort = sortKey();
    $("#toread-order-select").value = sort.startsWith("to_read") ? sort : "";
  }
}

// --------------------------------------------------------------------------
// Phones: the library as a gallery of cards or a list with thumbnails
// --------------------------------------------------------------------------
const MOBILE_VIEW_KEY = "mobileView";
state.mobileView = (() => { try { return localStorage.getItem(MOBILE_VIEW_KEY); } catch { return null; } })() === "list"
  ? "list" : "gallery";

// A generated cover for papers without figures: the colour comes from the journal's name
// (fixed saturation and lightness keep white text above 4.5:1 for every hue).
function journalHue(name) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return h % 360;
}

function thumbHTML(i) {
  if (i.cover) {
    return `<div class="tile"><img src="${esc(i.cover.url)}" alt="" loading="lazy" decoding="async"
      width="${i.cover.width}" height="${i.cover.height}"></div>`;
  }
  const venue = [i.venue, i.year].filter(Boolean).join(" · ");
  return `<div class="gen-cover" style="--h:${journalHue(i.venue || i.title || "")}">
    <span class="gc-venue">${esc(venue)}</span><span class="gc-title">${esc(i.title || "(untitled)")}</span></div>`;
}

// "gallery", "list" or null (the table).
function cardMode() {
  if (narrow.matches) return state.mobileView;
  return { gallery: "gallery", figures: "list" }[state.density] || null;
}

function cardHTML(i, mode = cardMode()) {
  const authors = authorsShort(i.authors);
  const desk = narrow.matches ? "" : ` draggable="true"${state.selectedIds.has(i.id) ? ' aria-current="true"' : ""}`;
  const sel = state.selectedIds.has(i.id) ? " selected" : "";
  const title = esc(i.title) || "(untitled)";
  const snippet = i.match ? `<div class="c-snippet">${highlight(i.match.snippet)}</div>` : "";
  const onList = i.to_read ? `<span class="sr-only">, on your reading list</span>` : "";
  if (mode === "list") {
    const meta = [authors, i.venue_short || i.venue, i.year].filter(Boolean).join(" · ");
    return `<a class="m-row${sel}" href="/paper/${i.id}" data-id="${i.id}"${desk}>
      <div class="thumb thumb-sm">${thumbHTML(i)}</div>
      <div class="r-text"><div class="c-title">${title}${onList}</div>
        <div class="c-meta">${esc(meta)}</div>${snippet}</div>
      ${i.to_read ? `<span class="r-mark" aria-hidden="true">${icon("bookmark")}</span>` : ""}
    </a>`;
  }
  return `<a class="card${sel}" href="/paper/${i.id}" data-id="${i.id}"${desk}>
    <div class="thumb">${thumbHTML(i)}
      ${i.to_read ? `<span class="badge badge-tl" aria-hidden="true">${icon("bookmark")}</span>` : ""}
      ${i.has_file ? `<span class="badge badge-br" aria-hidden="true">PDF</span>` : ""}
    </div>
    <div class="c-title">${title}${onList}</div>
    <div class="c-meta">${esc([authors, i.year].filter(Boolean).join(" · "))}</div>
    ${i.venue ? `<div class="c-venue">${esc(i.venue)}</div>` : ""}${snippet}
  </a>`;
}

const SORT_CHOICES = [["year", "Newest first"], ["year_asc", "Oldest first"], ["added", "Recently added"],
  ["title", "Title (A–Z)"], ["authors", "Author (A–Z)"]];
const QUEUE_CHOICES = [["to_read", "Longest on the list"], ["to_read_desc", "Latest on the list"]];

let figurePoll;
function renderCards() {
  const box = $("#cards");
  clearTimeout(figurePoll);
  const mode = cardMode();
  $(".table-wrap").classList.toggle("with-cards", !!mode);
  renderDeskSort(mode);
  if (!mode) { box.innerHTML = ""; box.className = "cards"; return; }
  box.className = `cards ${mode}`;
  box.innerHTML = state.items.map((i) => cardHTML(i, mode)).join("");
  $$(".view-switch [data-mode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === state.mobileView)));
  // Figures are extracted in the background after a PDF arrives: check back for them.
  if (state.items.some((i) => i.figures_status === "pending")) figurePoll = setTimeout(loadItems, 4000);
}

// On the desktop the order is chosen here, as the cards have no column headings.
function renderDeskSort(mode) {
  const wrap = $("#desk-sort");
  const show = !!mode && !narrow.matches;
  wrap.classList.toggle("hidden", !show);
  if (!show) return;
  $("#toread-order").classList.add("hidden");
  const choices = state.view.type === "toread" ? [...SORT_CHOICES, ...QUEUE_CHOICES] : SORT_CHOICES;
  const sort = sortKey(), select = $("#desk-sort-select");
  select.innerHTML = choices.map(([v, label]) => `<option value="${v}">${label}</option>`).join("") +
    (choices.some(([v]) => v === sort) ? "" : `<option value="${esc(sort)}">Custom order</option>`);
  select.value = sort;
}
$("#desk-sort-select").addEventListener("change", (e) => { setSortKey(e.target.value); loadItems(); });

$("#cards").addEventListener("click", (e) => {
  const a = e.target.closest("a[data-id]");
  if (!a) return;
  const id = Number(a.dataset.id);
  if (narrow.matches) {
    if (e.metaKey || e.ctrlKey || e.shiftKey) return;   // let the browser open the link
    e.preventDefault();
    return openPaper(id);   // paper.js
  }
  // Desktop: like a table row.
  e.preventDefault();
  const item = state.items.find((i) => i.id === id);
  if (item) clickItem(e, item);
});
$("#cards").addEventListener("dblclick", (e) => {
  const a = e.target.closest("a[data-id]");
  const item = a && !narrow.matches && state.items.find((i) => i.id === Number(a.dataset.id));
  if (item?.has_file) openViewer(item);
});
$$(".view-switch [data-mode]").forEach((b) => b.addEventListener("click", () => {
  state.mobileView = b.dataset.mode;
  try { localStorage.setItem(MOBILE_VIEW_KEY, state.mobileView); } catch {}
  renderCards();
}));

// Phones: the order is chosen in a sheet that rises from the bottom.
function openSortSheet() {
  const dlg = $("#sort-sheet");
  const choices = state.view.type === "toread" ? [...SORT_CHOICES, ...QUEUE_CHOICES] : SORT_CHOICES;
  const sort = sortKey();
  dlg.innerHTML = `<div class="sheet-handle" aria-hidden="true"></div>
    <h2 id="sort-sheet-title">Sort by</h2>
    <div class="sheet-options" role="radiogroup" aria-labelledby="sort-sheet-title">
      ${choices.map(([v, label]) => `<button type="button" role="radio" aria-checked="${v === sort}" data-sort="${v}">
        <span>${label}</span>${v === sort ? icon("check") : ""}</button>`).join("")}
    </div>`;
  dlg.showModal();
  (dlg.querySelector('[aria-checked="true"]') || dlg.querySelector("[data-sort]")).focus();
}
$("#m-sort-btn").addEventListener("click", openSortSheet);
$("#sort-sheet").addEventListener("click", (e) => {
  const dlg = $("#sort-sheet");
  if (e.target === dlg) return dlg.close();             // a tap outside the sheet
  const b = e.target.closest("[data-sort]");
  if (!b) return;
  setSortKey(b.dataset.sort);
  dlg.close();
  loadItems();
});
$("#fab-add").addEventListener("click", () => openUploadDialog());

// Phones: on the way down the list, the first header row slides away and only the search
// row stays; on the way up it comes back. A line under the header shows there is more above.
(() => {
  const wrap = $(".table-wrap"), bar = $(".topbar");
  let last = 0;
  const expand = () => bar.classList.remove("collapsed");
  wrap.addEventListener("scroll", () => {
    if (!narrow.matches) return;
    const y = wrap.scrollTop;
    bar.classList.toggle("scrolled", y > 0);
    if (document.activeElement === $("#search") || y <= 12) expand();
    else if (y > last + 4) bar.classList.add("collapsed");
    else if (y < last - 4) expand();
    last = y;
  }, { passive: true });
  $("#search").addEventListener("focus", expand);
  narrow.addEventListener("change", () => { bar.classList.remove("collapsed", "scrolled"); });
})();

$("#items-head").addEventListener("click", (e) => {
  const th = e.target.closest("th[data-sort]");
  if (!th) return;
  const key = th.dataset.sort;
  const sort = sortKey();
  const base = sort.replace(/_(asc|desc)$/, "");
  const descDefault = key === "year" || key === "added";
  if (base !== key) setSortKey(key);
  else if (descDefault) setSortKey(sort === key ? `${key}_asc` : key);
  else setSortKey(sort === key ? `${key}_desc` : key);
  loadItems();
});

$$(".density [data-density]").forEach((b) => b.addEventListener("click", () => {
  state.density = b.dataset.density;
  try { localStorage.setItem("density", state.density); } catch {}
  renderItems();
}));

$("#toread-order-select").addEventListener("change", (e) => {
  if (!e.target.value) return;
  setSortKey(e.target.value);
  loadItems();
});


$("#items").addEventListener("click", (e) => {
  const tr = e.target.closest("tr");
  if (!tr) return;
  const item = state.items.find((i) => i.id === Number(tr.dataset.id));
  if (!item) return;
  if (e.target.closest("td.status")) return setToRead([item.id], !item.to_read);
  if (e.target.closest("td.pdf") && !(e.shiftKey || e.metaKey || e.ctrlKey)) {
    return item.has_file ? openViewer(item) : findPdf(item);
  }
  if (!clickItem(e, item)) showDetailPane();
});

// A click on a paper (table row or card): Shift selects a range, Cmd/Ctrl adds or removes
// one, a plain click selects just that paper. Returns true for a multiple selection.
function clickItem(e, item) {
  if (e.shiftKey && state.anchor != null) {
    const ids = state.items.map((i) => i.id);
    const [a, b] = [ids.indexOf(state.anchor), ids.indexOf(item.id)].sort((x, y) => x - y);
    const range = ids.slice(a, b + 1);
    state.selectedIds = new Set([...(e.metaKey || e.ctrlKey ? state.selectedIds : []), ...range]);
    state.selected = item.id;
    renderSelection();
    return true;
  }
  if (e.metaKey || e.ctrlKey) {
    if (state.selectedIds.has(item.id)) state.selectedIds.delete(item.id);
    else state.selectedIds.add(item.id);
    state.anchor = item.id;
    state.selected = state.selectedIds.has(item.id) ? item.id : [...state.selectedIds].at(-1) ?? null;
    renderSelection();
    return true;
  }
  select(item);
  return false;
}
// Desktop: a click on an empty part of the list column (its heading included) or of the
// sidebar clears the selection and shows the library overview. Clicks on papers, sidebar
// entries, tags and controls keep doing their own thing.
function clickOnEmpty(e) {
  if (narrow.matches || !state.selectedIds.size || e.shiftKey || e.metaKey || e.ctrlKey) return;
  if (e.target.closest("tr, th, [data-id], [data-view], [data-cid], .side-item, .side-head, .tag-cloud > *, button, a, input, select, label, .menu")) return;
  state.selectedIds = new Set();
  state.selected = null;
  renderSelection();
}
$(".list").addEventListener("click", clickOnEmpty);
$("#sidebar").addEventListener("click", clickOnEmpty);
$("#items").addEventListener("dblclick", (e) => {
  const tr = e.target.closest("tr");
  const item = tr && state.items.find((i) => i.id === Number(tr.dataset.id));
  if (item?.has_file) openViewer(item);
});
$("#items").addEventListener("mouseover", (e) => {
  const id = e.target.closest("tr")?.dataset.id;
  $$("#items tr.hover").forEach((tr) => { if (tr.dataset.id !== id) tr.classList.remove("hover"); });
  if (id) $$(`#items tr[data-id="${id}"]`).forEach((tr) => tr.classList.add("hover"));
});
$("#items").addEventListener("mouseleave", () => $$("#items tr.hover").forEach((tr) => tr.classList.remove("hover")));
// Papers (rows or cards) can be dragged onto a collection or the reading list.
function dragItems(e) {
  const el = e.target.closest("[data-id]");
  if (!el) return;
  const id = Number(el.dataset.id);
  const ids = state.selectedIds.has(id) && state.selectedIds.size > 1 ? [...state.selectedIds] : [id];
  e.dataTransfer.setData("text/x-bubo-item", String(ids[0]));
  e.dataTransfer.setData("text/x-bubo-items", JSON.stringify(ids));
  e.dataTransfer.effectAllowed = "copyMove";
  if (ids.length > 1) {
    const ghost = Object.assign(document.createElement("div"), { className: "drag-ghost", textContent: `${ids.length} papers` });
    document.body.appendChild(ghost);
    e.dataTransfer.setDragImage(ghost, 10, 10);
    setTimeout(() => ghost.remove(), 0);
  }
}
$("#items").addEventListener("dragstart", dragItems);
$("#cards").addEventListener("dragstart", dragItems);

const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
$("#search-hint").textContent = IS_MAC ? "⌘K" : "Ctrl K";

document.addEventListener("keydown", (e) => {
  if (!$("#viewer").classList.contains("hidden")) return; // the viewer handles its own keys
  if (document.querySelector("dialog[open]")) return;
  if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey) && !e.altKey) {
    e.preventDefault();
    $("#search").focus();
    $("#search").select();
    return;
  }
  if (e.target.closest(".menu, .menu-wrap")) return; // the menu handles its own keys
  if (e.target.matches("input, textarea, select")) return;
  const idx = state.items.findIndex((i) => i.id === state.selected);
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const next = state.items[Math.max(0, Math.min(state.items.length - 1, idx + (e.key === "ArrowDown" ? 1 : -1)))];
    if (next) select(next);
  } else if (e.key === "Enter" && idx >= 0 && state.items[idx].has_file) {
    openViewer(state.items[idx]);
  } else if (e.key === "/") {
    e.preventDefault(); $("#search").focus();
  } else if (e.key.toLowerCase() === "a" && (e.metaKey || e.ctrlKey) && state.items.length) {
    e.preventDefault();
    state.selectedIds = new Set(state.items.map((i) => i.id));
    state.selected ??= state.items[0].id;
    renderSelection();
  } else if (e.key === "Escape" && state.selectedIds.size) {
    state.selectedIds = new Set();
    state.selected = null;
    renderSelection();
  }
});

function select(item) {
  state.selected = item?.id ?? null;
  state.selectedIds = new Set(item ? [item.id] : []);
  state.anchor = state.selected;
  renderSelection();
  $(`#items tr[data-id="${state.selected}"], #cards [data-id="${state.selected}"]`)?.scrollIntoView({ block: "nearest" });
}

let searchTimer;

function syncSearchClear() {
  const empty = !$("#search").value;
  $("#search-clear").classList.toggle("hidden", empty);
  $("#search-hint").classList.toggle("hidden", !empty);
}

// Runs a search (or clears it) and refreshes the selected item's "Found in the text".
async function applySearch(q) {
  clearTimeout(searchTimer);
  state.q = q;
  await loadItems();
  if (state.selected != null) renderDetail(state.items.find((i) => i.id === state.selected) || null);
}

function clearSearch() {
  $("#search").value = "";
  syncSearchClear();
  renderSuggest("");
  if (state.q) applySearch("");
}

// A DOI, arXiv ID, PubMed ID or URL typed in the search box is offered for adding.
const ID_KINDS = [
  [/^(doi:\s*)?10\.\d{4,9}\/\S+$/i, "DOI"],
  [/^https?:\/\/(dx\.)?doi\.org\/\S+$/i, "DOI"],
  [/^(arxiv:\s*)?\d{4}\.\d{4,5}(v\d+)?$/i, "arXiv ID"],
  [/^arxiv:\s*[a-z-]+(\.[a-z]{2})?\/\d{7}(v\d+)?$/i, "arXiv ID"],
  [/^https?:\/\/arxiv\.org\/(abs|pdf)\/\S+$/i, "arXiv ID"],
  [/^pmid:?\s*\d{1,9}$/i, "PubMed ID"],
  [/^https?:\/\/pubmed\.ncbi\.nlm\.nih\.gov\/\d+/i, "PubMed ID"],
  [/^https?:\/\/\S+$/i, "URL"],
];
function identifierKind(v, { bareNumbers = false } = {}) {
  v = v.trim();
  if (bareNumbers && /^\d{1,9}$/.test(v)) return "PubMed ID";
  return ID_KINDS.find(([re]) => re.test(v))?.[1] || null;
}

function renderSuggest(v) {
  const kind = identifierKind(v);
  const box = $("#search-suggest");
  box.classList.toggle("hidden", !kind);
  $("#search").setAttribute("aria-expanded", String(!!kind));
  if (!kind) return false;
  box.innerHTML = `<button type="button" id="suggest-add">${icon("plus")}
    <span class="id">Add <b>${esc(v.trim())}</b></span><span class="kind">${kind}</span><kbd>Enter</kbd></button>`;
  return true;
}
$("#search-suggest").addEventListener("mousedown", (e) => e.preventDefault()); // keep focus in the box
$("#search-suggest").addEventListener("click", () => quickAdd($("#search").value.trim()));
$("#search").addEventListener("blur", () => $("#search-suggest").classList.toggle("hidden", true));
$("#search").addEventListener("focus", (e) => renderSuggest(e.target.value));

$("#search").addEventListener("input", (e) => {
  syncSearchClear();
  clearTimeout(searchTimer);
  if (renderSuggest(e.target.value)) return; // an identifier: offer to add it rather than search
  searchTimer = setTimeout(() => applySearch(e.target.value.trim()), 250);
});
$("#search").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && identifierKind(e.target.value)) { e.preventDefault(); quickAdd(e.target.value.trim()); }
  if (e.key === "Escape" && e.target.value) { e.preventDefault(); clearSearch(); }
});
$("#search-clear").addEventListener("click", () => { clearSearch(); $("#search").focus(); });

// --------------------------------------------------------------------------
// Detail pane
// --------------------------------------------------------------------------
function collectionOptions(selected) {
  const byParent = {};
  for (const c of state.collections) (byParent[c.parent_id ?? "root"] ||= []).push(c);
  const out = [];
  const walk = (p, d) => (byParent[p] || []).forEach((c) => {
    out.push(`<label style="padding-left:${d * 14}px"><input type="checkbox" name="col" value="${c.id}"
      ${selected.includes(c.id) ? "checked" : ""}> ${esc(c.name)}</label>`);
    walk(c.id, d + 1);
  });
  walk("root", 0);
  return out.join("") || '<span class="muted">No collections</span>';
}

// The item pane: the paper sheet (paper.js), the same as the phone's paper screen; or, after
// "Edit details", the form with every field. On phones this pane is only used for the form.
function renderDetail(item) {
  const box = $("#detail");
  if (!item) {
    state.editing = null;
    box.classList.remove("editing");
    paneView.forget();
    return renderOverview();
  }
  if (state.editing !== item.id) state.editing = null;
  if (narrow.matches || state.editing === item.id) return renderEditForm(item);
  box.classList.remove("editing");
  overviewToken++;
  paneView.render(item.id, { keepPlace: paneView.state.id === item.id });
}

function renderEditForm(item) {
  const box = $("#detail");
  const desk = !narrow.matches;
  box.classList.toggle("editing", desk);
  if (desk) paneView.forget();
  const authorsText = item.authors.map((a) => [a.family, a.given].filter(Boolean).join(", ")).join("\n");
  const links = [
    item.doi && `<a href="https://doi.org/${esc(item.doi)}" target="_blank" rel="noopener">DOI</a>`,
    item.arxiv_id && `<a href="https://arxiv.org/abs/${esc(item.arxiv_id)}" target="_blank" rel="noopener">arXiv</a>`,
    item.url && `<a href="${esc(item.url)}" target="_blank" rel="noopener">Website</a>`,
  ].filter(Boolean).join(" · ");
  box.innerHTML = `
    ${desk ? `<div class="edit-back"><button type="button" id="edit-back">${icon("chevron-left")} Back to the paper</button></div>` : ""}
    <h2>${esc(item.title) || "(untitled)"}</h2>
    <div class="sub">${esc(authorsShort(item.authors))}${item.year ? " · " + item.year : ""}
      ${links ? `<div class="ids">${links}</div>` : ""}</div>
    <div class="buttons" role="toolbar" aria-label="Item actions">
      ${[
        item.has_file && ["view", "book-open", "View PDF", "primary"],
        !item.has_file && (item.doi || item.arxiv_id) && ["findpdf", "file-search", "Find PDF"],
        ["attach", "paperclip", item.has_file ? "Replace PDF" : "Attach PDF"],
        item.has_file && item.annotation_count && ["annotated", "download", "Download with annotations"],
        item.to_read ? ["toread", "bookmark-check", "On your reading list: click to remove", "on"]
                     : ["toread", "bookmark", "Add to reading list"],
        ["cite", "quote", "Copy citation"],
        ["bib", "braces", "Copy BibTeX"],
        (item.doi || item.arxiv_id) && ["refresh", "refresh", "Refresh metadata"],
        ["delete", "trash", "Delete", "danger"],
      ].filter(Boolean).map(([a, ic, label, cls = ""]) =>
        `<button type="button" class="icon-btn ${cls}" data-a="${a}" data-tip="${label}" aria-label="${label}">${icon(ic)}</button>`).join("")}
    </div>
    <div id="detail-matches"></div>
    <div id="detail-annotations"></div>
    ${supplementarySection(item)}
    <form id="item-form">
      <div class="field"><label>Item type</label><select name="item_type">
        ${Object.entries(TYPES).map(([k, v]) => `<option value="${k}" ${k === item.item_type ? "selected" : ""}>${v}</option>`).join("")}
      </select></div>
      <div class="field"><label>Title</label><textarea name="title" rows="2">${esc(item.title)}</textarea></div>
      <div class="field"><label>Authors (one per line: Surname, Forename)</label>
        <textarea name="authors" rows="${Math.min(8, Math.max(2, item.authors.length))}">${esc(authorsText)}</textarea></div>
      <div class="row2">
        <div class="field"><label>Year</label><input name="year" inputmode="numeric" value="${item.year ?? ""}"></div>
        <div class="field"><label>Citation key</label><input name="citekey" value="${esc(item.citekey)}"></div>
      </div>
      <div class="field"><label>Publication / journal / conference</label><input name="venue" value="${esc(item.venue)}"></div>
      <div class="row3">
        <div class="field"><label>Volume</label><input name="volume" value="${esc(item.volume)}"></div>
        <div class="field"><label>Issue</label><input name="issue" value="${esc(item.issue)}"></div>
        <div class="field"><label>Pages</label><input name="pages" value="${esc(item.pages)}"></div>
      </div>
      <div class="field"><label>Publisher</label><input name="publisher" value="${esc(item.publisher)}"></div>
      <div class="row2">
        <div class="field"><label>DOI</label><input name="doi" value="${esc(item.doi)}"></div>
        <div class="field"><label>arXiv</label><input name="arxiv_id" value="${esc(item.arxiv_id)}"></div>
      </div>
      <div class="field"><label>URL</label><input name="url" value="${esc(item.url)}"></div>
      <div class="field"><label>Tags (comma-separated)</label><input name="tags" value="${esc(item.tags.join(", "))}"></div>
      <div class="field"><label>Collections</label><div class="checklist">${collectionOptions(item.collections)}</div></div>
      <div class="field"><label>Abstract</label><textarea name="abstract" rows="5">${esc(item.abstract)}</textarea></div>
      <div class="field"><label>Notes</label><textarea name="notes" rows="4">${esc(item.notes)}</textarea></div>
      ${item.file_path ? `<div class="muted file-path" title="Location inside the data folder">${icon("folder")} papers/${esc(item.file_path)}</div>` : ""}
      ${item.to_read_at ? `<div class="muted" style="font-size:12px">On your reading list since ${new Date(item.to_read_at).toLocaleDateString("en-GB")}</div>` : ""}
      <div class="muted" style="font-size:12px">Added: ${new Date(item.added_at).toLocaleString("en-GB")}${item.file_size ? ` · PDF ${(item.file_size / 1048576).toFixed(1)} MB` : ""}</div>
      <div class="save-bar"><button type="submit" class="primary">Save changes</button></div>
    </form>`;

  if (item.annotation_count && !desk) loadDetailAnnotations(item);
  $("#detail-supplementary").addEventListener("click", (e) => supplementaryAction(e, item));
  $("#edit-back")?.addEventListener("click", () => {
    if (state.formDirty && !confirm("Your changes have not been saved. Discard them?")) return;
    state.editing = null;
    renderDetail(item);
  });
  if (state.q && item.has_file && !desk) loadDetailMatches(item, state.q);
  box.querySelector(".buttons").addEventListener("click", (e) => {
    const a = e.target.closest("[data-a]")?.dataset.a;
    if (a) itemAction(a, item);
  });
  state.formDirty = false;
  $("#item-form").addEventListener("input", () => { state.formDirty = true; });
  $("#item-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const body = Object.fromEntries(["item_type", "title", "venue", "volume", "issue", "pages",
      "publisher", "doi", "arxiv_id", "url", "abstract", "notes", "citekey"].map((k) => [k, f.get(k).trim()]));
    const year = f.get("year").trim();
    if (year && !/^\d{1,4}$/.test(year)) return toast("The year must be a number", true);
    body.year = year ? Number(year) : null;
    body.authors = f.get("authors").split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
      if (l.includes(",")) { const [family, ...rest] = l.split(","); return { family: family.trim(), given: rest.join(",").trim() }; }
      const parts = l.split(/\s+/); return { family: parts.pop(), given: parts.join(" ") };
    });
    body.tags = f.get("tags").split(",").map((t) => t.trim()).filter(Boolean);
    body.collections = f.getAll("col").map(Number);
    try {
      await api(`/api/items/${item.id}`, { method: "PATCH", json: body });
      toast("Saved");
      state.editing = null;   // back to the paper sheet
      refresh();
    } catch (err) { toast(err.message, true); }
  });
}

// Shown when nothing is selected: recent papers, the reading list and what needs fixing.
let overviewToken = 0;
async function renderOverview() {
  const token = ++overviewToken;
  let ov;
  try { ov = await api("/api/overview"); } catch { return; }
  if (token !== overviewToken || state.selectedIds.size) return;
  // In the style of the paper sheet (paper.js): cards with figures, a details-like list.
  const card = (i) => `<a class="card" href="/paper/${i.id}" data-id="${i.id}">
      <div class="thumb">${thumbHTML(i)}</div>
      <div class="c-title">${esc(i.title) || "(untitled)"}</div>
      <div class="c-meta">${esc([authorsShort(i.authors), i.year].filter(Boolean).join(" · ") || "No details yet")}</div></a>`;
  const strip = (items, empty) => items.length
    ? `<div class="pv-strip">${items.map(card).join("")}</div>` : `<p class="ov-empty">${empty}</p>`;
  const more = (shown, total, view) => total > shown
    ? `<button type="button" class="pv-link ov-all" data-view="${view}">All ${total}</button>` : "";
  const c = ov.counts;
  const stat = (n, label, view) => `<button type="button" class="ov-stat"${view ? ` data-view="${view}"` : " disabled"}>
      <span class="ov-n">${n}</span><span class="ov-label">${label}</span></button>`;
  $("#detail").innerHTML = `<div class="pv pv-pane overview">
    <div class="pv-bar"><span class="pv-bar-title">Library</span></div>
    <h1 class="pv-title">Library overview</h1>
    <div class="ov-stats">
      ${stat(c.papers, c.papers === 1 ? "paper" : "papers", "all")}
      ${stat(c.with_pdf, "with a PDF")}
      ${stat(c.to_read, "to read", "toread")}
    </div>
    <section class="pv-section"><h2>Recently added</h2>
      ${strip(ov.recent, "Nothing yet: press Add to bring in your first paper.")}</section>
    <section class="pv-section"><h2><span>On your reading list</span>${more(ov.to_read.length, ov.to_read_total, "toread")}</h2>
      ${strip(ov.to_read, "Your reading list is empty. Add papers with the bookmark on their sheet, or drag them onto Reading list.")}</section>
    <section class="pv-section"><h2><span>Incomplete metadata</span>${ov.incomplete_total ? `<span class="ov-count">${ov.incomplete_total}</span>` : ""}</h2>
      ${ov.incomplete.length ? `<div class="pv-details ov-list">${ov.incomplete.map((i) => `
        <button type="button" class="ov-row" data-id="${i.id}">
          <span class="thumb thumb-sm">${thumbHTML(i)}</span>
          <span class="ov-row-text"><span class="ov-row-title">${esc(i.title) || "(untitled)"}</span>
            <span class="ov-missing">Missing: ${esc(i.missing.join(", "))}</span></span>
        </button>`).join("")}</div>` : `<p class="ov-empty">Every paper has its basic details. Well done.</p>`}</section>
  </div>`;
  $("#detail .overview").addEventListener("click", (e) => {
    const target = e.target.closest("[data-id]");
    if (target) { e.preventDefault(); return showItem(Number(target.dataset.id)); }
    const view = e.target.closest("[data-view]")?.dataset.view;
    if (view) setView({ type: view });
  });
}

// Several papers selected: bulk actions.
function renderMulti() {
  overviewToken++;
  state.editing = null;
  $("#detail").classList.remove("editing");
  paneView.forget();
  const ids = [...state.selectedIds];
  const items = state.items.filter((i) => state.selectedIds.has(i.id));
  const onList = items.filter((i) => i.to_read).length;
  $("#detail").innerHTML = `<div class="multi">
    <h2>${ids.length} papers selected</h2>
    <div class="muted">Drag them onto a collection or the reading list, or use the actions below.
      Shift-click selects a range; ${IS_MAC ? "⌘" : "Ctrl"}-click adds or removes one.</div>
    <div class="actions">
      ${onList < items.length ? `<button type="button" data-bulk="toread">${icon("bookmark")} Add to reading list</button>` : ""}
      ${onList ? `<button type="button" data-bulk="unread">${icon("bookmark-check")} Remove from reading list</button>` : ""}
      ${state.collections.length ? `<div class="row"><select id="bulk-collection" aria-label="Collection">${
        collectionSelectOptions(null).replace("No collection", "Choose a collection…")}</select>
        <button type="button" data-bulk="collect">${icon("folder")} Add</button></div>` : ""}
      <button type="button" data-bulk="export">${icon("download")} Export to BibTeX</button>
      <button type="button" data-bulk="delete" class="danger">${icon("trash")} Delete ${ids.length} papers</button>
    </div>
    <ul class="muted" style="padding-left:18px;font-size:12.5px">${items.slice(0, 12).map((i) =>
      `<li>${esc(i.title) || "(untitled)"}</li>`).join("")}${items.length > 12 ? `<li>…and ${items.length - 12} more</li>` : ""}</ul>
  </div>`;
  $("#detail .multi").addEventListener("click", async (e) => {
    const action = e.target.closest("[data-bulk]")?.dataset.bulk;
    if (!action) return;
    try {
      if (action === "toread" || action === "unread") await setToRead(ids, action === "toread");
      else if (action === "collect") {
        const cid = Number($("#bulk-collection").value);
        if (!cid) return toast("Choose a collection first", true);
        await api(`/api/collections/${cid}/items`, { json: { item_ids: ids } });
        toast(`Added ${ids.length} papers to “${state.collections.find((c) => c.id === cid)?.name}”`);
        refresh();
      } else if (action === "export") exportBibtex(ids);
      else if (action === "delete") {
        if (!confirm(`Delete ${ids.length} papers and their PDFs? This cannot be undone.`)) return;
        await Promise.all(ids.map((id) => api(`/api/items/${id}`, { method: "DELETE" })));
        state.selectedIds = new Set();
        state.selected = null;
        toast(`Deleted ${ids.length} papers`);
        refresh();
      }
    } catch (err) { toast(err.message, true); }
  });
}

async function findPdf(item) {
  const pending = toast("Looking for a free PDF…", false, 60000);
  try {
    await api(`/api/items/${item.id}/find-pdf`, { method: "POST" });
    toast(`PDF found and attached: ${item.title}`);
    refresh();
  } catch (err) { toast(err.message, true, 7000); }
  finally { pending.remove(); }
}

async function itemAction(action, item) {
  try {
    if (action === "view") openViewer(item);
    else if (action === "findpdf") await findPdf(item);
    else if (action === "annotated") window.location.href = `/api/items/${item.id}/annotated.pdf`;
    else if (action === "attach") {
      if (item.has_file && item.annotation_count && !confirm("Your annotations will be kept, but they may no longer line up with the new PDF. Continue?")) return;
      const input = $("#attach-input");
      input.onchange = async () => {
        if (!input.files[0]) return;
        const fd = new FormData();
        fd.append("file", input.files[0]);
        const t = toast("Uploading PDF…", false, 60000);
        try { await api(`/api/items/${item.id}/file`, { method: "POST", body: fd }); toast("PDF attached"); refresh(); }
        catch (err) { toast(err.message, true); }
        finally { t.remove(); input.value = ""; }
      };
      input.click();
    } else if (action === "toread") {
      await setToRead([item.id], !item.to_read);
    } else if (action === "cite") {
      const c = await api(`/api/items/${item.id}/citation`);
      await copyRich(c.text, c.html);
      toast(`Citation copied (${c.name})`);
    } else if (action === "bib") {
      copyText(await api(`/api/items/${item.id}/bibtex`));
      toast("BibTeX copied to clipboard");
    } else if (action === "refresh") {
      await refreshMetadata(item);
    } else if (action === "delete") {
      if (!confirm(`Delete “${item.title || "this item"}”${item.has_file ? " and its PDF" : ""}? This cannot be undone.`)) return;
      await api(`/api/items/${item.id}`, { method: "DELETE" });
      state.selected = null;
      state.selectedIds = new Set();
      refresh();
    }
  } catch (err) { toast(err.message, true); }
}

async function loadDetailMatches(item, q) {
  let r;
  try { r = await api(`/api/items/${item.id}/text-matches?` + new URLSearchParams({ q })); } catch { return; }
  const box = $("#detail-matches");
  if (!box || state.selected !== item.id || state.q !== q || !r.hits.length) return;
  const more = r.total > r.hits.length ? `, showing the first ${r.hits.length}` : "";
  box.innerHTML = `<div class="field"><label>Found in the text (${r.total} sentence${r.total > 1 ? "s" : ""}${more})</label>
    <div class="detail-matches">${r.hits.map((h) => `
      <button type="button" class="detail-match" data-page="${h.page}" title="Open the PDF at page ${h.page}">
        <span class="page">p. ${h.page}</span><span>${highlight(h.snippet)}</span></button>`).join("")}</div></div>`;
  box.addEventListener("click", (e) => {
    const hit = e.target.closest(".detail-match");
    if (hit) openViewer(item, null, { page: Number(hit.dataset.page), terms: r.terms });
  });
}

// Supplementary information: files of any type kept with the paper. PDFs, images and
// text open in a new tab; other files are downloaded.
function supplementarySection(item) {
  const files = item.supplementary;
  return `<div class="field" id="detail-supplementary">
    <label>Supplementary information${files.length ? ` (${files.length})` : ""}</label>
    ${files.length ? `<ul class="supp-list">${files.map((s) => `
      <li data-id="${s.id}">
        ${icon("file")}
        <a href="/api/supplementary/${s.id}/file" target="_blank" rel="noopener" class="name"
          title="${esc(s.file_path ? `papers/${s.file_path}` : s.name)}">${esc(s.name)}</a>
        <span class="muted size">${s.size ? fmtSize(s.size) : ""}</span>
        <a class="supp-btn" href="/api/supplementary/${s.id}/file?download=true" title="Download" aria-label="Download ${esc(s.name)}">${icon("download")}</a>
        <button type="button" class="supp-btn" data-supp="remove" title="Remove" aria-label="Remove ${esc(s.name)}">${icon("x")}</button>
      </li>`).join("")}</ul>` : ""}
    <button type="button" class="link-btn" data-supp="add">${icon("plus")} Add supplementary files</button>
  </div>`;
}

async function supplementaryAction(e, item) {
  const action = e.target.closest("[data-supp]")?.dataset.supp;
  if (action === "add") {
    const input = $("#supp-input");
    input.onchange = async () => {
      const files = [...input.files];
      input.value = "";
      if (files.length) await addSupplementary(item.id, files);
    };
    input.click();
  } else if (action === "remove") {
    const id = Number(e.target.closest("li").dataset.id);
    const s = item.supplementary.find((x) => x.id === id);
    if (!confirm(`Remove “${s.name}” from this paper? The file is deleted.`)) return;
    try { await api(`/api/supplementary/${id}`, { method: "DELETE" }); toast("Supplementary file removed"); refresh(); }
    catch (err) { toast(err.message, true); }
  }
}

async function addSupplementary(itemId, files) {
  const t = toast(`Uploading ${files.length > 1 ? `${files.length} files` : files[0].name}…`, false, 120000);
  let added = 0;
  try {
    for (const file of files) {
      const fd = new FormData();
      fd.append("file", file);
      const r = await api(`/api/items/${itemId}/supplementary`, { method: "POST", body: fd });
      if (r.status === "added") added++;
      else toast(`“${file.name}” is already attached to this paper`);
    }
    if (added) toast(added > 1 ? `${added} supplementary files added` : "Supplementary file added");
  } catch (err) { toast(err.message, true); }
  finally { t.remove(); refresh(); }
}

async function loadDetailAnnotations(item) {
  let list;
  try { list = await api(`/api/items/${item.id}/annotations`); } catch { return; }
  const box = $("#detail-annotations");
  if (!box || state.selected !== item.id || !list.length) return;
  const colours = window.BuboViewer?.COLOURS || {};
  box.innerHTML = `<div class="field"><label>Annotations (${list.length})</label>
    <div class="detail-anns">${list.map((a) => `
      <div class="detail-ann" data-id="${a.id}" style="--c:${colours[a.color] || "#ffd400"}" title="Open in the viewer">
        <div class="muted">Page ${a.page + 1}${a.kind === "note" ? " · Note" : ""}</div>
        ${a.text ? `<div class="quote">${esc(a.text)}</div>` : ""}
        ${a.comment ? `<div>${esc(a.comment)}</div>` : ""}
      </div>`).join("")}</div></div>`;
  box.addEventListener("click", (e) => {
    const el = e.target.closest(".detail-ann");
    if (el && item.has_file) openViewer(item, Number(el.dataset.id));
  });
}

// --------------------------------------------------------------------------
// Refresh metadata: field-by-field comparison before saving
// --------------------------------------------------------------------------
const FIELD_LABELS = {
  item_type: "Item type", title: "Title", authors: "Authors", year: "Year", venue: "Publication",
  venue_short: "Journal abbreviation",
  volume: "Volume", issue: "Issue", pages: "Pages", publisher: "Publisher", doi: "DOI", url: "URL",
  abstract: "Abstract",
};

function formatValue(field, v) {
  if (v == null || v === "" || (Array.isArray(v) && !v.length)) return '<span class="muted">(empty)</span>';
  if (field === "authors") return esc(v.map((a) => [a.family, a.given].filter(Boolean).join(", ")).join("; "));
  if (field === "item_type") return esc(TYPES[v] || v);
  return esc(v);
}

async function refreshMetadata(item) {
  if (state.formDirty && !confirm("This item has unsaved changes, which will be discarded. Continue?")) return;
  const pending = toast("Looking up metadata…", false, 60000);
  let preview;
  try { preview = await api(`/api/items/${item.id}/refresh-preview`); }
  finally { pending.remove(); }
  const { source, changes } = preview;
  if (!changes.length) return toast(`Already up to date with ${source}`);

  const dlg = $("#refresh-dialog");
  dlg.innerHTML = `<form method="dialog">
    <h3 id="refresh-title">Refresh metadata from ${esc(source)}</h3>
    <p class="muted">${changes.length} field${changes.length > 1 ? "s differ" : " differs"}. Tick the ones to replace;
      nothing is saved until you apply.</p>
    <div class="diff-wrap"><table class="diff-table">
      <thead><tr><th class="pick"><input type="checkbox" id="diff-all" checked aria-label="Select all"></th>
        <th class="fname">Field</th><th>Current</th><th>New</th></tr></thead>
      <tbody>${changes.map((c, i) => `<tr>
        <td class="pick"><input type="checkbox" name="pick" value="${i}" checked aria-label="Replace ${FIELD_LABELS[c.field]}"></td>
        <th scope="row" class="fname">${FIELD_LABELS[c.field] || esc(c.field)}</th>
        <td class="old"><div class="val">${formatValue(c.field, c.current)}</div></td>
        <td class="new"><div class="val">${formatValue(c.field, c.new)}</div></td></tr>`).join("")}</tbody>
    </table></div>
    <div class="dialog-buttons">
      <button value="cancel">Cancel</button>
      <button value="apply" class="primary" id="diff-apply"></button>
    </div></form>`;

  const picks = $$('input[name="pick"]', dlg);
  const update = () => {
    const n = picks.filter((p) => p.checked).length;
    $("#diff-apply").textContent = n ? `Apply ${n} field${n > 1 ? "s" : ""}` : "Apply";
    $("#diff-apply").disabled = !n;
    $("#diff-all").checked = n === picks.length;
    $("#diff-all").indeterminate = n > 0 && n < picks.length;
  };
  $("#diff-all").addEventListener("change", (e) => { picks.forEach((p) => { p.checked = e.target.checked; }); update(); });
  dlg.querySelector("tbody").addEventListener("click", (e) => {
    const row = e.target.closest("tr");
    if (row && e.target.tagName !== "INPUT" && !window.getSelection()?.toString()) {
      const box = row.querySelector("input");
      box.checked = !box.checked;
    }
    update();
  });
  update();

  dlg.returnValue = "";
  dlg.showModal();
  dlg.addEventListener("close", async () => {
    if (dlg.returnValue !== "apply") return;
    const body = {};
    picks.filter((p) => p.checked).forEach((p) => { const c = changes[Number(p.value)]; body[c.field] = c.new; });
    try {
      await api(`/api/items/${item.id}`, { method: "PATCH", json: body });
      const n = Object.keys(body).length;
      toast(`Updated ${n} field${n > 1 ? "s" : ""} from ${source}`);
      refresh();
    } catch (err) { toast(err.message, true); }
  }, { once: true });
}

// Copies HTML (keeps italics when pasted into a word processor) with a plain-text fallback.
async function copyRich(text, htmlText) {
  if (navigator.clipboard && window.isSecureContext && window.ClipboardItem) {
    try {
      await navigator.clipboard.write([new ClipboardItem({
        "text/plain": new Blob([text], { type: "text/plain" }),
        "text/html": new Blob([htmlText], { type: "text/html" }),
      })]);
      return;
    } catch { /* fall through to plain text */ }
  }
  return copyText(text);
}

// --------------------------------------------------------------------------
// Settings
// --------------------------------------------------------------------------
async function openSettings() {
  let settings, styles;
  try {
    [settings, styles] = await Promise.all([api("/api/settings"), api("/api/citation-styles")]);
  } catch (err) { return toast(err.message, true); }
  const dlg = $("#settings-dialog");
  dlg.innerHTML = `<form method="dialog">
    <h3 id="settings-title" tabindex="-1" autofocus>Settings</h3>
    <fieldset class="settings-group">
      <legend>New papers</legend>
      <label class="settings-check"><input type="checkbox" class="switch" role="switch" name="new_items_to_read"
        ${settings.new_items_to_read ? "checked" : ""}>
        <span>Put new papers on the reading list
        <span class="muted">Applies to papers added by DOI, arXiv ID or URL, and is the default in the upload dialog.</span></span>
      </label>
    </fieldset>
    <fieldset class="settings-group">
      <legend>Finding PDFs</legend>
      <label class="settings-label" for="contact-email">Contact email</label>
      <input type="email" id="contact-email" name="contact_email" value="${esc(settings.contact_email)}" autocomplete="email"
        placeholder="${settings.contact_email_env ? `Using the server's: ${esc(settings.contact_email_env)}` : "you@example.org"}"
        aria-describedby="contact-email-note">
      <span class="muted settings-note" id="contact-email-note">Enables Unpaywall, which finds many more free PDFs.
        It is sent with each request to Unpaywall, Crossref and PubMed so that they know who is asking,
        so you may prefer an address you keep for this.</span>
    </fieldset>
    <fieldset class="style-picker">
      <legend>Citation style for <b>Copy citation</b></legend>
      ${styles.map((s) => `<label class="style-option">
        <input type="radio" name="citation_style" value="${s.id}" ${s.id === settings.citation_style ? "checked" : ""}>
        <span><span class="style-name">${esc(s.name)}</span>
        <span class="style-example">${s.example.html}</span></span>
      </label>`).join("")}
    </fieldset>
    <div class="dialog-buttons">
      <button value="cancel">Cancel</button>
      <button value="save" class="primary">Save</button>
    </div></form>`;
  dlg.returnValue = "";
  dlg.showModal();
  dlg.addEventListener("close", async () => {
    if (dlg.returnValue !== "save") return;
    const changes = {
      citation_style: dlg.querySelector('input[name="citation_style"]:checked')?.value,
      new_items_to_read: dlg.querySelector('input[name="new_items_to_read"]').checked,
      contact_email: dlg.querySelector('input[name="contact_email"]').value.trim(),
    };
    try {
      state.settings = { ...state.settings, ...(await api("/api/settings", { method: "PATCH", json: changes })) };
      toast("Settings saved");
    } catch (err) { toast(err.message, true); }
  }, { once: true });
}
// --------------------------------------------------------------------------
// Main menu (hamburger button): Settings, BibTeX export, sign out
// --------------------------------------------------------------------------
const menuBtn = $("#menu-btn"), menu = $("#main-menu");
const menuItems = () => $$('[role="menuitem"]', menu);

function openMenu(focusFirst = false) {
  menu.classList.toggle("hidden", false);
  menuBtn.setAttribute("aria-expanded", "true");
  if (focusFirst) menuItems()[0].focus();
}
function closeMenu(returnFocus = false) {
  if (menu.classList.contains("hidden")) return;
  menu.classList.toggle("hidden", true);
  menuBtn.setAttribute("aria-expanded", "false");
  if (returnFocus) menuBtn.focus();
}

menuBtn.addEventListener("click", () => (menu.classList.contains("hidden") ? openMenu() : closeMenu()));
menuBtn.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") { e.preventDefault(); openMenu(true); }
});
menu.addEventListener("keydown", (e) => {
  const items = menuItems(), i = items.indexOf(document.activeElement);
  if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length].focus(); }
  else if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
  else if (e.key === "Home") { e.preventDefault(); items[0].focus(); }
  else if (e.key === "End") { e.preventDefault(); items[items.length - 1].focus(); }
  else if (e.key === "Escape" || e.key === "Tab") { if (e.key === "Escape") e.preventDefault(); closeMenu(e.key === "Escape"); }
});
menu.addEventListener("click", (e) => {
  const action = e.target.closest("[data-menu]")?.dataset.menu;
  if (!action) { if (e.target.closest("a[role=menuitem]")) closeMenu(); return; }
  closeMenu();
  if (action === "settings") openSettings();
  else if (action === "export") exportBibtex();
  else if (action === "signout") signOut();
});
document.addEventListener("click", (e) => { if (!e.target.closest(".menu-wrap")) closeMenu(); });

function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
  const ta = document.createElement("textarea");
  ta.value = text; document.body.appendChild(ta); ta.select();
  document.execCommand("copy"); ta.remove();
}

// --------------------------------------------------------------------------
// PDF viewer (implemented in viewer.js)
// --------------------------------------------------------------------------
function openViewer(item, annotationId = null, extra = {}) {
  if (!window.BuboViewer) {
    window.open(`/api/items/${item.id}/file`, "_blank", "noopener");
    return;
  }
  window.BuboViewer.open(item, { annotationId, onClose: refresh, ...extra });
}

// --------------------------------------------------------------------------
// Adding items
// --------------------------------------------------------------------------
const currentCollection = () => (state.view.type === "collection" ? state.view.id : null);

$("#add-btn").addEventListener("click", () => openUploadDialog());

// Adds a paper by identifier straight from the search box.
async function quickAdd(identifier) {
  if (!identifier) return;
  const pending = toast("Looking up metadata…", false, 60000);
  try {
    const r = await api("/api/items/import", { json: {
      identifier, collection_id: currentCollection(), to_read: !!state.settings.new_items_to_read } });
    if (r.status === "duplicate") toast("Already in your library");
    else toast(`Added${r.item.has_file ? " with PDF" : " (no open-access PDF found)"}: ${r.item.title}`, false, 6000);
    $("#search").value = "";
    syncSearchClear();
    renderSuggest("");
    if (state.q) state.q = "";
    await refresh();
    showItem(r.item.id);
  } catch (err) { toast(err.message, true, 7000); }
  finally { pending.remove(); }
}

// --------------------------------------------------------------------------
// Upload dialog: drag and drop (or choose) PDFs, then upload them with progress
// --------------------------------------------------------------------------
const upload = { entries: [], busy: false, done: false, seq: 0, context: null, library: null };

// File names that usually mean supplementary material: "SI", "ESI", "ESM", "supp", "suppl",
// "supplementary", "supporting information", Elsevier's "mmc1"...
const SI_NAME = /(^|\s)(si|esi|esm|supp|suppl|supplement|supplementary|supplemental|supporting|mmc\d+)(\s|\d|$)/i;
const looksLikeSI = (name) => SI_NAME.test(name.replace(/\.[^.]+$/, "").replace(/[_\-.()[\]]+/g, " "));
const isPdf = (f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name);
const fmtSize = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const UPLOAD_CONCURRENCY = 2;

function collectionSelectOptions(selected) {
  const byParent = {};
  for (const c of state.collections) (byParent[c.parent_id ?? "root"] ||= []).push(c);
  const out = ['<option value="">No collection</option>'];
  const walk = (p, depth) => (byParent[p] || []).forEach((c) => {
    out.push(`<option value="${c.id}" ${c.id === selected ? "selected" : ""}>${"\u00a0\u00a0\u00a0".repeat(depth)}${esc(c.name)}</option>`);
    walk(c.id, depth + 1);
  });
  walk("root", 0);
  return out.join("");
}

function openUploadDialog(files = [], collectionId = currentCollection()) {
  const dlg = $("#upload-dialog");
  if (dlg.open) return addUploadFiles(files);
  upload.entries = [];
  upload.done = false;
  upload.library = null;
  // A paper open in the item pane is offered as the owner of supplementary files.
  upload.context = state.selectedIds.size === 1 ? state.items.find((i) => i.id === state.selected) || null : null;
  dlg.innerHTML = `
    <h3 id="upload-title">Add papers</h3>
    <form class="add-id" id="add-id-form">
      <div class="clearable">
        <input type="text" id="add-id-input" placeholder="DOI, arXiv ID, PubMed ID or publisher URL"
          aria-label="DOI, arXiv ID, PubMed ID or publisher URL" aria-describedby="add-id-hint" autocomplete="off" autofocus>
        <button type="button" id="add-id-clear" class="input-clear hidden" title="Clear (Esc)" aria-label="Clear">${icon("x")}</button>
      </div>
      <button type="submit" class="primary" id="add-id-submit">Add</button>
    </form>
    <div class="add-id-hint muted" id="add-id-hint">Paste an identifier: the details are filled in automatically.</div>
    <div class="add-or">or add PDFs and supplementary files</div>
    <div class="dropzone" id="dropzone" role="button" tabindex="0" aria-describedby="dropzone-hint">
      ${icon("upload")}
      ${TOUCH ? "<strong>Choose PDFs</strong>" : "<strong>Drag and drop PDFs here</strong>"}
      <span id="dropzone-hint" class="muted">${TOUCH ? "Tap to pick files from your device" : "or click to choose files"}</span>
      <input type="file" id="upload-input" multiple hidden>
    </div>
    <ul class="upload-list" id="upload-list"></ul>
    <datalist id="upload-papers"></datalist>
    <div class="field upload-target"><label for="upload-collection">Add to collection</label>
      <select id="upload-collection">${collectionSelectOptions(collectionId)}</select></div>
    <label class="upload-toread" title="The default can be changed in Settings"><input type="checkbox" class="switch" role="switch" id="upload-toread"
      ${state.settings.new_items_to_read ? "checked" : ""}> Add to reading list</label>
    <div class="upload-summary muted" id="upload-summary"></div>
    <div class="dialog-buttons">
      <button type="button" id="upload-manual" class="dialog-left" title="Create an empty entry in the chosen collection and fill it in yourself">
        ${icon("pencil")} Add manually</button>
      <button type="button" id="upload-close">Cancel</button>
      <button type="button" class="primary" id="upload-start"></button>
    </div>`;

  const zone = $("#dropzone"), input = $("#upload-input");
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  });
  input.addEventListener("change", () => { addUploadFiles(input.files); input.value = ""; });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.toggle("over", false));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    zone.classList.toggle("over", false);
    resetWindowDrag();
    addUploadFiles(e.dataTransfer.files);
  });
  $("#upload-list").addEventListener("change", (e) => {
    const row = e.target.closest("li");
    const entry = row && upload.entries[Number(row.dataset.i)];
    if (!entry) return;
    if (e.target.matches(".upload-role select")) setUploadRole(entry, e.target.value);
    else if (e.target.matches(".upload-pick")) pickUploadPaper(entry, e.target.value);
  });
  $("#upload-list").addEventListener("click", (e) => {
    const row = e.target.closest("li");
    if (!row) return;
    const entry = upload.entries[Number(row.dataset.i)];
    if (e.target.closest(".upload-remove") && !upload.busy) {
      upload.entries = upload.entries.filter((x) => x !== entry);
      renderUploadList();
    } else if (e.target.closest(".upload-show") && entry.itemId) {
      dlg.close();
      showItem(entry.itemId);
    }
  });
  $("#upload-close").addEventListener("click", () => dlg.close());
  const idInput = $("#add-id-input");
  const idHint = () => {
    const v = idInput.value.trim(), kind = identifierKind(v, { bareNumbers: true });
    $("#add-id-clear").classList.toggle("hidden", !v);
    $("#add-id-hint").classList.toggle("err", !!v && !kind);
    $("#add-id-hint").textContent = !v ? "Paste an identifier: the details are filled in automatically."
      : kind ? `Detected: ${kind}. Press Enter to add it.` : "Not recognised: use a DOI, arXiv ID, PubMed ID or URL.";
  };
  idInput.addEventListener("input", idHint);
  idInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && idInput.value) { e.preventDefault(); idInput.value = ""; idHint(); }
  });
  $("#add-id-clear").addEventListener("click", () => { idInput.value = ""; idHint(); idInput.focus(); });
  $("#add-id-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = idInput.value.trim();
    if (!v) return idInput.focus();
    idInput.value = "";
    idHint();
    addByIdentifier(v);
  });
  $("#upload-manual").addEventListener("click", () => {
    const cid = $("#upload-collection").value ? Number($("#upload-collection").value) : null;
    const toRead = $("#upload-toread").checked;
    dlg.close();
    addManualEntry(cid, toRead);
  });
  $("#upload-start").addEventListener("click", startUpload);
  dlg.addEventListener("cancel", (e) => { if (upload.busy) e.preventDefault(); });

  addUploadFiles(files);
  renderUploadList();
  dlg.showModal();
}

// Identifiers typed in the dialog join the same list as the PDFs, with their own status.
async function addByIdentifier(identifier) {
  if (upload.done) { upload.entries = []; upload.done = false; }
  const entry = { ident: identifier, kind: identifierKind(identifier, { bareNumbers: true }) || "URL", status: "processing" };
  upload.entries.push(entry);
  renderUploadList();
  const cid = $("#upload-collection").value ? Number($("#upload-collection").value) : null;
  try {
    const r = await api("/api/items/import", { json: { identifier, collection_id: cid, to_read: $("#upload-toread").checked } });
    Object.assign(entry, { status: r.status, identified: true, itemId: r.item.id, title: r.item.title, hasFile: r.item.has_file });
    refresh();
  } catch (err) {
    Object.assign(entry, { status: "error", message: err.message });
  }
  renderUploadList();
}

function addUploadFiles(fileList) {
  const files = [...(fileList || [])];
  if (!files.length) return;
  if (upload.busy) return toast("Please wait until the current upload has finished", true);
  if (upload.done) { upload.entries = []; upload.done = false; }
  const added = [];
  for (const file of files) {
    const known = upload.entries.some((x) => x.file && x.file.name === file.name && x.file.size === file.size);
    if (known) continue;
    const pdf = isPdf(file);
    // Anything that is not a PDF can only be supplementary material.
    const entry = { key: ++upload.seq, file, pdf, role: !pdf || looksLikeSI(file.name) ? "si" : "paper",
                    siFor: null, status: file.size ? "ready" : "invalid", progress: 0 };
    upload.entries.push(entry);
    added.push(entry);
  }
  // Guess which paper new supplementary files belong to: the only paper in the upload,
  // otherwise the paper open in the item pane.
  const papers = uploadPapers();
  for (const x of added) {
    if (x.role !== "si") continue;
    if (papers.length === 1) x.siFor = `batch:${papers[0].key}`;
    else if (!papers.length && upload.context) x.siFor = `item:${upload.context.id}`;
  }
  renderUploadList();
}

// PDFs in the current upload that are papers (not supplementary material).
const uploadPapers = () => upload.entries.filter((x) => x.file && x.role === "paper" && x.status === "ready");
const uploadable = (x) => x.status === "ready" && (x.role === "paper" || !!x.siFor);

function setUploadRole(entry, value) {
  entry.picking = false;
  if (value === "paper") { entry.role = "paper"; entry.siFor = null; }
  else if (value === "pick") { entry.role = "si"; entry.picking = true; loadUploadLibrary(); }
  else { entry.role = "si"; entry.siFor = value || null; }
  renderUploadList();
  if (entry.picking) $(`#upload-list li[data-i="${upload.entries.indexOf(entry)}"] .upload-pick`)?.focus();
}

async function loadUploadLibrary() {
  if (upload.library) return;
  upload.library = [];
  try { upload.library = await api("/api/items?sort=title"); } catch { return; }
  $("#upload-papers").innerHTML = upload.library.map((i) =>
    `<option value="${esc(paperLabel(i))}"></option>`).join("");
}
const paperLabel = (i) => `${i.title || "(untitled)"} (${[authorsShort(i.authors), i.year].filter(Boolean).join(", ")})`;

function pickUploadPaper(entry, label) {
  const item = (upload.library || []).find((i) => paperLabel(i) === label);
  if (!item) return;
  entry.siFor = `item:${item.id}`;
  entry.siTitle = item.title;
  entry.picking = false;
  renderUploadList();
}

function roleSelect(x, i) {
  const short = (s) => (s.length > 60 ? s.slice(0, 57) + "…" : s);
  const options = [];
  if (x.pdf) options.push(["paper", "Paper"]);
  for (const p of uploadPapers()) if (p !== x) options.push([`batch:${p.key}`, `Supplementary information for ${short(p.file.name)}`]);
  if (upload.context) options.push([`item:${upload.context.id}`, `Supplementary information for “${short(upload.context.title || "(untitled)")}”`]);
  if (x.siFor?.startsWith("item:") && !options.some(([v]) => v === x.siFor)) {
    options.push([x.siFor, `Supplementary information for “${short(x.siTitle || "a paper")}”`]);
  }
  options.push(["pick", "Supplementary information for another paper…"]);
  const value = x.picking ? "pick" : x.role === "paper" ? "paper" : x.siFor || "";
  return `<div class="upload-role">
    <select aria-label="What ${esc(x.file.name)} is">
      ${value === "" ? `<option value="" selected disabled>Supplementary information for…</option>` : ""}
      ${options.map(([v, label]) => `<option value="${esc(v)}" ${v === value ? "selected" : ""}>${esc(label)}</option>`).join("")}
    </select>
    ${x.picking ? `<input class="upload-pick" list="upload-papers" placeholder="Type to find the paper in your library"
      aria-label="Paper these supplementary files belong to" autocomplete="off">` : ""}
  </div>`;
}

function uploadStatus(x) {
  switch (x.status) {
    case "ready":
      if (x.role === "si" && !x.siFor) return ["err", "Choose its paper"];
      return ["", x.role === "si" ? "Ready (SI)" : "Ready"];
    case "invalid": return ["err", "Empty file"];
    case "si-added": return ["ok", "Added as supplementary information"];
    case "si-duplicate": return ["warn", "Already attached to that paper"];
    case "uploading": return ["", `Uploading ${Math.round(x.progress * 100)}%`];
    case "processing": return ["", "Looking up metadata…"];
    case "created":
      if (x.ident) return ["ok", x.hasFile ? "Added with PDF" : "Added, no free PDF found"];
      return x.identified ? ["ok", "Added"] : ["warn", "Added, metadata not recognised"];
    case "attached": return ["ok", "Attached to an existing item"];
    case "duplicate": return ["warn", "Already in your library"];
    default: return ["err", x.message || "Failed"];
  }
}

function renderUploadList() {
  const list = $("#upload-list");
  if (!list) return;
  // A supplementary file loses its owner if that paper is removed or becomes SI itself.
  // (Only while choosing: once uploading starts, the papers are no longer "ready".)
  if (!upload.busy && !upload.done) {
    const paperKeys = new Set(uploadPapers().map((p) => `batch:${p.key}`));
    for (const x of upload.entries) if (x.siFor?.startsWith("batch:") && !paperKeys.has(x.siFor)) x.siFor = null;
  }
  list.innerHTML = upload.entries.map((x, i) => {
    const [cls, text] = uploadStatus(x);
    const label = x.file ? x.file.name : (x.title || x.ident);
    const name = x.itemId
      ? `<button type="button" class="upload-show name" title="Show in library">${esc(label)}</button>`
      : `<span class="name" title="${esc(label)}">${esc(label)}</span>`;
    const removable = x.file && !upload.busy && !upload.done && (x.status === "ready" || x.status === "invalid");
    return `<li data-i="${i}">
      ${icon(x.file ? "file" : "plus")}${name}
      <span class="size muted">${x.file ? fmtSize(x.file.size) : esc(x.kind)}</span>
      <span class="status ${cls}">${text}</span>
      ${removable ? `<button type="button" class="upload-remove" title="Remove from list" aria-label="Remove ${esc(x.file.name)}">${icon("x")}</button>` : "<span></span>"}
      ${x.file && x.status === "ready" && !upload.busy ? roleSelect(x, i) : ""}
      ${x.status === "uploading" ? `<div class="progress"><span style="width:${Math.round(x.progress * 100)}%"></span></div>` : ""}
    </li>`;
  }).join("");

  const ready = upload.entries.filter(uploadable);
  const allPdfs = ready.every((x) => x.pdf);
  const start = $("#upload-start");
  start.classList.toggle("hidden", upload.done || !ready.length);
  start.disabled = upload.busy || !ready.length;
  start.textContent = upload.busy ? "Uploading…" : ready.length
    ? `Upload ${ready.length} ${allPdfs ? "PDF" : "file"}${ready.length > 1 ? "s" : ""}` : "Upload";
  const finished = upload.done || upload.entries.some((x) => x.ident && x.status !== "processing");
  $("#upload-close").textContent = finished && !ready.length ? "Close" : "Cancel";
  $("#upload-close").disabled = upload.busy;
  $("#upload-collection").disabled = upload.busy || upload.done;
  $("#upload-manual").disabled = upload.busy;
  $("#upload-toread").disabled = upload.busy || upload.done;
  $("#dropzone").classList.toggle("disabled", upload.busy);
}

// Sends one file with progress; `done` receives the JSON response.
function sendFile(entry, url, fd, done) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      entry.progress = e.loaded / e.total;
      entry.status = entry.progress >= 1 ? "processing" : "uploading";
      renderUploadList();
    };
    xhr.upload.onload = () => { entry.status = "processing"; renderUploadList(); };
    const fail = (message) => { entry.status = "error"; entry.message = message; resolve(); };
    xhr.onerror = () => fail("Network error");
    xhr.onload = () => {
      if (xhr.status === 401) { showLogin(); return fail("Not authenticated"); }
      if (xhr.status >= 400) return fail(xhr.response?.detail || `Upload failed (${xhr.status})`);
      done(xhr.response);
      resolve();
    };
    entry.status = "uploading";
    renderUploadList();
    xhr.send(fd);
  });
}

function uploadOne(entry, collectionId, toRead) {
  const fd = new FormData();
  fd.append("files", entry.file);
  if (collectionId != null) fd.append("collection_id", collectionId);
  if (toRead) fd.append("to_read", "true");
  return sendFile(entry, "/api/items/upload", fd, (res) => {
    const r = res.results[0];
    Object.assign(entry, { status: r.status, identified: r.identified, message: r.message, itemId: r.id });
  });
}

function uploadSupplementary(entry) {
  let itemId = null;
  if (entry.siFor.startsWith("batch:")) {
    const paper = upload.entries.find((x) => `batch:${x.key}` === entry.siFor);
    if (paper && ["created", "attached", "duplicate"].includes(paper.status)) itemId = paper.itemId;
  } else itemId = Number(entry.siFor.slice(5));
  if (!itemId) {
    Object.assign(entry, { status: "error", message: "Its paper was not added" });
    return Promise.resolve();
  }
  const fd = new FormData();
  fd.append("file", entry.file);
  return sendFile(entry, `/api/items/${itemId}/supplementary`, fd, (r) => {
    Object.assign(entry, { status: r.status === "added" ? "si-added" : "si-duplicate", itemId });
  });
}

async function startUpload() {
  const ready = upload.entries.filter(uploadable);
  if (!ready.length || upload.busy) return;
  const cid = $("#upload-collection").value ? Number($("#upload-collection").value) : null;
  upload.busy = true;
  renderUploadList();
  const toRead = $("#upload-toread").checked;
  const run = async (queue, send, workers) => {
    const worker = async () => { while (queue.length) await send(queue.shift()); };
    await Promise.all(Array.from({ length: workers }, worker));
  };
  await run(ready.filter((x) => x.role === "paper"), (x) => uploadOne(x, cid, toRead), UPLOAD_CONCURRENCY);
  // One at a time, so that "SI", "SI 2"... follow the order of the list.
  await run(ready.filter((x) => x.role === "si"), uploadSupplementary, 1);
  upload.busy = false;
  upload.done = true;
  renderUploadList();

  const count = (s) => upload.entries.filter((x) => x.status === s).length;
  const unknown = upload.entries.filter((x) => x.status === "created" && !x.identified).length;
  const parts = [];
  if (count("created")) parts.push(`${count("created")} added`);
  if (count("attached")) parts.push(`${count("attached")} attached to existing items`);
  if (count("duplicate")) parts.push(`${count("duplicate")} already in your library`);
  if (count("si-added")) parts.push(`${count("si-added")} supplementary file${count("si-added") > 1 ? "s" : ""} attached`);
  if (count("error")) parts.push(`${count("error")} failed`);
  $("#upload-summary").textContent = (parts.join(" · ") || "Nothing was added") +
    (unknown ? `. Check the ${unknown} item${unknown > 1 ? "s" : ""} whose metadata was not recognised.` : ".");
  refresh();
}

async function showItem(id) {
  if (!state.items.some((i) => i.id === id)) {
    state.view = { type: "all" };
    state.q = "";
    $("#search").value = "";
    syncSearchClear();
    renderSidebar();
    await loadItems();
  }
  const item = state.items.find((i) => i.id === id);
  if (item) select(item);
}


// Creates an empty entry to fill in by hand and opens it in the item pane.
async function addManualEntry(collectionId, toRead) {
  try {
    const item = await api("/api/items", { json: {
      title: "New item", item_type: "article",
      collections: collectionId != null ? [collectionId] : [], to_read: !!toRead } });
    await showItem(item.id);
    $('#item-form textarea[name="title"]')?.select();
    toast("New entry created: fill in its details and save");
  } catch (err) { toast(err.message, true); }
}

// Dropping PDFs anywhere on the window opens the upload dialog with them.
let dragDepth = 0;
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
const showOverlay = () => !$("#app").classList.contains("hidden") && !$("#upload-dialog").open;
function resetWindowDrag() {
  dragDepth = 0;
  $("#drop-overlay").classList.add("hidden");
}
window.addEventListener("dragenter", (e) => {
  if (!hasFiles(e)) return;
  dragDepth++;
  if (showOverlay()) $("#drop-overlay").classList.remove("hidden");
});
window.addEventListener("dragleave", (e) => { if (hasFiles(e) && --dragDepth <= 0) resetWindowDrag(); });
window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
window.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  resetWindowDrag();
  if (!$("#app").classList.contains("hidden")) openUploadDialog(e.dataTransfer.files);
});

// --------------------------------------------------------------------------
// Export
// --------------------------------------------------------------------------
// Downloads the papers currently listed (library, collection, tag, search…) as a .bib file.
async function exportBibtex(ids = state.items.map((i) => i.id)) {
  if (!ids.length) return toast("There are no items to export", true);
  try {
    const res = await fetch("/api/export/bibtex", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    if (!res.ok) throw new Error("Export failed");
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: "bubo.bib" });
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast(`Exported ${ids.length} item${ids.length > 1 ? "s" : ""} to BibTeX`);
  } catch (err) { toast(err.message, true); }
}

// --------------------------------------------------------------------------
// Start-up
// --------------------------------------------------------------------------
async function start() {
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  try { state.settings = { ...state.settings, ...(await api("/api/settings")) }; } catch {}
  await refresh();
  routeFromLocation();   // a /paper/<id> address (paper.js)
}

api("/api/me").then(start).catch(() => {});
