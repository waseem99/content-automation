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
  const money = (value, currency = "USD") => `${currency} ${Number(value || 0).toFixed(2)}`;
  const status = (message) => { document.getElementById("routing-spend-status").textContent = message; };
  const guarded = (task) => Promise.resolve().then(task).catch((error) => status(error.message));

  function panel() {
    const section = make("section", "routing-spend-section");
    section.id = "routing-spend-studio";
    section.innerHTML = `
      <div class="routing-spend-heading"><div>
        <p class="eyebrow dark-eyebrow">Shot Routing & Spend</p>
        <h3>Route alternatives, approval ceiling, and actual cost evidence</h3>
        <p>Managed jobs remain blocked until local visual approval, renderer preflight, and spend approval all match.</p>
      </div></div>
      <div class="routing-spend-controls">
        <label><span>Content UUID</span><input id="routing-spend-content" autocomplete="off"></label>
        <button id="routing-spend-load" class="secondary" type="button">Load current plan</button>
      </div>
      <p id="routing-spend-status" class="routing-spend-status" role="status">Connect Data and enter a content UUID with a routing plan.</p>
      <div id="routing-spend-summary"></div>
      <div id="routing-spend-decision"></div>
      <div id="routing-spend-grid" class="routing-spend-grid"></div>`;
    return section;
  }

  function badge(value) {
    return make("span", `routing-spend-badge ${value || "unknown"}`, String(value || "unknown").replaceAll("_", " "));
  }

  function metric(label, value) {
    const node = make("div", "routing-spend-metric");
    node.append(make("span", "routing-spend-muted", label), make("strong", "", value));
    return node;
  }

  function contentId() {
    const value = document.getElementById("routing-spend-content").value.trim();
    if (!value) throw new Error("Enter a content UUID.");
    return value;
  }

  function reservationFor(itemId) {
    return (state.data?.reservations || []).find((row) => String(row.routing_item_id) === String(itemId));
  }

  function renderDecision() {
    const root = document.getElementById("routing-spend-decision");
    root.replaceChildren();
    if (!state.data || state.data.plan.status !== "in_review" || !isReviewer()) return;
    const wrap = make("div", "routing-spend-decision");
    wrap.innerHTML = `
      <label><span>Approved ceiling</span><input id="routing-spend-ceiling" type="number" min="0" step="0.01" value="${Number(state.data.plan.total_estimated_cost || 0).toFixed(2)}"></label>
      <label><span>Decision rationale</span><textarea id="routing-spend-rationale" rows="2">Reviewed routes, exact renderer quotes, and monthly budget impact.</textarea></label>`;
    const actions = make("div", "routing-spend-actions");
    [
      ["Approve ceiling", "approved"],
      ["Request changes", "changes_requested"],
      ["Reject", "rejected"]
    ].forEach(([label, decision]) => {
      const button = make("button", decision === "approved" ? "" : "secondary", label);
      button.type = "button";
      button.addEventListener("click", () => guarded(() => decide(decision)));
      actions.append(button);
    });
    wrap.append(actions);
    root.append(wrap);
  }

  function render() {
    const summary = document.getElementById("routing-spend-summary");
    const grid = document.getElementById("routing-spend-grid");
    summary.replaceChildren();
    grid.replaceChildren();
    renderDecision();
    if (!state.data) return;

    const plan = state.data.plan;
    const latestDecision = (state.data.decisions || []).at(-1);
    const metrics = make("div", "routing-spend-metrics");
    metrics.append(
      metric("Plan", `v${plan.version} · ${String(plan.status).replaceAll("_", " ")}`),
      metric("Expected", money(plan.total_estimated_cost, plan.currency)),
      metric("Approved ceiling", latestDecision?.approved_ceiling == null ? "Pending" : money(latestDecision.approved_ceiling, plan.currency)),
      metric("Monthly soft / hard", `${money(plan.monthly_soft_limit, plan.currency)} / ${money(plan.monthly_hard_limit, plan.currency)}`),
      metric("Routes", `${plan.managed_shot_count} managed · ${plan.local_shot_count} local · ${plan.manual_shot_count} manual`)
    );
    const heading = make("div", "routing-spend-summary");
    const title = make("div");
    title.append(make("h4", "", `${plan.title} · ${plan.brand_name}`));
    const evidence = make("p");
    evidence.append(badge(plan.status), document.createTextNode(` · content v${plan.content_version} · lock ${plan.lock_version}`));
    title.append(evidence, make("small", "routing-spend-muted", "Reservations count before job submission; actuals and overage are retained after completion."));
    heading.append(title);
    summary.append(heading, metrics);

    (state.data.items || []).forEach((item) => {
      const card = make("article", "routing-spend-card");
      const titleRow = make("div", "routing-spend-summary");
      titleRow.append(make("h4", "", `Shot ${item.sequence}`), badge(item.route));
      card.append(titleRow, make("p", "", item.rationale));
      card.append(make("p", "", `Estimate: ${money(item.estimated_cost, plan.currency)}`));
      if (item.provider_key) {
        card.append(make("p", "", `${item.provider_key}/${item.model_key} · quality ${Number(item.quality_rating || 0).toFixed(0)} · ${item.health_status}`));
      }
      card.append(make("small", "routing-spend-muted", `Hero ${item.hero_importance} · realism ${item.realism_requirement} · motion ${item.motion_complexity} · local quality ${item.local_preview_quality}`));
      const alternatives = make("ul");
      (item.alternatives || []).forEach((alternative) => alternatives.append(make("li", "", `${String(alternative.route).replaceAll("_", " ")}: ${alternative.reason}`)));
      if (alternatives.children.length) card.append(make("strong", "", "Alternatives"), alternatives);

      const reservation = reservationFor(item.id);
      if (reservation) {
        const reservationText = make("p");
        reservationText.append(
          badge(reservation.status),
          document.createTextNode(` · reserved ${money(reservation.reserved_amount, plan.currency)} · actual ${money(reservation.actual_amount, plan.currency)}`)
        );
        card.append(reservationText);
        if (Number(reservation.overage_amount || 0) > 0) card.append(make("p", "routing-spend-warning", `Overage: ${money(reservation.overage_amount, plan.currency)}`));
        if (reservation.soft_limit_exceeded) card.append(make("p", "routing-spend-warning", "Monthly soft limit warning recorded."));
        if (reservation.job_status) card.append(make("small", "routing-spend-muted", `Job: ${reservation.job_status}`));
      } else if (item.route === "managed_render" && plan.status === "approved" && isProducer()) {
        const actions = make("div", "routing-spend-actions");
        const button = make("button", "", "Reserve & enqueue managed shot");
        button.type = "button";
        button.addEventListener("click", () => guarded(() => enqueue(item.id)));
        actions.append(button);
        card.append(actions);
      }
      grid.append(card);
    });
  }

  async function refreshAccess() {
    if (!window.PortfolioApi.configured()) { state.roles = []; state.data = null; render(); return; }
    const result = await window.PortfolioApi.access();
    state.roles = result.roles || result.operator?.roles || [];
    render();
  }

  async function load() {
    state.data = await window.PortfolioApi.currentRouting(contentId());
    render();
    status("Exact routing, quote, decision, reservation, and actual-cost evidence loaded.");
  }

  async function decide(decision) {
    const rationale = document.getElementById("routing-spend-rationale").value.trim();
    const ceilingValue = document.getElementById("routing-spend-ceiling").value;
    state.data = await window.PortfolioApi.decideRouting(state.data.plan.id, {
      expected_lock_version: state.data.plan.lock_version,
      decision,
      approved_ceiling: decision === "approved" ? ceilingValue : null,
      rationale
    });
    render();
    status(`Spend decision recorded: ${decision.replaceAll("_", " ")}.`);
  }

  async function enqueue(routingItemId) {
    state.data = await window.PortfolioApi.enqueueManagedRoute(state.data.plan.id, {
      routing_item_id: routingItemId,
      max_attempts: 3
    });
    await load();
    status("Spend reserved and managed job enqueued through the unified job queue.");
  }

  async function start() {
    if (!window.PortfolioApi || document.getElementById("routing-spend-studio")) return;
    const root = document.getElementById("portfolio-studio");
    if (!root) return;
    const view = panel();
    const anchor = document.getElementById("visual-candidate-studio") || document.getElementById("review-workspace-studio");
    if (anchor) anchor.insertAdjacentElement("afterend", view); else root.append(view);
    document.getElementById("routing-spend-load").addEventListener("click", () => guarded(load));
    document.getElementById("connect-api")?.addEventListener("click", () => setTimeout(() => guarded(refreshAccess), 300));
    await refreshAccess();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => void start(), { once: true }); else void start();
})();
