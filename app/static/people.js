// People followed by their ORCID iD, and the radar of their new publications (people.py).
// Loaded after app.js and uses its helpers ($, api, state, icon, esc, toast, setView…).

Object.assign(ICONS, {
  radar: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12l5.5-5.5"/><circle cx="12" cy="12" r="1"/>',
  person: '<circle cx="12" cy="8" r="3.6"/><path d="M5 20c.8-3.6 3.6-5.6 7-5.6s6.2 2 7 5.6"/>',
  "person-plus": '<circle cx="10" cy="8" r="3.6"/><path d="M3 20c.8-3.6 3.6-5.6 7-5.6 2 0 3.7.7 5 1.9M18 11v6M15 14h6"/>',
  "external-link": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  camera: '<path d="M4 8h3l2-2.5h6L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.5"/>',
});

// A person's photo, or their initials on a colour taken from their name.
function initials(name) {
  const parts = (name || "?").replace(/[^\p{L}\s-]/gu, "").trim().split(/\s+/);
  return ((parts[0] || "?")[0] + (parts.length > 1 ? parts.at(-1)[0] : "")).toUpperCase();
}
function avatarHTML(p, cls = "") {
  return p.photo_url
    ? `<span class="avatar ${cls}"><img src="${esc(p.photo_url)}" alt="" loading="lazy" decoding="async"></span>`
    : `<span class="avatar avatar-initials ${cls}" style="--h:${journalHue(p.name || "")}" aria-hidden="true">${esc(initials(p.name))}</span>`;
}
const countryName = (code) => {
  try { return code ? new Intl.DisplayNames(["en-GB"], { type: "region" }).of(code) : ""; } catch { return code || ""; }
};
const bigNumber = (n) => (n == null ? "" : n >= 10000 ? `${Math.round(n / 1000)}k` : n.toLocaleString("en-GB"));

const worksState = { works: [], person: null, token: 0 };
const isWorksView = () => ["person", "radar", "people"].includes(state.view.type);

// --------------------------------------------------------------------------
// Sidebar: the Radar entry and the people followed
// --------------------------------------------------------------------------
function renderPeople() {
  const list = $("#people");
  if (!list) return;
  const unseen = state.radarUnseen || 0;
  $("#count-radar").textContent = unseen || "";
  $("#count-radar").classList.toggle("new", unseen > 0);
  $("#count-radar").title = unseen ? `${unseen} new publication${unseen > 1 ? "s" : ""}` : "";
  const people = state.people || [];
  $("#count-people").textContent = state.everyone || "";
  list.innerHTML = people.length ? people.map((p) => `
    <div class="side-item person-item${state.view.type === "person" && state.view.id === p.id ? " active" : ""}" data-person="${p.id}" title="ORCID ${esc(p.orcid)}">
      ${avatarHTML(p, "avatar-xs")}<span class="name">${esc(p.name)}</span>
      <span class="count${p.unseen ? " new" : ""}">${p.unseen || ""}</span>
    </div>`).join("")
    : `<div class="side-empty muted">Follow authors from a paper's author list, or anyone by their ORCID iD.</div>`;
}

$("#people").addEventListener("click", (e) => {
  const el = e.target.closest("[data-person]");
  if (!el) return;
  const p = state.people.find((x) => x.id === Number(el.dataset.person));
  if (p) setView({ type: "person", id: p.id, name: p.name });
});
$("#add-person").addEventListener("click", (e) => { e.stopPropagation(); openFollowDialog(); });

// --------------------------------------------------------------------------
// Following someone
// --------------------------------------------------------------------------
function orcidSearchLink(name) {
  return `https://orcid.org/orcid-search/search?searchQuery=${encodeURIComponent(name)}`;
}

