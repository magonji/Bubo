// The journals in the library: a gallery of covers, and each journal's page (journals.py).
// Loaded after app.js and people.js and uses their helpers ($, api, state, icon, esc, setView…).

const journalsState = { list: [], token: 0, profileToken: 0 };

const yearsText = (j) => (j.first_year && j.last_year
  ? (j.first_year === j.last_year ? String(j.first_year) : `${j.first_year}–${j.last_year}`) : "");
const papersText = (n) => `${n} paper${n === 1 ? "" : "s"}`;

// A journal's cover: its name as a masthead over figures from your papers in it, or,
// without figures, the name alone on a colour taken from it.
function journalCoverHTML(j, cls = "") {
  const h = journalHue(j.name);
  // Long words get a smaller type, so that a name like "Communications" fits without breaking.
  const longest = (s) => Math.max(...(s || "").split(/\s+/).map((w) => w.length), 1);
  const figs = j.covers || [];
  const mast = `<span class="jc-mast"><span class="jc-name">${esc(j.short || j.name)}</span></span>`;
  if (!figs.length) {
    return `<span class="j-cover jc-plain ${cls}" style="--h:${h};--k:${Math.min(1, 10 / longest(j.name)).toFixed(2)}" aria-hidden="true">
      <span class="jc-name">${esc(j.name)}</span>${j.short && j.short !== j.name ? `<span class="jc-short">${esc(j.short)}</span>` : ""}</span>`;
  }
  return `<span class="j-cover ${cls}" style="--h:${h};--k:${Math.min(1, 11 / longest(j.short || j.name)).toFixed(2)}" aria-hidden="true">${mast}
    <span class="jc-figs jc-n${Math.min(figs.length, 4)}">${figs.slice(0, 4).map((f) =>
      `<span class="jc-fig${f.fill ? " jc-fill" : ""}"><img src="${esc(f.url)}" alt="" loading="lazy" decoding="async"></span>`).join("")}</span></span>`;
}

// --------------------------------------------------------------------------
// The gallery
// --------------------------------------------------------------------------
async function loadJournals() {
  const token = ++journalsState.token;
  try {
    const r = await api("/api/journals");
    if (token !== journalsState.token) return;
    journalsState.list = r.journals;
  } catch (err) {
    if (token !== journalsState.token) return;
    toast(err.message, true);
    return setView({ type: "all" });
  }
  state.items = [];
  renderJournalsPage();
}

function renderJournalsPage() {
  const all = journalsState.list;
  const q = (state.q || "").toLowerCase();
  const list = q ? all.filter((j) => `${j.name} ${j.short || ""} ${j.publisher || ""}`.toLowerCase().includes(q)) : all;
  renderJournalHero();   // hides the journal header
  document.body.classList.add("works-view");
  $(".table-wrap").classList.add("with-works");
  $("#cards").innerHTML = "";
  $("#empty").classList.add("hidden");
  $("#view-title").textContent = viewTitle();
  $("#count").textContent = `${list.length} journal${list.length === 1 ? "" : "s"}`;
  $("#m-title").textContent = sectionTitle();
  $("#m-count").textContent = String(list.length);
  $("#count-journals").textContent = all.length || "";
  renderSidebar();
  $("#works").innerHTML = `<div class="works-head">
      <div><h2>${icon("journal")} Journals</h2>
        <p class="muted">${all.length ? "Where the papers in your library were published." : "Journals appear here as you add papers."}</p></div>
    </div>
    ${list.length ? `<div class="journals-grid">${list.map((j) => `
      <a class="journal-card" href="#" data-journal="${esc(j.key)}">
        ${journalCoverHTML(j)}
        <span class="jcard-name">${esc(j.name)}</span>
        <span class="jcard-where">${esc(j.publisher || j.short || "")}</span>
        <span class="jcard-meta">${papersText(j.papers)}${yearsText(j) ? ` · ${yearsText(j)}` : ""}</span>
      </a>`).join("")}</div>`
      : all.length ? `<p class="works-empty muted">No journal matches your search.</p>` : ""}`;
}

