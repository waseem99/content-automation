(() => {
  const PILOT_KEY = "studio-v2.pilot-session";
  let busy = false;

  const $ = (selector, root = document) => root.querySelector(selector);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  const humanize = (value) => String(value || "unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

  function pilotSession() {
    try { return JSON.parse(sessionStorage.getItem(PILOT_KEY) || "null"); }
    catch { return null; }
  }

  function isAdmin(access) {
    const operator = access?.operator || {};
    return Boolean(operator.portfolio_wide) || (operator.roles || []).includes("admin");
  }

  function errorText(error) {
    const detail = error?.payload?.detail;
    if (detail && typeof detail === "object") {
      if (detail.message) return detail.message;
      if (detail.code) return humanize(detail.code);
      if (Array.isArray(detail.blockers)) return detail.blockers.map((item) => item.message || humanize(item.code || item)).join(" · ");
    }
    return error?.message || "The evidence action could not be completed.";
  }

  function snapshotPayload(preview) {
    return {
      bootstrap_request_sha256: preview.bootstrap_request_sha256,
      controlled_start_event_sha256: preview.controlled_start_event_sha256,
      runbook_sha256: preview.runbook.sha256,
      snapshot_sha256: preview.snapshot_sha256,
      started_at: preview.started_at
    };
  }

  function summaryMarkup(preview) {
    const passed = (preview.items || []).filter((item) => item.all_content_passed).length;
    const total = (preview.items || []).length;
    const blockers = (preview.blockers || []).map((item) => item.message || humanize(item.code || item));
    return `
      <div class="notice ${preview.snapshot_ready ? (preview.all_content_passed ? "good" : "warn") : "bad"}">
        <strong>${preview.snapshot_ready ? "Canonical evidence snapshot ready" : "Evidence snapshot blocked"}</strong>
        ${preview.snapshot_ready
          ? `${passed} of ${total} pilot items currently pass every content-evidence category.`
          : escapeHtml(blockers.join(" · ") || "The controlled pilot identity or scope is not valid for snapshotting.")}
      </div>
      <p style="color:var(--muted);margin-top:10px">The snapshot is generated from current PostgreSQL evidence. No pass/fail values or hashes are entered manually.</p>`;
  }

  async function renderSnapshotPanel() {
    if (busy || window.location.pathname !== "/app/operations" || !window.StudioApi?.configured()) return;
    const host = $("#p100-control-center");
    if (!host || $("#p100-evidence-snapshot", host)) return;

    const session = pilotSession();
    if (!session?.pilot_id) return;

    busy = true;
    try {
      const access = await window.StudioApi.access();
      if (!isAdmin(access)) return;
      const pilot = await window.StudioApi.pilot(session.pilot_id);
      const status = pilot.pilot?.status;
      if (!["running", "blocked"].includes(status)) return;

      const panel = document.createElement("section");
      panel.id = "p100-evidence-snapshot";
      panel.className = "card";
      panel.style.marginTop = "16px";
      panel.innerHTML = '<div class="card-header"><div><h3>Four-item evidence snapshot</h3><p>Loading current canonical evidence…</p></div></div><div class="skeleton"></div>';
      host.appendChild(panel);

      const preview = await window.StudioApi.request(`/acceptance/pilots/${session.pilot_id}/evidence-preview`);
      if (!document.body.contains(panel)) return;
      panel.innerHTML = `
        <div class="card-header">
          <div><h3>Four-item evidence snapshot</h3><p>Record all current content evidence atomically for this controlled pilot.</p></div>
          <button id="p100-snapshot-refresh" class="secondary-button" type="button">Refresh evidence</button>
        </div>
        <div id="p100-snapshot-summary">${summaryMarkup(preview)}</div>
        <div class="button-row" style="margin-top:14px">
          <button id="p100-record-snapshot" class="primary-button" type="button" ${preview.snapshot_ready ? "" : "disabled"}>Record exact snapshot</button>
        </div>`;

      $("#p100-snapshot-refresh", panel).addEventListener("click", () => {
        panel.remove();
        void renderSnapshotPanel();
      });
      $("#p100-record-snapshot", panel).addEventListener("click", async (event) => {
        const button = event.currentTarget;
        const previous = button.textContent;
        button.disabled = true;
        button.textContent = "Recording…";
        try {
          const result = await window.StudioApi.request(`/acceptance/pilots/${session.pilot_id}/snapshot-evidence`, {
            method: "POST",
            body: JSON.stringify(snapshotPayload(preview))
          });
          $("#p100-snapshot-summary", panel).innerHTML = `
            <div class="notice ${result.ok ? "good" : "warn"}">
              <strong>${result.reused ? "Existing snapshot verified" : "Evidence snapshot recorded"}</strong>
              ${escapeHtml(result.ok ? "All four items passed current content-evidence checks." : "The canonical snapshot was recorded and the pilot remains blocked until failed evidence is corrected.")}
            </div>`;
          button.textContent = result.reused ? "Snapshot verified" : "Snapshot recorded";
        } catch (error) {
          $("#p100-snapshot-summary", panel).innerHTML = `<div class="notice bad"><strong>Snapshot not recorded</strong>${escapeHtml(errorText(error))}</div>`;
          button.disabled = false;
          button.textContent = previous;
        }
      });
    } catch (error) {
      const hostNow = $("#p100-control-center");
      if (hostNow && !$("#p100-evidence-snapshot", hostNow)) {
        const panel = document.createElement("section");
        panel.id = "p100-evidence-snapshot";
        panel.className = "notice bad";
        panel.style.marginTop = "16px";
        panel.innerHTML = `<strong>Evidence snapshot unavailable</strong>${escapeHtml(errorText(error))}`;
        hostNow.appendChild(panel);
      }
    } finally {
      busy = false;
    }
  }

  const observer = new MutationObserver(() => window.setTimeout(renderSnapshotPanel, 75));
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", () => window.setTimeout(renderSnapshotPanel, 250));
  document.addEventListener("DOMContentLoaded", () => window.setTimeout(renderSnapshotPanel, 450), { once: true });
})();