function openFollowDialog(person = null) {
  const dlg = $("#follow-dialog");
  dlg.innerHTML = `<form id="follow-form">
    <h3 id="follow-title">${person ? `Follow ${esc(person.name)}` : "Follow a scientist"}</h3>
    <p class="muted">${person
      ? `Bubo has not found their ORCID iD, which it needs to follow them. <a href="${esc(orcidSearchLink(person.name))}" target="_blank" rel="noopener">Look for it on orcid.org</a> and paste it here.`
      : "Enter their ORCID iD. Bubo lists their publications and, every few hours, looks for new ones to show on your radar."}</p>
    <div class="field"><label for="follow-orcid">ORCID iD</label>
      <input id="follow-orcid" placeholder="0000-0002-1825-0097 or https://orcid.org/…" autocomplete="off" required></div>
    <p class="error" id="follow-error" role="alert"></p>
    <div class="dialog-buttons">
      <button type="button" data-close>Cancel</button>
      <button type="submit" class="primary" id="follow-submit">Follow</button>
    </div></form>`;
  dlg.querySelector("[data-close]").addEventListener("click", () => dlg.close());
  $("#follow-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#follow-submit");
    btn.disabled = true;
    btn.textContent = "Looking it up…";
    $("#follow-error").textContent = "";
    try {
      const orcid = $("#follow-orcid").value;
      const p = person ? await api(`/api/people/${person.id}/follow`, { json: { orcid } })
                       : await api("/api/people", { json: { orcid } });
      dlg.close();
      toast(`Following ${p.name}: ${p.works} publication${p.works === 1 ? "" : "s"}${p.unseen ? `, ${p.unseen} new` : ""}`);
      await loadSidebar();
      setView({ type: "person", id: p.id, name: p.name });
    } catch (err) {
      $("#follow-error").textContent = err.message;
      btn.disabled = false;
      btn.textContent = "Follow";
    }
  });
  dlg.showModal();
  $("#follow-orcid").focus();
}

// --------------------------------------------------------------------------
// The list: a person's publications, or the radar
// --------------------------------------------------------------------------
async function loadWorks() {
  const token = ++worksState.token;
  const v = state.view;
  let works, person = null;
  try {
    if (v.type === "people") {
      const r = await api("/api/people?scope=all");
      if (token !== worksState.token) return;
      peopleState.all = r.people;
      state.radarUnseen = r.radar_unseen;
      state.items = [];
      return renderPeoplePage();
    }
    if (v.type === "person") {
      person = await api(`/api/people/${v.id}`);
      // Someone followed: all their publications. Anyone else: their papers in your library.
      works = person.followed ? person.works_list : person.items.map((i) => ({
        id: `item-${i.id}`, title: i.title, authors: i.authors, venue: i.venue, pub_date: i.year ? String(i.year) : null,
        doi: i.doi, in_library: true, item_id: i.id }));
    } else {
      works = (await api("/api/radar")).works;
    }
  } catch (err) {
    if (token !== worksState.token) return;
    toast(err.message, true);
    return setView({ type: "all" });
  }
  if (token !== worksState.token) return;
  worksState.works = works;
  worksState.person = person;
  state.items = [];
  renderWorks();
  // A profile (position, citations, photo) is looked up when the page is first opened.
  if (person?.orcid && isStale(person.profile_checked)) {
    try {
      const p = await api(`/api/people/${person.id}/profile`, { method: "POST" });
      if (token !== worksState.token) return;
      Object.assign(worksState.person, p);
      renderWorks();
    } catch {}
  }
  // Opening the radar counts as having seen what is on it.
  if (v.type === "radar" && state.radarUnseen) {
    try {
      const r = await api("/api/radar/seen", { json: {} });
      state.radarUnseen = r.unseen;
      state.people?.forEach((p) => { p.unseen = 0; });
      renderPeople();
    } catch {}
  }
}

// The server decides (a week for people followed, a month for others); this only skips asking.
const isStale = (iso) => !iso || Date.now() - new Date(iso) > 7 * 86400e3;
const peopleState = { all: [], filter: "all", shown: 120, view: "grid", sort: { key: "", dir: 1 } };
try { peopleState.view = localStorage.getItem("peopleView") === "table" ? "table" : "grid"; } catch {}

// "Mario" and "González-Jiménez" from "Mario González-Jiménez" (family name as stored).
function nameParts(p) {
  const fam = p.family_name && p.name.endsWith(p.family_name) ? p.family_name : p.name.split(" ").slice(-1)[0];
  return { given: p.name.slice(0, p.name.length - fam.length).trim(), family: fam };
}

const PEOPLE_COLUMNS = [
  { key: "given", label: "Name", value: (p) => nameParts(p).given.toLowerCase() },
  { key: "family", label: "Family name", value: (p) => nameParts(p).family.toLowerCase() },
  { key: "affiliation", label: "Affiliation", value: (p) => (p.affiliation || "").toLowerCase() },
  { key: "h_index", label: "h-index", value: (p) => p.h_index ?? -1, numeric: true },
];

