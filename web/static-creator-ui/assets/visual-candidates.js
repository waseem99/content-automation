(() => {
  const state = { roles: [], data: null };
  const make = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const isProducer = () => state.roles.includes("admin") || state.roles.includes("producer");
  const isReviewer = () => state.roles.includes("admin") || state.roles.includes("reviewer");
  const setStatus = (message) => {
    const node = document.getElementById("visual-candidates-status");
    if (node) node.textContent = message;
  };
  const guarded = (task) => Promise.resolve().then(task).catch((error) => setStatus(error.message));

  function panel() {
    const section = make("section", "visual-candidates-section");
    section.id = "visual-candidates-studio";
    section.innerHTML = `
      <div class="visual-candidates-heading">
        <div><p class="eyebrow dark-eyebrow">Local Visual Candidate Review</p>
        <h3>Compare retained shot candidates</h3>
        <p>Three local candidates per shot retain exact prompt, seed, model, references, and ten-check evidence.</p></div>
      </div>
      <div class="visual-candidates-controls">
        <label><span>Content UUID</span><input id="visual-candidates-content" autocomplete="off"></label>
        <label><span>Visual preset UUID</span><input id="visual-candidates-preset" autocomplete="off"></label>
        <label><span>Local model</span><input id="visual-candidates-model" value="sdxl-base-1.0"></label>
        <button id="visual-candidates-load" class="secondary" type="button">Load</button>
        <button id="visual-candidates-initialize" type="button">Initialize 3 candidates</button>
      </div>
      <p id="visual-candidates-status" class="visual-candidates-status" role="status">Connect Data and enter an approved-script content UUID.</p>
      <div id="visual-candidates-summary"></div>
      <div id="visual-candidates-shots" class="visual-candidates-shots"></div>`;
    return section;
  }

  function badge(value) {
    const normalized = String(value || "unknown");
    return make("span", `visual-candidates-badge ${normalized}`, normalized.replaceAll("_", " "));
  }

  function button(text, task, primary = false) {
    const node = make("button", primary ? "" : "secondary", text);
    node.type = "button";
    node.addEventListener("click", () => guarded(task));
    return node;
  }

  function checksFor(candidateId) {
    return (state.data?.checks || []).filter((item) => String(item.visual_candidate_id) === String(candidateId));
  }

  function candidatesFor(shot) {
    return (state.data?.candidates || [])
      .filter((item) => String(item.visual_shot_version_id) === String(shot.current_version_id))
      .sort((left, right) => Number(left.ordinal) - Number(right.ordinal));
  }

  function rationale(label) {
    const value = window.prompt(label, "");
    if (value === null) return null;
    const normalized = value.trim();
    if (normalized.length < 3) throw new Error("A rationale of at least three characters is required.");
    return normalized;
  }

  function renderCandidate(shot, candidate) {
    const card = make("article", "visual-candidate-card");
    const title = make("div", "visual-candidate-title");
    title.append(make("strong", "", `Candidate ${candidate.ordinal}`), badge(candidate.status));
    card.append(title);

    const facts = make("dl", "visual-candidate-facts");
    [
      ["Seed", candidate.seed],
      ["Model", candidate.model_id],
      ["Checks", candidate.checks_status],
      ["Job", candidate.generation_job_status || "not claimed"],
      ["Asset", candidate.asset_id || "pending"],
      ["Cost", Number(candidate.actual_cost_usd || 0).toFixed(2)]
    ].forEach(([label, value]) => {
      facts.append(make("dt", "", label), make("dd", "", String(value)));
    });
    card.append(facts);

    const checks = make("div", "visual-candidate-checks");
    const rows = checksFor(candidate.id);
    if (!rows.length) checks.append(make("small", "", "Checks pending."));
    rows.forEach((item) => {
      const row = make("span", `visual-candidate-check ${item.status}`);
      row.textContent = `${String(item.check_type).replaceAll("_", " ")}: ${item.status}`;
      checks.append(row);
    });
    card.append(checks);

    if (isReviewer() && candidate.status === "generated") {
      const actions = make("div", "visual-candidate-actions");
      actions.append(
        button("Select", () => decideCandidate(shot, candidate, "selected"), true),
        button("Reject", () => decideCandidate(shot, candidate, "rejected"))
      );
      card.append(actions);
    }
    return card;
  }

  function renderShot(shot) {
    const card = make("article", "visual-shot-card");
    const header = make("div", "visual-shot-heading");
    const copy = make("div");
    copy.append(make("h4", "", `Shot ${shot.sequence} · ${shot.scene_key}`));
    const statusLine = make("p");
    statusLine.append(
      badge(shot.status),
      document.createTextNode(` · prompt v${shot.current_version} · lock ${shot.lock_version}`)
    );
    copy.append(statusLine, make("p", "visual-shot-brief", shot.visual_brief));
    header.append(copy);

    const controls = make("div", "visual-shot-actions");
    if (isReviewer() && shot.status === "candidates_ready") {
      controls.append(button("Request shot changes", () => decideShot(shot)));
    }
    if (isProducer() && ["changes_requested", "rejected"].includes(shot.status)) {
      controls.append(button("Revise this prompt", () => reviseShot(shot), true));
    }
    header.append(controls);
    card.append(header);

    const prompt = make("details", "visual-shot-prompt");
    prompt.append(make("summary", "", "Exact prompt and exclusions"));
    prompt.append(make("p", "", shot.compiled_prompt), make("small", "", shot.negative_prompt));
    card.append(prompt);

    const grid = make("div", "visual-candidate-grid");
    candidatesFor(shot).forEach((candidate) => grid.append(renderCandidate(shot, candidate)));
    card.append(grid);
    return card;
  }

  function render() {
    const summary = document.getElementById("visual-candidates-summary");
    const shots = document.getElementById("visual-candidates-shots");
    if (!summary || !shots) return;
    summary.replaceChildren();
    shots.replaceChildren();
    const initialize = document.getElementById("visual-candidates-initialize");
    if (initialize) initialize.disabled = state.roles.length > 0 && !isProducer();
    if (!state.data) return;

    const project = state.data.project;
    const header = make("div", "visual-candidates-summary-row");
    const copy = make("div");
    copy.append(make("h4", "", `${project.title} · script v${project.script_version}`));
    const line = make("p");
    line.append(
      badge(project.status),
      document.createTextNode(` · ${project.provider}/${project.model_id} · ${project.candidate_count} per shot · lock ${project.lock_version}`)
    );
    copy.append(line, make("small", "", "Selection requires all ten checks to pass and independent review."));
    header.append(copy);

    const actions = make("div", "visual-project-actions");
    const allApproved = (state.data.shots || []).length > 0 && state.data.shots.every((item) => item.status === "approved");
    if (isProducer() && project.status === "working" && allApproved) {
      actions.append(button("Submit visual project", submitProject, true));
    }
    if (isReviewer() && project.status === "ready_for_review") {
      actions.append(
        button("Approve project", () => decideProject("approved"), true),
        button("Request project changes", () => decideProject("changes_requested")),
        button("Reject project", () => decideProject("rejected"))
      );
    }
    header.append(actions);
    summary.append(header);
    (state.data.shots || []).forEach((shot) => shots.append(renderShot(shot)));
  }

  function contentId() {
    const value = document.getElementById("visual-candidates-content").value.trim();
    if (!value) throw new Error("Enter a content UUID.");
    return value;
  }

  async function refreshAccess() {
    if (!window.PortfolioApi.configured()) {
      state.roles = [];
      state.data = null;
      render();
      return;
    }
    const result = await window.PortfolioApi.access();
    state.roles = result.roles || result.operator?.roles || [];
    render();
  }

  async function load() {
    state.data = await window.PortfolioApi.visualsForContent(contentId());
    render();
    setStatus("Exact retained candidate project loaded.");
  }

  async function initialize() {
    const preset = document.getElementById("visual-candidates-preset").value.trim();
    if (!preset) throw new Error("Enter an active visual preset UUID.");
    const model = document.getElementById("visual-candidates-model").value.trim() || "sdxl-base-1.0";
    state.data = await window.PortfolioApi.initializeVisuals(contentId(), {
      visual_preset_id: preset,
      provider: "comfyui-sdxl-local",
      model_id: model,
      candidate_count: 3,
      width: 704,
      height: 1280,
      continuity_references: []
    });
    render();
    setStatus("Three zero-fee local candidates were queued for each approved scene.");
  }

  async function decideCandidate(shot, candidate, decision) {
    const note = rationale(`${decision === "selected" ? "Why should this candidate be selected?" : "Why should this candidate be rejected?"}`);
    if (note === null) return;
    state.data = await window.PortfolioApi.decideVisualCandidate(
      state.data.project.id,
      shot.id,
      shot.current_version_id,
      candidate.id,
      { expected_shot_lock_version: shot.lock_version, decision, rationale: note }
    );
    render();
    setStatus(`Candidate ${decision}. Prior candidates remain retained.`);
  }

  async function decideShot(shot) {
    const note = rationale("What must change in this shot prompt?");
    if (note === null) return;
    state.data = await window.PortfolioApi.decideVisualShot(
      state.data.project.id,
      shot.id,
      shot.current_version_id,
      { expected_shot_lock_version: shot.lock_version, decision: "changes_requested", rationale: note }
    );
    render();
    setStatus("Shot changes requested against the exact prompt version.");
  }

  async function reviseShot(shot) {
    const reason = rationale("Why is a new prompt version required?");
    if (reason === null) return;
    const action = window.prompt("Revised action or visual direction", shot.visual_brief || "");
    if (action === null || action.trim().length < 3) throw new Error("Enter the revised visual direction.");
    state.data = await window.PortfolioApi.reviseVisualShot(
      state.data.project.id,
      shot.id,
      {
        expected_shot_lock_version: shot.lock_version,
        reason,
        prompt_patch: { action: action.trim() },
        negative_prompt_append: "",
        base_seed: 920000
      }
    );
    render();
    setStatus("A child prompt version and three new local candidates were created; prior evidence remains retained.");
  }

  async function submitProject() {
    state.data = await window.PortfolioApi.submitVisualProject(state.data.project.id, {
      expected_project_lock_version: state.data.project.lock_version
    });
    render();
    setStatus("Visual project submitted for independent review.");
  }

  async function decideProject(decision) {
    const note = rationale(`Rationale for ${decision.replaceAll("_", " ")}`);
    if (note === null) return;
    state.data = await window.PortfolioApi.decideVisualProject(state.data.project.id, {
      expected_project_lock_version: state.data.project.lock_version,
      decision,
      rationale: note
    });
    render();
    setStatus(`Visual project ${decision.replaceAll("_", " ")}.`);
  }

  async function start() {
    if (!window.PortfolioApi || document.getElementById("visual-candidates-studio")) return;
    const root = document.getElementById("portfolio-studio");
    if (!root) return;
    const view = panel();
    const anchor = document.getElementById("audio-review-studio");
    if (anchor) anchor.insertAdjacentElement("afterend", view); else root.append(view);
    document.getElementById("visual-candidates-load").addEventListener("click", () => guarded(load));
    document.getElementById("visual-candidates-initialize").addEventListener("click", () => guarded(initialize));
    document.getElementById("connect-api")?.addEventListener("click", () => setTimeout(() => guarded(refreshAccess), 300));
    await refreshAccess();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => void start(), { once: true });
  } else {
    void start();
  }
})();
