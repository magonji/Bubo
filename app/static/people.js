// People followed by their ORCID iD, and the radar of their new publications (people.py).
// Loaded after app.js and uses its helpers ($, api, state, icon, esc, toast, setView…).

Object.assign(ICONS, {
  radar: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12l5.5-5.5"/><circle cx="12" cy="12" r="1"/>',
  person: '<circle cx="12" cy="8" r="3.6"/><path d="M5 20c.8-3.6 3.6-5.6 7-5.6s6.2 2 7 5.6"/>',
  "person-plus": '<circle cx="10" cy="8" r="3.6"/><path d="M3 20c.8-3.6 3.6-5.6 7-5.6 2 0 3.7.7 5 1.9M18 11v6M15 14h6"/>',
  "external-link": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  people: '<circle cx="9" cy="8" r="3.2"/><path d="M3 19c.6-3.2 3-5 6-5s5.4 1.8 6 5"/><circle cx="17" cy="9" r="2.6"/><path d="M15.5 14.2c2.6-.4 4.8 1.1 5.5 4.3"/>',
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
  list.innerHTML = people.length ? `
    <div class="side-item${state.view.type === "people" ? " active" : ""}" data-people title="Everyone you follow">
      ${icon("people")}<span class="name">Everyone</span><span class="count">${people.length}</span></div>` +
    people.map((p) => `
    <div class="side-item person-item${state.view.type === "person" && state.view.id === p.id ? " active" : ""}" data-person="${p.id}" title="ORCID ${esc(p.orcid)}">
      ${avatarHTML(p, "avatar-xs")}<span class="name">${esc(p.name)}</span>
      <span class="count${p.unseen ? " new" : ""}">${p.unseen || ""}</span>
    </div>`).join("")
    : `<div class="side-empty muted">Follow scientists by their ORCID iD to see their publications.</div>`;
}

$("#people").addEventListener("click", (e) => {
  if (e.target.closest("[data-people]")) return setView({ type: "people" });
  const el = e.target.closest("[data-person]");
  if (!el) return;
  const p = state.people.find((x) => x.id === Number(el.dataset.person));
  if (p) setView({ type: "person", id: p.id, name: p.name });
});
$("#add-person").addEventListener("click", (e) => { e.stopPropagation(); openFollowDialog(); });

// --------------------------------------------------------------------------
// Following someone
// --------------------------------------------------------------------------
function openFollowDialog() {
  const dlg = $("#follow-dialog");
  dlg.innerHTML = `<form id="follow-form">
    <h3 id="follow-title">Follow a scientist</h3>
    <p class="muted">Enter their ORCID iD. Bubo lists their publications and, every few hours, looks for new ones to show on your radar.</p>
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
      const p = await api("/api/people", { json: { orcid: $("#follow-orcid").value } });
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
      const r = await api("/api/people");
      if (token !== worksState.token) return;
      state.people = r.people;
      state.radarUnseen = r.radar_unseen;
      state.items = [];
      return renderPeoplePage();
    }
    if (v.type === "person") {
      person = await api(`/api/people/${v.id}`);
      works = person.works_list;
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
    : `<p class="works-empty muted">${state.q ? "No publications match your search." : "No publications found on ORCID or OpenAlex."}</p>`;
  $("#works").innerHTML = head + (works.length ? `<div class="works-list">${works.map((w) => workRow(w, radar)).join("")}</div>` : empty);
}

// The top of a person's page: photo, position, figures, topics and links.
function personHero(p) {
  const where = [p.role, p.affiliation, countryName(p.country)].filter(Boolean).join(" · ");
  const stats = [
    [p.works, p.works === 1 ? "publication" : "publications"],
    [p.in_library, "in your library"],
    p.cited_by != null && [bigNumber(p.cited_by), "citations"],
    p.h_index != null && [p.h_index, "h-index"],
  ].filter(Boolean);
  const links = [
    `<a href="https://orcid.org/${esc(p.orcid)}" target="_blank" rel="noopener">ORCID</a>`,
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
      <p class="ph-links muted">${links} · checked ${ago(p.last_checked)}${p.last_error ? ` · <span class="error">${esc(p.last_error)}</span>` : ""}
        ${p.photo_source === "wikidata" && p.photo_credit ? ` · <a href="${esc(p.photo_credit)}" target="_blank" rel="noopener">Photo: Wikimedia Commons</a>` : ""}
        ${p.photo_url ? ` · <button type="button" class="link-btn" data-act="remove-photo">Remove photo</button>` : ""}</p>
      <div class="works-buttons">
        <button type="button" data-act="check">${icon("refresh")} Check now</button>
        <button type="button" data-act="unfollow">Unfollow</button>
      </div>
    </div>
  </div>`;
}

// Everyone followed, as a wall of portraits.
function renderPeoplePage() {
  const all = state.people || [];
  const q = (state.q || "").toLowerCase();
  const people = q ? all.filter((p) => `${p.name} ${p.affiliation || ""} ${(p.topics || []).join(" ")}`.toLowerCase().includes(q)) : all;
  document.body.classList.add("works-view");
  $(".table-wrap").classList.add("with-works");
  $("#cards").innerHTML = "";
  $("#empty").classList.add("hidden");
  $("#view-title").textContent = viewTitle();
  $("#count").textContent = `${people.length} ${people.length === 1 ? "person" : "people"}`;
  $("#m-title").textContent = sectionTitle();
  $("#m-count").textContent = String(people.length);
  renderSidebar();
  $("#works").innerHTML = `<div class="works-head">
      <div><h2>${icon("people")} People</h2>
        <p class="muted">${all.length ? "The scientists you follow. Their new publications appear on your radar." : "Follow scientists by their ORCID iD to keep up with what they publish."}</p></div>
      <div class="works-buttons"><button type="button" class="primary" data-act="follow">${icon("person-plus")} Follow someone</button></div>
    </div>
    ${people.length ? `<div class="people-grid">${people.map((p) => `
      <a class="person-card" href="#" data-person-card="${p.id}">
        <span class="pc-photo">${avatarHTML(p, "avatar-card")}${p.unseen ? `<span class="badge badge-tl pc-new">${p.unseen} new</span>` : ""}</span>
        <span class="pc-name">${esc(p.name)}</span>
        <span class="pc-where">${esc(p.affiliation || "")}</span>
        <span class="pc-meta">${p.works} publication${p.works === 1 ? "" : "s"}${p.in_library ? ` · ${p.in_library} in your library` : ""}</span>
      </a>`).join("")}</div>`
      : all.length ? `<p class="works-empty muted">Nobody matches your search.</p>` : ""}`;
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
    const p = state.people.find((x) => x.id === Number(card.dataset.personCard));
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
      setView({ type: "radar" });
    } else if (act === "follow") {
      openFollowDialog();
    } else if (act === "photo") {
      choosePhoto(worksState.person);
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
    if (act === "add" || act === "check") renderWorks();
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