function sortedPeople(list) {
  const col = PEOPLE_COLUMNS.find((c) => c.key === peopleState.sort.key);
  if (!col) return list;
  const dir = peopleState.sort.dir;
  return [...list].sort((a, b) => {
    const x = col.value(a), y = col.value(b);
    // Empty values (no affiliation, no h-index) go last whichever the direction.
    const ex = x === "" || x === -1, ey = y === "" || y === -1;
    if (ex !== ey) return ex ? 1 : -1;
    return (x < y ? -1 : x > y ? 1 : 0) * dir;
  });
}

function peopleTableHTML(list) {
  const s = peopleState.sort;
  return `<div class="people-table-wrap"><table class="people-table">
    <thead><tr><th class="pt-photo"><span class="visually-hidden">Photo</span></th>${PEOPLE_COLUMNS.map((c) => `
      <th class="pt-${c.key}${c.numeric ? " num" : ""}" aria-sort="${s.key === c.key ? (s.dir > 0 ? "ascending" : "descending") : "none"}">
        <button type="button" data-act="people-sort" data-key="${c.key}">${c.label}${s.key === c.key ? icon(s.dir > 0 ? "arrow-up" : "arrow-down") : ""}</button></th>`).join("")}
    </tr></thead>
    <tbody>${list.map((p) => {
      const n = nameParts(p);
      return `<tr data-person-card="${p.id}" tabindex="0"${p.followed ? ' class="is-followed"' : ""}>
        <td class="pt-photo">${avatarHTML(p, "avatar-row")}</td>
        <td class="pt-given">${esc(n.given)}</td>
        <td class="pt-family"><span class="pt-fam">${esc(n.family)}</span>${p.followed ? `<span class="pt-following" title="You follow them">${icon("radar")}</span>` : ""}
          ${p.affiliation ? `<span class="pt-aff-under">${esc(p.affiliation)}</span>` : ""}</td>
        <td class="pt-affiliation">${esc(p.affiliation || "")}</td>
        <td class="pt-h_index num">${p.h_index ?? ""}</td>
      </tr>`;
    }).join("")}</tbody></table></div>`;
}

function workMatches(w, q) {
  const text = `${w.title} ${w.venue || ""} ${(w.authors || []).map((a) => `${a.given} ${a.family}`).join(" ")}`.toLowerCase();
  return q.toLowerCase().split(/\s+/).every((t) => text.includes(t));
}

const shortDate = (d) => {
  if (!d) return "";
  const p = d.split("-");
  if (p.length === 1) return p[0];
  const dt = new Date(Date.UTC(+p[0], +p[1] - 1, +(p[2] || 1)));
  return dt.toLocaleDateString("en-GB", { ...(p[2] ? { day: "numeric" } : {}), month: "short", year: "numeric", timeZone: "UTC" });
};
const ago = (iso) => {
  if (!iso) return "never";
  const h = (Date.now() - new Date(iso)) / 3600e3;
  return h < 1 ? "less than an hour ago" : h < 48 ? `${Math.round(h)} hours ago` : `${Math.round(h / 24)} days ago`;
};

function workRow(w, radar) {
  const link = w.doi ? `https://doi.org/${w.doi}` : w.url;
  const meta = [authorsShort(w.authors), w.venue, shortDate(w.pub_date)].filter(Boolean).join(" · ");
  const who = radar ? `<div class="w-people">${w.people.map((n) => `<span class="w-person">${icon("person")}${esc(n)}</span>`).join("")}</div>` : "";
  const fresh = radar && !w.seen_at ? `<span class="w-new" title="New since you last looked">New</span>` : "";
  return `<div class="work-row" data-work="${w.id}">
    <div class="w-text">
      <div class="w-title">${fresh}${link ? `<a href="${esc(link)}" target="_blank" rel="noopener">${esc(w.title)}</a>` : esc(w.title)}</div>
      <div class="w-meta">${esc(meta) || '<span class="muted">No details</span>'}${w.doi ? ` · <span class="w-doi">${esc(w.doi)}</span>` : ""}</div>
      ${who}
    </div>
    <div class="w-actions">
      ${w.in_library
        ? `<button type="button" class="w-in" data-act="open" data-item="${w.item_id}" title="Show it in your library">${icon("check")} In library</button>`
        : `<button type="button" class="w-add" data-act="add">${icon("plus")} Add</button>`}
      ${radar ? `<button type="button" class="w-dismiss" data-act="dismiss" aria-label="Remove from the radar" title="Remove from the radar">${icon("x")}</button>` : ""}
    </div>
  </div>`;
}