$("#works").addEventListener("click", (e) => {
  const card = e.target.closest("[data-journal]");
  if (!card) return;
  e.preventDefault();
  const j = journalsState.list.find((x) => x.key === card.dataset.journal);
  if (j) openJournal(j.name);
});

function openJournal(name) {
  setView({ type: "journal", name });
}

// --------------------------------------------------------------------------
// A journal's page: its header above your papers in it (the usual list)
// --------------------------------------------------------------------------
function renderJournalHero() {
  const box = $("#journal-hero");
  if (state.view.type !== "journal") {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  const name = state.view.name;
  const j = journalsState.list.find((x) => x.key === name.toLowerCase().split(/\s+/).join(" "))
    || { name, short: null, publisher: null, covers: [], papers: state.items.length };
  if (box.dataset.name !== name || box.hidden) {
    box.dataset.name = name;
    box.hidden = false;
    box.innerHTML = heroHTML(j, null);
    loadJournalProfile(j);
  }
}

function heroHTML(j, p) {
  const stats = [
    [j.papers, j.papers === 1 ? "paper in your library" : "papers in your library"],
    p?.h_index != null && [p.h_index, "h-index"],
    p?.mean_citedness != null && [p.mean_citedness, "citations per article", "Mean citations in the last two years of the articles of the two years before (OpenAlex)"],
    p?.works_count != null && [bigNumber(p.works_count), "articles published"],
  ].filter(Boolean);
  const where = [p?.publisher || j.publisher, p?.country && countryName(p.country)].filter(Boolean).join(" · ");
  const links = [
    p?.homepage && `<a href="${esc(p.homepage)}" target="_blank" rel="noopener">Website</a>`,
    p?.openalex_id && `<a href="https://openalex.org/sources/${esc(p.openalex_id)}" target="_blank" rel="noopener">OpenAlex</a>`,
    p?.issn && `<a href="https://portal.issn.org/resource/ISSN/${esc(p.issn)}" target="_blank" rel="noopener">ISSN ${esc(p.issn)}</a>`,
  ].filter(Boolean);
  const chips = [
    p?.in_doaj ? "Open access (DOAJ)" : p?.is_oa ? "Open access" : null,
    yearsText(j) && `Your papers: ${yearsText(j)}`,
  ].filter(Boolean);
  return `${journalCoverHTML(j, "jc-hero")}
    <div class="jh-text">
      <p class="jh-crumb"><button type="button" class="pv-link" data-act="journals">${icon("journal")} Journals</button></p>
      <h2>${esc(j.name)}</h2>
      ${where ? `<p class="jh-where">${esc(where)}</p>` : ""}
      <div class="ph-stats">${stats.map(([n, label, tip]) => `<span${tip ? ` title="${esc(tip)}"` : ""}><b>${esc(String(n))}</b> ${esc(label)}</span>`).join("")}</div>
      ${chips.length ? `<div class="ph-topics">${chips.map((c) => `<span>${esc(c)}</span>`).join("")}</div>` : ""}
      ${links.length ? `<p class="ph-links">${links.join(" · ")}</p>` : p === null ? `<p class="ph-links muted">Looking the journal up…</p>` : ""}
    </div>`;
}

async function loadJournalProfile(j) {
  const token = ++journalsState.profileToken;
  let p = {};
  try { p = await api(`/api/journals/profile?name=${encodeURIComponent(j.name)}`); } catch {}
  if (token !== journalsState.profileToken || state.view.type !== "journal" || state.view.name !== j.name) return;
  $("#journal-hero").innerHTML = heroHTML(j, p || {});
}

$("#journal-hero").addEventListener("click", (e) => {
  if (e.target.closest("[data-act=journals]")) setView({ type: "journals" });
});

// The journal page needs the gallery's list (covers, years); fetch it if we came straight here.
async function ensureJournalsList() {
  if (journalsState.list.length) return;
  try { journalsState.list = (await api("/api/journals")).journals; } catch {}
}
