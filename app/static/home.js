// The home page: the library at a glance, in the whole window but the sidebar (main.py /api/home).
// Loaded after app.js, people.js and journals.js, and uses their helpers.

const homeState = { token: 0, data: null };

async function loadHome() {
  const token = ++homeState.token;
  let ov;
  try { ov = await api("/api/home"); } catch (err) { return toast(err.message, true); }
  if (token !== homeState.token || state.view.type !== "home") return;
  homeState.data = ov;
  state.items = [];
  renderHome();
}

function renderHome() {
  const ov = homeState.data;
  if (!ov) return;
  const c = ov.counts;
  document.body.classList.add("works-view", "home-view");
  $(".table-wrap").classList.add("with-works");
  $("#cards").innerHTML = "";
  $("#empty").classList.add("hidden");
  renderJournalHero();
  $("#view-title").textContent = "Home";
  $("#count").textContent = "";
  $("#m-title").textContent = "Home";
  $("#m-count").textContent = "";
  renderSidebar();

  const plural = (n, one, many = one + "s") => (n === 1 ? one : many);
  const stat = (n, label, view, extra = "") => `<button type="button" class="hm-stat${extra}"${view ? ` data-view="${view}"` : " disabled"}>
      <span class="hm-n">${n}</span><span class="hm-label">${label}</span></button>`;
  const card = (i) => `<a class="card" href="/paper/${i.id}" data-id="${i.id}">
      <div class="thumb">${thumbHTML(i)}</div>
      <div class="c-title">${esc(i.title) || "(untitled)"}</div>
      <div class="c-meta">${esc([authorsShort(i.authors), i.year].filter(Boolean).join(" · ") || "No details yet")}</div></a>`;
  const strip = (items, empty) => items.length
    ? `<div class="pv-strip hm-strip">${items.map(card).join("")}</div>` : `<p class="ov-empty">${empty}</p>`;
  const all = (view, label) => `<button type="button" class="pv-link hm-all" data-view="${view}">${label}</button>`;
  const section = (title, body, link = "", cls = "") => `<section class="hm-section ${cls}"><h2><span>${title}</span>${link}</h2>${body}</section>`;

  const radar = ov.radar.length ? `<div class="hm-radar">${ov.radar.map((w) => `
      <button type="button" class="hm-work" data-view="radar">
        ${w.seen_at ? "" : `<span class="w-new">New</span>`}<span class="hm-work-title">${esc(w.title)}</span>
        <span class="hm-work-meta">${esc([w.people.join(", "), w.venue, shortDate(w.pub_date)].filter(Boolean).join(" · "))}</span>
      </button>`).join("")}</div>`
    : `<p class="ov-empty">${c.following ? "Nothing new from the people you follow for now." : "Follow scientists and their new publications will appear here."}</p>`;

  const incomplete = ov.incomplete.length ? `<div class="pv-details ov-list">${ov.incomplete.map((i) => {
      const known = i.doi || i.arxiv_id;
      return `<div class="ov-row-wrap">
        <button type="button" class="ov-row" data-id="${i.id}">
          <span class="thumb thumb-sm">${thumbHTML(i)}</span>
          <span class="ov-row-text"><span class="ov-row-title">${esc(i.title) || "(untitled)"}</span>
            <span class="ov-missing">Missing: ${esc(i.missing.join(", "))}</span></span>
        </button>
        <button type="button" class="ov-find" data-find="${i.id}" title="${known ? "Refresh metadata" : "Find metadata online"}">
          ${icon("refresh")}<span>${known ? "Refresh" : "Find"}</span></button>
      </div>`; }).join("")}</div>`
    : `<p class="ov-empty">Every paper has its basic details. Well done.</p>`;

  const shelf = ov.journals.length ? `<div class="hm-journals">${ov.journals.map((j) => `
      <a class="journal-card" href="#" data-journal-home="${esc(j.name)}">${journalCoverHTML(j)}
        <span class="jcard-name">${esc(j.name)}</span>
        <span class="jcard-meta">${j.papers} ${plural(j.papers, "paper")}</span></a>`).join("")}</div>`
    : `<p class="ov-empty">Journals appear here as you add papers.</p>`;

  const people = ov.following.length ? `<div class="hm-people">${ov.following.map((p) => `
      <a class="hm-person" href="#" data-person-home="${p.id}" data-name="${esc(p.name)}">
        ${avatarHTML(p, "avatar-home")}<span class="hm-person-name">${esc(p.name)}</span>
        ${p.unseen ? `<span class="hm-person-new">${p.unseen} new</span>` : ""}</a>`).join("")}</div>`
    : `<p class="ov-empty">Open a paper and choose <b>Follow authors</b>, or follow someone by their ORCID iD from People.</p>`;

  $("#works").innerHTML = `<div class="home">
    <header class="hm-head">
      <img src="/static/owl.svg" alt="" class="hm-owl" width="44" height="44">
      <div><h1>Your library</h1>
        <p class="muted">${c.papers ? `${c.papers} ${plural(c.papers, "paper")} from ${c.journals} ${plural(c.journals, "journal")} and ${c.people} ${plural(c.people, "author")}.`
          : "Press Add to bring in your first paper, or drop PDFs anywhere on the window."}</p></div>
    </header>
    <div class="hm-stats">
      ${stat(c.papers, plural(c.papers, "paper"), "all")}
      ${stat(c.to_read, "to read", "toread")}
      ${stat(c.radar_unseen || c.radar, c.radar_unseen ? "new on the radar" : "on the radar", "radar", c.radar_unseen ? " hm-hot" : "")}
      ${stat(c.journals, plural(c.journals, "journal"), "journals")}
      ${stat(c.people, plural(c.people, "person", "people"), "people")}
      ${stat(c.with_pdf, "with a PDF")}
    </div>
    <div class="hm-grid">
      ${section("Recently added", strip(ov.recent, "Nothing yet: press Add to bring in your first paper."), all("all", "My library"), "hm-wide")}
      ${section("On your reading list", strip(ov.to_read, "Your reading list is empty. Add papers with the bookmark on their sheet."),
        c.to_read > ov.to_read.length ? all("toread", `All ${c.to_read}`) : "", "hm-wide")}
      ${section("New on your radar", radar, c.radar ? all("radar", "Radar") : "")}
      ${section(`Incomplete metadata${ov.incomplete_total ? ` <span class="ov-count">${ov.incomplete_total}</span>` : ""}`, incomplete)}
      ${section("Your journals", shelf, c.journals > ov.journals.length ? all("journals", `All ${c.journals}`) : "", "hm-wide")}
      ${section("People you follow", people, all("people", "People"), "hm-wide")}
    </div>
  </div>`;
}

$("#works").addEventListener("click", (e) => {
  if (state.view.type !== "home") return;
  const find = e.target.closest("[data-find]");
  if (find) {
    const item = homeState.data?.incomplete.find((i) => i.id === Number(find.dataset.find));
    return item && itemAction("refresh", item);
  }
  const paper = e.target.closest("[data-id]");
  if (paper) {
    e.preventDefault();
    const id = Number(paper.dataset.id);
    return narrow.matches ? openPaper(id) : (setView({ type: "all" }), showItem(id));
  }
  const journal = e.target.closest("[data-journal-home]");
  if (journal) { e.preventDefault(); return setView({ type: "journal", name: journal.dataset.journalHome }); }
  const person = e.target.closest("[data-person-home]");
  if (person) {
    e.preventDefault();
    return setView({ type: "person", id: Number(person.dataset.personHome), name: person.dataset.name });
  }
  const view = e.target.closest("[data-view]")?.dataset.view;
  if (view) setView({ type: view });
});

// The owl in the header leads home.
$(".brand").addEventListener("click", () => setView({ type: "home" }));