function renderWorks() {
  const v = state.view, radar = v.type === "radar", p = worksState.person;
  const works = state.q ? worksState.works.filter((w) => workMatches(w, state.q)) : worksState.works;
  document.body.classList.add("works-view");
  $(".table-wrap").classList.add("with-works");
  $("#cards").innerHTML = "";
  $("#empty").classList.add("hidden");
  $("#view-title").textContent = viewTitle();
  $("#count").textContent = `${works.length} publication${works.length === 1 ? "" : "s"}`;
  $("#m-title").textContent = sectionTitle();
  $("#m-count").textContent = String(works.length);
  renderSidebar();

  let head;
  if (radar) {
    const nobody = !(state.people || []).length;
    head = `<div class="works-head">
      <div><h2>${icon("radar")} New publications</h2>
        <p class="muted">${nobody ? "Follow scientists by their ORCID iD and their new publications will appear here."
          : `From the ${state.people.length} ${state.people.length === 1 ? "person" : "people"} you follow, published in the last two months. Bubo looks every few hours.`}</p></div>
      <div class="works-buttons">${nobody
        ? `<button type="button" class="primary" data-act="follow">${icon("person-plus")} Follow someone</button>`
        : `<button type="button" data-act="check">${icon("refresh")} Check now</button>`}</div>
    </div>`;
  } else {
    head = personHero(p);
  }
  const empty = radar
    ? ((state.people || []).length ? `<p class="works-empty muted">Nothing new for now.</p>` : "")
    : `<p class="works-empty muted">${state.q ? "No publications match your search." : p.followed ? "No publications found on ORCID or OpenAlex." : "None of their papers is in your library."}</p>`;
  $("#works").innerHTML = head + (works.length ? `<div class="works-list">${works.map((w) => workRow(w, radar)).join("")}</div>` : empty);
}

// The top of a person's page: photo, position, figures, topics and links.
function personHero(p) {
  const where = [p.role, p.affiliation, countryName(p.country)].filter(Boolean).join(" · ");
  const stats = [
    p.followed && [p.works, p.works === 1 ? "publication" : "publications"],
    [p.followed ? p.in_library : p.papers, p.followed ? "in your library" : (p.papers === 1 ? "paper in your library" : "papers in your library")],
    p.cited_by != null && [bigNumber(p.cited_by), "citations"],
    p.h_index != null && [p.h_index, "h-index"],
  ].filter(Boolean);
  const links = [
    p.orcid ? `<a href="https://orcid.org/${esc(p.orcid)}" target="_blank" rel="noopener">ORCID ${esc(p.orcid)}</a>`
      : `<span>No ORCID iD found</span>`,
    p.openalex_id && `<a href="https://openalex.org/authors/${esc(p.openalex_id)}" target="_blank" rel="noopener">OpenAlex</a>`,
    p.wikipedia && `<a href="https://en.wikipedia.org/wiki/${encodeURIComponent(p.wikipedia.replace(/ /g, "_"))}" target="_blank" rel="noopener">Wikipedia</a>`,
    p.wikidata_id && `<a href="https://www.wikidata.org/wiki/${esc(p.wikidata_id)}" target="_blank" rel="noopener">Wikidata</a>`,
  ].filter(Boolean).join(" · ");
  return `<div class="person-hero">
    <div class="ph-photo">
      ${avatarHTML(p, "avatar-hero")}
      <button type="button" class="ph-photo-btn" data-act="photo" aria-label="${p.photo_url ? "Change the photo" : "Add a photo"}"
        title="${p.photo_url ? "Change the photo" : "Add a photo"}">${icon("camera")}</button>
    </div>
    <div class="ph-text">
      <h2>${esc(p.name)}</h2>
      ${p.description ? `<p class="ph-desc">${esc(p.description)}</p>` : ""}
      ${where ? `<p class="ph-where">${esc(where)}</p>` : ""}
      <div class="ph-stats">${stats.map(([n, l]) => `<span><b>${n}</b> ${l}</span>`).join("")}</div>
      ${p.topics?.length ? `<div class="ph-topics">${p.topics.map((t) => `<span>${esc(t)}</span>`).join("")}</div>` : ""}
      <p class="ph-links muted">${links}${p.followed ? ` · checked ${ago(p.last_checked)}` : ""}${p.last_error ? ` · <span class="error">${esc(p.last_error)}</span>` : ""}
        ${p.photo_source === "wikidata" && p.photo_credit ? ` · <a href="${esc(p.photo_credit)}" target="_blank" rel="noopener">Photo: Wikimedia Commons</a>` : ""}
        ${p.photo_url ? ` · <button type="button" class="link-btn" data-act="remove-photo">Remove photo</button>` : ""}
        · <button type="button" class="link-btn" data-act="merge" title="The same person, with their name spelt differently on some papers">Merge with…</button></p>
      <div class="works-buttons">${p.followed
        ? `<button type="button" data-act="check">${icon("refresh")} Check now</button>
           <button type="button" data-act="unfollow">Unfollow</button>`
        : `<button type="button" class="primary" data-act="follow-person">${icon("person-plus")} Follow</button>
           <span class="muted ph-follow-note">${p.orcid ? "Their new publications will appear on your radar." : "Needs their ORCID iD."}</span>`}
      </div>
    </div>
  </div>`;
}

