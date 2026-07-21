(() => {
  const state = { roles: [], data: null };

  function make(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }

  function operatorKey() {
    return String(sessionStorage.getItem("content-automation.operator-key") || "").trim();
  }

  async function request(path, options = {}) {
    const configuration = window.PortfolioApi?.configuration?.() || {};
    if (!configuration.base || !operatorKey()) throw new Error("Connect Data first.");
    const response = await fetch(`${configuration.base}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Operator-Key": operatorKey(),
        ...(options.headers || {})
      }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      const detail = payload.detail;
      throw new Error(typeof detail === "object" && detail ? detail.code : detail || `Request failed (${response.status})`);
    }
    return payload;
  }

  function hasRole(role) {
    return state.roles.includes("admin") || state.roles.includes(role);
  }

  function current(name) {
    const id = state.data?.document?.current_version_id;
    return (state.data?.[name] || []).filter((row) => String(row.script_version_id) === String(id));
  }

  function createPanel() {
    const section = make("section", "script-review-section");
    section.id = "script-review-studio";
    section.innerHTML = `
      <div class="script-review-heading">
        <div><p class="eyebrow dark-eyebrow">Script Evidence Review</p>
        <h3>Approve claims and scenes before narration</h3>
        <p>Deterministic drafts remain versioned. Unsupported factual claims and open review actions block approval.</p></div>
      </div>
      <div class="script-review-controls">
        <label><span>Content UUID</span><input id="script-review-content" type="text"></label>
        <label><span>Target seconds</span><input id="script-review-duration" type="number" value="60"></label>
        <label><span>Fixed seed</span><input id="script-review-seed" type="number" value="20261001"></label>
        <button id="script-review-load" type="button" class="secondary">Load</button>
        <button id="script-review-generate" type="button">Generate deterministic draft</button>
      </div>
      <p id="script-review-status" class="script-review-status" role="status" aria-live="polite">Enter a content UUID.</p>
      <div id="script-review-summary"></div>
      <div id="script-review-evidence" class="script-review-evidence"></div>`;
    return section;
  }

  function button(text, handler, secondary = false) {
    const item = make("button", secondary ? "secondary" : "", text);
    item.type = "button";
    item.addEventListener("click", handler);
    return item;
  }

  function render() {
    const summary = document.getElementById("script-review-summary");
    const evidence = document.getElementById("script-review-evidence");
    summary.replaceChildren();
    evidence.replaceChildren();
    if (!state.data) return;
    const documentRow = state.data.document;
    const version = state.data.versions.find((row) => String(row.id) === String(documentRow.current_version_id));
    const header = make("div", "script-review-summary-row");
    const copy = make("div");
    copy.append(make("h4", "", `${documentRow.title} · v${documentRow.current_version}`));
    copy.append(make("p", "", `${documentRow.current_version_status.replaceAll("_", " ")} · ${version.word_count} words · ${Number(version.estimated_duration_seconds).toFixed(1)}s estimated`));
    header.appendChild(copy);
    const actions = make("div", "script-review-actions");
    if (hasRole("producer") && documentRow.current_version_status === "working") {
      actions.appendChild(button("Submit exact version", submit));
    }
    if (hasRole("producer") && ["changes_requested", "rejected"].includes(documentRow.current_version_status)) {
      actions.appendChild(button("Create child revision", revise));
    }
    if (hasRole("reviewer") && documentRow.current_version_status === "in_review") {
      actions.appendChild(button("Add review action", addAction, true));
      actions.appendChild(button("Approve", () => decide("approved")));
      actions.appendChild(button("Request changes", () => decide("changes_requested"), true));
      actions.appendChild(button("Reject", () => decide("rejected"), true));
    }
    header.appendChild(actions);
    summary.appendChild(header);

    [
      ["Sections", current("sections"), (row) => `${row.section_type}: ${row.text}`],
      ["Scenes", current("scenes"), (row) => `${row.scene_key}: ${row.visual_brief}`],
      ["Claims", current("claims"), (row) => `${row.claim_key} [${row.support_status}]: ${row.claim_text}`],
      ["Sources", current("sources"), (row) => `${row.title} · quality ${Number(row.quality_score).toFixed(0)}`],
      ["Review actions", state.data.review_actions || [], (row) => `v${versionNumber(row.script_version_id)} ${row.action_type}: ${row.body}${row.resolved_at ? " [resolved]" : " [open]"}`]
    ].forEach(([title, rows, format]) => {
      const card = make("article", "script-review-card");
      card.appendChild(make("h4", "", title));
      if (!rows.length) card.appendChild(make("p", "", "No evidence recorded."));
      rows.forEach((row) => card.appendChild(make("p", "script-review-evidence-row", format(row))));
      evidence.appendChild(card);
    });
  }

  function versionNumber(id) {
    return state.data.versions.find((row) => String(row.id) === String(id))?.version || "?";
  }

  async function load() {
    const contentId = document.getElementById("script-review-content").value.trim();
    if (!contentId) throw new Error("Enter a content UUID.");
    state.data = await request(`/scripts/content/${contentId}`);
    render();
    document.getElementById("script-review-status").textContent = "Exact script version loaded.";
  }

  async function generate() {
    const contentId = document.getElementById("script-review-content").value.trim();
    if (!contentId) throw new Error("Enter a content UUID.");
    state.data = await request(`/scripts/content/${contentId}`, {
      method: "POST",
      body: JSON.stringify({
        platform: "facebook",
        format: "vertical_short",
        language: "en-US",
        target_duration_seconds: Number(document.getElementById("script-review-duration").value),
        words_per_minute: 150,
        duration_tolerance_percent: 10,
        seed: Number(document.getElementById("script-review-seed").value),
        adapter_mode: "deterministic"
      })
    });
    render();
    document.getElementById("script-review-status").textContent = "Draft created. Factual claims still require source support.";
  }

  async function submit() {
    state.data = await request(`/scripts/${state.data.document.id}/submit`, {
      method: "POST",
      body: JSON.stringify({ expected_lock_version: state.data.document.lock_version })
    });
    render();
  }

  async function addAction() {
    const body = window.prompt("Review action:", "Confirm source support and narrow unsupported wording.");
    if (!body) return;
    const section = current("sections").find((row) => row.section_type === "narration") || current("sections")[0];
    state.data = await request(`/scripts/${state.data.document.id}/review-actions`, {
      method: "POST",
      body: JSON.stringify({
        expected_lock_version: state.data.document.lock_version,
        action: {
          script_version_id: state.data.document.current_version_id,
          script_section_id: section?.id || null,
          action_type: "factual_query",
          body
        }
      })
    });
    render();
  }

  async function decide(decision) {
    const rationale = window.prompt(`Rationale for ${decision.replaceAll("_", " ")}:`);
    if (!rationale) return;
    state.data = await request(`/scripts/${state.data.document.id}/decisions`, {
      method: "POST",
      body: JSON.stringify({ expected_lock_version: state.data.document.lock_version, decision, rationale })
    });
    render();
  }

  async function revise() {
    const reason = window.prompt("Revision reason:", "Address the version-bound review actions.");
    if (!reason) return;
    state.data = await request(`/scripts/${state.data.document.id}/revise`, {
      method: "POST",
      body: JSON.stringify({ expected_lock_version: state.data.document.lock_version, reason })
    });
    render();
  }

  async function start() {
    if (!window.PortfolioApi || document.getElementById("script-review-studio")) return;
    const portfolio = document.getElementById("portfolio-studio");
    if (!portfolio) return;
    const panel = createPanel();
    const concept = document.getElementById("concept-slate-studio");
    if (concept) concept.insertAdjacentElement("afterend", panel);
    else portfolio.appendChild(panel);
    const status = document.getElementById("script-review-status");
    const guarded = (handler) => handler().catch((error) => { status.textContent = error.message; });
    document.getElementById("script-review-load").addEventListener("click", () => guarded(load));
    document.getElementById("script-review-generate").addEventListener("click", () => guarded(generate));
    if (window.PortfolioApi.configured()) {
      const access = await window.PortfolioApi.access();
      state.roles = access.roles || access.operator?.roles || [];
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => void start(), { once: true });
  else void start();
})();
