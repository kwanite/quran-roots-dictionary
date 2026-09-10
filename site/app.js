const state = {
  index: null,
  records: [],
  activeId: null,
  dataBase: null
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({
  "&":"&amp;",
  "<":"&lt;",
  ">":"&gt;",
  '"':"&quot;",
  "'":"&#39;"
}[c]));

async function fetchJson(relativePath) {
  const candidates = state.dataBase
    ? [state.dataBase]
    : ["./data", "../data"];

  let lastError = null;

  for (const base of candidates) {
    try {
      const res = await fetch(`${base}/${relativePath}`);
      if (res.ok) {
        state.dataBase = base;
        return await res.json();
      }
      lastError = new Error(`${base}/${relativePath} returned ${res.status}`);
    } catch (err) {
      lastError = err;
    }
  }

  throw lastError || new Error(`Unable to load ${relativePath}`);
}

function refs(items) {
  if (!Array.isArray(items) || !items.length) return "";
  return `<div class="source-refs">${
    items.map(r => `<span class="source-ref">${esc(r)}</span>`).join("")
  }</div>`;
}

function formatPrimitive(value) {
  if (value === null || value === undefined || value === "") return "";
  if (Array.isArray(value)) return value.map(formatPrimitive).filter(Boolean).join(", ");
  if (typeof value === "object") return "";
  return String(value);
}

function renderStructured(value) {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return `<div class="notice">${esc(value)}</div>`;
  }

  if (Array.isArray(value)) {
    return value.map(renderStructured).join("");
  }

  if (value && typeof value === "object") {
    const rows = Object.entries(value)
      .filter(([, v]) => v !== null && v !== "" && !(Array.isArray(v) && v.length === 0))
      .map(([key, v]) => {
        const primitive = formatPrimitive(v);
        if (primitive) {
          return `<div class="object-row">
            <div class="object-key">${esc(key.replaceAll("_", " "))}</div>
            <div class="object-value">${esc(primitive)}</div>
          </div>`;
        }
        return `<div class="object-row">
          <div class="object-key">${esc(key.replaceAll("_", " "))}</div>
          <div class="object-value">${renderStructured(v)}</div>
        </div>`;
      }).join("");

    return `<div class="object-list">${rows}</div>`;
  }

  return "";
}

function setupBrowserControls() {
  const toggle = document.querySelector("#browser-toggle");
  const close = document.querySelector("#browser-close");

  const setCollapsed = (collapsed) => {
    document.body.classList.toggle("browser-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
  };

  toggle.addEventListener("click", () => {
    setCollapsed(!document.body.classList.contains("browser-collapsed"));
  });

  close.addEventListener("click", () => setCollapsed(true));

  if (window.matchMedia("(max-width: 820px)").matches) {
    setCollapsed(true);
  }
}

async function init() {
  setupBrowserControls();

  const index = await fetchJson("root-index.json");
  state.index = index;
  state.records = index.root_order.map(id => index.by_id[id]);
  renderList(state.records);

  const search = document.querySelector("#search");
  search.addEventListener("input", () => renderList(currentFilteredRecords()));

  const hash = location.hash.replace("#", "");
  if (/^\d{4}$/.test(hash) && state.index.by_id[hash]) {
    await loadRoot(hash, { focus: false });
  }
}

function currentFilteredRecords() {
  const input = document.querySelector("#search");
  const raw = input.value.trim();
  const q = raw.toLowerCase();

  if (!q) return state.records;

  return state.records.filter(r =>
    r.root_id.includes(q) ||
    String(r.root).toLowerCase().includes(q) ||
    String(r.arabic || "").includes(raw)
  );
}

function renderList(records) {
  document.querySelector("#count").textContent =
    `${records.length.toLocaleString()} root${records.length === 1 ? "" : "s"}`;

  const list = document.querySelector("#root-list");
  list.innerHTML = records.map(r => `
    <button
      class="root-button ${state.activeId === r.root_id ? "active" : ""}"
      data-id="${esc(r.root_id)}"
      role="listitem"
      ${state.activeId === r.root_id ? 'aria-current="true"' : ""}
    >
      <span class="rid">${esc(r.root_id)}</span>
      <span class="root-code">${esc(r.root)}</span>
      <span class="root-list-arabic arabic">${esc(r.arabic)}</span>
    </button>
  `).join("");

  list.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", () => loadRoot(btn.dataset.id));
  });
}

