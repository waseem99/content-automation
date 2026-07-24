(() => {
  const BRAND_KEY = "studio-v2.wizard-brand";
  const SUGGESTION_KEY = "studio-v2.selected-suggestion";
  const PILOT_KEY = "studio-v2.pilot-session";
  let access = null;
  let suggestionBusy = false;
  let pilotBusy = false;
  let publisherBusy = false;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  const humanize = (value) => String(value || "unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const roles = () => access?.operator?.roles || [];
  const isAdmin = () => Boolean(access?.operator?.portfolio_wide) || roles().includes("admin");
  const hasRole = (role) => isAdmin() || roles().includes(role);

  function toast(message, kind = "") {
    const target = $("#toast-region");
    if (!target) return;
    const node = document.createElement("div");
    node.className = `toast ${kind}`.trim();
    node.textContent = message;
    target.appendChild(node);
    window.setTimeout(() => node.remove(), 5000);
  }

  function errorText(error) {
    const detail = error?.payload?.detail;
    if (detail && typeof detail === "object") {
      if (detail.message) return detail.message;
      if (detail.code) return humanize(detail.code);
      if (Array.isArray(detail.items)) return detail.items.map((item) => (item.selection_blockers || []).map(humanize).join(", ")).join(" · ");
    }
    return error?.message || "The action could not be completed.";
  }

  async function withButton(button, callback) {
    const previous = button.innerHTML;
    button.disabled = true;
    button.innerHTML = "Working…";
    try { return await callback(); }
    catch (error) { toast(errorText(error), "bad"); throw error; }
    finally { button.disabled = false; button.innerHTML = previous; }
  }

  async function refreshAccess() {
    if (!window.StudioApi?.configured()) return null;
    try {
      access = await window.StudioApi.access();
      ensurePublisherNavigation();
      return access;
    } catch { return null; }
  }

  function ensurePublisherNavigation() {
    const nav = $("#primary-nav");
    if (!nav || !hasRole("publisher") || $("#publisher-nav-link")) return;
    const link = document.createElement("a");
    link.id = "publisher-nav-link";
    link.className = `nav-link ${window.location.pathname === "/app/publishing" ? "active" : ""}`;
    link.href = "/app/publishing";
    link.innerHTML = '<span class="nav-icon">⇧</span><span>Release & delivery</span>';
    link.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      history.pushState({}, "", "/app/publishing");
      void renderPublishing();
    }, true);
    nav.appendChild(link);
  }

  async function renderPublishing() {
    if (publisherBusy || !window.StudioApi?.configured()) return;
    publisherBusy = true;
    try {
      if (!access) await refreshAccess();
      if (!hasRole("publisher")) return;
      const view = $("#app-view");
      if (!view) return;
      $$(".nav-link").forEach((item) => item.classList.remove("active"));
      $("#publisher-nav-link")?.classList.add("active");
      $("#page-eyebrow").textContent = "Publisher workspace";
      $("#page-title").textContent = "Release & delivery";
      $("#page-subtitle").textContent = "Inspect approved releases and controlled delivery records.";
      view.dataset.extensionRoute = "publishing";
      view.innerHTML = '<div class="grid two"><div class="skeleton"></div><div class="skeleton"></div></div>';
      const [releasePayload, deliveryPayload] = await Promise.all([
        window.StudioApi.releases().catch((error) => ({ error: errorText(error), items: [] })),
        window.StudioApi.deliveries().catch((error) => ({ error: errorText(error), items: [] }))
      ]);
      if (window.location.pathname !== "/app/publishing") return;
      const releases = releasePayload.items || releasePayload.releases || [];
      const deliveries = deliveryPayload.items || deliveryPayload.deliveries || [];
      view.innerHTML = `
        <div class="page-actions"><div><h2>Approved release packages</h2><p>Publishing remains human-controlled. No social platform action runs automatically.</p></div></div>
        <div class="grid two">
          <section class="card"><div class="card-header"><div><h2>Releases</h2><p>Immutable packages that passed final QA.</p></div></div><div class="content-card-list">${releasePayload.error ? `<div class="notice bad">${escapeHtml(releasePayload.error)}</div>` : releases.length ? releases.map((item) => `<article class="content-card"><div class="button-row between"><h3>${escapeHtml(item.release_key || item.title || `Release ${item.version || ""}`)}</h3><span class="status-badge status-${escapeHtml(item.status || "draft")}">${escapeHtml(humanize(item.status || "draft"))}</span></div><p>${escapeHtml(item.brand_name || item.platform || "Controlled release")} · ${escapeHtml(item.created_at ? new Date(item.created_at).toLocaleString() : "")}</p></article>`).join("") : '<div class="empty-state"><h3>No approved releases</h3><p>Final QA must complete before a publisher can act.</p></div>'}</div></section>
          <section class="card"><div class="card-header"><div><h2>Delivery requests</h2><p>Simulated staging delivery and externally recorded results.</p></div></div><div class="content-card-list">${deliveryPayload.error ? `<div class="notice bad">${escapeHtml(deliveryPayload.error)}</div>` : deliveries.length ? deliveries.map((item) => `<article class="content-card"><div class="button-row between"><h3>${escapeHtml(item.target_name || item.platform || "Delivery")}</h3><span class="status-badge status-${escapeHtml(item.status || "draft")}">${escapeHtml(humanize(item.status || "draft"))}</span></div><p>${escapeHtml(item.release_key || item.delivery_key || "Controlled request")}</p></article>`).join("") : '<div class="empty-state"><h3>No delivery requests</h3><p>Nothing is queued for delivery.</p></div>'}</div></section>
        </div>
        <div class="notice warn" style="margin-top:18px"><strong>Publishing safety</strong>Live platform OAuth is not connected. This screen cannot publish automatically.</div>`;
    } finally { publisherBusy = false; }
  }

  function rememberWizardBrand() {
    const selected = $('input[name="wizard-brand"]:checked');
    if (selected) sessionStorage.setItem(BRAND_KEY, selected.value);
  }

  function prefillBrief() {
    const form = $("#brief-form");
    if (!form || form.dataset.suggestionApplied === "true") return;
    const raw = sessionStorage.getItem(SUGGESTION_KEY);
    if (!raw) return;
    try {
      const suggestion = JSON.parse(raw);
      form.elements.title.value = suggestion.title || "";
      form.elements.topic.value = suggestion.concept || suggestion.hook || "";
      form.elements.objective.value = suggestion.objective || "Educate and engage the target audience.";
      form.dataset.suggestionApplied = "true";
      sessionStorage.removeItem(SUGGESTION_KEY);
      toast("Suggestion added to the brief. Edit it before continuing.", "good");
    } catch { sessionStorage.removeItem(SUGGESTION_KEY); }
  }

  async function enhanceWizardSource() {
    rememberWizardBrand();
    prefillBrief();
    const target = $("#wizard-source-extra");
    if (!target || target.dataset.enhanced === "true" || suggestionBusy) return;
    const selected = $('input[name="wizard-start"]:checked')?.value;
    if (!selected || selected === "manual_topic") return;
    target.dataset.enhanced = "true";
    if (selected === "suggestion") {
      target.innerHTML = `<div class="notice"><strong>Generate a small suggestion set</strong>Choose one idea here; it will be copied into the editable brief.</div><div class="button-row" style="margin-top:12px"><button id="wizard-generate-suggestions" class="secondary-button">Generate 6 suggestions</button></div><div id="wizard-suggestion-list" class="content-card-list" style="margin-top:12px"></div>`;
      $("#wizard-generate-suggestions").addEventListener("click", async (event) => {
        suggestionBusy = true;
        await withButton(event.currentTarget, async () => {
          const brandId = sessionStorage.getItem(BRAND_KEY);
          if (!brandId) throw new Error("Choose a brand first.");
          const month = new Date().toISOString().slice(0, 7) + "-01";
          const seed = Number(month.replaceAll("-", ""));
          const result = await window.StudioApi.generateConcepts({
            brand_id: brandId,
            month_start: month,
            candidate_count: 6,
            format_mix: { vertical_short: 6 },
            pillar_targets: { education: 2, conservation: 2, myth: 2 },
            seed,
            adapter_mode: "deterministic"
          });
          const batch = await window.StudioApi.conceptBatch(result.batch.id);
          const list = $("#wizard-suggestion-list");
          list.innerHTML = (batch.candidates || []).map((item) => `<article class="content-card"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.hook || item.concept)}</p><button class="primary-button" data-use-suggestion="${escapeHtml(item.id)}">Use this idea</button></article>`).join("");
          $$('[data-use-suggestion]', list).forEach((button) => button.addEventListener("click", () => {
            const candidate = (batch.candidates || []).find((item) => String(item.id) === button.dataset.useSuggestion);
            sessionStorage.setItem(SUGGESTION_KEY, JSON.stringify(candidate));
            $("#wizard-next")?.click();
          }));
        });
        suggestionBusy = false;
      });
    } else {
      target.innerHTML = '<div class="notice"><strong>Use an existing approved plan item</strong>Select an existing content record instead of creating a duplicate.</div><div id="wizard-approved-list" class="content-card-list" style="margin-top:12px"><div class="skeleton"></div></div>';
      try {
        const payload = await window.StudioApi.queue({ brandId: sessionStorage.getItem(BRAND_KEY) || undefined });
        const items = payload.items || [];
        $("#wizard-approved-list").innerHTML = items.length ? items.slice(0, 12).map((item) => `<article class="content-card"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.concept || "Approved plan content")} · ${escapeHtml(humanize(item.stage))}</p><a class="primary-button" href="/app/content/${item.id}">Open this item</a></article>`).join("") : '<div class="empty-state"><h3>No existing plan items</h3><p>Create a topic manually or generate suggestions.</p></div>';
      } catch (error) {
        $("#wizard-approved-list").innerHTML = `<div class="notice bad">${escapeHtml(errorText(error))}</div>`;
      }
    }
  }

  function pilotSession() {
    try { return JSON.parse(sessionStorage.getItem(PILOT_KEY) || "null"); }
    catch { return null; }
  }

  function savePilotSession(value) {
    sessionStorage.setItem(PILOT_KEY, JSON.stringify(value));
  }

  function candidateOption(candidate, mode) {
    const report = candidate.modes?.[mode] || {};
    const selectable = report.selection_ready && !candidate.already_bound_to_active_or_accepted_pilot;
    const label = `${candidate.title} · v${candidate.content_version}${selectable ? "" : ` · blocked: ${(report.selection_blockers || []).map(humanize).join(", ") || "not ready"}`}`;
    return `<option value="${candidate.portfolio_content_id}" data-version="${candidate.content_version}" ${selectable ? "" : "disabled"}>${escapeHtml(label)}</option>`;
  }

  async function enhanceP100() {
    if (pilotBusy || !isAdmin() || window.location.pathname !== "/app/operations") return;
    const view = $("#app-view");
    if (!view || $("#p100-control-center", view)) return;
    pilotBusy = true;
    const section = document.createElement("section");
    section.id = "p100-control-center";
    section.className = "card";
    section.style.marginTop = "18px";
    section.innerHTML = '<div class="card-header"><div><h2>P100 controlled pilot</h2><p>Loading canonical candidates and readiness…</p></div></div><div class="skeleton"></div>';
    view.appendChild(section);
    try {
      const inventory = await window.StudioApi.acceptanceCandidates();
      if (!document.body.contains(section)) return;
      const candidates = inventory.candidates || [];
      const slots = [
        ["rawr-nation", "local_only", "Rawr Nation · Local"],
        ["rawr-nation", "managed_render", "Rawr Nation · Managed"],
        ["animal-x", "local_only", "Animal X · Local"],
        ["animal-x", "managed_render", "Animal X · Managed"]
      ];
      section.innerHTML = `<div class="card-header"><div><h2>P100 controlled pilot</h2><p>Select exactly one local and one managed item per brand. Managed slots remain blocked until renderer lineage and spend evidence exist.</p></div><button id="p100-refresh" class="secondary-button">Refresh</button></div>
        <div class="form-grid">${slots.map(([brand,mode,label], index) => `<label>${escapeHtml(label)}<select data-pilot-slot="${index}" data-brand="${brand}" data-mode="${mode}"><option value="">Choose a candidate</option>${candidates.filter((item) => item.brand_slug === brand).map((item) => candidateOption(item, mode)).join("")}</select></label>`).join("")}
          <label class="wide">External live-result evidence item<select id="p100-live-slot"><option value="0">Rawr Nation · Local</option><option value="1">Rawr Nation · Managed</option><option value="2">Animal X · Local</option><option value="3">Animal X · Managed</option></select></label>
          <label class="wide">Pilot key<input id="p100-pilot-key" value="p100-local-team-pilot" pattern="[a-z0-9][a-z0-9._-]{7,119}"></label>
        </div>
        <div id="p100-action-area" style="margin-top:16px"></div>
        <div class="button-row" style="margin-top:16px"><button id="p100-bootstrap" class="primary-button">Create controlled draft</button><button id="p100-start" class="secondary-button" disabled>Start controlled pilot</button></div>`;
      $("#p100-refresh").addEventListener("click", () => { section.remove(); void enhanceP100(); });
      $("#p100-bootstrap").addEventListener("click", (event) => bootstrapPilot(event.currentTarget, candidates));
      $("#p100-start").addEventListener("click", (event) => startPilot(event.currentTarget));
      await renderStoredPilot();
    } catch (error) {
      section.innerHTML = `<div class="card-header"><div><h2>P100 controlled pilot</h2></div></div><div class="notice bad"><strong>Candidate inventory unavailable</strong>${escapeHtml(errorText(error))}</div>`;
    } finally { pilotBusy = false; }
  }

  async function bootstrapPilot(button, candidates) {
    const selects = $$('[data-pilot-slot]');
    const liveIndex = Number($("#p100-live-slot").value);
    const selected = selects.map((select, index) => {
      const candidate = candidates.find((item) => item.portfolio_content_id === select.value);
      return candidate ? {
        portfolio_content_id: candidate.portfolio_content_id,
        content_version: candidate.content_version,
        production_mode: select.dataset.mode,
        live_delivery_evidence_required: index === liveIndex
      } : null;
    });
    if (selected.some((item) => !item)) return toast("Choose one selectable candidate for all four pilot slots.", "bad");
    if (new Set(selected.map((item) => item.portfolio_content_id)).size !== 4) return toast("The four pilot items must be unique.", "bad");
    await withButton(button, async () => {
      const result = await window.StudioApi.request("/acceptance/pilots/bootstrap-draft", {
        method: "POST",
        body: JSON.stringify({
          pilot_key: $("#p100-pilot-key").value.trim(),
          acceptance_policy: { human_approval_required: true, staging_delivery: "simulated_only", live_delivery: "external_evidence_after_signoff" },
          items: selected
        })
      });
      savePilotSession({
        pilot_id: result.pilot.id,
        bootstrap_request_sha256: result.bootstrap_request_sha256,
        runbook_sha256: result.runbook.sha256
      });
      toast("Controlled draft created.", "good");
      await renderStoredPilot();
    });
  }

  async function renderStoredPilot() {
    const session = pilotSession();
    const area = $("#p100-action-area");
    const startButton = $("#p100-start");
    if (!area || !session) return;
    try {
      const [pilot, readiness, startReadiness] = await Promise.all([
        window.StudioApi.pilot(session.pilot_id),
        window.StudioApi.pilotReadiness(session.pilot_id),
        window.StudioApi.request(`/acceptance/pilots/${session.pilot_id}/start-readiness`)
      ]);
      const canStart = Boolean(startReadiness.can_start);
      area.innerHTML = `<div class="notice ${canStart ? "good" : "warn"}"><strong>Pilot ${escapeHtml(humanize(pilot.pilot?.status || "draft"))}</strong>${canStart ? "All controlled-start checks passed." : escapeHtml((startReadiness.blockers || startReadiness.readiness?.blockers || []).map((item) => item.message || humanize(item.code || item)).join(" · ") || "Pilot items still need required evidence.")}</div><p style="color:var(--muted)">${escapeHtml(readiness.passed_count || readiness.summary?.passed_count || 0)} evidence checks passed.</p>`;
      startButton.disabled = !canStart || pilot.pilot?.status !== "draft";
    } catch (error) {
      area.innerHTML = `<div class="notice bad">${escapeHtml(errorText(error))}</div>`;
      startButton.disabled = true;
    }
  }

  async function startPilot(button) {
    const session = pilotSession();
    if (!session) return toast("Create or reload the controlled draft first.", "bad");
    await withButton(button, async () => {
      await window.StudioApi.request(`/acceptance/pilots/${session.pilot_id}/start-controlled`, {
        method: "POST",
        body: JSON.stringify({ bootstrap_request_sha256: session.bootstrap_request_sha256, runbook_sha256: session.runbook_sha256 })
      });
      toast("Controlled pilot started.", "good");
      await renderStoredPilot();
    });
  }

  async function enhance() {
    if (!window.StudioApi?.configured()) return;
    if (!access) await refreshAccess();
    ensurePublisherNavigation();
    if (window.location.pathname === "/app/publishing") await renderPublishing();
    await enhanceWizardSource();
    await enhanceP100();
  }

  const observer = new MutationObserver(() => window.setTimeout(enhance, 50));
  observer.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("change", (event) => {
    if (event.target.matches('input[name="wizard-brand"]')) rememberWizardBrand();
  }, true);
  window.addEventListener("popstate", () => window.setTimeout(enhance, 250));
  document.addEventListener("DOMContentLoaded", () => window.setTimeout(enhance, 350), { once: true });
})();
