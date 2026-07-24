(() => {
  let access = null;
  let busy = false;
  const $ = (selector, root = document) => root.querySelector(selector);
  const roles = () => access?.operator?.roles || [];
  const canProduce = () => Boolean(access?.operator?.portfolio_wide) || roles().includes("admin") || roles().includes("producer");

  function notify(message, kind = "") {
    const region = $("#toast-region");
    if (!region) return;
    const node = document.createElement("div");
    node.className = `toast ${kind}`.trim();
    node.textContent = message;
    region.appendChild(node);
    window.setTimeout(() => node.remove(), 5000);
  }

  function summarize(result) {
    const entries = [
      ["scripts_enqueued", "script job(s) queued"],
      ["audio_initialized", "audio production(s) initialized"],
      ["visuals_initialized", "visual project(s) initialized"],
      ["previews_enqueued", "MP4 preview(s) queued"]
    ];
    const parts = entries
      .map(([key, label]) => [Number(result?.[key] || 0), label])
      .filter(([count]) => count > 0)
      .map(([count, label]) => `${count} ${label}`);
    return parts.join(" · ") || "No eligible work was found. Existing jobs and approvals were preserved.";
  }

  async function run(button, callback) {
    const previous = button.textContent;
    button.disabled = true;
    button.textContent = "Working…";
    try {
      const result = await callback();
      notify(summarize(result), "good");
      await renderStatus();
    } catch (error) {
      notify(error?.message || "The local queue action failed.", "bad");
    } finally {
      button.disabled = false;
      button.textContent = previous;
    }
  }

  async function renderStatus() {
    const target = $("#local-queue-status");
    if (!target) return;
    try {
      const status = await window.StudioApi.localStatus();
      const queue = status.queue || status.counts || status;
      const queued = Number(queue.queued || queue.queued_jobs || 0);
      const running = Number(queue.running || queue.running_jobs || 0);
      const failed = Number(queue.failed || queue.failed_jobs || queue.dead_letter || 0);
      target.innerHTML = `<strong>${queued} queued · ${running} running · ${failed} failed</strong><span>Only eligible, human-approved stages can continue.</span>`;
    } catch (error) {
      target.textContent = error?.message || "Queue status unavailable.";
    }
  }

  async function enhance() {
    if (busy || !window.StudioApi?.configured()) return;
    if (!["/app/dashboard", "/app/content"].includes(window.location.pathname)) return;
    const view = $("#app-view");
    if (!view || $("#local-queue-controls", view)) return;
    busy = true;
    try {
      access = access || await window.StudioApi.access();
      if (!canProduce()) return;
      const brandPayload = await window.StudioApi.brands();
      const brands = brandPayload.brands || brandPayload.items || [];
      const section = document.createElement("section");
      section.id = "local-queue-controls";
      section.className = "card";
      section.style.marginTop = "18px";
      section.innerHTML = `
        <div class="card-header"><div><h2>Local production queue</h2><p>Generate a bounded script batch or continue already approved work. Every approval and publication decision remains human-controlled.</p></div></div>
        <div class="form-grid">
          <label>Brand<select id="local-queue-brand"><option value="">All assigned brands</option>${brands.map((brand) => `<option value="${brand.id}">${brand.display_name}</option>`).join("")}</select></label>
          <label>Maximum items<input id="local-queue-limit" type="number" value="5" min="1" max="20"></label>
        </div>
        <div class="button-row" style="margin-top:14px">
          <button id="queue-more-scripts" class="primary-button" type="button">Generate more scripts</button>
          <button id="continue-approved-local" class="secondary-button" type="button">Continue approved locally</button>
        </div>
        <div id="local-queue-status" class="notice" style="margin-top:14px"><strong>Loading queue status…</strong></div>`;
      view.appendChild(section);
      const payload = () => {
        const limit = Math.max(1, Math.min(20, Number($("#local-queue-limit").value || 5)));
        const brandId = $("#local-queue-brand").value || null;
        return { limit, ...(brandId ? { brand_id: brandId } : {}) };
      };
      $("#queue-more-scripts").addEventListener("click", (event) => run(event.currentTarget, () => window.StudioApi.enqueueLocalScripts(payload())));
      $("#continue-approved-local").addEventListener("click", (event) => run(event.currentTarget, () => window.StudioApi.continueApproved({
        ...payload(),
        include_audio: true,
        include_visuals: true,
        include_previews: true
      })));
      await renderStatus();
    } finally {
      busy = false;
    }
  }

  const observer = new MutationObserver(() => window.setTimeout(enhance, 60));
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", () => window.setTimeout(enhance, 150));
  document.addEventListener("DOMContentLoaded", () => window.setTimeout(enhance, 300), { once: true });
})();
