(() => {
  const routeRoot = "/app/campaigns";
  const stateByCampaign = new Map();
  let observerBusy = false;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;"
  }[char]));
  const humanize = (value) => String(value || "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
  const statusBadge = (status) => `<span class="status-badge status-${escapeHtml(status || "draft")}">${escapeHtml(humanize(status || "draft"))}</span>`;

  function currentCampaignId() {
    if (!location.pathname.startsWith(`${routeRoot}/`)) return null;
    const value = location.pathname.slice(`${routeRoot}/`.length).split("/")[0];
    return /^[0-9a-f-]{36}$/i.test(value) ? value : null;
  }

  function defaultState() {
    return {
      query: "",
      state: "",
      exceptionCode: "",
      sort: "ordinal",
      direction: "asc",
      limit: 250,
      cursor: null,
      cursorHistory: [],
      loading: false,
      requestSerial: 0,
      payload: null
    };
  }

  function stateFor(campaignId) {
    if (!stateByCampaign.has(campaignId)) stateByCampaign.set(campaignId, defaultState());
    return stateByCampaign.get(campaignId);
  }

  function findItemsSection() {
    const heading = $$('section.card h2').find((node) => node.textContent.trim() === "Campaign items");
    return heading?.closest("section.card") || null;
  }

  function toast(message, kind = "") {
    const region = $("#toast-region");
    if (!region) return;
    const node = document.createElement("div");
    node.className = `toast ${kind}`.trim();
    node.textContent = message;
    region.appendChild(node);
    setTimeout(() => node.remove(), 5000);
  }

  function errorText(error) {
    const detail = error?.payload?.detail;
    if (detail && typeof detail === "object") return humanize(detail.code || detail.message || "request_failed");
    return error?.message || "The campaign operation failed.";
  }

  function queryUrl(campaignId, state) {
    const params = new URLSearchParams({
      sort: state.sort,
      direction: state.direction,
      limit: String(state.limit)
    });
    if (state.query) params.set("q", state.query);
    if (state.state) params.set("states", state.state);
    if (state.exceptionCode) params.set("exceptions", state.exceptionCode);
    if (state.cursor) params.set("cursor", state.cursor);
    return `/p121/campaigns/${campaignId}/items?${params.toString()}`;
  }

  function toolbar(state) {
    return `
      <form id="campaign-grid-filter" class="form-grid" style="margin-bottom:14px">
        <label class="wide">Search
          <input name="query" value="${escapeHtml(state.query)}" placeholder="Search item key, title, topic, objective or audience">
        </label>
        <label>State
          <select name="state">
            ${[
              ["", "All states"],
              ["activated", "Activated"],
              ["auto_progressing", "Auto progressing"],
              ["human_exception", "Human exception"],
              ["hard_block", "Hard block"],
              ["ready_for_final_video_generation", "Ready for final generation"]
            ].map(([value, label]) => `<option value="${value}" ${state.state === value ? "selected" : ""}>${label}</option>`).join("")}
          </select>
        </label>
        <label>Exception code
          <input name="exception_code" value="${escapeHtml(state.exceptionCode)}" placeholder="source_block">
        </label>
        <label>Sort
          <select name="sort">
            ${[
              ["ordinal", "Original order"],
              ["priority", "Priority"],
              ["scheduled_for", "Schedule date"],
              ["updated_at", "Last update"],
              ["title", "Title"],
              ["state", "State"],
              ["score", "Score"],
              ["exceptions", "Exception count"]
            ].map(([value, label]) => `<option value="${value}" ${state.sort === value ? "selected" : ""}>${label}</option>`).join("")}
          </select>
        </label>
        <label>Direction
          <select name="direction"><option value="asc" ${state.direction === "asc" ? "selected" : ""}>Ascending</option><option value="desc" ${state.direction === "desc" ? "selected" : ""}>Descending</option></select>
        </label>
        <label>Rows per page
          <select name="limit">${[100, 250, 500].map((value) => `<option value="${value}" ${state.limit === value ? "selected" : ""}>${value}</option>`).join("")}</select>
        </label>
        <div class="wide button-row">
          <button type="submit" class="primary-button">Apply filters</button>
          <button id="campaign-grid-clear" type="button" class="secondary-button">Clear</button>
          <button id="campaign-grid-retry-selected" type="button" class="secondary-button">Retry selected</button>
          <button id="campaign-grid-retry-matching" type="button" class="secondary-button">Retry all matching</button>
        </div>
      </form>`;
  }

  function itemRow(item) {
    const retryable = ["human_exception", "hard_block", "failed", "waiting"].includes(item.run_status)
      || ["human_exception", "hard_block"].includes(item.state);
    return `<tr>
      <td><input type="checkbox" data-p121-item value="${escapeHtml(item.id)}" ${retryable ? "" : "disabled"}></td>
      <td>${escapeHtml(item.ordinal)}</td>
      <td><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.item_key)}</small></td>
      <td>${statusBadge(item.state)}</td>
      <td>${escapeHtml(humanize(item.current_stage || "not started"))}</td>
      <td>${item.score == null ? "—" : Number(item.score).toFixed(0)}</td>
      <td>${Number(item.open_exception_count || 0)}</td>
      <td>${item.priority ?? "—"}</td>
      <td>${item.scheduled_for ? escapeHtml(String(item.scheduled_for)) : "—"}</td>
      <td>${item.package_id ? `<button type="button" class="ghost-button" data-p121-package="${escapeHtml(item.id)}">Open package</button>` : "—"}</td>
    </tr>`;
  }

  function groupChips(payload) {
    const groups = payload?.groups || {};
    const entries = Object.entries(groups);
    if (!entries.length) return "";
    return `<div class="button-row" style="margin-bottom:12px;flex-wrap:wrap">
      <button type="button" class="ghost-button" data-p121-state="">All ${Number(payload.filtered_count || 0).toLocaleString()}</button>
      ${entries.map(([state, count]) => `<button type="button" class="ghost-button" data-p121-state="${escapeHtml(state)}">${escapeHtml(humanize(state))} ${Number(count).toLocaleString()}</button>`).join("")}
    </div>`;
  }

  function renderSection(section, campaignId, state) {
    const payload = state.payload;
    const items = payload?.items || [];
    section.dataset.p121Enhanced = "true";
    section.innerHTML = `
      <div class="card-header">
        <div><h2>Campaign items</h2><p>${payload ? `${Number(payload.filtered_count).toLocaleString()} matching records. Only ${Number(payload.page_count).toLocaleString()} rows are rendered in this page.` : "Loading database-backed campaign records…"}</p></div>
        <button id="campaign-grid-refresh" class="secondary-button" type="button">Refresh</button>
      </div>
      ${toolbar(state)}
      ${payload ? groupChips(payload) : ""}
      <div id="campaign-grid-status" class="notice ${state.loading ? "warn" : ""}" style="margin-bottom:12px">
        <strong>${state.loading ? "Loading…" : "Database-backed view"}</strong>
        ${state.loading ? "The current page is refreshing." : "Search, filtering, sorting and pagination are executed in PostgreSQL; the browser never loads the full campaign."}
      </div>
      <div style="overflow:auto;max-height:65vh">
        <table class="data-table">
          <thead><tr><th><input id="campaign-grid-select-all" type="checkbox"></th><th>#</th><th>Title</th><th>State</th><th>Stage</th><th>Score</th><th>Exceptions</th><th>Priority</th><th>Schedule</th><th>Package</th></tr></thead>
          <tbody>${items.length ? items.map(itemRow).join("") : `<tr><td colspan="10"><div class="empty-state"><h3>No matching items</h3><p>Change the filters or let the automatic worker create campaign records.</p></div></td></tr>`}</tbody>
        </table>
      </div>
      <div class="button-row between" style="margin-top:14px">
        <div><strong>Page rows:</strong> ${items.length.toLocaleString()} · <strong>Total matching:</strong> ${Number(payload?.filtered_count || 0).toLocaleString()}</div>
        <div class="button-row"><button id="campaign-grid-prev" type="button" class="secondary-button" ${state.cursorHistory.length ? "" : "disabled"}>Previous</button><button id="campaign-grid-next" type="button" class="primary-button" ${payload?.has_more ? "" : "disabled"}>Next</button></div>
      </div>`;
    bindSection(section, campaignId, state);
  }

  async function loadPage(section, campaignId, state, { preserveDom = false } = {}) {
    if (state.loading) return;
    state.loading = true;
    const serial = ++state.requestSerial;
    if (!preserveDom) renderSection(section, campaignId, state);
    else $("#campaign-grid-status", section)?.classList.add("warn");
    try {
      const payload = await StudioApi.request(queryUrl(campaignId, state));
      if (serial !== state.requestSerial) return;
      state.payload = payload;
    } catch (error) {
      if (serial !== state.requestSerial) return;
      toast(errorText(error), "bad");
    } finally {
      if (serial === state.requestSerial) {
        state.loading = false;
        renderSection(section, campaignId, state);
      }
    }
  }

  function resetPaging(state) {
    state.cursor = null;
    state.cursorHistory = [];
  }

  function bindSection(section, campaignId, state) {
    $("#campaign-grid-filter", section)?.addEventListener("submit", (event) => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      state.query = String(data.get("query") || "").trim();
      state.state = String(data.get("state") || "").trim();
      state.exceptionCode = String(data.get("exception_code") || "").trim();
      state.sort = String(data.get("sort") || "ordinal");
      state.direction = String(data.get("direction") || "asc");
      state.limit = Number(data.get("limit") || 250);
      resetPaging(state);
      void loadPage(section, campaignId, state);
    });
    $("#campaign-grid-clear", section)?.addEventListener("click", () => {
      Object.assign(state, defaultState());
      void loadPage(section, campaignId, state);
    });
    $("#campaign-grid-refresh", section)?.addEventListener("click", () => void loadPage(section, campaignId, state));
    $("#campaign-grid-select-all", section)?.addEventListener("change", (event) => {
      $$('[data-p121-item]:not(:disabled)', section).forEach((box) => { box.checked = event.target.checked; });
    });
    $("#campaign-grid-prev", section)?.addEventListener("click", () => {
      if (!state.cursorHistory.length) return;
      state.cursor = state.cursorHistory.pop();
      void loadPage(section, campaignId, state);
    });
    $("#campaign-grid-next", section)?.addEventListener("click", () => {
      if (!state.payload?.next_cursor) return;
      state.cursorHistory.push(state.cursor);
      state.cursor = state.payload.next_cursor;
      void loadPage(section, campaignId, state);
    });
    $$('[data-p121-state]', section).forEach((button) => button.addEventListener("click", () => {
      state.state = button.dataset.p121State || "";
      resetPaging(state);
      void loadPage(section, campaignId, state);
    }));
    $("#campaign-grid-retry-selected", section)?.addEventListener("click", async (event) => {
      const ids = $$('[data-p121-item]:checked', section).map((box) => box.value);
      if (!ids.length) return toast("Select at least one retryable item.", "bad");
      if (!confirm(`Retry ${ids.length.toLocaleString()} selected items?`)) return;
      await runAction(event.currentTarget, async () => {
        await StudioApi.request(`/p120/campaigns/${campaignId}/items/retry`, {
          method: "POST",
          body: JSON.stringify({ item_ids: ids })
        });
      }, `${ids.length.toLocaleString()} items queued for retry.`, section, campaignId, state);
    });
    $("#campaign-grid-retry-matching", section)?.addEventListener("click", async (event) => {
      const count = Number(state.payload?.filtered_count || 0);
      if (!count) return toast("No matching items are available.", "bad");
      if (count > 20000) return toast("The matching set exceeds the 20,000-item safety limit.", "bad");
      if (!confirm(`Retry every matching exception record? Current matching set: ${count.toLocaleString()}.`)) return;
      await runAction(event.currentTarget, async () => {
        await StudioApi.request(`/p121/campaigns/${campaignId}/retry-matching`, {
          method: "POST",
          body: JSON.stringify({
            query: state.query || null,
            states: state.state ? [state.state] : [],
            exception_codes: state.exceptionCode ? state.exceptionCode.split(",").map((value) => value.trim()).filter(Boolean) : [],
            maximum: 20000
          })
        });
      }, "All matching exception records were queued for retry.", section, campaignId, state);
    });
    $$('[data-p121-package]', section).forEach((button) => button.addEventListener("click", async () => {
      try {
        const payload = await StudioApi.request(`/p120/campaigns/${campaignId}/items/${button.dataset.p121Package}/package`);
        showPackage(payload.package);
      } catch (error) {
        toast(errorText(error), "bad");
      }
    }));
  }

  async function runAction(button, task, success, section, campaignId, state) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Working…";
    try {
      await task();
      toast(success, "good");
      resetPaging(state);
      await loadPage(section, campaignId, state);
    } catch (error) {
      toast(errorText(error), "bad");
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function showPackage(packageRow) {
    const dialog = document.createElement("dialog");
    dialog.className = "confirm-dialog";
    dialog.innerHTML = `<form method="dialog" style="min-width:min(900px,90vw)"><div class="button-row between"><div><p class="eyebrow">Immutable package</p><h2>${escapeHtml(packageRow.item_key || `Version ${packageRow.version}`)}</h2></div><button value="close" class="secondary-button">Close</button></div><p>SHA-256: <code>${escapeHtml(packageRow.package_sha256)}</code></p><pre style="max-height:65vh;overflow:auto;white-space:pre-wrap;background:var(--surface-subtle,#f5f5f5);padding:14px;border-radius:10px">${escapeHtml(JSON.stringify(packageRow.package, null, 2))}</pre></form>`;
    document.body.appendChild(dialog);
    dialog.addEventListener("close", () => dialog.remove());
    dialog.showModal();
  }

  async function enhance() {
    if (observerBusy) return;
    const campaignId = currentCampaignId();
    const section = findItemsSection();
    if (!campaignId || !section || section.dataset.p121Enhanced === "true") return;
    observerBusy = true;
    try {
      const state = stateFor(campaignId);
      renderSection(section, campaignId, state);
      await loadPage(section, campaignId, state);
    } finally {
      observerBusy = false;
    }
  }

  const observer = new MutationObserver(() => { void enhance(); });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("DOMContentLoaded", () => void enhance());
  window.addEventListener("popstate", () => void enhance());
})();
