(() => {
  const state = { roles: [], data: null };
  const make = (tag, cls, text) => {
    const item = document.createElement(tag);
    if (cls) item.className = cls;
    if (text !== undefined) item.textContent = text;
    return item;
  };
  const isProducer = () => state.roles.includes("admin") || state.roles.includes("producer");
  const status = (message) => { document.getElementById("audio-review-status").textContent = message; };
  const guarded = (task) => Promise.resolve().then(task).catch((error) => status(error.message));

  function panel() {
    const section = make("section", "audio-review-section");
    section.id = "audio-review-studio";
    section.innerHTML = `
      <div class="audio-review-heading"><div><p class="eyebrow dark-eyebrow">Local Narration Review</p>
      <h3>Paragraph take and final-mix evidence</h3>
      <p>Kokoro remains local and zero-fee; media bytes stay in the asset store.</p></div></div>
      <div class="audio-review-controls">
        <label><span>Content UUID</span><input id="audio-review-content" autocomplete="off"></label>
        <label><span>Local model</span><input id="audio-review-model" value="kokoro-v1.0"></label>
        <button id="audio-review-load" class="secondary" type="button">Load</button>
        <button id="audio-review-initialize" type="button">Initialize</button>
      </div>
      <p id="audio-review-status" class="audio-review-status" role="status">Connect Data and enter an approved-script content UUID.</p>
      <div id="audio-review-summary"></div><div id="audio-review-grid" class="audio-review-grid"></div>`;
    return section;
  }

  function badge(value) {
    return make("span", `audio-review-badge ${value || "unknown"}`, String(value || "unknown").replaceAll("_", " "));
  }
  function selected(paragraphId) {
    return (state.data?.takes || []).find((take) => String(take.paragraph_id) === String(paragraphId) && take.status === "selected");
  }
  function action(text, task) {
    const button = make("button", "secondary", text);
    button.type = "button";
    button.addEventListener("click", () => guarded(task));
    return button;
  }

  function render() {
    const summary = document.getElementById("audio-review-summary");
    const grid = document.getElementById("audio-review-grid");
    summary.replaceChildren();
    grid.replaceChildren();
    document.getElementById("audio-review-initialize").disabled = state.roles.length > 0 && !isProducer();
    if (!state.data) return;

    const production = state.data.production;
    const header = make("div", "audio-review-summary-row");
    const copy = make("div");
    copy.append(make("h4", "", `${production.title} · script v${production.script_version}`));
    const note = make("p");
    note.append(badge(production.status), document.createTextNode(` · ${production.provider}/${production.model_id} · lock ${production.lock_version}`));
    copy.append(note, make("small", "", "Final approval requires forced alignment and passing QC, rights, and review gates."));
    header.append(copy);
    summary.append(header);

    const paragraphs = make("article", "audio-review-card");
    paragraphs.append(make("h4", "", "Paragraph takes"));
    state.data.paragraphs.forEach((paragraph) => {
      const row = make("div", "audio-review-row");
      row.append(make("strong", "", `Segment ${paragraph.sequence}`), make("p", "", paragraph.source_text));
      const take = selected(paragraph.id);
      if (take) {
        const evidence = make("p");
        evidence.append(badge(take.status), document.createTextNode(` · QC ${take.qc_status} · ${take.timing_source} · ${Number(take.duration_seconds).toFixed(2)}s`));
        row.append(evidence, make("small", "", `LUFS ${take.integrated_lufs} · peak ${take.true_peak_dbfs} dBFS · clipping ${take.clipping_count}`));
      } else {
        const latest = state.data.takes.filter((item) => String(item.paragraph_id) === String(paragraph.id)).sort((a, b) => b.take_version - a.take_version)[0];
        row.append(badge(latest?.status || "not_started"));
      }
      if (isProducer() && ["working", "changes_requested"].includes(production.status)) {
        row.append(action("Regenerate this paragraph", () => regenerate(paragraph.id)));
      }
      paragraphs.append(row);
    });

    const mix = state.data.mixes.find((item) => String(item.id) === String(production.current_mix_version_id));
    const mixCard = make("article", "audio-review-card");
    mixCard.append(make("h4", "", "Current mix"));
    if (!mix) mixCard.append(make("p", "", "No mix evidence registered."));
    else [
      ["Status", mix.status], ["QC", mix.qc_status], ["Alignment", mix.alignment_source],
      ["Loudness", mix.measured_lufs ?? "pending"], ["True peak", mix.true_peak_dbfs ?? "pending"],
      ["Clipping", mix.clipping_count], ["Final asset", mix.final_mix_asset_id || "pending"]
    ].forEach(([label, value]) => mixCard.append(make("p", "audio-review-row", `${label}: ${String(value).replaceAll("_", " ")}`)));
    grid.append(paragraphs, mixCard);
  }

  function contentId() {
    const value = document.getElementById("audio-review-content").value.trim();
    if (!value) throw new Error("Enter a content UUID.");
    return value;
  }
  async function refreshAccess() {
    if (!window.PortfolioApi.configured()) { state.roles = []; state.data = null; render(); return; }
    const result = await window.PortfolioApi.access();
    state.roles = result.roles || result.operator?.roles || [];
    render();
  }
  async function load() {
    state.data = await window.PortfolioApi.audioForContent(contentId());
    render();
    status("Exact local audio production loaded.");
  }
  async function initialize() {
    state.data = await window.PortfolioApi.initializeAudio(contentId(), document.getElementById("audio-review-model").value.trim() || "kokoro-v1.0");
    render();
    status("Zero-fee local paragraph jobs created.");
  }
  async function regenerate(paragraphId) {
    state.data = await window.PortfolioApi.regenerateAudioParagraph(state.data.production.id, paragraphId, state.data.production.model_id);
    render();
    status("Only the selected paragraph was queued for a new local take.");
  }

  async function start() {
    if (!window.PortfolioApi || document.getElementById("audio-review-studio")) return;
    const root = document.getElementById("portfolio-studio");
    if (!root) return;
    const view = panel();
    const anchor = document.getElementById("script-review-studio");
    if (anchor) anchor.insertAdjacentElement("afterend", view); else root.append(view);
    document.getElementById("audio-review-load").addEventListener("click", () => guarded(load));
    document.getElementById("audio-review-initialize").addEventListener("click", () => guarded(initialize));
    document.getElementById("connect-api")?.addEventListener("click", () => setTimeout(() => guarded(refreshAccess), 300));
    await refreshAccess();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => void start(), { once: true }); else void start();
})();