async function loadRoot(id, options = { focus: true }) {
  const meta = state.index.by_id[id];
  if (!meta) return;

  const data = await fetchJson(`roots/${encodeURIComponent(meta.file)}`);

  state.activeId = id;
  renderList(currentFilteredRecords());
  renderRoot(id, data);
  history.replaceState(null, "", `#${id}`);

  if (window.matchMedia("(max-width: 820px)").matches) {
    document.body.classList.add("browser-collapsed");
    document.querySelector("#browser-toggle").setAttribute("aria-expanded", "false");
  }

  if (options.focus !== false) {
    document.querySelector("#root-view").focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

function renderRoot(id, d) {
  const idea = d.root_idea || {};
  const forms = Array.isArray(d.quranic_forms) ? d.quranic_forms : [];
  const classical = Array.isArray(d.other_classical_meanings) ? d.other_classical_meanings : [];
  const cautions = Array.isArray(d.cautions) ? d.cautions : [];
  const ambiguous = Array.isArray(d.unassigned_or_ambiguous_evidence)
    ? d.unassigned_or_ambiguous_evidence
    : [];

  const formHtml = forms.map(f => {
    const senses = Array.isArray(f.senses) ? f.senses : [];
    const examples = Array.isArray(f.quran_examples) ? f.quran_examples : [];

    return `<div class="card form-card">
      <div class="form-title">
        <h4>
          <span class="form-arabic arabic">${esc(f.headword_arabic || "")}</span>
          ${esc(f.public_pos_label || "")}
        </h4>
        ${f.verb_form ? `<span class="pill">${esc(f.verb_form)}</span>` : ""}
        ${Number.isInteger(f.occurrence_count)
          ? `<span class="pill">${f.occurrence_count.toLocaleString()} occurrence${f.occurrence_count === 1 ? "" : "s"}</span>`
          : ""}
      </div>

      ${senses.map(s => `<div class="sense">
        <div class="sense-definition">${esc(s.definition || "")}</div>
        ${s.usage_conditions ? `<div class="usage">${esc(s.usage_conditions)}</div>` : ""}
        ${refs(s.source_refs)}
      </div>`).join("")}

      ${examples.length ? `
        <div class="examples-label">Selected Quran examples</div>
        <ul class="examples">
          ${examples.map(ex => `<li class="example">
            ${esc(ex.verse_key || "")}
            ${ex.word_location ? ` · ${esc(ex.word_location)}` : ""}
          </li>`).join("")}
        </ul>
      ` : ""}
    </div>`;
  }).join("");

  const classicalHtml = classical.map(m => `<div class="card">
    <div class="classical-definition">
      ${m.headword_arabic ? `<span class="form-arabic arabic">${esc(m.headword_arabic)}</span>` : ""}
      ${esc(m.definition || "")}
    </div>
    ${m.usage_conditions ? `<div class="usage">${esc(m.usage_conditions)}</div>` : ""}
    ${refs(m.source_refs)}
  </div>`).join("");

  document.querySelector("#root-view").innerHTML = `
    <div class="root-head">
      <div>
        <div class="root-kicker">ROOT ${esc(id)} · ${esc(d.root)}</div>
        <h2>${esc(idea.summary || d.root || "")}</h2>
      </div>
      <div class="root-arabic arabic">${esc(d.arabic || "")}</div>
    </div>

    ${idea.development ? `
      <section class="section">
        <div class="section-title"><h3>Semantic development</h3></div>
        <div class="prose">${esc(idea.development)}</div>
        ${refs(idea.source_refs)}
      </section>
    ` : ""}

    <section class="section">
      <div class="section-title">
        <h3>Quran-attested forms</h3>
        <span class="muted">${forms.length} form${forms.length === 1 ? "" : "s"}</span>
      </div>
      ${formHtml || `<div class="card">No forms listed.</div>`}
    </section>

    ${classicalHtml ? `
      <section class="section">
        <div class="section-title"><h3>Other Classical meanings</h3></div>
        ${classicalHtml}
      </section>
    ` : ""}

    ${cautions.length ? `
      <section class="section">
        <div class="section-title"><h3>Cautions</h3></div>
        ${cautions.map(c => `<div class="card warning">${renderStructured(c)}</div>`).join("")}
      </section>
    ` : ""}

    ${ambiguous.length ? `
      <section class="section">
        <div class="section-title"><h3>Unassigned or ambiguous evidence</h3></div>
        ${ambiguous.map(c => `<div class="card ambiguous">${renderStructured(c)}</div>`).join("")}
      </section>
    ` : ""}
  `;
}

init().catch(err => {
  const message =
    location.protocol === "file:"
      ? "This page must be served over HTTP so the browser can fetch the JSON files. Use the local preview command from the repository instructions."
      : `Unable to load root index. ${err.message || err}`;

  document.querySelector("#root-view").innerHTML = `
    <div class="card error-card">
      <strong>Unable to load data.</strong>
      <p>${esc(message)}</p>
    </div>
  `;
});