// Everyone in the library, as a wall of portraits: those you follow first.
function renderPeoplePage() {
  const all = peopleState.all;
  const following = all.filter((p) => p.followed);
  const pool = peopleState.filter === "following" ? following : all;
  const q = (state.q || "").toLowerCase();
  const list = sortedPeople(q ? pool.filter((p) => `${p.name} ${p.affiliation || ""} ${(p.topics || []).join(" ")}`.toLowerCase().includes(q)) : pool);
  document.body.classList.add("works-view");
  $(".table-wrap").classList.add("with-works");
  $("#cards").innerHTML = "";
  $("#empty").classList.add("hidden");
  $("#view-title").textContent = viewTitle();
  $("#count").textContent = `${list.length} ${list.length === 1 ? "person" : "people"}`;
  $("#m-title").textContent = sectionTitle();
  $("#m-count").textContent = String(list.length);
  renderSidebar();
  const shown = list.slice(0, peopleState.shown);
  const tab = (key, label, n) => `<button type="button" role="tab" data-act="people-filter" data-filter="${key}"
      aria-selected="${peopleState.filter === key}" class="${peopleState.filter === key ? "active" : ""}">${label} <span>${n}</span></button>`;
  $("#works").innerHTML = `<div class="works-head">
      <div><h2>${icon("people")} People</h2>
        <p class="muted">${all.length ? "Everyone who wrote the papers in your library. Follow someone to see their new publications on your radar."
          : "The authors of your papers appear here as you add them."}</p></div>
      <div class="works-buttons"><button type="button" data-act="follow">${icon("person-plus")} Follow by ORCID iD</button></div>
    </div>
    <div class="people-bar"><div class="people-tabs" role="tablist" aria-label="Who to show">${tab("all", "All", all.length)}${tab("following", "Following", following.length)}</div>
      <div class="people-view" role="group" aria-label="Layout">
        <button type="button" class="icon-btn${peopleState.view === "grid" ? " active" : ""}" data-act="people-view" data-view="grid" aria-pressed="${peopleState.view === "grid"}" data-tip="Portraits" aria-label="Portraits">${icon("grid")}</button>
        <button type="button" class="icon-btn${peopleState.view === "table" ? " active" : ""}" data-act="people-view" data-view="table" aria-pressed="${peopleState.view === "table"}" data-tip="Table" aria-label="Table">${icon("rows-1")}</button>
      </div></div>
    ${shown.length && peopleState.view === "table" ? peopleTableHTML(shown) : shown.length ? `<div class="people-grid">${shown.map((p) => `
      <a class="person-card${p.followed ? " is-followed" : ""}" href="#" data-person-card="${p.id}">
        <span class="pc-photo">${avatarHTML(p, "avatar-card")}${p.unseen ? `<span class="badge badge-tl pc-new">${p.unseen} new</span>`
          : p.followed ? `<span class="badge badge-tl pc-following" title="You follow them">${icon("radar")}</span>` : ""}</span>
        <span class="pc-name">${esc(p.name)}</span>
        <span class="pc-where">${esc(p.affiliation || "")}</span>
        <span class="pc-meta">${p.followed ? `${p.works} publication${p.works === 1 ? "" : "s"} · ${p.papers} in your library`
          : `${p.papers} paper${p.papers === 1 ? "" : "s"} in your library`}</span>
      </a>`).join("")}</div>
      ${list.length > shown.length ? `<div class="people-more"><button type="button" data-act="people-more">Show more (${list.length - shown.length} left)</button></div>` : ""}`
      : `<p class="works-empty muted">${q ? "Nobody matches your search." : peopleState.filter === "following" ? "You do not follow anyone yet. Open a paper and choose authors to follow, or follow someone by their ORCID iD." : ""}</p>`}`;
}

