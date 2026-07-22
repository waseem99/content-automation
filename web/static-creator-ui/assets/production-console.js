(() => {
  const state = {
    access: null,
    brands: [],
    queue: [],
    reviews: [],
    jobs: [],
    releases: [],
    deliveries: [],
    candidates: [],
    selected: {},
    pilot: null,
    startReadiness: null,
    script: null,
    scriptContent: null,
    brandFilter: "all",
    stageFilter: "all"
  };
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  const roles = () => state.access?.roles || state.access?.operator?.roles || [];
  const isAdmin = () => roles().includes("admin") || Boolean(state.access?.operator?.is_admin);
  const hasRole = (role) => isAdmin() || roles().includes(role);

  function setConnected(connected, message = "") {
    $("connect-api").hidden = connected;
    $("logout-api").hidden = !connected;
    $("refresh-console").disabled = !connected;
    $("refresh-p100").disabled = !connected;
    $("brand-filter").disabled = !connected;
    $("status-filter").disabled = !connected;
    $("data-mode").textContent = connected ? "Database connected" : (message || "Disconnected");
    $("data-mode").className = `data-mode ${connected ? "connected" : "demo"}`;
  }

  function renderRuntime(ready, jobs = []) {
    const checks = ready?.checks || {};
    const active = jobs.filter((job) => ["queued", "running", "failed"].includes(job.status)).length;
    const cards = [
      [ready?.ok ? "Ready" : "Unavailable", "API", ready?.ok],
      [checks.database_reachable ? "Reachable" : "Unavailable", "Database", checks.database_reachable],
      [String(active), "Active queue items", true],
      ["Human-controlled", "Publishing", true]
    ];
    $("runtime-cards").innerHTML = cards.map(([value, label, good]) => `<article class="${good ? "good" : "bad"}"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></article>`).join("");
  }

  function renderSession() {
    if (!state.access) {
      $("session-summary").innerHTML = "<strong>Not signed in</strong><span>Enter your assigned operator key.</span>";
      $("operator-badge").innerHTML = "<strong>Sign in required</strong><span>No data loaded</span>";
      return;
    }
    const operator = state.access.operator || state.access;
    const roleText = roles().join(", ") || "read-only";
    $("session-summary").innerHTML = `<strong>${escapeHtml(operator.display_name || operator.operator_id)}</strong><span>${escapeHtml(roleText)}</span>`;
    $("operator-badge").innerHTML = `<strong>${escapeHtml(operator.display_name || operator.operator_id)}</strong><span>${escapeHtml(state.brands.length)} assigned brand(s) · ${escapeHtml(roleText)}</span>`;
  }

  function filteredQueue() {
    return state.queue.filter((item) => (state.brandFilter === "all" || item.brand_id === state.brandFilter) && (state.stageFilter === "all" || item.stage === state.stageFilter));
  }

  function renderPortfolio() {
    const items = filteredQueue();
    const stageCounts = state.queue.reduce((acc, item) => ({ ...acc, [item.stage]: (acc[item.stage] || 0) + 1 }), {});
    $("portfolio-metrics").innerHTML = [
      [state.brands.length, "assigned brands"],
      [state.queue.length, "content items"],
      [state.reviews.length, "review tasks"],
      [state.jobs.filter((job) => ["queued", "running"].includes(job.status)).length, "queued / running jobs"]
    ].map(([value, label]) => `<article><strong>${value}</strong><span>${label}</span></article>`).join("");

    const selected = state.brands.find((brand) => brand.id === state.brandFilter);
    $("brand-summary").innerHTML = selected
      ? `<p class="eyebrow dark-eyebrow">Selected brand</p><h3>${escapeHtml(selected.display_name)}</h3><p>${escapeHtml(selected.niche)}</p><dl><div><dt>Platform</dt><dd>${escapeHtml(selected.primary_platform)}</dd></div><div><dt>Target</dt><dd>${escapeHtml(selected.monthly_target)} monthly</dd></div><div><dt>Queue</dt><dd>${state.queue.filter((item) => item.brand_id === selected.id).length} items</dd></div></dl>`
      : `<p class="eyebrow dark-eyebrow">Portfolio</p><h3>${state.brands.length} assigned brand(s)</h3><p>Stages: ${Object.entries(stageCounts).map(([key, value]) => `${escapeHtml(key)} ${value}`).join(" · ") || "no content"}</p><p>Only database-backed records are displayed.</p>`;

    $("content-queue").innerHTML = items.length ? items.map((item) => `<tr><td>${escapeHtml(item.scheduled_for || "—")}</td><td><strong>${escapeHtml(item.brand_name || "Brand")}</strong><span>${escapeHtml(item.title)}</span></td><td>${escapeHtml(item.format)}</td><td><span class="stage-pill ${escapeHtml(item.stage)}">${escapeHtml(item.stage)}</span></td><td>${item.has_voiceover_artifact ? "VO" : "VO pending"} · ${item.has_preview_artifact ? "preview" : "preview pending"}</td><td><button type="button" class="table-action" data-open-script="${escapeHtml(item.id)}">Review script</button></td></tr>`).join("") : '<tr><td colspan="6" class="empty-row">No content matches the selected filters.</td></tr>';
  }

  function renderCompact(targetId, items, formatter, emptyText) {
    $(targetId).innerHTML = items.length ? items.slice(0, 12).map(formatter).join("") : `<p>${escapeHtml(emptyText)}</p>`;
  }

  function renderTeamWork() {
    $("review-count").textContent = String(state.reviews.length);
    $("job-count").textContent = String(state.jobs.length);
    renderCompact("review-inbox-summary", state.reviews, (item) => {
      const contentId = item.portfolio_content_id || item.content_id || item.subject_content_id || "";
      return `<div class="compact-item"><strong>${escapeHtml(item.title || item.item_type || "Review item")}</strong><span>${escapeHtml(item.brand_name || item.brand_id || "")}</span><small>${escapeHtml(item.stage || "")} · ${escapeHtml(item.status || "pending")}${item.overdue ? " · overdue" : ""}</small>${contentId ? `<button type="button" class="inline-action" data-open-script="${escapeHtml(contentId)}">Open script</button>` : ""}</div>`;
    }, "No assigned review tasks.");
    renderCompact("job-summary", state.jobs, (job) => `<div class="compact-item"><strong>${escapeHtml(job.job_type)} · ${escapeHtml(job.status)}</strong><span>${escapeHtml(job.provider || "local")}${job.model_id ? ` / ${escapeHtml(job.model_id)}` : ""}</span><small>${escapeHtml(job.worker_id || "unclaimed")} · attempt ${escapeHtml(job.attempt_count || 0)}</small></div>`, "No generation jobs.");
  }

  function scriptCurrent(data) {
    if (!data?.document) return { document: null, version: null, sections: [], claims: [], sources: [], actions: [] };
    const currentId = String(data.document.current_version_id || "");
    return {
      document: data.document,
      version: (data.versions || []).find((row) => String(row.id) === currentId) || null,
      sections: (data.sections || []).filter((row) => String(row.script_version_id) === currentId),
      claims: (data.claims || []).filter((row) => String(row.script_version_id) === currentId),
      sources: (data.sources || []).filter((row) => String(row.script_version_id) === currentId),
      actions: (data.review_actions || []).filter((row) => String(row.script_version_id) === currentId && !row.resolved_at)
    };
  }

  function renderScriptDialog(message = "") {
    const target = $("script-dialog-body");
    const item = state.scriptContent;
    if (!state.script) {
      target.innerHTML = `<header class="script-dialog-head"><div><p class="eyebrow dark-eyebrow">Script production</p><h2>${escapeHtml(item?.title || "Content script")}</h2><p>${escapeHtml(item?.brand_name || "")}</p></div></header><div class="notice ${message ? "bad" : ""}">${escapeHtml(message || "No versioned script exists for this content item yet.")}</div>${hasRole("producer") ? '<button type="button" data-script-action="generate">Generate with local model</button>' : '<p>A Producer must generate the first draft.</p>'}`;
      return;
    }
    const current = scriptCurrent(state.script);
    const status = current.document?.current_version_status || current.version?.status || "unknown";
    const unsupported = current.claims.filter((claim) => claim.support_status !== "supported" && claim.support_status !== "not_applicable");
    const sectionHtml = current.sections.map((row) => `<article><strong>${escapeHtml(row.section_type)}</strong><p>${escapeHtml(row.text)}</p></article>`).join("") || "<p>No script sections.</p>";
    const claimsHtml = current.claims.map((row) => `<li class="${row.support_status === "supported" ? "good-text" : "warn-text"}"><strong>${escapeHtml(row.support_status)}</strong> ${escapeHtml(row.claim_text)}</li>`).join("") || "<li>No factual claims recorded.</li>";
    const sourcesHtml = current.sources.map((row) => `<li><strong>${escapeHtml(row.title)}</strong>${row.publisher ? ` · ${escapeHtml(row.publisher)}` : ""}</li>`).join("") || "<li>No sources attached.</li>";
    const actions = [];
    if (hasRole("producer") && status === "working") actions.push('<button type="button" data-script-action="submit">Submit for review</button>');
    if (hasRole("producer") && ["changes_requested", "rejected"].includes(status)) actions.push('<button type="button" data-script-action="revise">Create revision</button>');
    if (hasRole("reviewer") && status === "in_review") {
      actions.push('<button type="button" data-script-action="approve">Approve exact version</button>');
      actions.push('<button type="button" class="secondary" data-script-action="changes">Request changes</button>');
      actions.push('<button type="button" class="danger" data-script-action="reject">Reject</button>');
    }
    target.innerHTML = `<header class="script-dialog-head"><div><p class="eyebrow dark-eyebrow">${escapeHtml(item?.brand_name || "Script review")}</p><h2>${escapeHtml(current.document?.title || item?.title || "Content script")}</h2><p>Version ${escapeHtml(current.document?.current_version || current.version?.version || "?")} · <strong>${escapeHtml(status.replaceAll("_", " "))}</strong></p></div></header>${message ? `<div class="notice bad">${escapeHtml(message)}</div>` : ""}<div class="script-review-layout"><section><h3>Narration sections</h3>${sectionHtml}</section><aside><h3>Evidence gate</h3><p>${unsupported.length ? `${unsupported.length} claim(s) still require support.` : "All recorded claims are supported."}</p><ul>${claimsHtml}</ul><h4>Sources</h4><ul>${sourcesHtml}</ul>${current.actions.length ? `<p class="warn-text">${current.actions.length} open review action(s) block approval.</p>` : ""}</aside></div><label class="review-rationale">Review rationale<textarea id="script-rationale" rows="3" placeholder="Record a specific decision rationale."></textarea></label><div class="script-actions">${actions.join("") || "<span>No action is available for your role at this status.</span>"}</div>`;
  }

  async function openScript(contentId) {
    state.scriptContent = state.queue.find((item) => String(item.id) === String(contentId)) || { id: contentId, title: "Content script" };
    state.script = null;
    renderScriptDialog();
    if (!$("script-review-dialog").open) $("script-review-dialog").showModal();
    try {
      state.script = await window.PortfolioApi.scriptForContent(contentId);
      renderScriptDialog();
    } catch (error) {
      if (error.status !== 404) renderScriptDialog(error.message);
    }
  }

  async function runScriptAction(action) {
    const contentId = state.scriptContent?.id;
    const current = scriptCurrent(state.script);
    const documentId = current.document?.id;
    const lockVersion = Number(current.document?.lock_version || 0);
    const rationale = $("script-rationale")?.value.trim() || "";
    try {
      if (action === "generate") {
        await window.PortfolioApi.ensureWorkflow(contentId);
        const modelId = document.querySelector('meta[name="content-local-model-id"]')?.content || "qwen2.5:7b";
        state.script = await window.PortfolioApi.initializeScript(contentId, {
          platform: "facebook", format: state.scriptContent?.format || "vertical_short", language: "en-US",
          target_duration_seconds: 45, words_per_minute: 150, duration_tolerance_percent: 10,
          seed: 20260801, adapter_mode: "local_model", local_model_id: modelId, local_timeout_seconds: 120
        });
      } else if (action === "submit") {
        state.script = await window.PortfolioApi.submitScript(documentId, { expected_lock_version: lockVersion });
      } else if (action === "revise") {
        const reason = rationale || window.prompt("Revision reason:", "Address the recorded review feedback.");
        if (!reason) return;
        state.script = await window.PortfolioApi.reviseScript(documentId, { expected_lock_version: lockVersion, reason });
      } else {
        if (rationale.length < 10) throw new Error("Add a specific rationale of at least 10 characters.");
        const decision = { approve: "approved", changes: "changes_requested", reject: "rejected" }[action];
        state.script = await window.PortfolioApi.decideScript(documentId, { expected_lock_version: lockVersion, decision, rationale });
      }
      renderScriptDialog();
      await refreshAll();
    } catch (error) {
      renderScriptDialog(error.message);
    }
  }

  function organizeAdvancedTools() {
    const portfolio = $("portfolio-studio");
    const mount = $("advanced-tools-mount");
    if (!portfolio || !mount) return;
    const core = new Set(["team-work", "release-operations", "p100-console", "advanced-tools"]);
    const move = () => [...portfolio.children].forEach((node) => {
      if (node.tagName === "SECTION" && node.id && !core.has(node.id)) mount.appendChild(node);
    });
    move();
    new MutationObserver(move).observe(portfolio, { childList: true });
  }

  function renderOperations(runtime, analytics) {
    $("release-count").textContent = String(state.releases.length);
    $("delivery-count").textContent = String(state.deliveries.length);
    renderCompact("release-summary", state.releases, (release) => `<div class="compact-item"><strong>${escapeHtml(release.title || release.release_key || release.id)}</strong><span>${escapeHtml(release.status)} · v${escapeHtml(release.version || 1)}</span><small>${escapeHtml(release.platform || release.profile_key || "release package")}</small></div>`, "No final releases yet.");
    renderCompact("delivery-summary", state.deliveries, (delivery) => `<div class="compact-item"><strong>${escapeHtml(delivery.platform)} · ${escapeHtml(delivery.status)}</strong><span>${escapeHtml(delivery.target_key || delivery.platform_reference || "simulated target")}</span><small>${escapeHtml(delivery.scheduled_for || delivery.created_at || "")}</small></div>`, "No simulated delivery requests.");
    $("analytics-status").textContent = analytics?.ok ? "Ready" : "No data";
    $("analytics-summary").innerHTML = analytics?.ok ? `<div class="compact-item"><strong>${escapeHtml(analytics.brand_name || "Selected brand")}</strong><span>${escapeHtml(analytics.item_count || analytics.observation_count || 0)} observed item(s)</span><small>Recommendations remain advisory only.</small></div>` : "<p>No performance observations for the selected brand.</p>";
    $("ops-status").textContent = runtime?.ok ? "Ready" : "Blocked";
    $("operations-summary").innerHTML = `<div class="compact-item"><strong>Environment: ${escapeHtml(runtime?.release?.environment || "local")}</strong><span>Migration: ${escapeHtml(runtime?.release?.migration_head || "unknown")}</span><small>Database ${runtime?.checks?.database_reachable ? "reachable" : "unavailable"}; automatic publishing disabled.</small></div>`;
  }

  function candidateChoice(candidate, mode) {
    const report = candidate.modes?.[mode] || {};
    const selected = state.selected[candidate.brand_slug]?.[mode] === candidate.portfolio_content_id;
    const inputName = `p100-${candidate.brand_slug}-${mode}`;
    const blockers = [...(report.selection_blockers || []), ...(report.mode_blockers || [])];
    return `<label class="p100-choice ${report.selection_ready ? "" : "blocked"}"><input type="radio" name="${escapeHtml(inputName)}" value="${escapeHtml(candidate.portfolio_content_id)}" data-p100-brand="${escapeHtml(candidate.brand_slug)}" data-p100-mode="${escapeHtml(mode)}" data-p100-version="${escapeHtml(candidate.content_version)}" ${selected ? "checked" : ""} ${report.selection_ready ? "" : "disabled"}><span><strong>${escapeHtml(candidate.title)}</strong><small>${escapeHtml(mode.replaceAll("_", " "))} · ${report.selection_ready ? "selectable" : blockers.join(", ") || "blocked"}</small></span></label>`;
  }

  function renderP100() {
    const byBrand = Object.groupBy ? Object.groupBy(state.candidates, (item) => item.brand_slug) : state.candidates.reduce((acc, item) => { (acc[item.brand_slug] ||= []).push(item); return acc; }, {});
    $("p100-candidates").innerHTML = ["animal-x", "rawr-nation"].map((slug) => {
      const candidates = byBrand[slug] || [];
      return `<section class="p100-brand"><h4>${escapeHtml(candidates[0]?.brand_name || slug)}</h4><div class="p100-grid"><div><strong>Local item</strong>${candidates.slice(0, 10).map((item) => candidateChoice(item, "local_only")).join("") || "<p>No candidates.</p>"}</div><div><strong>Managed item</strong>${candidates.slice(0, 10).map((item) => candidateChoice(item, "managed_render")).join("") || "<p>No candidates.</p>"}</div></div></section>`;
    }).join("");
    const chosen = Object.values(state.selected).flatMap((value) => Object.values(value || {})).filter(Boolean);
    $("bootstrap-p100").disabled = !isAdmin() || chosen.length !== 4 || new Set(chosen).size !== 4;
    if (!state.candidates.length) $("p100-status").textContent = "No candidate inventory is available yet.";
  }

  function renderPilot() {
    if (!state.pilot) {
      $("start-p100").disabled = true;
      $("p100-readiness").innerHTML = "";
      return;
    }
    const readiness = state.startReadiness;
    $("p100-status").className = `notice ${readiness?.ready_to_start || readiness?.already_running ? "good" : "bad"}`;
    $("p100-status").textContent = readiness?.already_running ? "Pilot is running." : readiness?.ready_to_start ? "Controlled draft is ready to start." : `Draft blockers: ${(readiness?.blockers || []).map((item) => item.code).join(", ") || "loading"}`;
    $("start-p100").disabled = !isAdmin() || !readiness?.ready_to_start || readiness?.already_running;
    $("p100-readiness").innerHTML = `<div class="compact-item"><strong>${escapeHtml(state.pilot.pilot_key || state.pilot.id)}</strong><span>Status: ${escapeHtml(state.pilot.status)}</span><small>${escapeHtml(readiness?.blockers?.length || 0)} start blocker(s)</small></div>`;
  }

  async function loadReleases() {
    if (isAdmin()) return (await window.PortfolioApi.releases(null, 100)).items || [];
    const results = await Promise.allSettled(state.queue.slice(0, 25).map((item) => window.PortfolioApi.releases(item.id, 20)));
    return results.flatMap((result) => result.status === "fulfilled" ? (result.value.items || []) : []);
  }

  async function refreshAll() {
    if (!window.PortfolioApi?.configured()) return;
    $("refresh-console").disabled = true;
    try {
      const [ready, access, brands, queue, reviews, jobs, observability] = await Promise.all([
        window.PortfolioApi.runtimeReady(),
        window.PortfolioApi.access(),
        window.PortfolioApi.brands(),
        window.PortfolioApi.queue(),
        window.PortfolioApi.reviewInbox({ limit: 100 }),
        window.PortfolioApi.generationJobs({ limit: 100 }),
        window.PortfolioApi.runtimeObservability()
      ]);
      state.access = access;
      state.brands = brands.brands || [];
      $("brand-filter").innerHTML = '<option value="all">All assigned brands</option>' + state.brands.map((brand) => `<option value="${escapeHtml(brand.id)}">${escapeHtml(brand.display_name)}</option>`).join("");
      if (state.brandFilter !== "all" && !state.brands.some((brand) => brand.id === state.brandFilter)) state.brandFilter = "all";
      $("brand-filter").value = state.brandFilter;
      state.queue = queue.items || [];
      state.reviews = reviews.items || [];
      state.jobs = jobs.items || [];
      state.releases = await loadReleases();
      state.deliveries = roles().includes("publisher") || isAdmin() ? ((await window.PortfolioApi.deliveries([], 100)).items || []) : [];
      const selectedBrand = state.brandFilter !== "all" ? state.brandFilter : state.brands[0]?.id;
      let analytics = null;
      if (selectedBrand) analytics = await window.PortfolioApi.performanceDashboard(selectedBrand).catch(() => null);
      renderRuntime(ready, state.jobs);
      renderSession();
      renderPortfolio();
      renderTeamWork();
      renderOperations({ ...ready, observability }, analytics);
      setConnected(true);
    } catch (error) {
      setConnected(false, `Connection failed: ${error.message}`);
      $("runtime-cards").innerHTML = `<article class="bad"><strong>Blocked</strong><span>${escapeHtml(error.message)}</span></article>`;
      throw error;
    } finally {
      $("refresh-console").disabled = !window.PortfolioApi?.configured();
    }
  }

  async function refreshP100() {
    if (!window.PortfolioApi?.configured()) return;
    try {
      const payload = await window.PortfolioApi.acceptanceCandidates(50);
      state.candidates = payload.candidates || [];
      $("p100-status").className = "notice";
      $("p100-status").textContent = payload.ready_to_select_four_production_complete_items ? "Four production-complete items are available." : "Candidate inventory loaded. Resolve the displayed blockers before bootstrap.";
      renderP100();
      const saved = window.PortfolioApi.savedPilotId();
      if (saved) {
        const [detail, readiness] = await Promise.all([window.PortfolioApi.pilot(saved), window.PortfolioApi.pilotStartReadiness(saved)]);
        state.pilot = detail.pilot;
        state.startReadiness = readiness;
        renderPilot();
      }
    } catch (error) {
      $("p100-status").className = "notice bad";
      $("p100-status").textContent = `P100 inventory failed: ${error.message}`;
    }
  }

  async function signIn(key) {
    window.PortfolioApi.connect(window.location.origin, key);
    await refreshAll();
    await refreshP100();
  }

  function openLogin() {
    $("login-error").textContent = "";
    $("operator-key").value = "";
    $("operator-login").showModal();
    $("operator-key").focus();
  }

  function bind() {
    $("connect-api").addEventListener("click", openLogin);
    $("cancel-login").addEventListener("click", () => $("operator-login").close());
    $("operator-login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await signIn($("operator-key").value);
        $("operator-login").close();
      } catch (error) {
        window.PortfolioApi.disconnect();
        $("login-error").textContent = error.message;
      }
    });
    $("logout-api").addEventListener("click", () => { window.PortfolioApi.disconnect(); location.reload(); });
    $("refresh-console").addEventListener("click", () => refreshAll().catch(() => {}));
    $("refresh-p100").addEventListener("click", refreshP100);
    $("brand-filter").addEventListener("change", async (event) => { state.brandFilter = event.target.value; renderPortfolio(); const brand = state.brandFilter !== "all" ? state.brandFilter : state.brands[0]?.id; if (brand) renderOperations(null, await window.PortfolioApi.performanceDashboard(brand).catch(() => null)); });
    $("status-filter").addEventListener("change", (event) => { state.stageFilter = event.target.value; renderPortfolio(); });
    $("content-queue").addEventListener("click", (event) => {
      const button = event.target.closest("[data-open-script]");
      if (button) void openScript(button.dataset.openScript);
    });
    $("review-inbox-summary").addEventListener("click", (event) => {
      const button = event.target.closest("[data-open-script]");
      if (button) void openScript(button.dataset.openScript);
    });
    $("script-dialog-body").addEventListener("click", (event) => {
      const button = event.target.closest("[data-script-action]");
      if (button) void runScriptAction(button.dataset.scriptAction);
    });
    $("script-review-dialog").addEventListener("click", (event) => { if (event.target === $("script-review-dialog")) $("script-review-dialog").close(); });
    $("p100-candidates").addEventListener("change", (event) => {
      if (!event.target.matches("[data-p100-brand]")) return;
      const brand = event.target.dataset.p100Brand;
      const mode = event.target.dataset.p100Mode;
      state.selected[brand] ||= {};
      state.selected[brand][mode] = event.target.value;
      state.selected[brand][`${mode}_version`] = Number(event.target.dataset.p100Version);
      renderP100();
    });
    $("bootstrap-p100").addEventListener("click", async () => {
      const selections = ["animal-x", "rawr-nation"].flatMap((brand) => ["local_only", "managed_render"].map((mode) => ({ brand, mode, id: state.selected[brand]?.[mode], version: state.selected[brand]?.[`${mode}_version`] })));
      if (selections.some((item) => !item.id)) return;
      const payload = {
        pilot_key: $("p100-key").value.trim(),
        acceptance_policy: { local_runtime: true, managed_renderer_pending: true },
        items: selections.map((item, index) => ({ portfolio_content_id: item.id, content_version: item.version, production_mode: item.mode, live_delivery_evidence_required: index === 0 }))
      };
      try {
        const result = await window.PortfolioApi.bootstrapPilot(payload);
        state.pilot = result.pilot;
        window.PortfolioApi.savePilotId(result.pilot.id);
        state.startReadiness = await window.PortfolioApi.pilotStartReadiness(result.pilot.id);
        renderPilot();
      } catch (error) {
        $("p100-status").className = "notice bad";
        $("p100-status").textContent = `Bootstrap failed: ${error.message}`;
      }
    });
    $("start-p100").addEventListener("click", async () => {
      if (!state.pilot || !state.startReadiness) return;
      try {
        const result = await window.PortfolioApi.controlledStartPilot(state.pilot.id, { bootstrap_request_sha256: state.startReadiness.bootstrap_request_sha256, runbook_sha256: state.startReadiness.runbook_sha256 });
        state.pilot = result.pilot;
        state.startReadiness = await window.PortfolioApi.pilotStartReadiness(state.pilot.id);
        renderPilot();
      } catch (error) {
        $("p100-status").className = "notice bad";
        $("p100-status").textContent = `Start failed: ${error.message}`;
      }
    });
  }

  async function start() {
    organizeAdvancedTools();
    bind();
    setConnected(false);
    if (window.PortfolioApi?.configured()) {
      try {
        await refreshAll();
        await refreshP100();
        return;
      } catch (_error) {
        window.PortfolioApi.disconnect();
      }
    }
    renderSession();
    openLogin();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
