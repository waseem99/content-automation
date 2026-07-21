(() => {
  const STATUS_VALUES = ["", "queued", "running", "failed", "dead_letter", "cancelled", "succeeded"];
  const TYPE_VALUES = ["", "concept", "script", "narration", "keyframe", "preview", "premium_clip", "assembly", "caption", "thumbnail", "package", "publishing"];
  const state = { brands: [], items: [] };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  }

  function formatCost(value) {
    const amount = Number(value || 0);
    return Number.isFinite(amount) ? `$${amount.toFixed(4)}` : "$0.0000";
  }

  function makeSelect(id, label, values) {
    const wrapper = element("label", "generation-filter");
    wrapper.appendChild(element("span", "", label));
    const select = document.createElement("select");
    select.id = id;
    values.forEach(([value, text]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    });
    wrapper.appendChild(select);
    return wrapper;
  }

  function createSection() {
    const section = element("section", "generation-queue-section");
    section.id = "generation-queue";
    section.setAttribute("aria-labelledby", "generation-queue-heading");

    const heading = element("div", "generation-queue-heading");
    const title = element("div");
    title.appendChild(element("p", "eyebrow dark-eyebrow", "Worker Orchestration"));
    const h3 = element("h3", "", "Generation and delivery queue");
    h3.id = "generation-queue-heading";
    title.appendChild(h3);
    title.appendChild(element("p", "", "Read-only visibility into idempotent jobs, active leases, retries, costs, dependencies, and retained attempts."));
    heading.appendChild(title);
    const refresh = element("button", "secondary", "Refresh queue");
    refresh.id = "generation-queue-refresh";
    refresh.type = "button";
    heading.appendChild(refresh);
    section.appendChild(heading);

    const metrics = element("div", "generation-queue-metrics");
    metrics.id = "generation-queue-metrics";
    section.appendChild(metrics);

    const filters = element("div", "generation-queue-filters");
    filters.appendChild(makeSelect("generation-brand-filter", "Brand", [["", "All assigned brands"]]));
    filters.appendChild(makeSelect("generation-status-filter", "Status", STATUS_VALUES.map((value) => [value, value ? value.replaceAll("_", " ") : "All statuses"])));
    filters.appendChild(makeSelect("generation-type-filter", "Job type", TYPE_VALUES.map((value) => [value, value ? value.replaceAll("_", " ") : "All job types"])));
    const worker = element("label", "generation-filter");
    worker.appendChild(element("span", "", "Worker"));
    const workerInput = document.createElement("input");
    workerInput.id = "generation-worker-filter";
    workerInput.placeholder = "operator or worker ID";
    worker.appendChild(workerInput);
    filters.appendChild(worker);
    section.appendChild(filters);

    const status = element("p", "generation-queue-status", "Connect Data to inspect the queue.");
    status.id = "generation-queue-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    section.appendChild(status);

    const wrap = element("div", "table-wrap generation-table-wrap");
    const table = element("table", "content-table generation-table");
    const thead = document.createElement("thead");
    const header = document.createElement("tr");
    ["Brand / job", "Status", "Worker / lease", "Attempts", "Costs", "Dependencies", "Action"].forEach((text) => {
      header.appendChild(element("th", "", text));
    });
    thead.appendChild(header);
    table.appendChild(thead);
    const body = document.createElement("tbody");
    body.id = "generation-queue-body";
    table.appendChild(body);
    wrap.appendChild(table);
    section.appendChild(wrap);
    return section;
  }

  function createDialog() {
    const dialog = element("dialog", "generation-job-dialog");
    dialog.id = "generation-job-dialog";
    const close = element("form", "review-close-row");
    close.method = "dialog";
    const closeButton = element("button", "review-close", "×");
    closeButton.setAttribute("aria-label", "Close generation job details");
    close.appendChild(closeButton);
    dialog.appendChild(close);
    const body = element("div", "generation-job-detail");
    body.id = "generation-job-detail";
    dialog.appendChild(body);
    return dialog;
  }

  function metric(label, value, note) {
    const card = element("article", "generation-metric");
    card.appendChild(element("span", "", label));
    card.appendChild(element("strong", "", String(value)));
    card.appendChild(element("small", "", note));
    return card;
  }

  function renderMetrics(items) {
    const target = document.getElementById("generation-queue-metrics");
    target.replaceChildren();
    const running = items.filter((item) => item.status === "running").length;
    const attention = items.filter((item) => ["failed", "dead_letter"].includes(item.status)).length;
    const blocked = items.filter((item) => item.dependency_blocked).length;
    const totalCost = items.reduce((sum, item) => sum + Number(item.actual_cost_usd || 0), 0);
    target.append(
      metric("Visible jobs", items.length, "Current filters"),
      metric("Running", running, "Active worker leases"),
      metric("Needs attention", attention, "Failed or dead-letter"),
      metric("Dependency blocked", blocked, "Waiting on parent output"),
      metric("Recorded cost", formatCost(totalCost), "Visible actual cost")
    );
  }

  function statusBadge(status) {
    return element("span", `generation-status generation-status-${status}`, status.replaceAll("_", " "));
  }

  function renderRows(items) {
    const body = document.getElementById("generation-queue-body");
    body.replaceChildren();
    if (!items.length) {
      const row = document.createElement("tr");
      const cell = element("td", "generation-empty", "No jobs match the current filters.");
      cell.colSpan = 7;
      row.appendChild(cell);
      body.appendChild(row);
      return;
    }
    items.forEach((job) => {
      const row = document.createElement("tr");
      const identity = document.createElement("td");
      identity.appendChild(element("strong", "", job.brand_name || job.brand_slug || "Brand"));
      identity.appendChild(element("span", "generation-job-type", job.job_type.replaceAll("_", " ")));
      identity.appendChild(element("small", "", `Content v${job.content_version} · ${String(job.id).slice(0, 8)}`));
      row.appendChild(identity);

      const status = document.createElement("td");
      status.appendChild(statusBadge(job.status));
      if (job.error_code) status.appendChild(element("small", "generation-error-code", job.error_code));
      row.appendChild(status);

      const worker = document.createElement("td");
      worker.appendChild(element("strong", "", job.current_worker_id || "Unclaimed"));
      worker.appendChild(element("small", "", job.lease_expires_at ? `Lease: ${formatDate(job.lease_expires_at)}` : "No active lease"));
      row.appendChild(worker);

      const attempts = document.createElement("td");
      attempts.appendChild(element("strong", "", `${job.attempt_count}/${job.max_attempts}`));
      attempts.appendChild(element("small", "", job.heartbeat_at ? `Heartbeat: ${formatDate(job.heartbeat_at)}` : "No heartbeat"));
      row.appendChild(attempts);

      const costs = document.createElement("td");
      costs.appendChild(element("strong", "", formatCost(job.actual_cost_usd)));
      costs.appendChild(element("small", "", `Est. ${formatCost(job.estimated_cost_usd)} · Reserved ${formatCost(job.reserved_cost_usd)}`));
      row.appendChild(costs);

      const dependencies = document.createElement("td");
      dependencies.appendChild(element("strong", "", job.dependency_blocked ? "Blocked" : "Ready"));
      dependencies.appendChild(element("small", "", job.dependency_blocked ? "Parent output pending" : "Dependencies satisfied"));
      row.appendChild(dependencies);

      const action = document.createElement("td");
      const inspect = element("button", "secondary", "Inspect");
      inspect.type = "button";
      inspect.addEventListener("click", () => openDetail(job.id));
      action.appendChild(inspect);
      row.appendChild(action);
      body.appendChild(row);
    });
  }

  function detailBlock(title, value) {
    const block = element("section", "generation-detail-block");
    block.appendChild(element("h4", "", title));
    const pre = element("pre", "", JSON.stringify(value ?? {}, null, 2));
    block.appendChild(pre);
    return block;
  }

  async function openDetail(jobId) {
    const dialog = document.getElementById("generation-job-dialog");
    const target = document.getElementById("generation-job-detail");
    target.textContent = "Loading job history…";
    dialog.showModal();
    try {
      const payload = await window.PortfolioApi.generationJob(jobId);
      const job = payload.job;
      target.replaceChildren();
      target.appendChild(element("p", "eyebrow dark-eyebrow", "Generation Job"));
      target.appendChild(element("h2", "", `${job.brand_name || job.brand_slug} · ${job.job_type.replaceAll("_", " ")}`));
      const summary = element("div", "generation-detail-summary");
      [
        ["Status", job.status],
        ["Content version", `${job.content_version} / current ${job.current_content_version}`],
        ["Worker", job.current_worker_id || "Unclaimed"],
        ["Attempts", `${job.attempt_count}/${job.max_attempts}`],
        ["Actual cost", formatCost(job.actual_cost_usd)],
        ["Queued", formatDate(job.queued_at)]
      ].forEach(([label, value]) => summary.appendChild(metric(label, value, "")));
      target.appendChild(summary);
      if (job.error_code || job.error_message) {
        const error = element("div", "generation-detail-error");
        error.appendChild(element("strong", "", job.error_code || "Job error"));
        error.appendChild(element("p", "", job.error_message || "No error message recorded."));
        target.appendChild(error);
      }
      target.appendChild(detailBlock("Input payload", job.input_payload));
      target.appendChild(detailBlock("Output payload", job.output_payload));
      target.appendChild(detailBlock("Dependencies", payload.dependencies));
      target.appendChild(detailBlock("Attempt history", payload.attempts));
      target.appendChild(detailBlock("Lifecycle events", payload.events));
    } catch (error) {
      target.textContent = error.message;
    }
  }

  function filters() {
    return {
      brandId: document.getElementById("generation-brand-filter").value,
      status: document.getElementById("generation-status-filter").value,
      jobType: document.getElementById("generation-type-filter").value,
      workerId: document.getElementById("generation-worker-filter").value.trim(),
      limit: 200
    };
  }

  async function refresh() {
    const status = document.getElementById("generation-queue-status");
    const button = document.getElementById("generation-queue-refresh");
    if (!window.PortfolioApi?.configured()) {
      status.textContent = "Connect Data to inspect the queue.";
      renderMetrics([]);
      renderRows([]);
      return;
    }
    button.disabled = true;
    status.textContent = "Loading generation jobs…";
    try {
      const [jobs, brands] = await Promise.all([
        window.PortfolioApi.generationJobs(filters()),
        state.brands.length ? Promise.resolve({ brands: state.brands }) : window.PortfolioApi.brands()
      ]);
      state.items = jobs.items;
      state.brands = brands.brands || [];
      const brandSelect = document.getElementById("generation-brand-filter");
      if (brandSelect.options.length === 1) {
        state.brands.forEach((brand) => {
          const option = document.createElement("option");
          option.value = brand.id;
          option.textContent = brand.display_name;
          brandSelect.appendChild(option);
        });
      }
      renderMetrics(state.items);
      renderRows(state.items);
      status.textContent = `${state.items.length} job(s) visible. Last refreshed ${new Date().toLocaleTimeString()}.`;
    } catch (error) {
      status.textContent = error.message;
      renderMetrics([]);
      renderRows([]);
    } finally {
      button.disabled = false;
    }
  }

  function start() {
    if (!window.PortfolioApi || document.getElementById("generation-queue")) return;
    const portfolio = document.getElementById("portfolio-studio");
    if (!portfolio) return;
    const section = createSection();
    const reference = document.getElementById("reference-intelligence");
    if (reference) reference.insertAdjacentElement("afterend", section);
    else portfolio.appendChild(section);
    document.body.appendChild(createDialog());

    document.getElementById("generation-queue-refresh").addEventListener("click", refresh);
    ["generation-brand-filter", "generation-status-filter", "generation-type-filter"].forEach((id) => {
      document.getElementById(id).addEventListener("change", refresh);
    });
    document.getElementById("generation-worker-filter").addEventListener("keydown", (event) => {
      if (event.key === "Enter") refresh();
    });
    document.getElementById("connect-api")?.addEventListener("click", () => setTimeout(refresh, 300));
    refresh();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();