// Leaving the works views: app.js renders the papers again.
function leaveWorksView() {
  document.body.classList.remove("works-view");
  $(".table-wrap").classList.remove("with-works");
  $("#works").innerHTML = "";
}

$("#works").addEventListener("click", async (e) => {
  const card = e.target.closest("[data-person-card]");
  if (card) {
    e.preventDefault();
    const p = peopleState.all.find((x) => x.id === Number(card.dataset.personCard));
    return p && setView({ type: "person", id: p.id, name: p.name });
  }
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const act = el.dataset.act;
  const row = el.closest("[data-work]");
  const w = row && worksState.works.find((x) => x.id === Number(row.dataset.work));
  try {
    if (act === "add") {
      el.disabled = true;
      el.innerHTML = "Adding…";
      const r = await api(`/api/works/${w.id}/add`, { json: { to_read: !!state.settings.new_items_to_read } });
      Object.assign(w, { in_library: true, item_id: r.item.id, seen_at: w.seen_at || "now" });
      toast(r.status === "duplicate" ? "Already in your library" : r.item.has_file ? "Added with its PDF" : "Added to your library");
      renderWorks();
      loadSidebar();
    } else if (act === "open") {
      showItem(Number(el.dataset.item));
    } else if (act === "dismiss") {
      const r = await api(`/api/radar/${w.id}/dismiss`, { method: "POST" });
      state.radarUnseen = r.unseen;
      worksState.works = worksState.works.filter((x) => x.work_key !== w.work_key);
      renderWorks();
    } else if (act === "check") {
      el.disabled = true;
      el.innerHTML = "Checking…";
      const r = state.view.type === "radar"
        ? await api("/api/radar/refresh", { method: "POST" })
        : await api(`/api/people/${state.view.id}/refresh`, { method: "POST" });
      toast(r.new ? `${r.new} new publication${r.new > 1 ? "s" : ""}` : "Nothing new");
      await loadSidebar();
      loadWorks();
    } else if (act === "unfollow") {
      const p = worksState.person;
      if (!confirm(`Stop following ${p.name}? Their publications leave your radar; papers you added stay in your library.`)) return;
      await api(`/api/people/${p.id}`, { method: "DELETE" });
      toast(`No longer following ${p.name}`);
      await loadSidebar();
      loadWorks();
    } else if (act === "follow") {
      openFollowDialog();
    } else if (act === "people-filter") {
      peopleState.filter = el.dataset.filter;
      peopleState.shown = 120;
      renderPeoplePage();
    } else if (act === "people-view") {
      peopleState.view = el.dataset.view;
      try { localStorage.setItem("peopleView", peopleState.view); } catch {}
      renderPeoplePage();
    } else if (act === "people-sort") {
      const key = el.dataset.key, s = peopleState.sort;
      // h-index starts highest first; text columns A to Z.
      peopleState.sort = s.key === key ? { key, dir: -s.dir } : { key, dir: key === "h_index" ? -1 : 1 };
      renderPeoplePage();
    } else if (act === "people-more") {
      peopleState.shown += 240;
      renderPeoplePage();
    } else if (act === "follow-person") {
      const p = worksState.person;
      if (!p.orcid) return openFollowDialog(p);
      el.disabled = true;
      el.innerHTML = "Looking up their publications…";
      const r = await api(`/api/people/${p.id}/follow`, { json: {} });
      toast(`Following ${r.name}: ${r.works} publication${r.works === 1 ? "" : "s"}`);
      await loadSidebar();
      loadWorks();
    } else if (act === "photo") {
      choosePhoto(worksState.person);
    } else if (act === "merge") {
      openMergeDialog(worksState.person);
    } else if (act === "remove-photo") {
      const p = worksState.person;
      if (!confirm(`Remove ${p.name}'s photo? Bubo will not look for one on Wikidata again; you can still add one yourself.`)) return;
      await api(`/api/people/${p.id}/photo`, { method: "DELETE" });
      toast("Photo removed");
      await loadSidebar();
      loadWorks();
    }
  } catch (err) {
    toast(err.message, true);
    if (["add", "check", "follow-person"].includes(act)) renderWorks();
  }
});

