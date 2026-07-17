(() => {
  const state = {
    brief: null,
    pack: null,
    engineFilter: "all",
    selectedStage: "brief-intake",
    brandFilter: "all",
    statusFilter: "all",
    referenceBrandFilter: "",
    referencePlatformFilter: "",
    referenceStatusFilter: ""
  };

  const $ = (id) => document.getElementById(id);

  const demoPortfolioBrands = [
    { id: "rawr-nation", name: "Rawr Nation", niche: "Wildlife facts", kind: "video", cadence: "5 shorts + 1 feature weekly", monthlyTarget: 24, primary: "Facebook", pillars: ["Animal senses", "Survival mechanisms", "Myth vs fact", "Behaviour reveals"] },
    { id: "animal-x", name: "Animal X", niche: "Animal behaviour", kind: "video", cadence: "5 shorts + 1 feature weekly", monthlyTarget: 24, primary: "Facebook", pillars: ["Hidden signals", "Social intelligence", "Anatomy in action", "Field discoveries"] },
    { id: "historiq", name: "Historiq", niche: "AI-assisted history, philosophy, and ideas", kind: "video", cadence: "5 shorts + 1 feature weekly", monthlyTarget: 24, primary: "Facebook", pillars: ["Hidden history", "Ideas that changed society", "Historical turning points", "Myth versus record"] },
    { id: "ani-films", name: "Ani Films", niche: "Simple animation for complex ideas", kind: "video", cadence: "5 shorts + 1 feature weekly", monthlyTarget: 24, primary: "Facebook", pillars: ["Visual explainers", "How systems work", "Everyday science", "Big ideas made simple"] },
    { id: "brand-05", name: "Brand 05", niche: "Awaiting onboarding", kind: "video", cadence: "5 shorts + 1 feature weekly", monthlyTarget: 24, primary: "Facebook", pillars: ["Complete brand onboarding"] },
    { id: "brand-06", name: "Brand 06", niche: "Awaiting onboarding", kind: "video", cadence: "5 shorts + 1 feature weekly", monthlyTarget: 24, primary: "Facebook", pillars: ["Complete brand onboarding"] },
    { id: "news-brand", name: "News Brand", niche: "News and explainers", kind: "mixed", cadence: "2 timely posts daily", monthlyTarget: 60, primary: "Facebook", pillars: ["Breaking update", "Context card", "What changes next", "Daily roundup"] }
  ];

  const demoPortfolioItems = [
    { date: "Day 01", brand: "rawr-nation", title: "The hidden blind spot predators exploit", format: "45s vertical", stage: "ready", assets: ["3 exports", "thumbnail", "caption", "hashtags"] },
    { date: "Day 02", brand: "animal-x", title: "How elephants hear through the ground", format: "50s vertical", stage: "premium", assets: ["VO", "captions", "4 premium shots"] },
    { date: "Day 03", brand: "rawr-nation", title: "Why owl flight sounds almost silent", format: "35s vertical", stage: "preview", assets: ["script", "VO", "rough preview"] },
    { date: "Day 04", brand: "animal-x", title: "The warning signal hidden in a tail", format: "40s vertical", stage: "script", assets: ["research", "script", "scene plan"] },
    { date: "Day 05", brand: "rawr-nation", title: "The animal that sees colors we cannot", format: "40s vertical", stage: "idea", assets: ["sources", "hook options"] },
    { date: "Day 06", brand: "news-brand", title: "Daily context card and source summary", format: "1080×1350", stage: "script", assets: ["sources", "headline", "image brief"] }
  ];
  let portfolioBrands = demoPortfolioBrands.slice();
  let portfolioItems = demoPortfolioItems.slice();
  let portfolioReadiness = null;
  let portfolioReferences = [];
  let activeContentReview = null;
  let reviewMediaUrls = [];
  let monthStudioItems = new Map();

  const stageLabels = { idea: "Idea review", script: "Script review", preview_build: "Preview build", preview: "Preview review", premium: "Premium render", package: "Package review", ready: "Ready", published: "Published record", blocked: "Blocked", archived: "Archived" };

  function renderPortfolio() {
    const brands = state.brandFilter === "all" ? portfolioBrands : portfolioBrands.filter((brand) => brand.id === state.brandFilter);
    const items = portfolioItems.filter((item) => (state.brandFilter === "all" || item.brand === state.brandFilter) && (state.statusFilter === "all" || item.stage === state.statusFilter));
    const monthlyMasters = portfolioBrands.reduce((total, brand) => total + brand.monthlyTarget, 0);
    const videoMasters = portfolioBrands.filter((brand) => brand.kind === "video").reduce((total, brand) => total + brand.monthlyTarget, 0);
    const metrics = portfolioReadiness ? [
      [String(portfolioReadiness.brand_count), "brand workspaces"],
      [`${portfolioReadiness.planned_count}/${portfolioReadiness.target_count}`, "ideas planned"],
      [String(portfolioReadiness.ready_brand_count), "inventories complete"],
      [String(Math.max(portfolioReadiness.target_count - portfolioReadiness.planned_count, 0)), "remaining idea gap"]
    ] : [
      ["7", "brand workspaces"], [String(monthlyMasters), "monthly master assets"], [String(videoMasters * 3), "video platform exports"], ["30 days", "target approval buffer"]
    ];
    $("portfolio-metrics").innerHTML = metrics.map(([value, label]) => `<article><strong>${value}</strong><span>${label}</span></article>`).join("");

    const selected = brands[0];
    $("brand-summary").innerHTML = state.brandFilter === "all"
      ? `<p class="eyebrow dark-eyebrow">Portfolio policy</p><h3>Facebook-first, platform-native delivery</h3><p>Create one strong original master, then export deliberately for Facebook, YouTube Shorts and TikTok. Do not publish identical metadata or visible watermarks across platforms.</p><dl><div><dt>Video brands</dt><dd>24 masters / month each</dd></div><div><dt>News brand</dt><dd>60 timely visual posts / month</dd></div><div><dt>Quality gate</dt><dd>Human approval before paid render and publishing</dd></div></dl>`
      : `<p class="eyebrow dark-eyebrow">Selected brand</p><h3>${escapeHtml(selected.name)}</h3><p>${escapeHtml(selected.niche)}</p><dl><div><dt>Primary platform</dt><dd>${selected.primary}</dd></div><div><dt>Cadence</dt><dd>${escapeHtml(selected.cadence)}</dd></div><div><dt>Monthly target</dt><dd>${selected.monthlyTarget} original masters</dd></div>${selected.conceptCount !== undefined ? `<div><dt>Concept inventory</dt><dd>${selected.conceptCount}/${selected.monthlyTarget}</dd></div>` : ""}</dl>${selected.blocker ? `<p class="review-error"><strong>Blocked:</strong> ${escapeHtml(selected.blocker.replaceAll("_", " "))}</p>` : ""}<h4>Content pillars</h4><ul>${selected.pillars.map((pillar) => `<li>${escapeHtml(pillar)}</li>`).join("")}</ul>`;

    $("content-queue").innerHTML = items.length ? items.map((item) => {
      const brand = portfolioBrands.find((candidate) => candidate.id === item.brand);
      const next = { idea: "Review idea", script: "Review script", preview_build: "Build preview", preview: "Watch preview", premium: "Inspect render", package: "Review package", ready: "Open package" }[item.stage];
      return `<tr><td>${item.date}</td><td><strong>${escapeHtml(brand.name)}</strong><span>${escapeHtml(item.title)}</span></td><td>${escapeHtml(item.format)}</td><td><span class="stage-pill ${item.stage}">${stageLabels[item.stage]}</span></td><td>${item.assets.map((asset) => `<span class="asset-chip">${escapeHtml(asset)}</span>`).join("")}</td><td><button class="table-action" type="button" data-item-id="${escapeHtml(item.id || "")}" data-item-title="${escapeHtml(item.title)}">${next || "Review"}</button></td></tr>`;
    }).join("") : '<tr><td colspan="6" class="empty-row">No content matches these filters.</td></tr>';
  }

  function renderReferenceQueue() {
    const ready = portfolioReferences.filter((item) => item.status === "ready_for_review").length;
    const failed = portfolioReferences.filter((item) => ["failed", "blocked"].includes(item.status)).length;
    const artifacts = portfolioReferences.reduce((total, item) => total + Number(item.artifact_count || 0), 0);
    $("reference-metrics").innerHTML = [[portfolioReferences.length, "references"], [ready, "ready for review"], [artifacts, "review artifacts"], [failed, "need attention"]].map(([value, label]) => `<article><strong>${value}</strong><span>${label}</span></article>`).join("");
    $("reference-queue").innerHTML = portfolioReferences.length ? portfolioReferences.map((item) => `<tr><td><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.local_reference_id)}</span></td><td>${escapeHtml(item.platform)}</td><td><span class="stage-pill ${item.status === "ready_for_review" ? "ready" : item.status === "processing" ? "preview" : "idea"}">${escapeHtml(item.status.replaceAll("_", " "))}</span></td><td>${Number(item.progress_percent || 0)}%</td><td>${Number(item.artifact_count || 0)} artifacts · ${Number(item.approved_gate_count || 0)}/3 gates · ${Number(item.idea_link_count || 0)} ideas</td><td><button class="table-action reference-review" type="button" data-reference-id="${item.id}">Review</button></td></tr>`).join("") : '<tr><td colspan="6" class="empty-row">No database-backed references match these filters. Source media remains local.</td></tr>';
  }

  function renderStaticReferenceDetail(item) {
    const reference = item.staticEvidence;
    const fingerprint = reference.creative_fingerprint || {};
    const analysis = reference.analysis || {};
    const transcript = reference.transcript || "No transcript available.";
    $("reference-detail").innerHTML = `<p class="eyebrow dark-eyebrow">Verified local evidence</p><h4>${escapeHtml(item.title)}</h4><p><a href="${escapeHtml(reference.source_url)}" target="_blank" rel="noreferrer">Open public source</a> · ${Number(reference.duration_seconds || 0).toFixed(1)}s · ${Number(reference.decoded_frame_count || 0)} decoded frames</p><dl><div><dt>Scenes</dt><dd>${Number(reference.scene_count || 0)}</dd></div><div><dt>Transcript segments</dt><dd>${Number(reference.transcript_segment_count || 0)}</dd></div><div><dt>Use</dt><dd>Mechanics only; never source wording, assets, or shot sequence</dd></div></dl><details><summary>Creative fingerprint</summary><pre>${escapeHtml(JSON.stringify(fingerprint, null, 2))}</pre></details><details><summary>Measured analysis</summary><pre>${escapeHtml(JSON.stringify(analysis, null, 2))}</pre></details><details><summary>Transcript</summary><p>${escapeHtml(transcript)}</p></details><small>Source media, cookies, and the browser profile remain on the operator-controlled PC.</small>`;
  }

  function renderReferenceDetail(payload) {
    const source = payload.source;
    const gates = Object.fromEntries((payload.gates || []).map((gate) => [gate.gate, gate.decision]));
    const evidence = (payload.artifacts || [])[0]?.sha256 || "";
    $("reference-detail").innerHTML = `<p class="eyebrow dark-eyebrow">Human review</p><h4>${escapeHtml(source.title)}</h4><p>${escapeHtml(source.platform)} · ${escapeHtml(source.media_type)} · rights declared: ${escapeHtml(source.rights_declaration)}</p><dl><div><dt>Artifacts</dt><dd>${(payload.artifacts || []).map((item) => escapeHtml(item.artifact_kind)).join(", ") || "None yet"}</dd></div><div><dt>Brands</dt><dd>${(payload.brand_assignments || []).map((item) => escapeHtml(item.brand_name)).join(", ") || "Unassigned"}</dd></div><div><dt>Idea links</dt><dd>${(payload.idea_links || []).length}</dd></div></dl><div class="reference-gates">${["rights", "originality", "editorial"].map((gate) => `<button type="button" data-reference-gate="${gate}" data-reference-id="${source.id}" data-evidence="${evidence}" ${evidence ? "" : "disabled"}>${escapeHtml(gate)}: ${escapeHtml(gates[gate] || "pending")}</button>`).join("")}</div><small>Approvals are explicit, append-only human decisions. No approval triggers generation or publication.</small>`;
  }

  async function refreshReferencesFromApi() {
    if (!window.PortfolioApi?.configured()) {
      portfolioReferences = [];
      renderReferenceQueue();
      return;
    }
    const payload = await window.PortfolioApi.references({ brandId: state.referenceBrandFilter, platform: state.referencePlatformFilter, status: state.referenceStatusFilter });
    portfolioReferences = payload.items || [];
    renderReferenceQueue();
  }

  function mapApiBrand(brand) {
    return {
      id: brand.id,
      name: brand.display_name,
      niche: brand.niche,
      kind: brand.content_mode,
      cadence: brand.metadata?.cadence || `${brand.monthly_target} masters monthly`,
      monthlyTarget: brand.monthly_target,
      primary: brand.primary_platform === "facebook" ? "Facebook" : brand.primary_platform,
      pillars: Array.isArray(brand.content_pillars) ? brand.content_pillars : []
    };
  }

  function mapApiItem(item) {
    return {
      id: item.id,
      date: item.scheduled_for,
      brand: item.brand_id || portfolioBrands.find((brand) => brand.name === item.brand_name)?.id,
      title: item.title,
      format: item.format,
      stage: item.stage,
      sourceStage: item.stage,
      assets: [item.script ? "script" : "concept", item.has_voiceover_artifact ? "VO" : item.voiceover ? "VO metadata" : "VO pending", item.has_preview_artifact ? "preview" : "preview pending"]
    };
  }

  function prettyJson(value) {
    return value ? JSON.stringify(value, null, 2) : "";
  }

  function reviewGate(stage) {
    return { idea: "idea", script: "script", preview: "preview", premium: "premium_spend", package: "package", ready: "publish" }[stage];
  }

  async function hydrateReviewMedia(payload) {
    reviewMediaUrls.forEach((url) => URL.revokeObjectURL(url));
    reviewMediaUrls = [];
    for (const artifact of payload.artifacts || []) {
      if (!String(artifact.mime_type).startsWith("audio/") && !String(artifact.mime_type).startsWith("video/")) continue;
      const mount = document.querySelector(`[data-media-artifact="${artifact.id}"]`);
      if (!mount) continue;
      try {
        const response = await fetch(window.PortfolioApi.mediaUrl(payload.item.id, artifact.id), { headers: window.PortfolioApi.mediaHeaders() });
        if (!response.ok) throw new Error("Media is not mounted in the local API runtime.");
        const url = URL.createObjectURL(await response.blob());
        reviewMediaUrls.push(url);
        const tag = String(artifact.mime_type).startsWith("video/") ? "video" : "audio";
        mount.innerHTML = `<${tag} controls preload="metadata" src="${url}"></${tag}>`;
      } catch (error) {
        mount.innerHTML = `<small>${escapeHtml(error.message)}</small>`;
      }
    }
  }

  function renderContentReview(payload) {
    activeContentReview = payload;
    const item = payload.item;
    const gate = reviewGate(item.stage);
    const missing = item.missing_for_approval || [];
    const artifacts = payload.artifacts || [];
    const artifactCards = artifacts.length ? artifacts.map((artifact) => `<article class="review-artifact"><div><strong>${escapeHtml(artifact.label)}</strong><span>${escapeHtml(artifact.kind)} · v${artifact.version} · ${escapeHtml(artifact.review_status)}</span></div><div data-media-artifact="${artifact.id}"><small>${escapeHtml(artifact.mime_type)} · local review media</small></div></article>`).join("") : '<p class="empty-review">No review media has been registered yet. Local generation workers can attach narration, keyframes, and preview files through the artifact API.</p>';
    const history = (payload.approvals || []).length ? payload.approvals.map((approval) => `<li><strong>${escapeHtml(approval.decision.replaceAll("_", " "))}</strong> ${escapeHtml(approval.gate)} v${approval.content_version}<span>${escapeHtml(approval.rationale)} · ${escapeHtml(approval.reviewer)}</span></li>`).join("") : "<li>No review decisions yet.</li>";
    $("content-review-body").innerHTML = `
      <header class="review-header"><div><p class="eyebrow dark-eyebrow">${escapeHtml(item.brand_name)} · ${escapeHtml(item.scheduled_for)}</p><h2>${escapeHtml(item.title)}</h2><p>${escapeHtml(item.concept)}</p></div><span class="stage-pill ${escapeHtml(item.stage)}">${escapeHtml(stageLabels[item.stage] || item.stage)}</span></header>
      <div class="review-grid">
        <section class="review-editor"><h3>Script workspace</h3><label>Script JSON<textarea id="review-script" rows="12" placeholder='{"hook":"...","narration":["..."]}'>${escapeHtml(prettyJson(item.script))}</textarea></label><label>Scene plan JSON<textarea id="review-scenes" rows="12" placeholder='{"scenes":[{"id":"s1","visual":"..."}]}'>${escapeHtml(prettyJson(item.scene_plan))}</textarea></label><label>Voice metadata JSON<textarea id="review-voice" rows="6" placeholder='{"provider":"kokoro","voice":"..."}'>${escapeHtml(prettyJson(item.voiceover))}</textarea></label><label>Premium budget (USD)<input id="review-budget" type="number" min="0" step="0.01" value="${item.premium_budget_usd ?? ""}"></label><button id="save-workspace" type="button">Save new version</button><span id="review-save-status" class="review-status"></span></section>
        <section class="review-media"><h3>Narration & video</h3>${artifactCards}<h3>Review history</h3><ol class="review-history">${history}</ol></section>
      </div>
      <section class="review-decision"><div><h3>Human decision</h3><p>${missing.length ? `Approval blocked until: <strong>${missing.map(escapeHtml).join(", ")}</strong>` : "Required review evidence is present."}</p></div><label>Rationale<textarea id="review-rationale" rows="3" placeholder="What was reviewed, and why is this decision appropriate?"></textarea></label><div class="decision-actions"><button type="button" data-review-decision="approved" ${!gate || missing.length ? "disabled" : ""}>Approve next stage</button><button type="button" class="secondary" data-review-decision="changes_requested" ${!gate ? "disabled" : ""}>Request changes</button><button type="button" class="danger" data-review-decision="rejected" ${!gate ? "disabled" : ""}>Reject</button></div><span id="review-decision-status" class="review-status"></span></section>`;
    hydrateReviewMedia(payload);
  }

  function parseReviewJson(id) {
    const value = $(id).value.trim();
    return value ? JSON.parse(value) : null;
  }

  function openStaticContentReview(item) {
    const dialog = $("content-review");
    const pkg = item.studioPackage;
    const decisions = JSON.parse(localStorage.getItem("rawr-month-review-decisions") || "{}");
    const saved = decisions[item.id] || { decision: "pending", rationale: "" };
    const scenes = pkg.scene_plan.map((scene) => `<article class="artifact-card"><strong>${scene.start_seconds}–${scene.end_seconds}s · ${escapeHtml(scene.purpose)}</strong><p>${escapeHtml(scene.narration)}</p><small>${escapeHtml(scene.visual_direction)} · Preview: ${escapeHtml(scene.preview_route)} · Final: ${escapeHtml(scene.final_route)}</small></article>`).join("");
    const platforms = pkg.platform_packages.map((entry) => `<article class="artifact-card"><strong>${escapeHtml(entry.platform.replaceAll("_", " "))}</strong><p>${escapeHtml(entry.title)}</p><p>${escapeHtml(entry.caption)}</p><small>#${entry.hashtags.map(escapeHtml).join(" #")} · ${escapeHtml(entry.cta)}</small></article>`).join("");
    const sources = (pkg.script.sources || []).map((source) => `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a><span>${escapeHtml(source.supports)}</span></li>`).join("");
    const factReady = pkg.script.fact_status === "source_ready_pending_human";
    $("content-review-body").innerHTML = `
      <div class="review-header"><div><p class="eyebrow dark-eyebrow">Rawr Nation · Batch ${pkg.batch}</p><h2>${escapeHtml(pkg.title)}</h2><p>${escapeHtml(pkg.concept)}</p></div><span class="stage-pill script">Script review</span></div>
      <div class="review-grid">
        <section><h3>Narration</h3><p class="review-script-copy">${escapeHtml(pkg.script.narration)}</p><dl><div><dt>Duration</dt><dd>${pkg.duration_seconds}s</dd></div><div><dt>Words</dt><dd>${pkg.script.word_count}</dd></div><div><dt>Pillar</dt><dd>${escapeHtml(pkg.pillar)}</dd></div><div><dt>Fact gate</dt><dd>${escapeHtml((pkg.script.fact_status || "research_pending").replaceAll("_", " "))}</dd></div><div><dt>Preview</dt><dd>${escapeHtml(pkg.production.free_preview.replaceAll("_", " "))}</dd></div></dl><h3>Research sources</h3>${sources ? `<ul class="review-history">${sources}</ul>` : `<p class="review-error">Research sources must be attached before script approval.</p>`}<h3>Scene plan</h3><div class="artifact-grid">${scenes}</div></section>
        <section><h3>Thumbnail</h3><article class="artifact-card"><strong>${escapeHtml(pkg.thumbnail.primary_text)}</strong><p>${escapeHtml(pkg.thumbnail.composition)}</p><small>Alternates: ${pkg.thumbnail.alternates.map(escapeHtml).join(" · ")}</small></article><h3>Platform packages</h3><div class="artifact-grid">${platforms}</div><h3>Voice direction</h3><p>${escapeHtml(pkg.voice.style)} · ${escapeHtml(pkg.voice.pace)} · development: ${escapeHtml(pkg.voice.development_provider)}</p>${pkg.voice.preview_url ? `<audio controls preload="metadata" src="${escapeHtml(pkg.voice.preview_url)}"></audio><small>Local Kokoro narration preview · human performance review required</small>` : `<p class="review-loading">Narration preview is queued for local generation.</p>`}</section>
      </div>
      <section class="review-decision"><div><h3>Human decision</h3><p>Current local decision: <strong id="static-review-state">${escapeHtml(saved.decision.replaceAll("_", " "))}</strong>. Paid rendering and publishing remain blocked.</p></div><label>Rationale<textarea id="static-review-rationale" rows="3" placeholder="What should stay or change?">${escapeHtml(saved.rationale)}</textarea></label><div class="decision-actions"><button type="button" data-static-decision="approved" ${factReady ? "" : "disabled"}>Approve script</button><button type="button" class="secondary" data-static-decision="changes_requested">Request changes</button><button type="button" class="danger" data-static-decision="rejected">Reject</button><button type="button" class="secondary" id="download-static-package">Download package</button></div><span id="static-review-status" class="review-status"></span></section>`;
    dialog.showModal();
    $("download-static-package").addEventListener("click", () => download(`${item.id}-production-package.json`, JSON.stringify(pkg, null, 2), "application/json"));
    $("content-review-body").querySelectorAll("[data-static-decision]").forEach((button) => button.addEventListener("click", () => {
      const rationale = $("static-review-rationale").value.trim();
      if (rationale.length < 10) { $("static-review-status").textContent = "Add a specific rationale of at least 10 characters."; return; }
      decisions[item.id] = { decision: button.dataset.staticDecision, rationale, reviewed_at: new Date().toISOString(), content_fingerprint: pkg.content_fingerprint };
      localStorage.setItem("rawr-month-review-decisions", JSON.stringify(decisions));
      $("static-review-state").textContent = button.dataset.staticDecision.replaceAll("_", " ");
      $("static-review-status").textContent = "Decision saved in this browser. Database sync will preserve it when connected.";
    }));
  }

  async function openContentReview(contentId) {
    const dialog = $("content-review");
    $("content-review-body").innerHTML = '<p class="review-loading">Loading content workspace…</p>';
    dialog.showModal();
    try { renderContentReview(await window.PortfolioApi.content(contentId)); }
    catch (error) { $("content-review-body").innerHTML = `<p class="review-error">${escapeHtml(error.message)}</p>`; }
  }

  function updateDataMode(message, connected) {
    $("data-mode").textContent = message;
    $("data-mode").className = `data-mode ${connected ? "connected" : "demo"}`;
    $("connect-api").textContent = connected ? "Disconnect" : "Connect Data";
  }

  async function refreshPortfolioFromApi() {
    if (!window.PortfolioApi?.configured()) return false;
    try {
      const planMonth = document.querySelector('meta[name="content-plan-month"]')?.content || "2026-08-01";
      const [brandPayload, queuePayload, readinessPayload, referencePayload] = await Promise.all([
        window.PortfolioApi.brands(),
        window.PortfolioApi.queue(),
        window.PortfolioApi.readiness(planMonth),
        window.PortfolioApi.references()
      ]);
      portfolioBrands = brandPayload.brands.map(mapApiBrand);
      portfolioItems = queuePayload.items.map(mapApiItem);
      portfolioReadiness = readinessPayload;
      portfolioReferences = referencePayload.items || [];
      state.brandFilter = "all";
      $("brand-filter").innerHTML = '<option value="all">All brands</option>' + portfolioBrands.map((brand) => `<option value="${brand.id}">${escapeHtml(brand.name)}</option>`).join("");
      $("reference-brand-filter").innerHTML = '<option value="">All brands</option>' + portfolioBrands.map((brand) => `<option value="${brand.id}">${escapeHtml(brand.name)}</option>`).join("");
      updateDataMode(`${queuePayload.count} database items`, true);
      renderPortfolio();
      renderReferenceQueue();
      return true;
    } catch (error) {
      window.PortfolioApi?.disconnect();
      updateDataMode(`Local database unavailable: ${error.message}`, false);
      return false;
    }
  }

  function restoreDemoPortfolio() {
    portfolioBrands = demoPortfolioBrands.slice();
    portfolioItems = demoPortfolioItems.slice();
    portfolioReadiness = null;
    portfolioReferences = [];
    state.brandFilter = "all";
    $("brand-filter").innerHTML = '<option value="all">All brands</option>' + portfolioBrands.map((brand) => `<option value="${brand.id}">${escapeHtml(brand.name)}</option>`).join("");
    updateDataMode("Demo data", false);
    renderPortfolio();
    renderReferenceQueue();
  }

  async function loadMonthFactory() {
    try {
      const [response, studioResponse, referenceResponse] = await Promise.all([
        fetch("data/month-factory.json", { cache: "no-store" }),
        fetch("data/rawr-nation-month-studio.json", { cache: "no-store" }),
        fetch("data/rawr-nation-reference-evidence.json", { cache: "no-store" }).catch(() => null)
      ]);
      if (!response.ok) throw new Error("month factory unavailable");
      if (!studioResponse.ok) throw new Error("Rawr Nation month studio unavailable");
      const factory = await response.json();
      const studio = await studioResponse.json();
      monthStudioItems = new Map(studio.items.map((item) => [item.id, item]));
      portfolioBrands = factory.brands;
      portfolioItems = factory.items.map((item) => ({ ...item, studioPackage: monthStudioItems.get(item.id) || null }));
      if (referenceResponse?.ok) {
        const evidence = await referenceResponse.json();
        portfolioReferences = evidence.references.map((reference) => ({
          id: reference.id,
          title: `Rawr Nation reference ${reference.index}`,
          local_reference_id: reference.id,
          platform: "facebook",
          status: reference.status === "analyzed" ? "ready_for_review" : reference.status,
          progress_percent: reference.status === "analyzed" ? 100 : 0,
          artifact_count: [reference.analysis, reference.creative_fingerprint, reference.transcript].filter(Boolean).length,
          approved_gate_count: 0,
          idea_link_count: 24,
          staticEvidence: reference
        }));
      }
      portfolioReadiness = {
        brand_count: factory.priority_brand_count,
        planned_count: factory.summary.concepts_ready,
        target_count: factory.summary.monthly_target,
        ready_brand_count: factory.summary.brands_with_complete_inventory
      };
      state.brandFilter = "all";
      $("brand-filter").innerHTML = '<option value="all">All brands</option>' + portfolioBrands.map((brand) => `<option value="${brand.id}">${escapeHtml(brand.name)}</option>`).join("");
      updateDataMode(`${studio.summary.scripts_ready} Rawr Nation scripts ready · ${studio.summary.batch_one_preview_queue} previews queued`, false);
      renderPortfolio();
    } catch (_error) {
      restoreDemoPortfolio();
    }
  }

  function bindPortfolioControls() {
    $("brand-filter").innerHTML = '<option value="all">All brands</option>' + portfolioBrands.map((brand) => `<option value="${brand.id}">${escapeHtml(brand.name)}</option>`).join("");
    $("brand-filter").addEventListener("change", (event) => { state.brandFilter = event.target.value; renderPortfolio(); });
    $("status-filter").addEventListener("change", (event) => { state.statusFilter = event.target.value; renderPortfolio(); });
    $("export-calendar").addEventListener("click", () => download("portfolio-30-day-plan.json", JSON.stringify({ schema_version: "portfolio_plan.v1", brands: portfolioBrands, items: portfolioItems, publishing_policy: { primary: "facebook", derivatives: ["youtube_shorts", "tiktok"], approval_required: true } }, null, 2), "application/json"));
    $("connect-api").addEventListener("click", async () => {
      if (window.PortfolioApi?.configured()) {
        window.PortfolioApi.disconnect();
        loadMonthFactory();
        return;
      }
      const base = prompt("Operator API URL (HTTPS in staging/production):", "http://127.0.0.1:8000");
      if (!base) return;
      const key = prompt("Operator key (stored for this browser tab only):", "");
      if (!key) return;
      try {
        window.PortfolioApi.connect(base, key);
        await refreshPortfolioFromApi();
      } catch (error) {
        updateDataMode(error.message, false);
      }
    });
    $("content-queue").addEventListener("click", async (event) => {
      if (!event.target.matches(".table-action")) return;
      const item = portfolioItems.find((candidate) => candidate.id === event.target.dataset.itemId);
      if (item?.studioPackage && !window.PortfolioApi?.configured()) {
        openStaticContentReview(item);
        return;
      }
      if (!item?.id || !window.PortfolioApi?.configured()) {
        alert(`${event.target.dataset.itemTitle}\n\nThis brand still needs a generated review package or a connected operator API.`);
        return;
      }
      await openContentReview(item.id);
    });
    $("content-review").addEventListener("close", () => { reviewMediaUrls.forEach((url) => URL.revokeObjectURL(url)); reviewMediaUrls = []; activeContentReview = null; });
    $("content-review-body").addEventListener("click", async (event) => {
      if (!activeContentReview) return;
      const contentId = activeContentReview.item.id;
      if (event.target.id === "save-workspace") {
        try {
          await window.PortfolioApi.updateWorkspace(contentId, { script: parseReviewJson("review-script"), scene_plan: parseReviewJson("review-scenes"), voiceover: parseReviewJson("review-voice"), premium_budget_usd: $("review-budget").value === "" ? null : Number($("review-budget").value), metadata: { last_workspace_editor: "operator-ui" } });
          renderContentReview(await window.PortfolioApi.content(contentId));
          await refreshPortfolioFromApi();
        } catch (error) { $("review-save-status").textContent = `Save failed: ${error.message}`; }
      }
      if (event.target.matches("[data-review-decision]")) {
        const rationale = $("review-rationale").value.trim();
        if (rationale.length < 10) { $("review-decision-status").textContent = "Add a specific rationale of at least 10 characters."; return; }
        const decision = event.target.dataset.reviewDecision;
        try {
          await window.PortfolioApi.approve(contentId, reviewGate(activeContentReview.item.stage), decision, rationale);
          renderContentReview(await window.PortfolioApi.content(contentId));
          await refreshPortfolioFromApi();
        } catch (error) { $("review-decision-status").textContent = `Decision failed: ${error.message}`; }
      }
    });
    ["reference-brand-filter", "reference-platform-filter", "reference-status-filter"].forEach((id) => $(id).addEventListener("change", async () => {
      state.referenceBrandFilter = $("reference-brand-filter").value;
      state.referencePlatformFilter = $("reference-platform-filter").value;
      state.referenceStatusFilter = $("reference-status-filter").value;
      try { await refreshReferencesFromApi(); } catch (error) { alert(`Reference queue failed: ${error.message}`); }
    }));
    $("reference-queue").addEventListener("click", async (event) => {
      if (!event.target.matches(".reference-review")) return;
      const local = portfolioReferences.find((item) => item.id === event.target.dataset.referenceId);
      if (local?.staticEvidence && !window.PortfolioApi?.configured()) {
        renderStaticReferenceDetail(local);
        return;
      }
      try { renderReferenceDetail(await window.PortfolioApi.reference(event.target.dataset.referenceId)); } catch (error) { alert(`Reference review failed: ${error.message}`); }
    });
    $("reference-detail").addEventListener("click", async (event) => {
      if (!event.target.matches("[data-reference-gate]")) return;
      const rationale = prompt(`Rationale for approving ${event.target.dataset.referenceGate}:`, "Evidence reviewed and approved for controlled research use.");
      if (!rationale) return;
      if (!confirm("Record this human approval? This does not generate or publish content.")) return;
      try {
        await window.PortfolioApi.decideReferenceGate(event.target.dataset.referenceId, event.target.dataset.referenceGate, "approved", rationale, event.target.dataset.evidence);
        renderReferenceDetail(await window.PortfolioApi.reference(event.target.dataset.referenceId));
        await refreshReferencesFromApi();
      } catch (error) { alert(`Reference approval failed: ${error.message}`); }
    });
    renderPortfolio();
    renderReferenceQueue();
    refreshPortfolioFromApi();
  }

  const engineStages = [
    {
      id: "brief-intake",
      number: "01",
      title: "Brief Intake & Normalization",
      status: "static",
      statusLabel: "Static + local",
      focus: ["engagement", "compliance", "monetization"],
      summary: "Turns one business request into a structured, reusable content brief.",
      purpose: "Capture topic, platform, audience, tone, duration, must-use points, avoid rules, source notes, and monetization intent before any content is produced.",
      modules: ["P59 Creator Studio", "P60 Brief Adapter", "P61 Single-Brief Runner"],
      tools: ["HTML5 form", "Vanilla JavaScript", "JSON schema", "Python adapter"],
      outputs: ["Normalized brief JSON", "Custom brief library", "Feedback starter", "Cycle manifest"],
      gate: "Generation cannot be trusted until platform, audience, monetization goal, rights constraints, and source notes are explicit.",
      objectives: {
        engagement: "Audience, tone, platform, and duration define the creative direction before scripting.",
        compliance: "Avoid rules and source notes establish policy and rights boundaries at input stage.",
        monetization: "The commercial objective and desired CTA are captured before the content strategy is created."
      }
    },
    {
      id: "content-package",
      number: "02",
      title: "Content Package Generation",
      status: "local",
      statusLabel: "Implemented local",
      focus: ["engagement", "monetization"],
      summary: "Builds the structured concept, titles, hook, script, storyboard, and platform plan.",
      purpose: "Transform the normalized brief into a complete, reviewable content package rather than a single unstructured script.",
      modules: ["P40 Package Generator", "P48 Platform Templates", "P49 Pilot Batch"],
      tools: ["Python", "Deterministic templates", "JSON artifacts", "Markdown outputs"],
      outputs: ["Concept", "Hook", "Title options", "Script", "Storyboard", "Platform notes"],
      gate: "Every package must contain enough information for creative, production, policy, and monetization review as separate artifacts.",
      objectives: {
        engagement: "Multiple creative components can be reviewed independently instead of accepting one generic draft.",
        compliance: "Policy notes remain attached to the same package as the creative output.",
        monetization: "Platform and conversion intent stay connected to the script and CTA."
      }
    },
    {
      id: "engagement-engine",
      number: "03",
      title: "Engagement & Retention Engine",
      status: "local",
      statusLabel: "Implemented local",
      focus: ["engagement"],
      summary: "Evaluates the opening, pacing, retention structure, clarity, and platform fit.",
      purpose: "Improve the probability that a viewer understands the value quickly and remains engaged through a deliberate sequence of beats.",
      modules: ["P42 Engagement", "P50 Creative QA", "P53 Comparator"],
      tools: ["Hook checks", "Retention beats", "Platform heuristics", "Before/after review"],
      outputs: ["Hook assessment", "Retention plan", "Pacing notes", "Creative QA findings", "Comparison report"],
      gate: "The first seconds must be specific, the middle must deliver proof or value, and the CTA must arrive without breaking audience trust.",
      objectives: {
        engagement: "Directly controls hook strength, pacing, clarity, relevance, and retention beats.",
        compliance: "Avoids engagement tactics that rely on false urgency, misleading claims, or unsafe creative shortcuts.",
        monetization: "Higher-quality attention is connected to a relevant CTA instead of engagement for its own sake."
      }
    },
    {
      id: "policy-rights",
      number: "04",
      title: "Policy, Rights & Safety",
      status: "local",
      statusLabel: "Implemented local",
      focus: ["compliance"],
      summary: "Creates explicit cautions for copyright, likeness, logos, music, claims, and asset provenance.",
      purpose: "Prevent production teams from using risky assets or claims merely because a creative idea appears engaging.",
      modules: ["P41 Rights & Safety", "P50 Creative QA", "P56 Feedback Queue"],
      tools: ["Rights checklist", "Claims guard", "Source notes", "Human policy review"],
      outputs: ["Rights notes", "Prohibited-use warnings", "Source requirements", "Reviewer issues", "Approval status"],
      gate: "Owned, original, or properly licensed assets must be confirmed and factual claims must not overpromise outcomes.",
      objectives: {
        engagement: "Preserves strong creative ideas while replacing risky execution methods with safe alternatives.",
        compliance: "Primary control for copyright, platform policy, likeness, logos, music, sourcing, and claims.",
        monetization: "Protects long-term account eligibility, brand safety, advertiser confidence, and commercial reuse."
      }
    },
    {
      id: "monetization-readiness",
      number: "05",
      title: "Monetization Readiness",
      status: "local",
      statusLabel: "Implemented local",
      focus: ["monetization"],
      summary: "Aligns the content format and CTA with the selected commercial outcome.",
      purpose: "Ensure the content has a clear next action, platform-appropriate value exchange, and realistic business path without guaranteeing performance.",
      modules: ["P44 Monetization", "P48 Platform Templates", "P49 Pilot Batch"],
      tools: ["CTA mapping", "Platform fit checks", "Offer alignment", "Readiness notes"],
      outputs: ["Primary monetization path", "CTA recommendation", "Platform notes", "Readiness cautions"],
      gate: "The CTA must match the audience and platform, provide a reasonable next action, and avoid revenue or performance guarantees.",
      objectives: {
        engagement: "The CTA is introduced as a natural continuation of the content value rather than a disruptive sales pitch.",
        compliance: "Commercial claims remain factual and do not promise guaranteed revenue, views, conversions, or savings.",
        monetization: "Directly maps content to leads, products, affiliates, subscriptions, sponsorship, or platform revenue paths."
      }
    },
    {
      id: "production-handoff",
      number: "06",
      title: "Production Handoff",
      status: "local",
      statusLabel: "Implemented local",
      focus: ["engagement", "compliance", "monetization"],
      summary: "Packages the approved plan for producers, editors, designers, and reviewers.",
      purpose: "Remove ambiguity between strategy and execution by exporting a consistent producer-ready package.",
      modules: ["P43 Production Handoff", "P46 Producer Export", "P47 Folder Runner"],
      tools: ["Markdown brief", "Script TXT", "Storyboard JSON", "QA checklist"],
      outputs: ["Producer brief", "Editor script", "Storyboard", "Asset cautions", "QA checklist"],
      gate: "A production team should be able to understand the creative, timing, visuals, source restrictions, and CTA without reconstructing strategy.",
      objectives: {
        engagement: "Timing, scene direction, subtitles, and visual beats are preserved during production.",
        compliance: "Rights notes and source constraints travel with the production brief.",
        monetization: "CTA placement and commercial objective remain visible to the production team."
      }
    },
    {
      id: "orchestration",
      number: "07",
      title: "Orchestration & Batch Operations",
      status: "local",
      statusLabel: "Implemented local",
      focus: ["engagement", "compliance", "monetization"],
      summary: "Runs the modules in a repeatable order for one brief or a folder of briefs.",
      purpose: "Make the process operationally consistent, reproducible, and auditable instead of relying on ad hoc manual execution.",
      modules: ["P45 Orchestration", "P47 Folder Runner", "P58 Review Cycle", "P61 Full Cycle"],
      tools: ["Python CLI", "Local folders", "Manifests", "Summary reports"],
      outputs: ["Run summary", "Cycle index", "Operator report", "Input/output manifest", "Review workspace"],
      gate: "The same input must produce a traceable artifact chain with no hidden publishing or approval action.",
      objectives: {
        engagement: "Creative checks are applied consistently across batches and platforms.",
        compliance: "Rights and approval stages cannot be silently skipped in the defined cycle.",
        monetization: "Commercial readiness checks are repeated consistently instead of depending on individual operators."
      }
    },
    {
      id: "human-review",
      number: "08",
      title: "Human Review & Revision Loop",
      status: "human",
      statusLabel: "Human-controlled",
      focus: ["engagement", "compliance", "monetization"],
      summary: "Captures approve, revise, or reject decisions and converts them into a revision plan.",
      purpose: "Keep final judgment with a reviewer while making feedback structured enough to regenerate and compare versions.",
      modules: ["P50 Creative QA", "P51 Revision Planner", "P52 Regeneration", "P53 Comparator", "P56 Feedback", "P57 Gallery"],
      tools: ["Feedback JSON", "Revision queue", "Comparison view", "Reviewer notes"],
      outputs: ["Decision", "Issues", "Requested changes", "Revision plan", "Revised pack", "Before/after comparison"],
      gate: "No content becomes production-ready merely because it was generated; a human reviewer must explicitly approve it.",
      objectives: {
        engagement: "Reviewers can reject generic hooks, weak pacing, or unclear creative direction.",
        compliance: "Human oversight resolves context-sensitive policy and rights issues the templates cannot decide alone.",
        monetization: "Reviewers confirm the CTA and offer fit before money or brand reputation is put at risk."
      }
    },
    {
      id: "workspace-deployment",
      number: "09",
      title: "Review Workspaces & Deployment",
      status: "static",
      statusLabel: "Deployed static",
      focus: ["engagement", "compliance", "monetization"],
      summary: "Presents the workflow in local browser workspaces and a Vercel-deployed static interface.",
      purpose: "Make complex content artifacts understandable to non-technical reviewers and decision-makers.",
      modules: ["P54 Review Workspace", "P55 Demo Gallery", "P62 Static UI", "P63 Vercel Lock"],
      tools: ["Static HTML", "CSS", "Vanilla JavaScript", "Vercel", "Local galleries"],
      outputs: ["Interactive engine map", "Creator Studio", "Review gallery", "Local index", "Downloadable exports"],
      gate: "Presentation must remain read-only with respect to final publishing and must disclose what is static, local, human-controlled, or planned.",
      objectives: {
        engagement: "Decision-makers can inspect creative structure without reading raw JSON files.",
        compliance: "Guardrails, implementation status, and human approval requirements are visible in the interface.",
        monetization: "Commercial strategy and readiness are visible beside the creative and policy evidence."
      }
    },
    {
      id: "ai-layer",
      number: "10",
      title: "Secure AI Generation Layer",
      status: "planned",
      statusLabel: "Planned next",
      focus: ["engagement", "compliance", "monetization"],
      summary: "Will replace deterministic browser copy with model-generated structured content through a protected API.",
      purpose: "Use external language models for richer creative generation while preserving schemas, safety gates, cost controls, and human approval.",
      modules: ["Planned model adapter", "Planned Vercel API", "Planned validation layer"],
      tools: ["Vercel serverless", "OpenAI / Gemini / Claude", "Environment secrets", "JSON validation"],
      outputs: ["Model-generated hooks", "Scripts", "Storyboards", "Revision variants", "Usage logs"],
      gate: "Model output must be validated, policy-checked, cost-controlled, and reviewed by a human before production.",
      objectives: {
        engagement: "Provides more varied, context-aware creative options and revisions.",
        compliance: "Structured validation and the existing rights/human gates remain mandatory after model generation.",
        monetization: "Allows more tailored platform and offer strategies while retaining realistic, non-guaranteed claims."
      }
    }
  ];

  const sampleBrief = {
    demo_id: "custom-ai-operations-short",
    topic: "AI operations audit for service businesses",
    platform: "youtube_shorts",
    audience: "agency founders and service business owners with manual operations",
    tone: "practical, confident, high-trust, founder-led",
    duration_seconds: 45,
    content_format: "vertical_short",
    monetization_goal: "Generate qualified leads for a paid AI operations audit.",
    must_use_points: [
      "Open with the hidden cost of manual follow-ups and scattered tools.",
      "Show a simple before/after workflow from lead capture to follow-up.",
      "End with a soft CTA to request an operations audit checklist."
    ],
    avoid: [
      "Do not promise guaranteed revenue, savings, or automation success.",
      "Do not use celebrity likeness, copied music, third-party clips, or brand logos."
    ],
    source_notes: [
      "Use original narration, owned diagrams, simple UI mockups, and licensed or owned assets only."
    ]
  };

  function lines(value) {
    return String(value || "")
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function slugify(value) {
    return String(value || "custom-brief")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 64) || "custom-brief";
  }

  function collectBrief() {
    const topic = $("topic").value.trim() || "Custom video brief";
    return {
      schema_version: "p62.static_creator_brief.v1",
      demo_id: slugify(topic),
      topic,
      platform: $("platform").value,
      audience: $("audience").value.trim(),
      tone: $("tone").value.trim(),
      duration_seconds: Number($("duration_seconds").value || 45),
      content_format: $("content_format").value.trim() || inferFormat($("platform").value),
      monetization_goal: $("monetization_goal").value.trim(),
      must_use_points: lines($("must_use_points").value),
      avoid: lines($("avoid").value),
      source_notes: lines($("source_notes").value),
      guardrails: guardrails()
    };
  }

  function inferFormat(platform) {
    if (["youtube_shorts", "instagram_reels", "tiktok"].includes(platform)) return "vertical_short";
    if (platform === "youtube_long") return "longform_video";
    return "social_video";
  }

  function platformLabel(platform) {
    return {
      youtube_shorts: "YouTube Shorts",
      instagram_reels: "Instagram Reels",
      tiktok: "TikTok",
      youtube_long: "YouTube Longform",
      linkedin_video: "LinkedIn Video"
    }[platform] || platform;
  }

  function guardrails() {
    return {
      static_browser_only: true,
      vercel_ready: true,
      backend_required: false,
      python_required_in_browser: false,
      external_calls_performed: false,
      asset_download_performed: false,
      upload_or_publish_performed: false,
      automated_final_approval: false,
      creative_improvement_guaranteed: false,
      monetization_guaranteed: false,
      performance_guaranteed: false,
      human_review_required_before_production: true
    };
  }

  function renderEnginePipeline() {
    const pipeline = $("engine-pipeline");
    if (!pipeline) return;
    pipeline.innerHTML = "";

    const visibleStages = engineStages.filter((stage) => {
      return state.engineFilter === "all" || stage.focus.includes(state.engineFilter);
    });

    if (!visibleStages.some((stage) => stage.id === state.selectedStage)) {
      state.selectedStage = visibleStages[0]?.id || engineStages[0].id;
    }

    visibleStages.forEach((stage) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `engine-stage${stage.id === state.selectedStage ? " selected" : ""}`;
      button.dataset.stageId = stage.id;
      button.dataset.status = stage.status;
      button.setAttribute("aria-pressed", stage.id === state.selectedStage ? "true" : "false");
      button.innerHTML = `
        <div class="stage-top">
          <span class="stage-number">${escapeHtml(stage.number)}</span>
          <span class="stage-status">${escapeHtml(stage.statusLabel)}</span>
        </div>
        <h3>${escapeHtml(stage.title)}</h3>
        <p>${escapeHtml(stage.summary)}</p>
        <div class="stage-objectives">
          ${stage.focus.map((objective) => `<span class="objective-tag ${objective}">${escapeHtml(objectiveLabel(objective))}</span>`).join("")}
        </div>`;
      button.addEventListener("click", () => selectEngineStage(stage.id));
      pipeline.appendChild(button);
    });

    renderEngineDetail();
    syncFilterControls();
  }

  function selectEngineStage(stageId) {
    state.selectedStage = stageId;
    renderEnginePipeline();
  }

  function renderEngineDetail() {
    const stage = engineStages.find((item) => item.id === state.selectedStage) || engineStages[0];
    if (!$("detail-title")) return;

    $("detail-title").textContent = `${stage.number} · ${stage.title}`;
    $("detail-purpose").textContent = stage.purpose;
    $("detail-modules").innerHTML = stage.modules.map((item) => `<span class="module-pill">${escapeHtml(item)}</span>`).join("");
    $("detail-tools").innerHTML = stage.tools.map((item) => `<span class="tool-pill">${escapeHtml(item)}</span>`).join("");
    $("detail-outputs").innerHTML = stage.outputs.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    $("detail-gate").textContent = stage.gate;
    $("detail-objectives").innerHTML = Object.entries(stage.objectives).map(([objective, impact]) => `
      <div class="detail-objective-card ${objective}">
        <strong>${escapeHtml(objectiveLabel(objective))}</strong>
        <span>${escapeHtml(impact)}</span>
      </div>`).join("");
  }

  function objectiveLabel(objective) {
    return {
      engagement: "Engagement",
      compliance: "Policy & rights",
      monetization: "Monetization"
    }[objective] || objective;
  }

  function setEngineFilter(filter) {
    state.engineFilter = filter;
    renderEnginePipeline();
  }

  function syncFilterControls() {
    document.querySelectorAll(".filter-chip").forEach((button) => {
      const selected = button.dataset.filter === state.engineFilter;
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });

    document.querySelectorAll(".objective-card").forEach((button) => {
      const active = state.engineFilter === "all" || button.dataset.objective === state.engineFilter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function bindEngineControls() {
    document.querySelectorAll(".filter-chip").forEach((button) => {
      button.addEventListener("click", () => setEngineFilter(button.dataset.filter || "all"));
    });

    document.querySelectorAll(".objective-card").forEach((button) => {
      button.addEventListener("click", () => {
        const objective = button.dataset.objective || "all";
        setEngineFilter(state.engineFilter === objective ? "all" : objective);
      });
    });
  }

  function buildReviewPack(brief) {
    const topic = brief.topic;
    const platform = platformLabel(brief.platform);
    const audience = brief.audience || "the target audience";
    const hook = `Most ${audience} lose time on ${topic.toLowerCase()} because the real problem is hidden in the workflow.`;
    const titleOptions = [
      `The Hidden Cost of ${topic}`,
      `Before You Scale, Fix This ${topic} Problem`,
      `${topic}: The ${brief.duration_seconds}-Second Audit`,
      `Stop Guessing: Audit Your ${topic} Workflow`,
      `The Simple ${topic} Fix Most Teams Miss`
    ];
    const beats = buildBeats(brief, hook);
    const script = buildScript(brief, beats);
    const storyboard = buildStoryboard(brief, beats);
    const qa = buildQaChecklist(brief);
    const rights = buildRightsNotes(brief);
    const monetization = buildMonetizationNotes(brief);
    const producerBrief = buildProducerMarkdown(brief, hook, titleOptions, beats, script, storyboard, qa, rights, monetization);

    return {
      schema_version: "p62.static_review_pack.v1",
      created_in_browser: true,
      brief,
      review_status: "first_pass_ready_for_human_review",
      hook,
      title_options: titleOptions,
      retention_beats: beats,
      script,
      storyboard,
      rights_notes: rights,
      monetization_notes: monetization,
      qa_checklist: qa,
      revision_prompts: [
        "Is the opening hook specific enough to stop scrolling?",
        "Can the script be produced with owned or licensed assets only?",
        "Does the CTA match the monetization goal without overpromising?",
        "Which storyboard frame needs a clearer visual direction?"
      ],
      exports: {
        producer_brief_md: producerBrief,
        script_txt: script.join("\n\n"),
        qa_checklist_md: qa.map((item) => `- [ ] ${item}`).join("\n")
      },
      platform_notes: [
        `Primary platform: ${platform}.`,
        brief.content_format === "vertical_short"
          ? "Use fast cuts, subtitles, and a strong first 2 seconds."
          : "Use chapter-like structure and stronger explanation depth.",
        "Keep visuals original, licensed, or owned."
      ],
      objective_assurance: {
        engagement: ["Hook", "Retention beats", "Platform format", "Creative QA"],
        compliance: ["Avoid rules", "Rights notes", "Source notes", "Human approval"],
        monetization: ["Monetization goal", "CTA alignment", "Platform notes", "No outcome guarantee"]
      },
      guardrails: guardrails()
    };
  }

  function buildBeats(brief, hook) {
    const points = brief.must_use_points.length
      ? brief.must_use_points
      : ["Introduce the problem.", "Show the better workflow.", "Close with a soft CTA."];
    return [
      { time: "0-3s", label: "Hook", direction: hook },
      { time: "3-12s", label: "Problem", direction: points[0] || "Frame the pain clearly." },
      { time: "12-28s", label: "Proof / process", direction: points[1] || "Show the before and after." },
      { time: "28-40s", label: "Value", direction: points[2] || "Give a practical takeaway." },
      { time: "40s+", label: "CTA", direction: `Invite viewers to take the next step toward: ${brief.monetization_goal || "a useful next action"}` }
    ];
  }

  function buildScript(brief, beats) {
    const avoid = brief.avoid.length
      ? `Avoid: ${brief.avoid.join(" ")}`
      : "Avoid overclaiming or using unlicensed assets.";
    return [
      `HOOK: ${beats[0].direction}`,
      "PROBLEM: If your team is relying on memory, scattered tools, or manual follow-ups, the leak is probably not one person. It is the system around them.",
      "PROCESS: Map the lead or customer journey from first touch to final follow-up. Mark every delay, repeated task, missing owner, and message that depends on manual effort.",
      "VALUE: Once the workflow is visible, you can decide what should be automated, what should stay human, and what should be removed completely.",
      `CTA: ${brief.monetization_goal || "Use this as a checklist before you invest more time or ad spend."}`,
      `SAFETY: ${avoid}`
    ];
  }

  function buildStoryboard(brief, beats) {
    return beats.map((beat, index) => ({
      frame: index + 1,
      time: beat.time,
      scene: beat.label,
      visual_direction: index === 0
        ? "Close-up founder or presenter speaking to camera with bold subtitle overlay."
        : index === beats.length - 1
          ? "Clean CTA card with checklist, download, consultation, or request prompt."
          : "Simple owned diagram, screen mockup, workflow card, or original B-roll.",
      narration: beat.direction,
      production_note: "Use owned footage, original graphics, licensed music, and burned-in captions."
    }));
  }

  function buildRightsNotes(brief) {
    const notes = [
      "Use original voiceover or licensed voice assets only.",
      "Use owned footage, created graphics, or properly licensed stock assets.",
      "Do not use celebrity likeness, brand logos, copyrighted music, film clips, or scraped social clips unless rights are confirmed.",
      "Keep proof points factual and avoid guaranteed business outcomes."
    ];
    return notes.concat((brief.source_notes || []).map((note) => `Source note: ${note}`));
  }

  function buildMonetizationNotes(brief) {
    return [
      `Primary monetization path: ${brief.monetization_goal || "qualified lead generation"}.`,
      "Best CTA style: soft, useful, and action-based rather than hype-led.",
      "Suggested CTA asset: checklist, audit request, consultation form, product page, or saved-post prompt.",
      "Do not imply guaranteed revenue, savings, conversion, or platform performance."
    ];
  }

  function buildQaChecklist(brief) {
    return [
      "Hook is specific and understandable in the first 2-3 seconds.",
      "Script is practical and avoids generic claims.",
      "Storyboard can be produced with owned or licensed assets.",
      "Copyright, likeness, logo, and music risks are identified before production.",
      "CTA matches the monetization goal and audience intent.",
      `Format fits ${platformLabel(brief.platform)} and ${brief.duration_seconds} seconds.`,
      "Human reviewer has approved before production or publishing."
    ];
  }

  function buildProducerMarkdown(brief, hook, titles, beats, script, storyboard, qa, rights, monetization) {
    return [
      `# Producer Brief — ${brief.topic}`,
      "",
      `Platform: ${platformLabel(brief.platform)}`,
      `Audience: ${brief.audience}`,
      `Tone: ${brief.tone}`,
      `Duration: ${brief.duration_seconds}s`,
      `Monetization goal: ${brief.monetization_goal}`,
      "",
      "## Hook",
      hook,
      "",
      "## Title Options",
      ...titles.map((item) => `- ${item}`),
      "",
      "## Retention Beats",
      ...beats.map((item) => `- ${item.time} — ${item.label}: ${item.direction}`),
      "",
      "## Script",
      ...script.map((item) => `- ${item}`),
      "",
      "## Storyboard",
      ...storyboard.map((item) => `- Frame ${item.frame} (${item.time}): ${item.visual_direction} Narration: ${item.narration}`),
      "",
      "## Rights Notes",
      ...rights.map((item) => `- ${item}`),
      "",
      "## Monetization Notes",
      ...monetization.map((item) => `- ${item}`),
      "",
      "## QA Checklist",
      ...qa.map((item) => `- [ ] ${item}`),
      "",
      "Human review required before production."
    ].join("\n");
  }

  function renderPack(pack) {
    const output = $("review-output");
    output.innerHTML = "";
    output.appendChild(card("Hook", `<p>${escapeHtml(pack.hook)}</p>`));
    output.appendChild(card("Title Options", list(pack.title_options)));
    output.appendChild(card("Script", ordered(pack.script)));
    output.appendChild(card("Storyboard", ordered(pack.storyboard.map((item) => `${item.time} — ${item.visual_direction} ${item.narration}`))));
    output.appendChild(card("Rights Notes", list(pack.rights_notes)));
    output.appendChild(card("Monetization Notes", list(pack.monetization_notes)));
    output.appendChild(card("QA Checklist", list(pack.qa_checklist)));
    output.appendChild(card("Three-Objective Assurance", objectiveAssurance(pack.objective_assurance)));
    output.appendChild(card("Export Status", '<div class="badges"><span class="badge">Browser-only</span><span class="badge">Vercel-ready</span><span class="badge">Human review required</span></div>'));
    $("quality-banner").className = "notice ok";
    $("quality-banner").textContent = "Review pack generated. Inspect engagement, rights, monetization, and QA evidence before production.";
    $("json-preview").textContent = JSON.stringify(pack, null, 2);
  }

  function objectiveAssurance(assurance) {
    return `<div class="detail-objectives">${Object.entries(assurance).map(([objective, items]) => `
      <div class="detail-objective-card ${objective}">
        <strong>${escapeHtml(objectiveLabel(objective))}</strong>
        <span>${escapeHtml(items.join(" · "))}</span>
      </div>`).join("")}</div>`;
  }

  function card(title, html) {
    const el = document.createElement("article");
    el.className = "review-card";
    el.innerHTML = `<h3>${escapeHtml(title)}</h3>${html}`;
    return el;
  }

  function list(items) {
    return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
  }

  function ordered(items) {
    return `<ol>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>`;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      alert("Copied.");
    } catch (_err) {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
      alert("Copied.");
    }
  }

  function download(filename, content, type = "text/plain") {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function requirePack() {
    if (!state.pack) alert("Generate a review pack first.");
    return Boolean(state.pack);
  }

  function loadBrief(brief) {
    $("topic").value = brief.topic || "";
    $("platform").value = brief.platform || "youtube_shorts";
    $("audience").value = brief.audience || "";
    $("tone").value = brief.tone || "";
    $("duration_seconds").value = brief.duration_seconds || 45;
    $("content_format").value = brief.content_format || inferFormat(brief.platform || "");
    $("monetization_goal").value = brief.monetization_goal || "";
    $("must_use_points").value = (brief.must_use_points || []).join("\n");
    $("avoid").value = (brief.avoid || []).join("\n");
    $("source_notes").value = (brief.source_notes || []).join("\n");
  }

  function bindStudioControls() {
    $("brief-form").addEventListener("submit", (event) => {
      event.preventDefault();
      state.brief = collectBrief();
      state.pack = buildReviewPack(state.brief);
      renderPack(state.pack);
    });

    $("load-sample").addEventListener("click", () => loadBrief(sampleBrief));
    $("clear-form").addEventListener("click", () => {
      Array.from($("brief-form").querySelectorAll("input, textarea")).forEach((el) => { el.value = ""; });
      $("platform").value = "youtube_shorts";
      $("content_format").value = "vertical_short";
    });

    $("copy-brief").addEventListener("click", () => copyText(JSON.stringify(state.brief || collectBrief(), null, 2)));
    $("download-brief").addEventListener("click", () => download("brief.json", JSON.stringify(state.brief || collectBrief(), null, 2), "application/json"));
    $("copy-pack").addEventListener("click", () => requirePack() && copyText(JSON.stringify(state.pack, null, 2)));
    $("download-pack").addEventListener("click", () => requirePack() && download("review-pack.json", JSON.stringify(state.pack, null, 2), "application/json"));
    $("download-markdown").addEventListener("click", () => requirePack() && download("producer-brief.md", state.pack.exports.producer_brief_md, "text/markdown"));
    $("download-script").addEventListener("click", () => requirePack() && download("script.txt", state.pack.exports.script_txt, "text/plain"));
    $("download-qa").addEventListener("click", () => requirePack() && download("qa-checklist.md", state.pack.exports.qa_checklist_md, "text/markdown"));
  }

  bindPortfolioControls();
  loadMonthFactory().then(() => refreshPortfolioFromApi());
  bindEngineControls();
  renderEnginePipeline();
  bindStudioControls();
  loadBrief(sampleBrief);
})();
