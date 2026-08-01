(() => {
  const routeRoot = "/app/campaigns";
  let rendering = false;
  let refreshTimer = null;
  let access = null;
  let brands = [];

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  const humanize = (value) => String(value || "unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const statusBadge = (status) => `<span class="status-badge status-${escapeHtml(status || "draft")}">${escapeHtml(humanize(status || "draft"))}</span>`;
  const dateTime = (value) => value ? new Date(value).toLocaleString() : "—";

  function errorText(error) {
    const detail = error?.payload?.detail;
    if (detail && typeof detail === "object") return humanize(detail.code || detail.message || "request_failed");
    return error?.message || "The campaign action failed.";
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

  function setPage(title, subtitle) {
    $("#page-eyebrow").textContent = "Database-native production";
    $("#page-title").textContent = title;
    $("#page-subtitle").textContent = subtitle;
    document.title = `${title} · Content Engine Studio`;
  }

  async function ensureContext() {
    if (!access) access = await StudioApi.access();
    if (!brands.length) {
      const payload = await StudioApi.brands();
      brands = payload.brands || [];
    }
    return access;
  }

  function isAdmin() {
    return Boolean(access?.operator?.portfolio_wide) || (access?.operator?.roles || []).includes("admin");
  }

  function ensureNav() {
    const nav = $("#primary-nav");
    if (!nav || $("#campaigns-nav-link")) return;
    const link = document.createElement("a");
    link.id = "campaigns-nav-link";
    link.className = `nav-link ${location.pathname.startsWith(routeRoot) ? "active" : ""}`;
    link.href = routeRoot;
    link.innerHTML = '<span class="nav-icon">▦</span><span>Campaigns</span>';
    link.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      navigate(routeRoot);
    }, true);
    const contentLink = nav.querySelector('a[href="/app/content"]');
    if (contentLink?.nextSibling) nav.insertBefore(link, contentLink.nextSibling);
    else nav.appendChild(link);
  }

  function navigate(path) {
    stopRefresh();
    history.pushState({}, "", path);
    void renderRoute(true);
  }

  function stopRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = null;
  }

  async function renderRoute(force = false) {
    if (!location.pathname.startsWith(routeRoot) || rendering) return;
    const view = $("#app-view");
    if (!view) return;
    const routeKey = location.pathname;
    if (!force && view.dataset.campaignRoute === routeKey && view.dataset.campaignReady === "true") return;
    rendering = true;
    stopRefresh();
    try {
      await ensureContext();
      $$(".nav-link").forEach((node) => node.classList.remove("active"));
      $("#campaigns-nav-link")?.classList.add("active");
      view.dataset.campaignRoute = routeKey;
      view.dataset.campaignReady = "false";
      view.innerHTML = '<div class="grid three"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>';
      const segments = location.pathname.split("/").filter(Boolean);
      const campaignId = segments[2] || null;
      if (campaignId) await renderCampaignDetail(campaignId, view);
      else await renderCampaignList(view);
      view.dataset.campaignReady = "true";
    } catch (error) {
      setPage("Campaigns", "The database-native campaign workspace could not be loaded.");
      view.innerHTML = `<div class="notice bad"><strong>Unable to load campaigns</strong><p>${escapeHtml(errorText(error))}</p></div><button id="campaign-retry" class="primary-button" style="margin-top:16px">Retry</button>`;
      $("#campaign-retry")?.addEventListener("click", () => void renderRoute(true));
    } finally {
      rendering = false;
    }
  }

  async function renderCampaignList(view) {
    setPage("Campaigns", "Create and operate thousands of videos from one database-native workspace.");
    const payload = await StudioApi.request("/p119/campaigns?limit=500");
    const campaigns = payload.campaigns || [];
    view.innerHTML = `
      <div class="page-actions">
        <div><h2>Production campaigns</h2><p>PostgreSQL is the system of record. Routine pre-generation runs automatically.</p></div>
        <button id="new-campaign-toggle" class="primary-button">+ New campaign</button>
      </div>
      <section id="new-campaign-panel" class="card" hidden style="margin-bottom:18px">
        <div class="card-header"><div><h2>Create and start campaign</h2><p>Enter one item per line. Use <code>Title | Topic</code> when the title and brief differ.</p></div></div>
        <form id="campaign-form" class="form-grid">
          <label>Brand<select name="brand_id" required>${brands.map((brand) => `<option value="${escapeHtml(brand.id)}">${escapeHtml(brand.display_name)}</option>`).join("")}</select></label>
          <label>Campaign name<input name="name" required minlength="3" placeholder="September Football Explainers"></label>
          <label>Campaign key<input name="campaign_key" required pattern="[a-z0-9][a-z0-9._-]{2,119}" placeholder="2026-09-football"></label>
          <label>Primary platform<select name="primary_platform"><option value="facebook">Facebook</option><option value="youtube">YouTube</option><option value="instagram">Instagram</option><option value="tiktok">TikTok</option><option value="youtube_shorts">YouTube Shorts</option></select></label>
          <label>Master duration<select name="duration"><option value="120">120 seconds</option><option value="90">90 seconds</option><option value="60">60 seconds</option><option value="45">45 seconds</option><option value="30">30 seconds</option><option value="15">15 seconds</option></select></label>
          <label>Short versions<select name="shorts"><option value="2">2 shorts</option><option value="1">1 short</option><option value="0">None</option></select></label>
          <label>Schedule date<input name="scheduled_for" type="date" value="${new Date().toISOString().slice(0, 10)}" required></label>
          <label>Language<input name="language" value="en-US" required></label>
          <label class="wide">Objective<input name="objective" value="Create accurate, engaging, platform-ready content." maxlength="2000"></label>
          <label class="wide">Audience<input name="audience" value="General social media audience" maxlength="1000"></label>
          <label class="wide">Items<textarea name="items" rows="14" required placeholder="Why Offside Exists | Explain why the offside law exists and what problem it solves.\nHow a High Press Works | Explain the structure and risks of a high press."></textarea></label>
          <div class="wide notice"><strong>Automatic path</strong>Creation, validation, activation, scripts, source checks, narration planning, scene planning, captions and final-generation packages progress without routine approvals. Rendering and publishing remain off.</div>
          <div class="wide button-row"><button class="primary-button" type="submit">Create, activate and start autopilot</button><span id="campaign-item-count">0 items</span></div>
        </form>
      </section>
      <section class="card">
        <div class="card-header"><div><h2>All campaigns</h2><p>${campaigns.length} campaign${campaigns.length === 1 ? "" : "s"} visible to your role.</p></div><button id="campaign-refresh" class="secondary-button">Refresh</button></div>
        <div class="content-card-list">${campaigns.length ? campaigns.map(campaignCard).join("") : '<div class="empty-state"><h3>No campaigns yet</h3><p>Create the first database-native campaign above.</p></div>'}</div>
      </section>`;
    $("#new-campaign-toggle")?.addEventListener("click", () => { $("#new-campaign-panel").hidden = !$("#new-campaign-panel").hidden; });
    $("#campaign-refresh")?.addEventListener("click", () => void renderRoute(true));
    const itemsField = $("#campaign-form textarea[name=items]");
    itemsField?.addEventListener("input", () => {
      const count = parseItems(itemsField.value).length;
      $("#campaign-item-count").textContent = `${count.toLocaleString()} item${count === 1 ? "" : "s"}`;
    });
    $("#campaign-form")?.addEventListener("submit", createCampaign);
  }

  function campaignCard(item) {
    const progress = item.item_count ? `${item.valid_item_count || 0}/${item.item_count} validated` : "No items";
    return `<a class="content-card" href="${routeRoot}/${escapeHtml(item.id)}" data-campaign-link>
      <div class="button-row between"><h3>${escapeHtml(item.name)}</h3>${statusBadge(item.status)}</div>
      <p>${escapeHtml(item.brand_name || item.brand_slug)} · ${escapeHtml(progress)} · Updated ${escapeHtml(dateTime(item.updated_at))}</p>
    </a>`;
  }

  function parseItems(raw) {
    return String(raw || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line, index) => {
      const separator = line.indexOf("|");
      const title = (separator >= 0 ? line.slice(0, separator) : line).trim();
      const topic = (separator >= 0 ? line.slice(separator + 1) : line).trim();
      return { title, topic, index };
    }).filter((item) => item.title.length >= 3 && item.topic.length >= 3);
  }

  async function createCampaign(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Creating campaign…";
    try {
      const data = new FormData(form);
      const parsed = parseItems(data.get("items"));
      if (!parsed.length) throw new Error("Add at least one valid item.");
      if (parsed.length > 10000) throw new Error("One campaign version supports up to 10,000 items.");
      const primary = String(data.get("primary_platform"));
      const created = await StudioApi.request("/p119/campaigns", {
        method: "POST",
        body: JSON.stringify({
          campaign_key: String(data.get("campaign_key")).trim(),
          brand_id: String(data.get("brand_id")),
          name: String(data.get("name")).trim(),
          description: `${parsed.length} database-native production items`,
          metadata: { creator_studio: true, manual_sheet_required: false }
        })
      });
      const version = (created.versions || [])[0];
      if (!version?.id) throw new Error("Campaign version was not created.");
      const items = parsed.map((item) => ({
        item_key: `item-${String(item.index + 1).padStart(5, "0")}`,
        title: item.title,
        topic: item.topic,
        objective: String(data.get("objective") || ""),
        audience: String(data.get("audience") || ""),
        format_name: "master_video",
        primary_platform: primary,
        target_platforms: [primary],
        target_duration_seconds: Number(data.get("duration")),
        short_cut_count: Number(data.get("shorts")),
        language: String(data.get("language")),
        scheduled_for: String(data.get("scheduled_for")),
        priority: 50,
        metadata: { creator_studio_line: item.index + 1 }
      }));
      button.textContent = `Saving ${items.length.toLocaleString()} items…`;
      await StudioApi.request(`/p119/campaign-versions/${version.id}/items`, { method: "POST", body: JSON.stringify({ items }) });
      button.textContent = "Validating…";
      const validation = await StudioApi.request(`/p119/campaign-versions/${version.id}/validate`, { method: "POST" });
      if (!validation.ok) throw new Error(`${validation.counts?.invalid_item_count || "Some"} items failed validation.`);
      button.textContent = "Activating…";
      await StudioApi.request(`/p119/campaign-versions/${version.id}/activate`, { method: "POST" });
      await StudioApi.request(`/p120/campaigns/${created.campaign.id}/autopilot/start`, { method: "POST" });
      toast(`${items.length.toLocaleString()} items activated. Pre-generation is running.`, "good");
      navigate(`${routeRoot}/${created.campaign.id}`);
    } catch (error) {
      toast(errorText(error), "bad");
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function renderCampaignDetail(campaignId, view) {
    const [detail, dashboard, gridPayload, exceptionsPayload] = await Promise.all([
      StudioApi.request(`/p119/campaigns/${campaignId}`),
      StudioApi.request(`/p120/campaigns/${campaignId}/dashboard`),
      StudioApi.request(`/p120/campaigns/${campaignId}/items?limit=200`),
      StudioApi.request(`/p120/campaigns/${campaignId}/exception-groups`)
    ]);
    const campaign = detail.campaign;
    const metrics = dashboard.metrics || {};
    const items = gridPayload.items || [];
    const groups = exceptionsPayload.groups || [];
    setPage(campaign.name, `${campaign.brand_name} · Automatic pre-generation control center`);
    view.innerHTML = `
      <div class="page-actions"><div><a href="${routeRoot}" data-campaign-link>← All campaigns</a><h2>${escapeHtml(campaign.name)}</h2><p>${escapeHtml(campaign.campaign_key)} · Final video generation is not connected.</p></div><div class="button-row"><button id="campaign-start" class="secondary-button">Ensure autopilot</button>${campaign.status === "paused" ? '<button id="campaign-resume" class="primary-button">Resume</button>' : '<button id="campaign-pause" class="secondary-button">Pause</button>'}</div></div>
      <section class="grid four">
        <article class="metric-card"><strong>${Number(metrics.total || 0).toLocaleString()}</strong><span>Total items</span></article>
        <article class="metric-card"><strong>${Number(metrics.ready || 0).toLocaleString()}</strong><span>Ready for generation</span></article>
        <article class="metric-card ${metrics.human_exception ? "alert" : ""}"><strong>${Number(metrics.human_exception || 0).toLocaleString()}</strong><span>Human exceptions</span></article>
        <article class="metric-card ${metrics.hard_block ? "alert" : ""}"><strong>${Number(metrics.hard_block || 0).toLocaleString()}</strong><span>Hard blocks</span></article>
      </section>
      <section class="grid two" style="margin-top:18px">
        <article class="card"><div class="card-header"><div><h2>Automation</h2><p>Routine work advances without individual approvals.</p></div>${statusBadge(campaign.status)}</div>
          <div class="grid two"><div class="metric-card"><strong>${Number(metrics.automation_rate || 0).toFixed(1)}%</strong><span>Ready rate</span></div><div class="metric-card"><strong>${Number(metrics.average_score || 0).toFixed(1)}</strong><span>Average score</span></div></div>
          <div class="content-card-list" style="margin-top:12px">${(dashboard.stage_counts || []).map((row) => `<div class="content-card"><div class="button-row between"><strong>${escapeHtml(humanize(row.current_stage))}</strong>${statusBadge(row.status)}</div><p>${Number(row.count).toLocaleString()} items</p></div>`).join("") || '<p>No runs yet.</p>'}</div>
        </article>
        <article class="card"><div class="card-header"><div><h2>Grouped exceptions</h2><p>Review causes, not thousands of individual pages.</p></div></div>
          <div class="content-card-list">${groups.length ? groups.map(exceptionCard).join("") : '<div class="empty-state"><h3>No open exceptions</h3><p>The automatic path is clear.</p></div>'}</div>
        </article>
      </section>
      <section class="card" style="margin-top:18px">
        <div class="card-header"><div><h2>Campaign items</h2><p>First 200 records. Filtered, cursor-based APIs support the full campaign.</p></div><div class="button-row"><button id="retry-selected" class="secondary-button">Retry selected</button><button id="campaign-refresh" class="secondary-button">Refresh</button></div></div>
        <div style="overflow:auto"><table class="data-table"><thead><tr><th><input id="select-all-items" type="checkbox"></th><th>#</th><th>Title</th><th>State</th><th>Stage</th><th>Score</th><th>Exceptions</th><th>Package</th></tr></thead><tbody>${items.map(itemRow).join("")}</tbody></table></div>
      </section>
      <div class="notice warn" style="margin-top:18px"><strong>Boundary enforced</strong>Paid generation and public publishing cannot start from this workspace.</div>`;
    bindCampaignDetail(campaignId, campaign, groups);
    refreshTimer = setInterval(() => { if (!document.hidden && location.pathname === `${routeRoot}/${campaignId}`) void renderRoute(true); }, 10000);
  }

  function exceptionCard(group) {
    return `<article class="content-card"><div class="button-row between"><h3>${escapeHtml(humanize(group.exception_code))}</h3>${statusBadge(group.severity)}</div><p>${Number(group.count).toLocaleString()} items · ${escapeHtml(humanize(group.category))} · Rule ${escapeHtml(group.rule_version)}</p><div class="button-row"><button class="secondary-button" data-retry-group="${escapeHtml(group.fingerprint)}" data-code="${escapeHtml(group.exception_code)}" data-rule="${escapeHtml(group.rule_version)}">Retry group</button>${group.severity !== "hard_block" ? `<button class="ghost-button" data-waive-group="${escapeHtml(group.fingerprint)}" data-code="${escapeHtml(group.exception_code)}" data-rule="${escapeHtml(group.rule_version)}">Waive & retry</button>` : ""}</div></article>`;
  }

  function itemRow(item) {
    const canRetry = ["human_exception", "hard_block", "failed", "waiting"].includes(item.run_status);
    return `<tr><td><input type="checkbox" data-item-select value="${escapeHtml(item.id)}" ${canRetry ? "" : "disabled"}></td><td>${escapeHtml(item.ordinal)}</td><td><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.item_key)}</small></td><td>${statusBadge(item.state)}</td><td>${escapeHtml(humanize(item.current_stage || "not started"))}</td><td>${item.score == null ? "—" : Number(item.score).toFixed(0)}</td><td>${Number(item.open_exception_count || 0)}</td><td>${item.package_id ? `<button class="ghost-button" data-package-item="${escapeHtml(item.id)}">Open package</button>` : "—"}</td></tr>`;
  }

  function bindCampaignDetail(campaignId, campaign, groups) {
    $("#campaign-refresh")?.addEventListener("click", () => void renderRoute(true));
    $("#campaign-start")?.addEventListener("click", async (event) => runButton(event.currentTarget, () => StudioApi.request(`/p120/campaigns/${campaignId}/autopilot/start`, { method: "POST" }), "Autopilot runs ensured."));
    $("#campaign-pause")?.addEventListener("click", async (event) => runButton(event.currentTarget, () => StudioApi.request(`/p120/campaigns/${campaignId}/pause`, { method: "POST" }), "Campaign paused."));
    $("#campaign-resume")?.addEventListener("click", async (event) => runButton(event.currentTarget, () => StudioApi.request(`/p120/campaigns/${campaignId}/resume`, { method: "POST" }), "Campaign resumed."));
    $("#select-all-items")?.addEventListener("change", (event) => $$('[data-item-select]:not(:disabled)').forEach((box) => { box.checked = event.target.checked; }));
    $("#retry-selected")?.addEventListener("click", async (event) => {
      const itemIds = $$('[data-item-select]:checked').map((box) => box.value);
      if (!itemIds.length) return toast("Select at least one retryable item.", "bad");
      await runButton(event.currentTarget, () => StudioApi.request(`/p120/campaigns/${campaignId}/items/retry`, { method: "POST", body: JSON.stringify({ item_ids: itemIds }) }), `${itemIds.length} items queued for retry.`);
    });
    $$('[data-retry-group]').forEach((button) => button.addEventListener("click", () => resolveGroup(campaignId, button, "retry")));
    $$('[data-waive-group]').forEach((button) => button.addEventListener("click", () => resolveGroup(campaignId, button, "waive")));
    $$('[data-package-item]').forEach((button) => button.addEventListener("click", async () => {
      try {
        const payload = await StudioApi.request(`/p120/campaigns/${campaignId}/items/${button.dataset.packageItem}/package`);
        showPackage(payload.package);
      } catch (error) { toast(errorText(error), "bad"); }
    }));
  }

  async function resolveGroup(campaignId, button, action) {
    const rationale = prompt(action === "waive" ? "Why is this non-blocking exception safe to waive?" : "What was corrected before retrying this group?", action === "waive" ? "Reviewed as acceptable under the current policy." : "Underlying cause corrected; retry the identical group.");
    if (!rationale) return;
    await runButton(button, () => StudioApi.request(`/p120/campaigns/${campaignId}/exceptions/resolve`, {
      method: "POST",
      body: JSON.stringify({ exception_code: button.dataset.code, rule_version: button.dataset.rule, fingerprint: button.dataset.retryGroup || button.dataset.waiveGroup, action, rationale })
    }), `${humanize(button.dataset.code)} group queued.`);
  }

  async function runButton(button, task, success) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Working…";
    try { await task(); toast(success, "good"); await renderRoute(true); }
    catch (error) { toast(errorText(error), "bad"); }
    finally { button.disabled = false; button.textContent = original; }
  }

  function showPackage(packageRow) {
    const dialog = document.createElement("dialog");
    dialog.className = "confirm-dialog";
    dialog.innerHTML = `<form method="dialog" style="min-width:min(900px,90vw)"><div class="button-row between"><div><p class="eyebrow">Immutable package</p><h2>${escapeHtml(packageRow.item_key || `Version ${packageRow.version}`)}</h2></div><button value="close" class="secondary-button">Close</button></div><p>SHA-256: <code>${escapeHtml(packageRow.package_sha256)}</code></p><pre style="max-height:65vh;overflow:auto;white-space:pre-wrap;background:var(--surface-subtle,#f5f5f5);padding:14px;border-radius:10px">${escapeHtml(JSON.stringify(packageRow.package, null, 2))}</pre></form>`;
    document.body.appendChild(dialog);
    dialog.addEventListener("close", () => dialog.remove());
    dialog.showModal();
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-campaign-link]");
    if (!link) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    navigate(link.getAttribute("href"));
  }, true);

  window.addEventListener("popstate", () => { if (location.pathname.startsWith(routeRoot)) void renderRoute(true); else stopRefresh(); });
  $("#refresh-view")?.addEventListener("click", (event) => {
    if (!location.pathname.startsWith(routeRoot)) return;
    event.stopImmediatePropagation();
    void renderRoute(true);
  }, true);

  const observer = new MutationObserver(() => {
    ensureNav();
    if (location.pathname.startsWith(routeRoot)) void renderRoute();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("DOMContentLoaded", () => { ensureNav(); if (location.pathname.startsWith(routeRoot)) void renderRoute(true); });
})();
