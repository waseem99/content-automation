(() => {
  const state = { brands: [], roles: [], batches: [], current: null };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function operatorKey() {
    return String(
      sessionStorage.getItem("content-automation.operator-key") ||
      document.querySelector('meta[name="content-operator-key"]')?.content ||
      ""
    ).trim();
  }

  async function request(path, options = {}) {
    const configuration = window.PortfolioApi?.configuration?.() || {};
    const key = operatorKey();
    if (!configuration.base || !key) throw new Error("Connect Data before using concept generation.");
    const response = await fetch(`${configuration.base}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Operator-Key": key,
        ...(options.headers || {})
      }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      const detail = payload.detail;
      const message = typeof detail === "object" && detail ? detail.code : detail;
      throw new Error(payload.error || message || `Concept API request failed (${response.status})`);
    }
    return payload;
  }

  function parseDistribution(value) {
    const result = {};
    String(value || "").split(",").forEach((part) => {
      const [rawKey, rawCount] = part.split(":");
      const key = String(rawKey || "").trim().toLowerCase().replaceAll(" ", "_");
      const count = Number.parseInt(String(rawCount || "").trim(), 10);
      if (key && Number.isInteger(count) && count > 0) result[key] = count;
    });
    if (!Object.keys(result).length) throw new Error("Enter distribution values as name:count.");
    return result;
  }

  function rolesInclude(role) {
    return state.roles.includes("admin") || state.roles.includes(role);
  }

  function createField(labelText, id, value, type = "text") {
    const label = element("label", "concept-field");
    label.appendChild(element("span", "", labelText));
    const input = document.createElement("input");
    input.id = id;
    input.type = type;
    input.value = value;
    label.appendChild(input);
    return label;
  }

  function createSection() {
    const section = element("section", "concept-slate-section");
    section.id = "concept-slate-studio";
    section.setAttribute("aria-labelledby", "concept-slate-heading");

    const heading = element("div", "concept-slate-heading");
    const title = element("div");
    title.appendChild(element("p", "eyebrow dark-eyebrow", "Local Concept Slate"));
    const h3 = element("h3", "", "Generate candidates, review evidence, then apply a balanced slate");
    h3.id = "concept-slate-heading";
    title.appendChild(h3);
    title.appendChild(element("p", "", "Deterministic generation is the default. Candidates remain outside monthly plans until a reviewer approves a balanced slate and an administrator applies it."));
    heading.appendChild(title);
    const refresh = element("button", "secondary", "Refresh batches");
    refresh.type = "button";
    refresh.id = "concept-refresh";
    heading.appendChild(refresh);
    section.appendChild(heading);

    const controls = element("div", "concept-controls");
    const brandField = element("label", "concept-field");
    brandField.appendChild(element("span", "", "Brand"));
    const brand = document.createElement("select");
    brand.id = "concept-brand";
    brandField.appendChild(brand);
    controls.append(
      brandField,
      createField("Month", "concept-month", document.querySelector('meta[name="content-plan-month"]')?.content || "2026-08-01", "date"),
      createField("Candidate count", "concept-count", "30", "number"),
      createField("Format mix", "concept-formats", "vertical_short:20, carousel:10"),
      createField("Pillar targets", "concept-pillars", "education:10, conservation:10, myth:10"),
      createField("Fixed seed", "concept-seed", "20260801", "number")
    );
    const generate = element("button", "", "Generate deterministic candidates");
    generate.id = "concept-generate";
    generate.type = "button";
    controls.appendChild(generate);
    section.appendChild(controls);

    const status = element("p", "concept-status", "Connect Data to load concept batches.");
    status.id = "concept-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    section.appendChild(status);

    const layout = element("div", "concept-layout");
    const batches = element("aside", "concept-batches");
    batches.appendChild(element("h4", "", "Generation batches"));
    const batchList = element("div", "concept-batch-list");
    batchList.id = "concept-batch-list";
    batches.appendChild(batchList);
    layout.appendChild(batches);

    const workspace = element("div", "concept-workspace");
    const summary = element("div", "concept-summary");
    summary.id = "concept-summary";
    workspace.appendChild(summary);
    const candidates = element("div", "concept-candidates");
    candidates.id = "concept-candidates";
    workspace.appendChild(candidates);
    layout.appendChild(workspace);
    section.appendChild(layout);
    return section;
  }

  function badge(value) {
    return element("span", `concept-badge concept-badge-${value}`, String(value).replaceAll("_", " "));
  }

  function renderBatches() {
    const list = document.getElementById("concept-batch-list");
    list.replaceChildren();
    if (!state.batches.length) {
      list.appendChild(element("p", "concept-empty", "No batches for the current brand and month."));
      return;
    }
    state.batches.forEach((batch) => {
      const button = element("button", `concept-batch${state.current?.batch?.id === batch.id ? " active" : ""}`);
      button.type = "button";
      button.appendChild(element("strong", "", `${batch.brand_name} · ${batch.month_start}`));
      button.appendChild(badge(batch.status));
      button.appendChild(element("small", "", `${batch.candidate_count}/${batch.requested_count} candidates · ${batch.duplicate_count} duplicate(s)`));
      button.addEventListener("click", () => loadBatch(batch.id));
      list.appendChild(button);
    });
  }

  function scoreRow(candidate) {
    const row = element("div", "concept-score-row");
    [
      ["Total", candidate.total_score],
      ["Originality", candidate.originality_score],
      ["Engagement", candidate.engagement_score],
      ["Monetization", candidate.monetization_fit_score],
      ["Policy risk", candidate.policy_risk_score],
      ["Feasibility", candidate.feasibility_score]
    ].forEach(([label, value]) => {
      const metric = element("span", "concept-score");
      metric.appendChild(element("small", "", label));
      metric.appendChild(element("strong", "", Number(value).toFixed(1)));
      row.appendChild(metric);
    });
    return row;
  }

  async function reviewCandidate(candidateId, action) {
    const rationale = window.prompt(`Reason for ${action.replaceAll("_", " ")}:`, "Reviewed against originality, evidence, policy risk, and feasibility.");
    if (!rationale) return;
    await request(`/concepts/candidates/${candidateId}/review`, {
      method: "POST",
      body: JSON.stringify({ action, rationale })
    });
    await loadBatch(state.current.batch.id);
  }

  async function reviseCandidate(candidate) {
    const hook = window.prompt("Revised hook:", candidate.hook);
    if (!hook || hook === candidate.hook) return;
    const reason = window.prompt("Revision reason:", "Improve specificity and first-seconds clarity.");
    if (!reason) return;
    await request(`/concepts/candidates/${candidate.id}/revise`, {
      method: "POST",
      body: JSON.stringify({ hook, revision_reason: reason })
    });
    await loadBatch(state.current.batch.id);
  }

  function renderCandidates() {
    const target = document.getElementById("concept-candidates");
    target.replaceChildren();
    const candidates = state.current?.candidates || [];
    if (!candidates.length) {
      target.appendChild(element("p", "concept-empty", "No candidates in this batch."));
      return;
    }
    candidates.forEach((candidate) => {
      const card = element("article", "concept-card");
      const head = element("div", "concept-card-head");
      const identity = element("div");
      identity.appendChild(element("small", "", `${candidate.format.replaceAll("_", " ")} · ${candidate.pillar.replaceAll("_", " ")}`));
      identity.appendChild(element("h4", "", candidate.title));
      head.append(identity, badge(candidate.status));
      card.appendChild(head);
      card.appendChild(element("p", "concept-hook", candidate.hook));
      card.appendChild(element("p", "", candidate.concept));
      card.appendChild(scoreRow(candidate));
      const evidence = element("details", "concept-evidence");
      evidence.appendChild(element("summary", "", "Score and research evidence"));
      evidence.appendChild(element("pre", "", JSON.stringify({
        score: candidate.score_evidence,
        research: candidate.required_research,
        sources: candidate.source_requirements,
        duplicate: {
          kind: candidate.duplicate_kind,
          content_id: candidate.duplicate_content_id,
          candidate_id: candidate.duplicate_candidate_id,
          similarity: candidate.duplicate_similarity
        }
      }, null, 2)));
      card.appendChild(evidence);
      const actions = element("div", "concept-actions");
      if (rolesInclude("reviewer") && ["candidate", "shortlisted", "rejected"].includes(candidate.status)) {
        if (candidate.status !== "shortlisted") {
          const shortlist = element("button", "", "Shortlist");
          shortlist.type = "button";
          shortlist.addEventListener("click", () => reviewCandidate(candidate.id, "shortlist"));
          actions.appendChild(shortlist);
        }
        if (candidate.status !== "rejected") {
          const reject = element("button", "secondary", "Reject");
          reject.type = "button";
          reject.addEventListener("click", () => reviewCandidate(candidate.id, "reject"));
          actions.appendChild(reject);
        }
        if (["shortlisted", "rejected"].includes(candidate.status)) {
          const restore = element("button", "secondary", "Restore");
          restore.type = "button";
          restore.addEventListener("click", () => reviewCandidate(candidate.id, "restore"));
          actions.appendChild(restore);
        }
      }
      if (rolesInclude("producer") && ["candidate", "shortlisted", "rejected"].includes(candidate.status)) {
        const revise = element("button", "secondary", "Revise hook");
        revise.type = "button";
        revise.addEventListener("click", () => reviseCandidate(candidate));
        actions.appendChild(revise);
      }
      card.appendChild(actions);
      target.appendChild(card);
    });
  }

  function renderSummary() {
    const target = document.getElementById("concept-summary");
    target.replaceChildren();
    if (!state.current) {
      target.appendChild(element("p", "concept-empty", "Select a batch to inspect candidates."));
      return;
    }
    const batch = state.current.batch;
    const shortlisted = state.current.candidates.filter((item) => item.status === "shortlisted").length;
    const summary = element("div", "concept-summary-head");
    const title = element("div");
    title.appendChild(element("p", "eyebrow dark-eyebrow", "Current Batch"));
    title.appendChild(element("h3", "", `${batch.brand_name} · ${batch.month_start}`));
    title.appendChild(element("p", "", `${shortlisted} shortlisted · ${batch.duplicate_count} duplicate(s) blocked · fixed seed ${batch.seed}`));
    summary.appendChild(title);
    const actions = element("div", "concept-actions");
    if (rolesInclude("reviewer") && shortlisted > 0) {
      const build = element("button", "", "Build balanced slate");
      build.type = "button";
      build.addEventListener("click", buildSlate);
      actions.appendChild(build);
    }
    const latest = state.current.slates?.[0];
    if (rolesInclude("reviewer") && latest?.status === "draft") {
      const approve = element("button", "secondary", "Approve latest slate");
      approve.type = "button";
      approve.addEventListener("click", () => approveSlate(latest.id));
      actions.appendChild(approve);
    }
    if (rolesInclude("admin") && latest?.status === "approved") {
      const apply = element("button", "secondary", "Apply to draft plan");
      apply.type = "button";
      apply.addEventListener("click", () => applySlate(latest.id));
      actions.appendChild(apply);
    }
    summary.appendChild(actions);
    target.appendChild(summary);
    if (latest) {
      const slateNote = element("p", "concept-slate-note", `Latest slate v${latest.version}: ${latest.status} · ${latest.item_count} item(s)`);
      target.appendChild(slateNote);
    }
  }

  async function buildSlate() {
    const batch = state.current.batch;
    const selectedCount = Number.parseInt(window.prompt("Slate size:", String(batch.shortlisted_count || batch.requested_count)), 10);
    if (!Number.isInteger(selectedCount) || selectedCount < 1) return;
    const formatText = window.prompt("Format mix (name:count):", Object.entries(batch.requested_format_mix).map(([key, value]) => `${key}:${value}`).join(", "));
    const pillarText = window.prompt("Pillar targets (name:count):", Object.entries(batch.requested_pillar_targets).map(([key, value]) => `${key}:${value}`).join(", "));
    if (!formatText || !pillarText) return;
    await request("/concepts/slates", {
      method: "POST",
      body: JSON.stringify({
        batch_id: batch.id,
        selected_count: selectedCount,
        format_mix: parseDistribution(formatText),
        pillar_targets: parseDistribution(pillarText)
      })
    });
    await loadBatch(batch.id);
  }

  async function approveSlate(slateId) {
    await request(`/concepts/slates/${slateId}/approve`, { method: "POST" });
    await loadBatch(state.current.batch.id);
  }

  async function applySlate(slateId) {
    const planId = window.prompt("Draft monthly plan UUID:");
    if (!planId) return;
    const slate = await request(`/concepts/slates/${slateId}`);
    const startText = window.prompt("First scheduled date (YYYY-MM-DD):", slate.slate.month_start);
    if (!startText) return;
    const start = new Date(`${startText}T00:00:00Z`);
    if (Number.isNaN(start.getTime())) throw new Error("Invalid first scheduled date.");
    const items = slate.items.map((item, index) => {
      const scheduled = new Date(start.getTime());
      scheduled.setUTCDate(scheduled.getUTCDate() + index);
      return { candidate_id: item.candidate_id, scheduled_for: scheduled.toISOString().slice(0, 10) };
    });
    await request(`/concepts/slates/${slateId}/apply`, {
      method: "POST",
      body: JSON.stringify({ plan_id: planId.trim(), items })
    });
    await loadBatch(state.current.batch.id);
  }

  async function loadBatch(batchId) {
    const status = document.getElementById("concept-status");
    status.textContent = "Loading candidate evidence…";
    try {
      state.current = await request(`/concepts/batches/${batchId}`);
      renderBatches();
      renderSummary();
      renderCandidates();
      status.textContent = `${state.current.candidates.length} candidate(s) loaded. No plan is changed until administrator application.`;
    } catch (error) {
      status.textContent = error.message;
    }
  }

  async function refresh() {
    const status = document.getElementById("concept-status");
    if (!window.PortfolioApi?.configured()) {
      status.textContent = "Connect Data to load concept batches.";
      return;
    }
    status.textContent = "Loading concept batches…";
    try {
      const brandId = document.getElementById("concept-brand").value;
      const monthStart = document.getElementById("concept-month").value;
      const payload = await request(`/concepts/batches?brand_id=${encodeURIComponent(brandId)}&month_start=${encodeURIComponent(monthStart)}&limit=100`);
      state.batches = payload.items || [];
      renderBatches();
      if (state.batches.length) await loadBatch(state.batches[0].id);
      else {
        state.current = null;
        renderSummary();
        renderCandidates();
        status.textContent = "No concept batches match the selected brand and month.";
      }
    } catch (error) {
      status.textContent = error.message;
    }
  }

  async function generate() {
    const status = document.getElementById("concept-status");
    const button = document.getElementById("concept-generate");
    button.disabled = true;
    status.textContent = "Generating deterministic review candidates…";
    try {
      const candidateCount = Number.parseInt(document.getElementById("concept-count").value, 10);
      const payload = await request("/concepts/batches", {
        method: "POST",
        body: JSON.stringify({
          brand_id: document.getElementById("concept-brand").value,
          month_start: document.getElementById("concept-month").value,
          candidate_count: candidateCount,
          format_mix: parseDistribution(document.getElementById("concept-formats").value),
          pillar_targets: parseDistribution(document.getElementById("concept-pillars").value),
          seed: Number.parseInt(document.getElementById("concept-seed").value, 10),
          adapter_mode: "deterministic"
        })
      });
      await refresh();
      await loadBatch(payload.batch.id);
    } catch (error) {
      status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  async function initializeData() {
    if (!window.PortfolioApi?.configured()) return;
    const [brands, access] = await Promise.all([window.PortfolioApi.brands(), window.PortfolioApi.access()]);
    state.brands = brands.brands || [];
    state.roles = access.roles || access.operator?.roles || [];
    const select = document.getElementById("concept-brand");
    select.replaceChildren();
    state.brands.forEach((brand) => {
      const option = document.createElement("option");
      option.value = brand.id;
      option.textContent = brand.display_name;
      select.appendChild(option);
    });
    await refresh();
  }

  function start() {
    if (!window.PortfolioApi || document.getElementById("concept-slate-studio")) return;
    const portfolio = document.getElementById("portfolio-studio");
    if (!portfolio) return;
    if (!document.querySelector('link[data-studio-module="concept-slate"]')) {
      const style = document.createElement("link");
      style.rel = "stylesheet";
      style.href = new URL("concept-slate.css", import.meta.url).href;
      style.dataset.studioModule = "concept-slate";
      document.head.appendChild(style);
    }
    const section = createSection();
    const queue = document.getElementById("generation-queue");
    if (queue) queue.insertAdjacentElement("afterend", section);
    else portfolio.appendChild(section);
    document.getElementById("concept-refresh").addEventListener("click", refresh);
    document.getElementById("concept-generate").addEventListener("click", generate);
    document.getElementById("concept-brand").addEventListener("change", refresh);
    document.getElementById("concept-month").addEventListener("change", refresh);
    document.getElementById("connect-api")?.addEventListener("click", () => setTimeout(initializeData, 300));
    initializeData().catch((error) => {
      document.getElementById("concept-status").textContent = error.message;
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