// Choose a photo for a person: any image, cropped to a portrait.
function choosePhoto(p) {
  const input = $("#person-photo-input");
  input.onchange = async () => {
    const file = input.files[0];
    input.value = "";
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api(`/api/people/${p.id}/photo`, { method: "POST", body: fd });
      toast("Photo updated");
      await loadSidebar();
      loadWorks();
    } catch (err) { toast(err.message, true); }
  };
  input.click();
}

// --------------------------------------------------------------------------
// Choosing which authors of a paper to follow
// --------------------------------------------------------------------------
function openFollowAuthors(item, matches, done) {
  const dlg = $("#follow-dialog");
  const rows = item.authors.map((a, n) => ({ a, m: matches[n], name: [a.given, a.family].filter(Boolean).join(" ") }))
    .filter((r) => r.m);
  dlg.innerHTML = `<form id="fa-form">
    <h3 id="follow-title">Follow authors</h3>
    <p class="muted">Their new publications will appear on your radar. Following needs an ORCID iD: Bubo looks for
      everyone's, and you can paste one it did not find.</p>
    <div class="fa-list">${rows.map(({ m, name }, n) => `
      <label class="fa-row">
        <input type="checkbox" data-n="${n}" ${m.followed ? "checked" : ""}>
        ${avatarHTML({ name: m.name, photo_url: m.photo_url }, "avatar-xs")}
        <span class="fa-name">${esc(name)}</span>
        ${m.orcid ? `<span class="fa-orcid muted">${esc(m.orcid)}</span>`
          : `<span class="fa-orcid"><input type="text" data-orcid="${n}" placeholder="ORCID iD" aria-label="ORCID iD of ${esc(name)}"
              autocomplete="off"><a href="${esc(orcidSearchLink(name))}" target="_blank" rel="noopener" title="Look for it on orcid.org">Find</a></span>`}
      </label>`).join("")}</div>
    <p class="error" id="fa-error" role="alert"></p>
    <div class="dialog-buttons">
      <button type="button" data-close>Cancel</button>
      <button type="submit" class="primary" id="fa-submit">Save</button>
    </div></form>`;
  dlg.querySelector("[data-close]").addEventListener("click", () => dlg.close());
  // Typing an iD ticks the box.
  dlg.querySelectorAll("[data-orcid]").forEach((inp) => inp.addEventListener("input", () => {
    dlg.querySelector(`input[type=checkbox][data-n="${inp.dataset.orcid}"]`).checked = !!inp.value.trim();
  }));
  $("#fa-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#fa-submit"), err = $("#fa-error");
    const jobs = rows.map((r, n) => ({ ...r, on: dlg.querySelector(`input[type=checkbox][data-n="${n}"]`).checked,
      orcid: dlg.querySelector(`[data-orcid="${n}"]`)?.value.trim() || null }))
      .filter((j) => j.on !== j.m.followed);
    const missing = jobs.find((j) => j.on && !j.m.orcid && !j.orcid);
    if (missing) { err.textContent = `Paste ${missing.name}'s ORCID iD to follow them.`; return; }
    if (!jobs.length) return dlg.close();
    btn.disabled = true;
    err.textContent = "";
    const failed = [];
    for (const [k, j] of jobs.entries()) {
      btn.textContent = j.on ? `Following ${k + 1} of ${jobs.length}…` : `Saving ${k + 1} of ${jobs.length}…`;
      try {
        if (j.on) await api(`/api/people/${j.m.id}/follow`, { json: { orcid: j.orcid } });
        else await api(`/api/people/${j.m.id}`, { method: "DELETE" });
      } catch (x) { failed.push(`${j.name}: ${x.message}`); }
    }
    if (failed.length) {
      err.textContent = failed.join(" · ");
      btn.disabled = false;
      btn.textContent = "Save";
    } else {
      dlg.close();
      const n = jobs.filter((j) => j.on).length;
      toast(n ? `Following ${n} more ${n === 1 ? "person" : "people"}` : "Saved");
    }
    done?.();
  });
  dlg.showModal();
}

