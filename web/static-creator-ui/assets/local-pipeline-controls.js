(() => {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));

  function key() {
    return String(sessionStorage.getItem("content-automation.operator-key") || "").trim();
  }

  async function request(path, options = {}) {
    const configuration = window.PortfolioApi?.configuration?.() || {};
    if (!configuration.base || !key()) throw new Error("Sign in before using local production controls.");
    const response = await fetch(`${configuration.base}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", "X-Operator-Key": key(), ...(options.headers || {}) }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      const detail = payload.detail;
      const code = typeof detail === "object" && detail ? detail.code : detail;
      throw new Error(payload.error || code || `Local production request failed (${response.status})`);
    }
    return payload;
  }

  function selectedBrand() {
    const value = $("brand-filter")?.value;
    return value && value !== "all" ? value : null;
  }

  function render(payload, message = "") {
    const target = $("local-pipeline-status");
    if (!target) return;
    if (!payload) {
      target.innerHTML = `<p>${escapeHtml(message || "Sign in to inspect the local production queue.")}</p>`;
      return;
    }
    const eligible = payload.eligible || {};
    const jobs = payload.jobs || [];
    const active = jobs.reduce((sum, row) => sum + Number(row.count || 0), 0);
    const supervisor = payload.supervisor || {};
    const supervisorText = supervisor.healthy ? `Supervisor healthy · heartbeat ${escapeHtml(supervisor.age_seconds || 0)}s ago` : `Supervisor ${escapeHtml(supervisor.reason || "not healthy")}`;
    target.innerHTML = `${message ? `<div class="notice good">${escapeHtml(message)}</div>` : ""}<div class="compact-item"><strong>${escapeHtml(eligible.scripts || 0)} script draft(s) ready to queue</strong><span>${escapeHtml(eligible.audio || 0)} approved script(s) need audio · ${escapeHtml(eligible.visuals || 0)} need local visuals</span><small>${escapeHtml(active)} active/recoverable local queue item(s) · ComfyUI ${payload.capabilities?.comfyui_configured ? "configured" : "not configured"} · ${supervisorText}</small></div>`;
  }

  async function refresh() {
    if (!window.PortfolioApi?.configured()) return render(null);
    try {
      render(await request("/local-production/status"));
    } catch (error) {
      render(null, error.message);
    }
  }

  async function run(action) {
    const limit = Math.max(1, Math.min(20, Number($("local-batch-limit")?.value || 5)));
    const payload = { limit, brand_id: selectedBrand() };
    const button = $(action === "scripts" ? "queue-more-scripts" : "continue-approved-local");
    if (button) button.disabled = true;
    try {
      let result;
      if (action === "scripts") {
        result = await request("/local-production/enqueue-scripts", { method: "POST", body: JSON.stringify(payload) });
        await refresh();
        render(await request("/local-production/status"), `${result.enqueued?.length || 0} script job(s) queued. Existing jobs were reused safely.`);
      } else {
        result = await request("/local-production/continue-approved", { method: "POST", body: JSON.stringify({ ...payload, include_audio: true, include_visuals: true }) });
        await refresh();
        render(await request("/local-production/status"), `${result.audio_initialized?.length || 0} audio production(s) and ${result.visuals_initialized?.length || 0} visual project(s) queued. ${result.blocked?.length || 0} item(s) remain blocked.`);
      }
      $("refresh-console")?.click();
    } catch (error) {
      render(null, error.message);
    } finally {
      if (button) button.disabled = false;
    }
  }

  function bind() {
    $("queue-more-scripts")?.addEventListener("click", () => run("scripts"));
    $("continue-approved-local")?.addEventListener("click", () => run("approved"));
    $("refresh-local-pipeline")?.addEventListener("click", refresh);
    $("connect-api")?.addEventListener("click", () => setTimeout(refresh, 1000));
    $("refresh-console")?.addEventListener("click", () => setTimeout(refresh, 200));
    $("brand-filter")?.addEventListener("change", refresh);
    setInterval(() => { if (window.PortfolioApi?.configured()) void refresh(); }, 15000);
    void refresh();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind, { once: true });
  else bind();
})();
