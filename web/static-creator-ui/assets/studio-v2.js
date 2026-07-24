(() => {
  const state = {
    access: null,
    brands: [],
    overview: null,
    route: null,
    routeData: null,
    polling: null,
    refreshToken: 0,
    wizard: { step: 1, brandId: "", startingPoint: "manual_topic" },
    settingsTab: "runtime"
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const view = () => $("#app-view");
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  const humanize = (value) => String(value || "unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const dateValue = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(`${String(value).slice(0, 10)}T00:00:00`)) : "Not scheduled";
  const dateTime = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
  const roles = () => state.access?.operator?.roles || [];
  const isAdmin = () => Boolean(state.access?.operator?.portfolio_wide) || roles().includes("admin");
  const hasRole = (role) => isAdmin() || roles().includes(role);
  const contentPath = (id, tab = "overview") => `/app/content/${id}${tab === "overview" ? "" : `/${tab}`}`;
  const currentRoutePath = () => window.location.pathname.startsWith("/app") ? window.location.pathname : "/app/dashboard";

  const navItems = () => [
    { path: "/app/dashboard", label: "Dashboard", icon: "⌂", show: true },
    { path: "/app/content", label: "Content", icon: "▤", show: true },
    { path: "/app/content/new", label: "Create content", icon: "+", show: hasRole("producer") },
    { path: "/app/reviews", label: "Reviews", icon: "✓", show: hasRole("reviewer") },
    { path: "/app/team", label: "Team & access", icon: "◎", show: isAdmin() },
    { path: "/app/settings", label: "Settings", icon: "⚙", show: isAdmin() },
    { path: "/app/operations", label: "Operations", icon: "◫", show: isAdmin() }
  ].filter((item) => item.show);

  function toast(message, kind = "") {
    const node = document.createElement("div");
    node.className = `toast ${kind}`.trim();
    node.textContent = message;
    $("#toast-region").appendChild(node);
    window.setTimeout(() => node.remove(), 5000);
  }

  function errorText(error) {
    const detail = error?.payload?.detail;
    if (detail && typeof detail === "object") {
      if (Array.isArray(detail.blockers) && detail.blockers.length) return detail.blockers.map((item) => item.message || humanize(item.code)).join(" ");
      if (detail.code) return humanize(detail.code);
    }
    return error?.message || "Something went wrong.";
  }

  function statusBadge(status, label = null) {
    const safe = String(status || "draft").toLowerCase();
    return `<span class="status-badge status-${escapeHtml(safe)}">${escapeHtml(label || humanize(safe))}</span>`;
  }

  function emptyState(title, body, action = "") {
    return `<div class="empty-state"><div class="empty-icon">○</div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(body)}</p>${action}</div>`;
  }

  function loadingCards(count = 3) {
    return `<div class="grid ${count > 2 ? "three" : "two"}">${Array.from({ length: count }, () => '<div class="skeleton"></div>').join("")}</div>`;
  }

  function setPage(title, subtitle, eyebrow = "Creator Studio") {
    $("#page-title").textContent = title;
    $("#page-subtitle").textContent = subtitle;
    $("#page-eyebrow").textContent = eyebrow;
    document.title = `${title} · Content Engine Studio`;
  }

  function renderSession() {
    const operator = state.access?.operator;
    if (!operator) return;
    $("#session-card").innerHTML = `<strong>${escapeHtml(operator.display_name || operator.operator_id)}</strong><span>${escapeHtml(roles().map(humanize).join(", ") || "Read only")}</span>`;
  }

  function renderNavigation() {
    const path = currentRoutePath();
    $("#primary-nav").innerHTML = navItems().map((item) => {
      const active = path === item.path || (item.path === "/app/content" && path.startsWith("/app/content/") && path !== "/app/content/new");
      const badge = item.path === "/app/reviews" && state.overview?.counts?.awaiting_review ? `<span class="nav-badge">${state.overview.counts.awaiting_review}</span>` : "";
      return `<a class="nav-link ${active ? "active" : ""}" href="${item.path}" data-route><span class="nav-icon">${item.icon}</span><span>${escapeHtml(item.label)}</span>${badge}</a>`;
    }).join("");
  }

  async function updateRuntimeChip() {
    const chip = $("#sidebar-runtime");
    try {
      const ready = await StudioApi.ready();
      chip.className = `runtime-chip ${ready.ok ? "good" : "bad"}`;
      chip.innerHTML = `<span class="status-dot"></span><span>${ready.ok ? "Local system ready" : "Runtime unavailable"}</span>`;
    } catch (error) {
      chip.className = "runtime-chip bad";
      chip.innerHTML = `<span class="status-dot"></span><span>${escapeHtml(errorText(error))}</span>`;
    }
  }

  function navigate(path, { replace = false } = {}) {
    stopPolling();
    if (replace) history.replaceState({}, "", path); else history.pushState({}, "", path);
    void loadRoute();
  }

  function routeLinkHandler(event) {
    const link = event.target.closest("[data-route]");
    if (!link) return;
    const href = link.getAttribute("href");
    if (!href || !href.startsWith("/app")) return;
    event.preventDefault();
    navigate(href);
  }

  function stopPolling() {
    if (state.polling) window.clearInterval(state.polling);
    state.polling = null;
  }

  function startPolling(callback, milliseconds) {
    stopPolling();
    state.polling = window.setInterval(() => {
      if (!document.hidden) void callback(true);
    }, milliseconds);
  }

  async function withButton(button, task, successMessage = "") {
    const original = button?.innerHTML;
    if (button) {
      button.disabled = true;
      button.innerHTML = "Working…";
    }
    try {
      const result = await task();
      if (successMessage) toast(successMessage, "good");
      return result;
    } catch (error) {
      toast(errorText(error), "bad");
      throw error;
    } finally {
      if (button) {
        button.disabled = false;
        button.innerHTML = original;
      }
    }
  }

  async function authenticateSavedSession() {
    state.access = await StudioApi.access();
    const brandPayload = await StudioApi.brands();
    state.brands = brandPayload.brands || [];
    renderSession();
    renderNavigation();
    $("#boot-screen").hidden = true;
    $("#studio-shell").hidden = false;
    await updateRuntimeChip();
  }

  function showLogin(message = "") {
    $("#boot-screen").hidden = true;
    $("#studio-shell").hidden = true;
    $("#login-error").textContent = message;
    $("#operator-key").value = "";
    const dialog = $("#login-dialog");
    if (!dialog.open) dialog.showModal();
  }

  async function boot() {
    $("#boot-message").textContent = "Checking the local API, database, and access…";
    try {
      await StudioApi.ready();
      if (!StudioApi.configured()) return showLogin();
      await authenticateSavedSession();
      const initial = currentRoutePath() === "/" ? "/app/dashboard" : currentRoutePath();
      if (!window.location.pathname.startsWith("/app")) history.replaceState({}, "", initial);
      await loadRoute();
    } catch (error) {
      if (error.status === 401 || error.status === 403 || /operator key/i.test(error.message)) {
        StudioApi.disconnect();
        return showLogin("Your saved access key is no longer valid. Sign in again.");
      }
      $("#boot-message").textContent = errorText(error);
      $(".loading-bar", $("#boot-screen")).hidden = true;
    }
  }

  function parseRoute() {
    const path = currentRoutePath().replace(/\/+$/, "") || "/app/dashboard";
    const segments = path.split("/").filter(Boolean);
    if (path === "/app" || path === "/app/dashboard") return { name: "dashboard", path };
    if (path === "/app/content") return { name: "content", path };
    if (path === "/app/content/new") return { name: "new-content", path };
    if (segments[1] === "content" && segments[2]) return { name: "content-detail", path, contentId: segments[2], tab: segments[3] || "overview" };
    if (path === "/app/reviews") return { name: "reviews", path };
    if (path === "/app/team") return { name: "team", path };
    if (path === "/app/settings") return { name: "settings", path };
    if (path === "/app/operations") return { name: "operations", path };
    return { name: "not-found", path };
  }

  async function loadRoute() {
    state.route = parseRoute();
    state.refreshToken += 1;
    const token = state.refreshToken;
    renderNavigation();
    view().innerHTML = loadingCards(3);
    view().focus();
    try {
      if (state.route.name === "dashboard") await renderDashboard(token);
      else if (state.route.name === "content") await renderContentList(token);
      else if (state.route.name === "new-content") await renderCreateContent(token);
      else if (state.route.name === "content-detail") await renderContentDetail(token);
      else if (state.route.name === "reviews") await renderReviews(token);
      else if (state.route.name === "team") await renderTeam(token);
      else if (state.route.name === "settings") await renderSettings(token);
      else if (state.route.name === "operations") await renderOperations(token);
      else renderNotFound();
    } catch (error) {
      if (token !== state.refreshToken) return;
      setPage("Something went wrong", "The requested screen could not be loaded.");
      view().innerHTML = `<div class="notice bad"><strong>Unable to load this screen</strong>${escapeHtml(errorText(error))}</div><div class="button-row" style="margin-top:16px"><button id="retry-screen" class="primary-button">Try again</button><a class="secondary-button" href="/app/dashboard" data-route>Return to dashboard</a></div>`;
      $("#retry-screen")?.addEventListener("click", () => void loadRoute());
    }
  }

  async function refreshOverview() {
    state.overview = await StudioApi.overview();
    renderNavigation();
    return state.overview;
  }

  function attentionCard(item) {
    const content = item.item || {};
    const action = item.next_actions?.[0];
    return `<article class="attention-item"><div><div class="button-row"><h3>${escapeHtml(content.title || "Untitled content")}</h3>${statusBadge(item.status, item.status_label)}</div><p>${escapeHtml(content.brand_name || "Brand")} · ${escapeHtml(humanize(content.format || "content"))}${item.blockers?.length ? ` · ${escapeHtml(item.blockers[0].message || humanize(item.blockers[0].code))}` : ""}</p></div><a class="primary-button" href="${contentPath(content.id)}" data-route>${escapeHtml(action?.label || "Open content")}</a></article>`;
  }

  async function renderDashboard(token) {
    setPage("Dashboard", "See what needs attention and move content forward.");
    const overview = await refreshOverview();
    if (token !== state.refreshToken) return;
    const counts = overview.counts || {};
    view().innerHTML = `
      <div class="page-actions"><div><h2>Today’s workspace</h2><p>The system shows only real database-backed content and jobs.</p></div>${hasRole("producer") ? '<a class="primary-button" href="/app/content/new" data-route>+ Create content</a>' : '<a class="primary-button" href="/app/reviews" data-route>Open review inbox</a>'}</div>
      <section class="grid four">
        <article class="metric-card"><strong>${counts.content || 0}</strong><span>Content items</span></article>
        <article class="metric-card"><strong>${counts.awaiting_review || 0}</strong><span>Awaiting review</span></article>
        <article class="metric-card"><strong>${counts.active_jobs || 0}</strong><span>Jobs running or queued</span></article>
        <article class="metric-card ${counts.failed_jobs ? "alert" : ""}"><strong>${counts.failed_jobs || 0}</strong><span>Failed jobs</span></article>
      </section>
      <section class="grid two" style="margin-top:18px">
        <article class="card"><div class="card-header"><div><h2>Needs attention</h2><p>Items that require a decision or correction.</p></div><a class="ghost-button" href="/app/content" data-route>View all</a></div><div class="attention-list">${overview.attention?.length ? overview.attention.map(attentionCard).join("") : emptyState("Nothing is blocked", "No content currently needs an urgent decision.")}</div></article>
        <article class="card"><div class="card-header"><div><h2>Recent content</h2><p>Continue from the latest real production records.</p></div></div><div class="content-card-list">${overview.recent?.length ? overview.recent.slice(0, 6).map((item) => `<a class="content-card" href="${contentPath(item.item.id)}" data-route><div class="button-row between"><h3>${escapeHtml(item.item.title)}</h3>${statusBadge(item.status, item.status_label)}</div><p>${escapeHtml(item.item.brand_name)} · ${dateValue(item.item.scheduled_for)}</p></a>`).join("") : emptyState("No content yet", "Create the first content item to begin local production.", hasRole("producer") ? '<a class="primary-button" href="/app/content/new" data-route>Create content</a>' : "")}</div></article>
      </section>`;
    startPolling(() => renderDashboard(state.refreshToken), 15000);
  }

  async function loadContentStates(items, limit = 100) {
    const selected = items.slice(0, limit);
    const results = await Promise.allSettled(selected.map((item) => StudioApi.contentState(item.id)));
    return selected.map((item, index) => results[index].status === "fulfilled" ? results[index].value : ({ item, status: "blocked", status_label: "State unavailable", blockers: [{ message: errorText(results[index].reason) }], next_actions: [] }));
  }

  function contentRow(item) {
    const content = item.item || {};
    const action = item.next_actions?.[0];
    return `<tr data-content-row="${escapeHtml(content.id)}"><td><a href="${contentPath(content.id)}" data-route><span class="item-title">${escapeHtml(content.title || "Untitled")}</span><span class="item-subtitle">${escapeHtml(content.concept || "No brief")}</span></a></td><td>${escapeHtml(content.brand_name || "—")}</td><td>${statusBadge(item.status, item.status_label)}</td><td>${escapeHtml(dateValue(content.scheduled_for))}</td><td><span class="next-action">${escapeHtml(action?.label || (item.blockers?.[0]?.message || "Open content"))}</span></td><td><a class="table-action" href="${contentPath(content.id)}" data-route>Open</a></td></tr>`;
  }

  async function renderContentList(token) {
    setPage("Content", "Every idea, script, media item, and preview in one understandable list.");
    const [queuePayload] = await Promise.all([StudioApi.queue(), refreshOverview()]);
    const states = await loadContentStates(queuePayload.items || []);
    if (token !== state.refreshToken) return;
    state.routeData = states;
    view().innerHTML = `
      <div class="page-actions"><div><h2>Content library</h2><p>Open an item to see its exact status and next action.</p></div>${hasRole("producer") ? '<a class="primary-button" href="/app/content/new" data-route>+ Create content</a>' : ""}</div>
      <section class="card flush">
        <div class="toolbar" style="padding:18px 18px 0">
          <label class="search-field">Search<input id="content-search" placeholder="Search title or topic"></label>
          <label>Brand<select id="content-brand-filter"><option value="">All brands</option>${state.brands.map((brand) => `<option value="${brand.id}">${escapeHtml(brand.display_name)}</option>`).join("")}</select></label>
          <label>Status<select id="content-status-filter"><option value="">All statuses</option><option value="draft">Draft</option><option value="awaiting_review">Awaiting review</option><option value="in_production">In production</option><option value="blocked">Blocked</option><option value="ready">Ready</option></select></label>
        </div>
        <div class="table-wrap"><table class="data-table"><thead><tr><th>Content</th><th>Brand</th><th>Status</th><th>Schedule</th><th>Next action</th><th></th></tr></thead><tbody id="content-table-body">${states.length ? states.map(contentRow).join("") : `<tr><td colspan="6">${emptyState("No content yet", "Create a brief and queue the first local script.")}</td></tr>`}</tbody></table></div>
      </section>`;
    const applyFilters = () => {
      const search = $("#content-search").value.trim().toLowerCase();
      const brandId = $("#content-brand-filter").value;
      const status = $("#content-status-filter").value;
      const filtered = states.filter((item) => {
        const content = item.item || {};
        return (!search || `${content.title} ${content.concept}`.toLowerCase().includes(search)) && (!brandId || String(content.brand_id) === brandId) && (!status || item.status === status);
      });
      $("#content-table-body").innerHTML = filtered.length ? filtered.map(contentRow).join("") : `<tr><td colspan="6">${emptyState("No matching content", "Adjust the filters to see other items.")}</td></tr>`;
    };
    ["#content-search", "#content-brand-filter", "#content-status-filter"].forEach((selector) => $(selector).addEventListener("input", applyFilters));
  }

  function wizardProgress(step) {
    const labels = ["Brand", "Starting point", "Brief", "Confirm"];
    return `<div class="wizard-progress">${labels.map((label, index) => `<div class="wizard-step ${index + 1 === step ? "active" : index + 1 < step ? "done" : ""}">${index + 1}. ${label}</div>`).join("")}</div>`;
  }

  async function renderCreateContent(token) {
    if (!hasRole("producer")) return navigate("/app/dashboard", { replace: true });
    setPage("Create content", "A guided brief that queues a real local script job.");
    if (!state.brands.length) {
      const brands = await StudioApi.brands();
      state.brands = brands.brands || [];
    }
    if (token !== state.refreshToken) return;
    state.wizard = { step: 1, brandId: state.wizard.brandId || state.brands[0]?.id || "", startingPoint: state.wizard.startingPoint || "manual_topic", suggestions: [] };
    renderWizard();
  }

  function renderWizard() {
    const wizard = state.wizard;
    const brand = state.brands.find((item) => String(item.id) === String(wizard.brandId));
    let panel = "";
    if (wizard.step === 1) {
      panel = `<h2>Choose a brand</h2><p>Select the brand this content belongs to. The correct profile, language, voice, and visual rules will follow it.</p><div class="choice-grid">${state.brands.map((item) => `<label class="choice-card ${String(item.id) === String(wizard.brandId) ? "selected" : ""}"><input type="radio" name="wizard-brand" value="${item.id}" ${String(item.id) === String(wizard.brandId) ? "checked" : ""}><strong>${escapeHtml(item.display_name)}</strong><span>${escapeHtml(item.niche || "Content brand")} · ${escapeHtml(item.monthly_target)} monthly target</span></label>`).join("")}</div>`;
    } else if (wizard.step === 2) {
      panel = `<h2>How do you want to start?</h2><p>You can write a topic directly, ask for suggestions, or use an already approved plan idea.</p><div class="choice-grid">
        ${[["manual_topic","Write my own topic","Start with a specific topic or message."],["suggestion","Generate topic suggestions","Create a small reviewable idea set."],["approved_plan","Use an approved plan idea","Choose an existing approved content item."]].map(([value,title,body]) => `<label class="choice-card ${wizard.startingPoint === value ? "selected" : ""}"><input type="radio" name="wizard-start" value="${value}" ${wizard.startingPoint === value ? "checked" : ""}><strong>${title}</strong><span>${body}</span></label>`).join("")}
      </div><div id="wizard-source-extra" style="margin-top:18px"></div>`;
    } else if (wizard.step === 3) {
      const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
      panel = `<h2>Describe the content</h2><p>Only the information a content producer needs. Technical model settings stay in Settings.</p><form id="brief-form" class="form-grid">
        <label class="wide">Title<input name="title" required minlength="3" maxlength="240" value="${escapeHtml(wizard.title || "")}" placeholder="A clear working title"></label>
        <label class="wide">Topic or core message<textarea name="topic" required minlength="3" maxlength="3000" placeholder="What should the audience learn, feel, or do?">${escapeHtml(wizard.topic || "")}</textarea></label>
        <label>Objective<input name="objective" maxlength="2000" value="${escapeHtml(wizard.objective || "")}" placeholder="Educate, entertain, build trust…"></label>
        <label>Audience<input name="audience" maxlength="1000" value="${escapeHtml(wizard.audience || "")}" placeholder="Who is this for?"></label>
        <label>Platform<select name="platform"><option value="facebook">Facebook</option><option value="instagram">Instagram</option><option value="youtube_shorts">YouTube Shorts</option><option value="tiktok">TikTok</option></select></label>
        <label>Format<select name="format_name"><option value="vertical_short">Vertical short</option><option value="carousel">Carousel</option><option value="explainer">Explainer</option></select></label>
        <label>Duration<select name="duration_seconds"><option value="30">30 seconds</option><option value="45" selected>45 seconds</option><option value="60">60 seconds</option><option value="90">90 seconds</option></select></label>
        <label>Language<select name="language"><option value="en-US">English</option><option value="ur-PK">Urdu</option></select></label>
        <label>Schedule date<input name="scheduled_for" type="date" value="${escapeHtml(wizard.scheduledFor || tomorrow)}" required></label>
        <label class="wide">Optional notes<textarea name="notes" maxlength="5000" placeholder="Tone, must-include points, exclusions, or references">${escapeHtml(wizard.notes || "")}</textarea></label>
      </form>`;
    } else {
      panel = `<h2>Confirm and generate</h2><p>This creates a real content record, prepares its workflow, and queues a local Ollama script job.</p><dl class="review-summary">
        <div><dt>Brand</dt><dd>${escapeHtml(brand?.display_name || "—")}</dd></div><div><dt>Starting point</dt><dd>${escapeHtml(humanize(wizard.startingPoint))}</dd></div><div><dt>Title</dt><dd>${escapeHtml(wizard.title)}</dd></div><div><dt>Topic</dt><dd>${escapeHtml(wizard.topic)}</dd></div><div><dt>Platform and format</dt><dd>${escapeHtml(humanize(wizard.platform))} · ${escapeHtml(humanize(wizard.formatName))}</dd></div><div><dt>Duration and language</dt><dd>${escapeHtml(wizard.durationSeconds)} seconds · ${escapeHtml(wizard.language)}</dd></div><div><dt>Schedule</dt><dd>${escapeHtml(dateValue(wizard.scheduledFor))}</dd></div>
      </dl><div class="notice good" style="margin-top:18px"><strong>Local and controlled</strong>The job uses your local Ollama model. Nothing is automatically approved or published.</div>`;
    }
    view().innerHTML = `<div class="wizard-shell">${wizardProgress(wizard.step)}<section class="wizard-panel">${panel}<div class="button-row between" style="margin-top:24px"><button id="wizard-back" class="secondary-button" ${wizard.step === 1 ? "disabled" : ""}>Back</button>${wizard.step < 4 ? '<button id="wizard-next" class="primary-button">Continue</button>' : '<button id="wizard-create" class="primary-button">Create and generate script</button>'}</div></section></div>`;
    bindWizard();
  }

  function saveBriefForm() {
    const form = $("#brief-form");
    if (!form) return true;
    if (!form.reportValidity()) return false;
    const data = new FormData(form);
    Object.assign(state.wizard, {
      title: data.get("title"), topic: data.get("topic"), objective: data.get("objective"), audience: data.get("audience"),
      platform: data.get("platform"), formatName: data.get("format_name"), durationSeconds: Number(data.get("duration_seconds")), language: data.get("language"), scheduledFor: data.get("scheduled_for"), notes: data.get("notes")
    });
    return true;
  }

  function bindWizard() {
    $$('input[name="wizard-brand"]').forEach((input) => input.addEventListener("change", () => { state.wizard.brandId = input.value; renderWizard(); }));
    $$('input[name="wizard-start"]').forEach((input) => input.addEventListener("change", () => { state.wizard.startingPoint = input.value; renderWizard(); }));
    $("#wizard-back")?.addEventListener("click", () => { if (state.wizard.step === 4) saveBriefForm(); state.wizard.step -= 1; renderWizard(); });
    $("#wizard-next")?.addEventListener("click", async () => {
      if (state.wizard.step === 1 && !state.wizard.brandId) return toast("Choose a brand.", "bad");
      if (state.wizard.step === 3 && !saveBriefForm()) return;
      state.wizard.step += 1;
      renderWizard();
      if (state.wizard.step === 3 && state.wizard.startingPoint === "suggestion") toast("Enter the selected suggestion as the topic. A dedicated suggestion picker is available under Settings → Ideas.");
    });
    $("#wizard-create")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      await withButton(button, async () => {
        const result = await StudioApi.createContent({
          brand_id: state.wizard.brandId,
          title: state.wizard.title,
          topic: state.wizard.topic,
          objective: state.wizard.objective || "",
          audience: state.wizard.audience || "",
          platform: state.wizard.platform || "facebook",
          format_name: state.wizard.formatName || "vertical_short",
          duration_seconds: state.wizard.durationSeconds || 45,
          language: state.wizard.language || "en-US",
          scheduled_for: state.wizard.scheduledFor,
          notes: state.wizard.notes || "",
          generate_script: true,
          starting_point: state.wizard.startingPoint
        });
        toast("Content created. The local script job is queued.", "good");
        state.wizard = { step: 1, brandId: "", startingPoint: "manual_topic" };
        navigate(contentPath(result.content_id, "script"));
      });
    });
  }

  function pipelineSteps(data) {
    const scriptStatus = data.script?.current_version_status;
    const audioStatus = data.audio?.status;
    const visualStatus = data.visual?.status;
    const preview = data.artifacts?.find((item) => ["preview", "final_video"].includes(item.kind));
    const activeJobTypes = new Set((data.jobs || []).filter((job) => ["queued", "running"].includes(job.status)).map((job) => job.job_type));
    const steps = [
      ["Brief", true, "The content brief is saved."],
      ["Script", scriptStatus === "approved", scriptStatus ? humanize(scriptStatus) : activeJobTypes.has("script") ? "Generating" : "Not generated"],
      ["Narration", ["approved", "completed"].includes(audioStatus), audioStatus ? humanize(audioStatus) : activeJobTypes.has("narration") ? "Generating" : "Not started"],
      ["Visuals", ["approved", "completed"].includes(visualStatus), visualStatus ? humanize(visualStatus) : activeJobTypes.has("keyframe") ? "Generating" : "Not started"],
      ["Preview", Boolean(preview), preview ? "MP4 ready" : activeJobTypes.has("preview") ? "Generating" : "Not started"]
    ];
    const currentIndex = steps.findIndex(([, complete]) => !complete);
    return `<div class="pipeline-stepper">${steps.map(([label, complete, detail], index) => `<div class="pipeline-step ${complete ? "complete" : index === currentIndex ? "current" : ""}"><strong>${complete ? "✓ " : ""}${label}</strong><span>${escapeHtml(detail)}</span></div>`).join("")}</div>`;
  }

  function currentScript(scriptPayload) {
    if (!scriptPayload?.document) return null;
    const currentId = String(scriptPayload.document.current_version_id || "");
    return {
      document: scriptPayload.document,
      version: (scriptPayload.versions || []).find((item) => String(item.id) === currentId) || null,
      sections: (scriptPayload.sections || []).filter((item) => String(item.script_version_id) === currentId),
      claims: (scriptPayload.claims || []).filter((item) => String(item.script_version_id) === currentId),
      sources: (scriptPayload.sources || []).filter((item) => String(item.script_version_id) === currentId),
      actions: (scriptPayload.review_actions || []).filter((item) => String(item.script_version_id) === currentId && !item.resolved_at)
    };
  }

  async function contentBundle(contentId) {
    const statePayload = await StudioApi.contentState(contentId);
    const tasks = [];
    tasks.push(statePayload.script ? StudioApi.scriptForContent(contentId) : Promise.resolve(null));
    tasks.push(statePayload.audio ? StudioApi.audioForContent(contentId) : Promise.resolve(null));
    tasks.push(statePayload.visual ? StudioApi.visualsForContent(contentId) : Promise.resolve(null));
    const [scriptResult, audioResult, visualResult] = await Promise.allSettled(tasks);
    return {
      state: statePayload,
      script: scriptResult.status === "fulfilled" ? scriptResult.value : null,
      audio: audioResult.status === "fulfilled" ? audioResult.value : null,
      visual: visualResult.status === "fulfilled" ? visualResult.value : null
    };
  }

  async function renderContentDetail(token, silent = false) {
    const contentId = state.route.contentId;
    const bundle = await contentBundle(contentId);
    if (token !== state.refreshToken) return;
    state.routeData = bundle;
    const data = bundle.state;
    const item = data.item;
    setPage(item.title, `${item.brand_name} · ${data.status_label}`, "Content workspace");
    const tab = state.route.tab;
    const nav = [["overview","Overview"],["script","Script"],["production","Production"],["media","Media review"],["history","History"]];
    view().innerHTML = `
      <div class="breadcrumb"><a href="/app/content" data-route>Content</a><span>›</span><span>${escapeHtml(item.title)}</span></div>
      <div class="page-actions"><div><div class="button-row"><h2>${escapeHtml(item.title)}</h2>${statusBadge(data.status, data.status_label)}</div><p>${escapeHtml(item.concept || "No brief")} · ${escapeHtml(dateValue(item.scheduled_for))}</p></div><div class="button-row"><button id="content-refresh" class="secondary-button">Refresh</button>${hasRole("producer") && !data.script ? '<button id="quick-generate-script" class="primary-button">Generate script</button>' : ""}</div></div>
      <section class="card">${pipelineSteps(data)}</section>
      ${data.blockers?.length ? `<div class="notice warn" style="margin-top:16px"><strong>Before the next step</strong>${data.blockers.map((blocker) => escapeHtml(blocker.message || humanize(blocker.code))).join(" ")}</div>` : ""}
      <nav class="section-tabs" style="margin-top:18px">${nav.map(([value,label]) => `<a class="section-tab ${tab === value ? "active" : ""}" href="${contentPath(contentId,value)}" data-route>${label}</a>`).join("")}</nav>
      <div id="content-tab" style="margin-top:18px"></div>`;
    $("#content-refresh").addEventListener("click", () => renderContentDetail(state.refreshToken));
    $("#quick-generate-script")?.addEventListener("click", (event) => generateScriptAction(contentId, event.currentTarget));
    if (tab === "script") renderScriptTab(bundle);
    else if (tab === "production") renderProductionTab(bundle);
    else if (tab === "media") await renderMediaTab(bundle);
    else if (tab === "history") renderHistoryTab(bundle);
    else renderOverviewTab(bundle);
    if (!silent && (data.jobs || []).some((job) => ["queued", "running"].includes(job.status))) startPolling(() => renderContentDetail(state.refreshToken, true), 5000);
  }

  function renderOverviewTab(bundle) {
    const data = bundle.state;
    const item = data.item;
    const action = data.next_actions?.[0];
    $("#content-tab").innerHTML = `<div class="detail-layout"><div class="detail-main">
      <section class="card"><div class="card-header"><div><h2>What happens next</h2><p>The system calculates this from the real workflow and job state.</p></div></div>${action ? `<div class="notice ${data.status === "blocked" ? "warn" : "good"}"><strong>${escapeHtml(action.label)}</strong>${escapeHtml(data.blockers?.[0]?.message || "This action is ready for the appropriate role.")}</div><div class="button-row" style="margin-top:14px"><button class="primary-button" data-next-action="${escapeHtml(action.action)}">${escapeHtml(action.label)}</button></div>` : emptyState("No immediate action", "This item is waiting for another production event or review.")}</section>
      <section class="card"><div class="card-header"><div><h2>Brief</h2><p>The source information for this item.</p></div></div><dl class="definition-list"><div class="definition-row"><dt>Topic</dt><dd>${escapeHtml(item.concept || "—")}</dd></div><div class="definition-row"><dt>Format</dt><dd>${escapeHtml(humanize(item.format))}</dd></div><div class="definition-row"><dt>Schedule</dt><dd>${escapeHtml(dateValue(item.scheduled_for))}</dd></div><div class="definition-row"><dt>Content version</dt><dd>${escapeHtml(item.version)}</dd></div></dl></section>
    </div><aside class="detail-sidebar"><section class="card"><div class="card-header"><div><h3>Production summary</h3></div></div><dl class="definition-list"><div class="definition-row"><dt>Script</dt><dd>${escapeHtml(bundle.script ? humanize(currentScript(bundle.script)?.document?.current_version_status) : "Not generated")}</dd></div><div class="definition-row"><dt>Narration</dt><dd>${escapeHtml(bundle.audio ? humanize(bundle.audio.production?.status) : "Not started")}</dd></div><div class="definition-row"><dt>Visuals</dt><dd>${escapeHtml(bundle.visual ? humanize(bundle.visual.project?.status) : "Not started")}</dd></div><div class="definition-row"><dt>Jobs</dt><dd>${escapeHtml(data.jobs?.length || 0)}</dd></div></dl></section></aside></div>`;
    $("[data-next-action]")?.addEventListener("click", (event) => performNextAction(event.currentTarget.dataset.nextAction, event.currentTarget));
  }

  async function performNextAction(action, button) {
    const contentId = state.route.contentId;
    if (action === "generate_script") return generateScriptAction(contentId, button);
    if (action === "submit_script" || action === "review_script" || action === "revise_script") return navigate(contentPath(contentId, "script"));
    if (action === "start_local_production") return startProductionAction(contentId, button);
    if (["review_audio", "review_visuals", "review_preview"].includes(action)) return navigate(contentPath(contentId, "media"));
    if (action === "inspect_failed_jobs") return navigate(contentPath(contentId, "production"));
    toast("Open the relevant workspace tab to continue.");
  }

  function renderScriptTab(bundle) {
    const target = $("#content-tab");
    const script = currentScript(bundle.script);
    if (!script) {
      target.innerHTML = `<section class="card">${emptyState("No script exists yet", "Generate the first version with the local Ollama model. The job will continue in the background.", hasRole("producer") ? '<button id="generate-script" class="primary-button">Generate script</button>' : "A Producer must generate the first script.")}</section>`;
      $("#generate-script")?.addEventListener("click", (event) => generateScriptAction(state.route.contentId, event.currentTarget));
      return;
    }
    const document = script.document;
    const status = document.current_version_status || script.version?.status || "unknown";
    const unsupported = script.claims.filter((claim) => !["supported", "not_applicable"].includes(claim.support_status));
    target.innerHTML = `<div class="detail-layout"><div class="detail-main"><section class="card"><div class="card-header"><div><h2>Script version ${escapeHtml(document.current_version || script.version?.version || "")}</h2><p>${statusBadge(status)}</p></div><span>${escapeHtml(script.sections.reduce((sum, section) => sum + String(section.text || "").split(/\s+/).filter(Boolean).length, 0))} words</span></div><div>${script.sections.length ? script.sections.map((section) => `<article class="script-section"><strong>${escapeHtml(humanize(section.section_type))}</strong><p>${escapeHtml(section.text)}</p></article>`).join("") : '<p>No script sections were returned.</p>'}</div></section>
      <section class="card"><div class="card-header"><div><h2>Review decision</h2><p>Decisions apply to this exact version only.</p></div></div><div id="script-action-panel"></div></section></div>
      <aside class="detail-sidebar"><section class="card"><div class="card-header"><div><h3>Evidence gate</h3><p>${unsupported.length ? `${unsupported.length} claim(s) require attention.` : "All recorded claims pass the evidence gate."}</p></div></div><div class="evidence-list">${script.claims.length ? script.claims.map((claim) => `<div class="evidence-item ${["supported","not_applicable"].includes(claim.support_status) ? "good" : "warn"}"><strong>${escapeHtml(humanize(claim.support_status))}</strong><p>${escapeHtml(claim.claim_text)}</p></div>`).join("") : '<p>No factual claims recorded.</p>'}</div></section><section class="card"><div class="card-header"><div><h3>Sources</h3></div></div>${script.sources.length ? `<ul>${script.sources.map((source) => `<li><strong>${escapeHtml(source.title)}</strong>${source.publisher ? ` · ${escapeHtml(source.publisher)}` : ""}</li>`).join("")}</ul>` : '<p>No external sources were attached.</p>'}</section></aside></div>`;
    renderScriptActions(script, status);
  }

  function renderScriptActions(script, status) {
    const panel = $("#script-action-panel");
    const document = script.document;
    const lockVersion = Number(document.lock_version || 0);
    if (hasRole("producer") && status === "working") {
      panel.innerHTML = `<div class="notice good"><strong>Draft ready</strong>Review the text and submit it for an independent decision.</div><div class="button-row" style="margin-top:14px"><button id="submit-script" class="primary-button">Submit for review</button></div>`;
      $("#submit-script").addEventListener("click", (event) => withButton(event.currentTarget, async () => { await StudioApi.submitScript(document.id, lockVersion); toast("Script submitted for review.", "good"); await renderContentDetail(state.refreshToken); }));
    } else if (hasRole("reviewer") && status === "in_review") {
      panel.innerHTML = `<div class="rationale-panel"><label>Decision rationale<textarea id="script-rationale" placeholder="Explain the specific reason for this decision."></textarea></label><div class="button-row"><button data-script-decision="approved" class="primary-button">Approve version</button><button data-script-decision="changes_requested" class="secondary-button">Request changes</button><button data-script-decision="rejected" class="danger-button">Reject</button></div></div>`;
      $$('[data-script-decision]').forEach((button) => button.addEventListener("click", () => decideScriptAction(button, document.id, lockVersion, button.dataset.scriptDecision)));
    } else if (hasRole("producer") && ["changes_requested", "rejected"].includes(status)) {
      panel.innerHTML = `<div class="rationale-panel"><label>Revision reason<textarea id="script-revision-reason" placeholder="Describe what will be corrected."></textarea></label><button id="revise-script" class="primary-button">Create revision</button></div>`;
      $("#revise-script").addEventListener("click", (event) => reviseScriptAction(event.currentTarget, document.id, lockVersion));
    } else {
      panel.innerHTML = `<div class="notice"><strong>${escapeHtml(humanize(status))}</strong>No action is available for your role at this status.</div>`;
    }
  }

  async function generateScriptAction(contentId, button) {
    await withButton(button, async () => {
      await StudioApi.generateScript(contentId);
      toast("Script job queued. You can leave this page while it runs.", "good");
      navigate(contentPath(contentId, "production"));
    });
  }

  async function decideScriptAction(button, documentId, lockVersion, decision) {
    const rationale = $("#script-rationale").value.trim();
    if (rationale.length < 10) return toast("Add a specific rationale of at least 10 characters.", "bad");
    await withButton(button, async () => {
      await StudioApi.decideScript(documentId, lockVersion, decision, rationale);
      toast(`Script ${humanize(decision).toLowerCase()}.`, "good");
      await renderContentDetail(state.refreshToken);
    });
  }

  async function reviseScriptAction(button, documentId, lockVersion) {
    const reason = $("#script-revision-reason").value.trim();
    if (reason.length < 10) return toast("Add a specific revision reason of at least 10 characters.", "bad");
    await withButton(button, async () => {
      await StudioApi.reviseScript(documentId, lockVersion, reason);
      toast("New script revision created.", "good");
      await renderContentDetail(state.refreshToken);
    });
  }

  function renderProductionTab(bundle) {
    const data = bundle.state;
    const jobs = data.jobs || [];
    const scriptApproved = data.script?.current_version_status === "approved";
    $("#content-tab").innerHTML = `<div class="detail-layout"><div class="detail-main"><section class="card"><div class="card-header"><div><h2>Local production</h2><p>Start narration and visuals after the exact script version is approved.</p></div>${scriptApproved && hasRole("producer") ? '<button id="start-production" class="primary-button">Start local production</button>' : ""}</div>${scriptApproved ? '<div class="notice good"><strong>Approved script ready</strong>Kokoro narration and ComfyUI visuals can now run locally.</div>' : '<div class="notice warn"><strong>Script approval required</strong>Submit and approve the script before generating media.</div>'}</section>
      <section class="card"><div class="card-header"><div><h2>Generation jobs</h2><p>Jobs continue safely in the background and survive browser refreshes.</p></div></div><div class="job-list">${jobs.length ? jobs.map(jobCard).join("") : emptyState("No jobs yet", "Generate a script or start local production to create the first job.")}</div></section></div><aside class="detail-sidebar"><section class="card"><div class="card-header"><div><h3>Worker safety</h3></div></div><p>Automatic approval and live publishing remain disabled. Failed jobs can be retried without duplicating successful work.</p></section></aside></div>`;
    $("#start-production")?.addEventListener("click", (event) => startProductionAction(state.route.contentId, event.currentTarget));
    $$('[data-retry-job]').forEach((button) => button.addEventListener("click", () => retryJobAction(button.dataset.retryJob, button)));
  }

  function jobCard(job) {
    const status = String(job.status || "unknown");
    const error = job.last_error_message || job.error_message || job.last_error_code;
    return `<article class="job-item"><div><div class="button-row"><h3>${escapeHtml(humanize(job.job_type))}</h3>${statusBadge(status)}</div><div class="job-meta"><span>${escapeHtml(job.provider || "local")}</span><span>${escapeHtml(job.model_id || "")}</span><span>Attempt ${escapeHtml(job.attempt_count || 0)}</span><span>${escapeHtml(dateTime(job.queued_at))}</span></div>${["queued","running"].includes(status) ? '<div class="progress-track"><span></span></div>' : ""}${error ? `<div class="notice bad" style="margin-top:10px"><strong>${escapeHtml(humanize(job.last_error_code || "Job failed"))}</strong>${escapeHtml(error)}</div>` : ""}</div><div>${["failed","dead_letter"].includes(status) && hasRole("producer") ? `<button class="secondary-button" data-retry-job="${job.id}">Retry</button>` : ""}</div></article>`;
  }

  async function retryJobAction(jobId, button) {
    await withButton(button, async () => { await StudioApi.retryJob(jobId); toast("Job queued for retry.", "good"); await renderContentDetail(state.refreshToken); });
  }

  async function startProductionAction(contentId, button) {
    await withButton(button, async () => {
      const result = await StudioApi.startLocalProduction(contentId, { include_audio: true, include_visuals: true });
      if (result.blocked?.length) toast(result.blocked.map((item) => humanize(item.code)).join(" · "), "bad");
      else toast("Narration and visuals started locally.", "good");
      navigate(contentPath(contentId, "production"));
    });
  }

  async function renderMediaTab(bundle) {
    const data = bundle.state;
    const previewArtifacts = (data.artifacts || []).filter((item) => ["preview", "final_video"].includes(item.kind));
    const previewHtml = previewArtifacts.length ? await Promise.all(previewArtifacts.map(async (artifact) => {
      try {
        const url = await StudioApi.authenticatedMediaUrl(data.item.id, artifact.id);
        return `<article class="media-card"><div class="media-preview"><video src="${url}" controls preload="metadata"></video></div><div class="media-card-body"><h4>${escapeHtml(artifact.label)}</h4><p>${escapeHtml(humanize(artifact.kind))} · Version ${escapeHtml(artifact.version)}</p><a class="secondary-button" href="${url}" download>Export file</a></div></article>`;
      } catch (error) {
        return `<article class="media-card"><div class="media-preview">Preview unavailable</div><div class="media-card-body"><h4>${escapeHtml(artifact.label)}</h4><p>${escapeHtml(errorText(error))}</p></div></article>`;
      }
    })).then((items) => items.join("")) : "";
    $("#content-tab").innerHTML = `<div class="grid two"><section class="card"><div class="card-header"><div><h2>Narration review</h2><p>Listen to generated takes and decide the current production.</p></div></div><div id="audio-review-area"></div></section><section class="card"><div class="card-header"><div><h2>Visual review</h2><p>Select candidates and approve the complete storyboard.</p></div></div><div id="visual-review-area"></div></section></div><section class="card" style="margin-top:18px"><div class="card-header"><div><h2>MP4 preview</h2><p>The preview is assembled only from approved narration and visuals.</p></div></div><div class="media-grid">${previewHtml || emptyState("No MP4 preview yet", "Approve narration and visuals. The preview worker will then assemble the video automatically.")}</div></section>`;
    renderAudioReview(bundle.audio);
    renderVisualReview(bundle.visual);
  }

  function renderAudioReview(audio) {
    const target = $("#audio-review-area");
    if (!audio?.production) return target.innerHTML = emptyState("Narration not started", "Start local production after script approval.");
    const production = audio.production;
    const takes = audio.takes || [];
    const generated = takes.filter((take) => ["generated", "selected"].includes(take.status));
    target.innerHTML = `<div class="button-row">${statusBadge(production.status)}<span>${escapeHtml(production.model_id || "Local Kokoro")}</span></div><div class="job-list" style="margin-top:14px">${(audio.paragraphs || []).map((paragraph) => { const paragraphTakes = generated.filter((take) => String(take.paragraph_id) === String(paragraph.id)); return `<article class="job-item"><div><h3>Paragraph ${escapeHtml(paragraph.sequence)}</h3><p>${escapeHtml(paragraph.source_text)}</p><div class="job-meta"><span>${paragraphTakes.length} generated take(s)</span></div></div></article>`; }).join("") || '<p>Audio jobs are still generating.</p>'}</div><div id="audio-decision-area" style="margin-top:14px"></div>`;
    const decision = $("#audio-decision-area");
    if (hasRole("reviewer") && production.status === "in_review") {
      decision.innerHTML = `<div class="rationale-panel"><label>Review rationale<textarea id="audio-rationale" placeholder="Describe the audio quality decision."></textarea></label><div class="button-row"><button data-audio-decision="approved" class="primary-button">Approve narration</button><button data-audio-decision="changes_requested" class="secondary-button">Request changes</button><button data-audio-decision="rejected" class="danger-button">Reject</button></div></div>`;
      $$('[data-audio-decision]').forEach((button) => button.addEventListener("click", () => decideAudioAction(button, production, button.dataset.audioDecision)));
    } else if (hasRole("producer") && ["working", "changes_requested"].includes(production.status) && production.current_mix_version_id) {
      decision.innerHTML = '<button id="submit-audio" class="primary-button">Submit narration for review</button>';
      $("#submit-audio").addEventListener("click", (event) => submitAudioAction(event.currentTarget, production));
    } else decision.innerHTML = `<div class="notice"><strong>${escapeHtml(humanize(production.status))}</strong>${generated.length ? "Generated narration is recorded in the production." : "The local worker is still generating takes."}</div>`;
  }

  async function submitAudioAction(button, production) {
    await withButton(button, async () => { await StudioApi.submitAudio(production.id, production.lock_version); toast("Narration submitted for review.", "good"); await renderContentDetail(state.refreshToken); });
  }

  async function decideAudioAction(button, production, decision) {
    const rationale = $("#audio-rationale").value.trim();
    if (rationale.length < 10) return toast("Add a specific rationale of at least 10 characters.", "bad");
    await withButton(button, async () => { await StudioApi.decideAudio(production.id, { expected_lock_version: production.lock_version, decision, rationale }); toast(`Narration ${humanize(decision).toLowerCase()}.`, "good"); await renderContentDetail(state.refreshToken); });
  }

  function renderVisualReview(visual) {
    const target = $("#visual-review-area");
    if (!visual?.project) return target.innerHTML = emptyState("Visuals not started", "Start local production after script approval.");
    const project = visual.project;
    const candidates = visual.candidates || [];
    target.innerHTML = `<div class="button-row">${statusBadge(project.status)}<span>${escapeHtml(project.preset_name || "Local visual preset")}</span></div><div class="media-grid" style="margin-top:14px">${(visual.shots || []).map((shot) => { const shotCandidates = candidates.filter((candidate) => String(candidate.visual_shot_version_id) === String(shot.current_version_id)); return `<article class="media-card"><div class="media-preview">${shotCandidates.some((candidate) => candidate.status === "generated" || candidate.status === "selected") ? `${shotCandidates.length} candidate(s)` : "Generating…"}</div><div class="media-card-body"><h4>Scene ${escapeHtml(shot.sequence)}</h4><p>${escapeHtml(shot.visual_brief || shot.narration_text || "Visual scene")}</p><div class="button-row">${shotCandidates.filter((candidate) => ["generated","selected"].includes(candidate.status)).map((candidate) => `<button class="secondary-button" data-select-candidate="${candidate.id}" data-shot="${shot.id}" data-version="${shot.current_version_id}" data-lock="${shot.lock_version}">${candidate.status === "selected" ? "Selected" : `Select ${candidate.ordinal}`}</button>`).join("")}</div></div></article>`; }).join("")}</div><div id="visual-decision-area" style="margin-top:14px"></div>`;
    $$('[data-select-candidate]').forEach((button) => button.addEventListener("click", () => selectVisualCandidate(button, project)));
    const decision = $("#visual-decision-area");
    if (hasRole("producer") && ["working", "changes_requested"].includes(project.status)) {
      decision.innerHTML = '<button id="submit-visuals" class="primary-button">Submit visuals for review</button>';
      $("#submit-visuals").addEventListener("click", (event) => withButton(event.currentTarget, async () => { await StudioApi.submitVisualProject(project.id, { expected_project_lock_version: project.lock_version }); toast("Visual project submitted for review.", "good"); await renderContentDetail(state.refreshToken); }));
    } else if (hasRole("reviewer") && project.status === "in_review") {
      decision.innerHTML = `<div class="rationale-panel"><label>Review rationale<textarea id="visual-rationale" placeholder="Describe the visual decision."></textarea></label><div class="button-row"><button data-visual-decision="approved" class="primary-button">Approve visuals</button><button data-visual-decision="changes_requested" class="secondary-button">Request changes</button><button data-visual-decision="rejected" class="danger-button">Reject</button></div></div>`;
      $$('[data-visual-decision]').forEach((button) => button.addEventListener("click", () => decideVisualProject(button, project, button.dataset.visualDecision)));
    } else decision.innerHTML = `<div class="notice"><strong>${escapeHtml(humanize(project.status))}</strong>Select one candidate for every scene before submitting the project.</div>`;
  }

  async function selectVisualCandidate(button, project) {
    const rationale = `Selected candidate ${button.textContent.trim()} after visual review.`;
    await withButton(button, async () => { await StudioApi.decideVisualCandidate(project.id, button.dataset.shot, button.dataset.version, button.dataset.selectCandidate, { expected_shot_lock_version: Number(button.dataset.lock), decision: "selected", rationale }); toast("Visual candidate selected.", "good"); await renderContentDetail(state.refreshToken); });
  }

  async function decideVisualProject(button, project, decision) {
    const rationale = $("#visual-rationale").value.trim();
    if (rationale.length < 10) return toast("Add a specific rationale of at least 10 characters.", "bad");
    await withButton(button, async () => { await StudioApi.decideVisualProject(project.id, { expected_project_lock_version: project.lock_version, decision, rationale }); toast(`Visuals ${humanize(decision).toLowerCase()}.`, "good"); await renderContentDetail(state.refreshToken); });
  }

  function renderHistoryTab(bundle) {
    const workflow = bundle.state.workflow;
    const history = workflow?.history || [];
    const decisions = workflow?.decisions || [];
    $("#content-tab").innerHTML = `<div class="grid two"><section class="card"><div class="card-header"><div><h2>Workflow history</h2><p>Immutable stage transitions.</p></div></div><div class="job-list">${history.length ? history.map((item) => `<article class="job-item"><div><h3>${escapeHtml(humanize(item.event))}</h3><p>${escapeHtml(humanize(item.from_stage || "Created"))} → ${escapeHtml(humanize(item.to_stage))}</p><div class="job-meta"><span>${escapeHtml(item.actor)}</span><span>${escapeHtml(dateTime(item.created_at))}</span></div></div></article>`).join("") : '<p>No workflow events yet.</p>'}</div></section><section class="card"><div class="card-header"><div><h2>Review decisions</h2></div></div><div class="job-list">${decisions.length ? decisions.map((item) => `<article class="job-item"><div><h3>${escapeHtml(humanize(item.decision))}</h3><p>${escapeHtml(item.rationale)}</p><div class="job-meta"><span>${escapeHtml(item.reviewer_name || item.reviewer_operator_id)}</span><span>${escapeHtml(dateTime(item.created_at))}</span></div></div></article>`).join("") : '<p>No decisions yet.</p>'}</div></section></div>`;
  }

  async function renderReviews(token) {
    if (!hasRole("reviewer")) return navigate("/app/dashboard", { replace: true });
    setPage("Review inbox", "Decide scripts, narration, visuals, and previews without navigating admin tools.");
    const inbox = await StudioApi.reviewInbox({ statuses: ["pending", "in_review"], limit: 100 });
    if (token !== state.refreshToken) return;
    const items = inbox.items || [];
    view().innerHTML = `<div class="page-actions"><div><h2>${items.length} item${items.length === 1 ? "" : "s"} need review</h2><p>Open an item to compare evidence and record an exact decision.</p></div></div><section class="card"><div class="review-list">${items.length ? items.map((item) => { const contentId = item.portfolio_content_id || item.content_id || item.subject_content_id; return `<article class="review-item"><div class="button-row between"><div><h3>${escapeHtml(item.title || humanize(item.item_type || "Review item"))}</h3><p>${escapeHtml(item.brand_name || "Assigned brand")} · ${escapeHtml(humanize(item.stage || item.item_type))}${item.due_at ? ` · Due ${escapeHtml(dateValue(item.due_at))}` : ""}</p></div>${statusBadge(item.status || "awaiting_review")}</div>${contentId ? `<div class="button-row" style="margin-top:12px"><a class="primary-button" href="${contentPath(contentId, reviewTabForItem(item))}" data-route>Open review</a></div>` : ""}</article>`; }).join("") : emptyState("Review inbox is clear", "No assigned items currently need a decision.")}</div></section>`;
    startPolling(() => renderReviews(state.refreshToken), 15000);
  }

  function reviewTabForItem(item) {
    const type = String(item.item_type || item.stage || "");
    if (type.includes("script")) return "script";
    if (type.includes("audio") || type.includes("narration") || type.includes("visual") || type.includes("preview")) return "media";
    return "overview";
  }

  async function renderTeam(token) {
    if (!isAdmin()) return navigate("/app/dashboard", { replace: true });
    setPage("Team & access", "Manage roles, brand access, and local team keys without PowerShell.");
    const [operatorsPayload, keysPayload] = await Promise.all([StudioApi.operators(), StudioApi.teamKeys().catch(() => ({ items: [] }))]);
    if (token !== state.refreshToken) return;
    const users = operatorsPayload.users || [];
    view().innerHTML = `<div class="team-grid"><section class="card"><div class="card-header"><div><h2>Team members</h2><p>Each person sees only the brands and actions allowed by their role.</p></div><button id="new-team-member" class="primary-button">Add team member</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Name</th><th>Roles</th><th>Brands</th><th>Status</th><th></th></tr></thead><tbody>${users.map((user) => `<tr><td><span class="item-title">${escapeHtml(user.display_name)}</span><span class="item-subtitle">${escapeHtml(user.operator_id)}</span></td><td><div class="role-chips">${(user.roles || []).map((role) => `<span class="role-chip">${escapeHtml(humanize(role))}</span>`).join("")}</div></td><td>${escapeHtml((user.brand_ids || []).length || "All")}</td><td>${statusBadge(user.active ? "ready" : "cancelled", user.active ? "Active" : "Inactive")}</td><td><button class="table-action" data-edit-operator="${escapeHtml(user.operator_id)}">Edit</button></td></tr>`).join("")}</tbody></table></div><div id="operator-form-area"></div></section><aside class="card"><div class="card-header"><div><h2>Role access keys</h2><p>Copy only the key needed for each team member. The Admin key is never shown here.</p></div></div><div>${keysPayload.items?.length ? keysPayload.items.map((item) => `<div class="key-row"><div><strong>${escapeHtml(humanize(item.operator_id))}</strong><code>${escapeHtml(maskKey(item.key))}</code></div><button class="secondary-button" data-copy-key="${escapeHtml(item.key)}">Copy</button></div>`).join("") : '<div class="notice warn"><strong>Keys unavailable</strong>Local key display is available only on the workstation environment.</div>'}</div></aside></div>`;
    $("#new-team-member").addEventListener("click", () => renderOperatorForm(null));
    $$('[data-edit-operator]').forEach((button) => button.addEventListener("click", () => renderOperatorForm(users.find((user) => user.operator_id === button.dataset.editOperator))));
    $$('[data-copy-key]').forEach((button) => button.addEventListener("click", async () => { await navigator.clipboard.writeText(button.dataset.copyKey); toast("Role key copied.", "good"); }));
  }

  const maskKey = (key) => `${String(key).slice(0, 6)}••••••••${String(key).slice(-4)}`;

  function renderOperatorForm(user) {
    const area = $("#operator-form-area");
    const selectedRoles = new Set(user?.roles || []);
    const selectedBrands = new Set((user?.brand_ids || []).map(String));
    area.innerHTML = `<div class="card" style="margin-top:18px;background:#f9fafb"><div class="card-header"><div><h3>${user ? "Edit team member" : "Add team member"}</h3><p>Set a role and brand scope. The access key mapping remains controlled locally.</p></div><button id="close-operator-form" class="ghost-button">Close</button></div><form id="operator-form" class="form-grid"><label>Operator ID<input name="operator_id" required pattern="[A-Za-z0-9._-]+" value="${escapeHtml(user?.operator_id || "")}" ${user ? "readonly" : ""}></label><label>Display name<input name="display_name" required value="${escapeHtml(user?.display_name || "")}"></label><fieldset class="wide"><legend>Roles</legend><div class="choice-grid">${["producer","reviewer","publisher","admin"].map((role) => `<label class="choice-card ${selectedRoles.has(role) ? "selected" : ""}"><input type="checkbox" name="roles" value="${role}" ${selectedRoles.has(role) ? "checked" : ""}><strong>${humanize(role)}</strong></label>`).join("")}</div></fieldset><fieldset class="wide"><legend>Brand access</legend><div class="choice-grid">${state.brands.map((brand) => `<label class="choice-card ${selectedBrands.has(String(brand.id)) ? "selected" : ""}"><input type="checkbox" name="brand_ids" value="${brand.id}" ${selectedBrands.has(String(brand.id)) ? "checked" : ""}><strong>${escapeHtml(brand.display_name)}</strong></label>`).join("")}</div></fieldset><label><input type="checkbox" name="active" ${user?.active !== false ? "checked" : ""}> Active account</label><div class="wide button-row end"><button class="primary-button" type="submit">Save team member</button></div></form></div>`;
    $("#close-operator-form").addEventListener("click", () => area.replaceChildren());
    $$('input[type="checkbox"]', area).forEach((input) => input.addEventListener("change", () => input.closest(".choice-card")?.classList.toggle("selected", input.checked)));
    $("#operator-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const data = new FormData(form);
      const submit = $('button[type="submit"]', form);
      await withButton(submit, async () => {
        await StudioApi.upsertOperator({ operator_id: data.get("operator_id"), display_name: data.get("display_name"), active: data.get("active") === "on", roles: data.getAll("roles"), brand_ids: data.getAll("brand_ids") });
        toast("Team member saved.", "good");
        await renderTeam(state.refreshToken);
      });
    });
  }

  async function renderSettings(token) {
    if (!isAdmin()) return navigate("/app/dashboard", { replace: true });
    setPage("Settings", "Technical configuration stays separate from daily content production.");
    const [local, voices] = await Promise.all([StudioApi.localStatus(), StudioApi.approvedVoices().catch(() => ({ voices: [] }))]);
    if (token !== state.refreshToken) return;
    view().innerHTML = `<div class="settings-nav">${[["runtime","Runtime"],["brands","Brand profiles"],["voices","Voices"],["ideas","Idea generation"],["renderers","Renderers"]].map(([value,label]) => `<button data-settings-tab="${value}" class="${state.settingsTab === value ? "active" : ""}">${label}</button>`).join("")}</div><section id="settings-panel" class="card"></section>`;
    $$('[data-settings-tab]').forEach((button) => button.addEventListener("click", () => { state.settingsTab = button.dataset.settingsTab; void renderSettings(state.refreshToken); }));
    const panel = $("#settings-panel");
    if (state.settingsTab === "runtime") panel.innerHTML = `<div class="card-header"><div><h2>Local runtime</h2><p>Models and worker capabilities currently configured on this PC.</p></div></div><dl class="definition-list"><div class="definition-row"><dt>Supervisor</dt><dd>${escapeHtml(local.supervisor?.healthy ? "Healthy" : humanize(local.supervisor?.reason || "Unavailable"))}</dd></div><div class="definition-row"><dt>Ollama script model</dt><dd>${escapeHtml(local.capabilities?.ollama_model)}</dd></div><div class="definition-row"><dt>Kokoro narration model</dt><dd>${escapeHtml(local.capabilities?.kokoro_model)}</dd></div><div class="definition-row"><dt>Local visual model</dt><dd>${escapeHtml(local.capabilities?.visual_model)}</dd></div><div class="definition-row"><dt>ComfyUI</dt><dd>${local.capabilities?.comfyui_configured ? "Ready" : "Not configured"}</dd></div><div class="definition-row"><dt>FFmpeg</dt><dd>${local.capabilities?.ffmpeg_configured ? "Ready" : "Not configured"}</dd></div><div class="definition-row"><dt>Managed renderer</dt><dd>Not connected</dd></div><div class="definition-row"><dt>Automatic approval</dt><dd>Disabled</dd></div><div class="definition-row"><dt>Live publishing</dt><dd>Disabled</dd></div></dl>`;
    else if (state.settingsTab === "brands") await renderBrandSettings(panel);
    else if (state.settingsTab === "voices") panel.innerHTML = `<div class="card-header"><div><h2>Approved voices</h2><p>Only approved local voices can be selected for brand narration.</p></div></div><div class="content-card-list">${(voices.voices || voices.items || []).length ? (voices.voices || voices.items).map((voice) => `<article class="content-card"><h3>${escapeHtml(voice.display_name || voice.voice_id || voice.id)}</h3><p>${escapeHtml(voice.language || voice.locale || "")}</p></article>`).join("") : emptyState("No voices returned", "The local onboarding process may need to seed approved voices.")}</div>`;
    else if (state.settingsTab === "ideas") renderIdeasSettings(panel);
    else panel.innerHTML = `<div class="card-header"><div><h2>Renderer connections</h2><p>Local preview generation is ready. Managed rendering remains separate until Xfield/Higgsfield is connected.</p></div></div><div class="notice warn"><strong>Managed renderer not connected</strong>Local scripts, narration, keyframes, and MP4 previews remain available without it.</div>`;
  }

  async function renderBrandSettings(panel) {
    const selectedId = state.brands[0]?.id;
    panel.innerHTML = `<div class="card-header"><div><h2>Brand profiles</h2><p>Profiles control language, editorial rules, voices, and visual presets.</p></div></div><div class="toolbar"><label>Brand<select id="settings-brand">${state.brands.map((brand) => `<option value="${brand.id}">${escapeHtml(brand.display_name)}</option>`).join("")}</select></label></div><div id="brand-profile-list"></div>`;
    const load = async () => {
      const payload = await StudioApi.brandProfiles($("#settings-brand").value);
      const profiles = payload.profiles || payload.items || [];
      $("#brand-profile-list").innerHTML = profiles.length ? `<div class="content-card-list">${profiles.map((profile) => `<article class="content-card"><div class="button-row between"><div><h3>${escapeHtml(profile.display_name || `Profile v${profile.version}`)}</h3><p>${escapeHtml(profile.default_language || "")}</p></div>${statusBadge(profile.status === "active" ? "ready" : "draft", profile.status)}</div>${profile.status !== "active" ? `<button class="secondary-button" data-activate-profile="${profile.id}">Activate profile</button>` : ""}</article>`).join("")}</div>` : emptyState("No profiles", "Create or seed a brand profile before production.");
      $$('[data-activate-profile]').forEach((button) => button.addEventListener("click", () => withButton(button, async () => { await StudioApi.activateBrandProfile($("#settings-brand").value, button.dataset.activateProfile); toast("Brand profile activated.", "good"); await load(); })));
    };
    $("#settings-brand").addEventListener("change", load);
    if (selectedId) await load();
  }

  function renderIdeasSettings(panel) {
    const month = new Date().toISOString().slice(0, 7) + "-01";
    panel.innerHTML = `<div class="card-header"><div><h2>Topic suggestions</h2><p>Create a small, reviewable idea set. Advanced distribution controls are optional.</p></div></div><form id="idea-form" class="form-grid"><label>Brand<select name="brand_id">${state.brands.map((brand) => `<option value="${brand.id}">${escapeHtml(brand.display_name)}</option>`).join("")}</select></label><label>Month<input name="month_start" type="date" value="${month}"></label><label>Suggestion count<input name="candidate_count" type="number" value="8" min="3" max="30"></label><label>Content mix<select name="mix"><option value="vertical_short">Mostly vertical shorts</option><option value="balanced">Balanced formats</option></select></label><div class="wide button-row"><button class="primary-button" type="submit">Generate suggestions</button></div></form><div id="idea-results" style="margin-top:18px"></div>`;
    $("#idea-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      const count = Number(data.get("candidate_count"));
      const button = $('button[type="submit"]', event.currentTarget);
      await withButton(button, async () => {
        const result = await StudioApi.generateConcepts({ brand_id: data.get("brand_id"), month_start: data.get("month_start"), candidate_count: count, format_mix: data.get("mix") === "balanced" ? { vertical_short: Math.ceil(count * .7), carousel: Math.floor(count * .3) } : { vertical_short: count }, pillar_targets: { education: count }, seed: Number(String(data.get("month_start")).replaceAll("-", "")), adapter_mode: "deterministic" });
        const batch = await StudioApi.conceptBatch(result.batch.id);
        $("#idea-results").innerHTML = `<div class="content-card-list">${(batch.candidates || []).map((item) => `<article class="content-card"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.hook || item.concept)}</p></article>`).join("")}</div>`;
      });
    });
  }

  async function renderOperations(token) {
    if (!isAdmin()) return navigate("/app/dashboard", { replace: true });
    setPage("Operations", "Runtime health, job recovery, releases, delivery, and the controlled pilot.");
    const [ops, jobs, releases, deliveries, candidates] = await Promise.all([
      StudioApi.operations().catch((error) => ({ error: errorText(error) })),
      StudioApi.jobs({ statuses: ["failed", "dead_letter", "running", "queued"], limit: 100 }),
      StudioApi.releases().catch(() => ({ items: [] })),
      StudioApi.deliveries().catch(() => ({ items: [] })),
      StudioApi.acceptanceCandidates().catch(() => ({ candidates: [] }))
    ]);
    if (token !== state.refreshToken) return;
    view().innerHTML = `<div class="grid four"><article class="metric-card"><strong>${escapeHtml(jobs.items?.filter((item) => item.status === "running").length || 0)}</strong><span>Running jobs</span></article><article class="metric-card"><strong>${escapeHtml(jobs.items?.filter((item) => item.status === "queued").length || 0)}</strong><span>Queued jobs</span></article><article class="metric-card alert"><strong>${escapeHtml(jobs.items?.filter((item) => ["failed","dead_letter"].includes(item.status)).length || 0)}</strong><span>Failed jobs</span></article><article class="metric-card"><strong>${escapeHtml((releases.items || releases.releases || []).length)}</strong><span>Release records</span></article></div>
      <div class="grid two" style="margin-top:18px"><section class="card"><div class="card-header"><div><h2>Runtime and recovery</h2><p>Technical monitoring is deliberately separated from daily content work.</p></div></div>${ops.error ? `<div class="notice bad">${escapeHtml(ops.error)}</div>` : `<dl class="definition-list">${Object.entries(ops.monitoring || ops.snapshot || ops).slice(0, 12).map(([key,value]) => `<div class="definition-row"><dt>${escapeHtml(humanize(key))}</dt><dd>${escapeHtml(typeof value === "object" ? "Available" : value)}</dd></div>`).join("")}</dl>`}</section><section class="card"><div class="card-header"><div><h2>Active and failed jobs</h2></div></div><div class="job-list">${(jobs.items || []).length ? jobs.items.map(jobCard).join("") : '<p>No active or failed jobs.</p>'}</div></section></div>
      <div class="grid two" style="margin-top:18px"><section class="card"><div class="card-header"><div><h2>Release & delivery</h2><p>Delivery remains simulated or manually recorded.</p></div></div><p>${escapeHtml((releases.items || releases.releases || []).length)} release record(s) · ${escapeHtml((deliveries.items || deliveries.deliveries || []).length)} delivery request(s)</p></section><section class="card"><div class="card-header"><div><h2>P100 acceptance pilot</h2><p>Daily content creation does not depend on these controls.</p></div></div><p>${escapeHtml((candidates.candidates || candidates.items || []).length)} candidate item(s) currently discoverable.</p><div class="notice warn"><strong>Managed renderer still blocked</strong>The four-item pilot cannot complete its managed-render lane until Xfield/Higgsfield is connected.</div></section></div>`;
    $$('[data-retry-job]').forEach((button) => button.addEventListener("click", () => retryJobAction(button.dataset.retryJob, button)));
  }

  function renderNotFound() {
    setPage("Page not found", "The requested Creator Studio route does not exist.");
    view().innerHTML = emptyState("Page not found", "Return to the dashboard to continue.", '<a class="primary-button" href="/app/dashboard" data-route>Dashboard</a>');
  }

  function bindGlobalEvents() {
    document.addEventListener("click", routeLinkHandler);
    window.addEventListener("popstate", () => void loadRoute());
    $("#refresh-view").addEventListener("click", () => void loadRoute());
    $("#sign-out").addEventListener("click", () => { StudioApi.disconnect(); state.access = null; stopPolling(); showLogin(); });
    $("#login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const key = $("#operator-key").value.trim();
      const submit = $('button[type="submit"]', event.currentTarget);
      try {
        await withButton(submit, async () => {
          StudioApi.connect(key);
          await authenticateSavedSession();
          $("#login-dialog").close();
          const landing = hasRole("reviewer") && !hasRole("producer") ? "/app/reviews" : "/app/dashboard";
          navigate(landing, { replace: true });
        });
      } catch (error) {
        StudioApi.disconnect();
        $("#login-error").textContent = errorText(error);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindGlobalEvents();
    void boot();
  }, { once: true });
})();