// --------------------------------------------------------------------------
// Merging two people (a name misspelt on some papers)
// --------------------------------------------------------------------------
async function openMergeDialog(p) {
  const dlg = $("#follow-dialog");
  let similar = [], everyone = peopleState.all;
  try {
    [similar, everyone] = await Promise.all([
      api(`/api/people/${p.id}/similar`).then((r) => r.people),
      everyone.length ? everyone : api("/api/people?scope=all").then((r) => r.people)]);
  } catch (err) { return toast(err.message, true); }
  peopleState.all = everyone;
  const row = (o) => `<button type="button" class="mg-row" data-id="${o.id}">
      ${avatarHTML(o, "avatar-xs")}<span class="mg-name">${esc(o.name)}</span>
      <span class="mg-meta muted">${o.papers} paper${o.papers === 1 ? "" : "s"}${o.orcid ? ` · ${esc(o.orcid)}` : ""}</span></button>`;

  function chooseStep() {
    dlg.innerHTML = `<div class="mg">
      <h3 id="follow-title">Merge with ${esc(p.name)}</h3>
      <p class="muted">For someone whose name is spelt differently on some papers. Their papers become ${esc(p.name)}'s,
        and Bubo remembers the other spelling for papers you add later. The papers' author lists stay as printed.</p>
      ${similar.length ? `<h4>Possibly the same person</h4><div class="mg-list">${similar.map(row).join("")}</div>` : ""}
      <h4>Anyone else</h4>
      <input type="search" id="mg-search" placeholder="Search people by name" autocomplete="off" aria-label="Search people by name">
      <div class="mg-list" id="mg-results"></div>
      <div class="dialog-buttons"><button type="button" data-close>Cancel</button></div></div>`;
    const results = $("#mg-results");
    const search = () => {
      const q = $("#mg-search").value.trim().toLowerCase();
      results.innerHTML = q ? everyone.filter((o) => o.id !== p.id && o.name.toLowerCase().includes(q)).slice(0, 30).map(row).join("")
        || `<p class="muted mg-none">Nobody by that name.</p>` : "";
    };
    $("#mg-search").addEventListener("input", search);
    dlg.querySelector("[data-close]").addEventListener("click", () => dlg.close());
    dlg.querySelectorAll(".mg-list").forEach((l) => l.addEventListener("click", (e) => {
      const b = e.target.closest(".mg-row");
      const o = b && everyone.find((x) => x.id === Number(b.dataset.id));
      if (o) confirmStep(o);
    }));
    if (!similar.length) $("#mg-search").focus();
  }

  function confirmStep(o) {
    const names = [...new Set([p.name, o.name])];
    dlg.innerHTML = `<form class="mg" id="mg-form">
      <h3 id="follow-title">Merge ${esc(o.name)} into ${esc(p.name)}</h3>
      <p class="muted">${p.papers + o.papers} papers in your library will be by one person${o.followed && !p.followed ? ", whom you follow" : ""}.</p>
      <fieldset class="mg-names"><legend>The name to keep</legend>
        ${names.map((n, k) => `<label><input type="radio" name="mg-name" value="${esc(n)}" ${k === 0 ? "checked" : ""}> ${esc(n)}</label>`).join("")}
        <label><input type="radio" name="mg-name" value="" id="mg-own"> Another: <input type="text" id="mg-own-name" value="${esc(p.name)}" aria-label="Another name"></label>
      </fieldset>
      <p class="error" id="mg-error" role="alert"></p>
      <div class="dialog-buttons">
        <button type="button" data-back>Back</button>
        <button type="submit" class="primary" id="mg-submit">Merge</button>
      </div></form>`;
    $("#mg-own-name").addEventListener("focus", () => { $("#mg-own").checked = true; });
    dlg.querySelector("[data-back]").addEventListener("click", chooseStep);
    $("#mg-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const picked = dlg.querySelector("input[name=mg-name]:checked").value || $("#mg-own-name").value.trim();
      if (!picked) { $("#mg-error").textContent = "Write the name to keep."; return; }
      $("#mg-submit").disabled = true;
      try {
        const r = await api(`/api/people/${p.id}/merge`, { json: { other_id: o.id, name: picked } });
        dlg.close();
        toast(`Merged: ${r.papers} paper${r.papers === 1 ? "" : "s"} by ${r.name}`);
        peopleState.all = [];
        await loadSidebar();
        setView({ type: "person", id: r.id, name: r.name });
      } catch (err) {
        $("#mg-error").textContent = err.message;
        $("#mg-submit").disabled = false;
      }
    });
  }

  chooseStep();
  dlg.showModal();
}

$("#works").addEventListener("keydown", (e) => {
  const row = e.target.closest("tr[data-person-card]");
  if (row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); row.click(); }
});
