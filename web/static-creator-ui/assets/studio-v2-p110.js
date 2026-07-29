(() => {
  const CREATE_KEY = "studio-v2.p110-create";
  const SOURCE_DRAFT_PREFIX = "studio-v2.p110-source-draft:";
  const PLATFORM_VALUES = ["facebook", "instagram", "tiktok", "youtube", "youtube_shorts"];
  const PLATFORM_LABELS = {
    facebook: "Facebook",
    instagram: "Instagram",
    tiktok: "TikTok",
    youtube: "YouTube",
    youtube_shorts: "YouTube Shorts"
  };
  const DURATION_PRESETS = [15, 30, 45, 60, 90, 120, 150];
  let access = null;
  let familyBusy = false;
  let researchBusy = false;
  let policyBusy = false;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  const humanize = (value) => String(value || "unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const currentContentId = () => window.location.pathname.match(/^\/app\/content\/([^/]+)/)?.[1] || null;
  const currentTab = () => window.location.pathname.match(/^\/app\/content\/[^/]+\/([^/]+)/)?.[1] || "overview";
  const roles = () => access?.operator?.roles || [];
  const isAdmin = () => Boolean(access?.operator?.portfolio_wide) || roles().includes("admin") || roles().includes("super_admin");

  function errorText(error) {
    const detail = error?.payload?.detail;
    if (detail && typeof detail === "object") {
      if (detail.message) return detail.message;
      if (detail.code) return humanize(detail.code);
      if (Array.isArray(detail.blockers)) return detail.blockers.map((item) => item.message || humanize(item.code)).join(" ");
    }
    return error?.message || "The action could not be completed.";
  }

  function showToast(message, kind = "") {
    const region = $("#toast-region");
    if (!region) return;
    const item = document.createElement("div");
    item.className = `toast ${kind}`.trim();
    item.textContent = message;
    region.appendChild(item);
    window.setTimeout(() => item.remove(), 5000);
  }

  function readCreateConfig() {
    try {
      return JSON.parse(sessionStorage.getItem(CREATE_KEY) || "{}") || {};
    } catch {
      return {};
    }
  }

  function writeCreateConfig(value) {
    sessionStorage.setItem(CREATE_KEY, JSON.stringify(value));
  }

  function patchApi() {
    if (!window.StudioApi || window.StudioApi.__p110Patched) return;
    window.StudioApi.__p110Patched = true;
    const create = window.StudioApi.createContent.bind(window.StudioApi);
    window.StudioApi.createContent = async (payload) => {
      const config = readCreateConfig();
      const requested = String(payload.platform || config.platform || "facebook");
      const primary = requested === "all"
        ? String(config.primaryPlatform || "facebook")
        : requested;
      let targets = requested === "all"
        ? (Array.isArray(config.targetPlatforms) && config.targetPlatforms.length ? config.targetPlatforms : [...PLATFORM_VALUES])
        : [primary];
      targets = [...new Set(targets.filter((value) => PLATFORM_VALUES.includes(value)))];
      if (!targets.includes(primary)) targets.unshift(primary);
      const customDuration = Number(config.durationSeconds || payload.duration_seconds || 120);
      const result = await create({
        ...payload,
        platform: requested,
        primary_platform: primary,
        target_platforms: targets,
        duration_seconds: Math.max(10, Math.min(150, customDuration)),
        short_cut_count: requested === "all" ? Math.max(0, Math.min(2, Number(config.shortCutCount || 0))) : 0,
        format_name: payload.format_name || (customDuration >= 90 ? "master_video" : "explainer")
      });
      sessionStorage.removeItem(CREATE_KEY);
      return result;
    };
  }

  function enhanceCreateWizard() {
    const form = $("#brief-form");
    if (!form || form.dataset.p110Enhanced === "true") return;
    form.dataset.p110Enhanced = "true";
    const config = readCreateConfig();
    const platform = form.elements.platform;
    const format = form.elements.format_name;
    const duration = form.elements.duration_seconds;
    if (!platform || !format || !duration) return;

    const selectedPlatform = config.platform || platform.value || "facebook";
    platform.innerHTML = [
      ...PLATFORM_VALUES.map((value) => `<option value="${value}">${PLATFORM_LABELS[value]}</option>`),
      '<option value="all">All platforms</option>'
    ].join("");
    platform.value = selectedPlatform;

    const selectedFormat = config.formatName || format.value || "master_video";
    format.innerHTML = [
      '<option value="master_video">Master video</option>',
      '<option value="explainer">Explainer</option>',
      '<option value="vertical_short">Vertical short</option>'
    ].join("");
    format.value = ["master_video", "explainer", "vertical_short"].includes(selectedFormat) ? selectedFormat : "master_video";

    const initialDuration = Math.max(10, Math.min(150, Number(config.durationSeconds || duration.value || 120)));
    duration.innerHTML = DURATION_PRESETS.map((seconds) => `<option value="${seconds}">${seconds} seconds${seconds === 120 ? " (2 min)" : seconds === 150 ? " (2 min 30 sec)" : ""}</option>`).join("") + `<option value="${initialDuration}" data-custom-duration>Custom: ${initialDuration} seconds</option>`;
    duration.value = String(initialDuration);

    const advanced = document.createElement("div");
    advanced.id = "p110-create-controls";
    advanced.className = "wide card";
    advanced.style.padding = "16px";
    advanced.innerHTML = `
      <div class="form-grid">
        <label>Custom duration (10–150 seconds)
          <input id="p110-custom-duration" type="number" min="10" max="150" step="1" value="${initialDuration}">
        </label>
        <label id="p110-primary-platform-label">Primary platform
          <select id="p110-primary-platform">${PLATFORM_VALUES.map((value) => `<option value="${value}">${PLATFORM_LABELS[value]}</option>`).join("")}</select>
        </label>
        <label id="p110-short-cuts-label">Short-form cuts
          <select id="p110-short-cut-count"><option value="0">None</option><option value="1">1 cut</option><option value="2">2 cuts</option></select>
        </label>
        <fieldset id="p110-target-platforms" class="wide" style="border:0;padding:0;margin:0">
          <legend style="font-weight:700;margin-bottom:8px">Adapt the approved master for</legend>
          <div class="button-row" style="flex-wrap:wrap">${PLATFORM_VALUES.map((value) => `<label class="choice-card" style="min-width:150px;padding:10px"><input type="checkbox" value="${value}" data-p110-target><strong>${PLATFORM_LABELS[value]}</strong></label>`).join("")}</div>
        </fieldset>
      </div>
      <div class="notice" style="margin-top:12px"><strong>Master-first workflow</strong>Generate one approved primary video, then create linked platform adaptations and up to two separately reviewed short-form cuts.</div>`;
    form.appendChild(advanced);

    const primary = $("#p110-primary-platform", advanced);
    const cuts = $("#p110-short-cut-count", advanced);
    const custom = $("#p110-custom-duration", advanced);
    primary.value = config.primaryPlatform || (selectedPlatform === "all" ? "facebook" : selectedPlatform);
    cuts.value = String(config.shortCutCount ?? (initialDuration >= 120 && selectedPlatform === "all" ? 2 : 0));
    const selectedTargets = new Set(config.targetPlatforms || (selectedPlatform === "all" ? PLATFORM_VALUES : [selectedPlatform]));
    $$('[data-p110-target]', advanced).forEach((input) => { input.checked = selectedTargets.has(input.value); });

    const persist = () => {
      const requested = platform.value;
      const seconds = Math.max(10, Math.min(150, Number(custom.value || duration.value || 120)));
      let customOption = $('option[data-custom-duration]', duration);
      if (!customOption) {
        customOption = document.createElement("option");
        customOption.dataset.customDuration = "true";
        duration.appendChild(customOption);
      }
      customOption.value = String(seconds);
      customOption.textContent = `Custom: ${seconds} seconds`;
      duration.value = String(seconds);
      const targetPlatforms = requested === "all"
        ? $$('[data-p110-target]:checked', advanced).map((input) => input.value)
        : [requested];
      const primaryPlatform = requested === "all" ? primary.value : requested;
      if (!targetPlatforms.includes(primaryPlatform)) targetPlatforms.unshift(primaryPlatform);
      writeCreateConfig({
        platform: requested,
        primaryPlatform,
        targetPlatforms: [...new Set(targetPlatforms)],
        durationSeconds: seconds,
        shortCutCount: requested === "all" ? Number(cuts.value) : 0,
        formatName: format.value
      });
      const multi = requested === "all";
      $("#p110-primary-platform-label", advanced).hidden = !multi;
      $("#p110-short-cuts-label", advanced).hidden = !multi;
      $("#p110-target-platforms", advanced).hidden = !multi;
      if (!multi) primary.value = requested;
    };

    [platform, format, duration, custom, primary, cuts, ...$$('[data-p110-target]', advanced)].forEach((input) => {
      input.addEventListener("input", persist);
      input.addEventListener("change", persist);
    });
    duration.addEventListener("change", () => { custom.value = duration.value; persist(); });
    persist();
  }

  function enhanceConfirmation() {
    const summary = $(".review-summary");
    if (!summary || summary.dataset.p110Enhanced === "true") return;
    summary.dataset.p110Enhanced = "true";
    const config = readCreateConfig();
    const platform = config.platform || "facebook";
    const primary = config.primaryPlatform || (platform === "all" ? "facebook" : platform);
    const targets = config.targetPlatforms || [primary];
    summary.insertAdjacentHTML("beforeend", `
      <div><dt>Production model</dt><dd>${platform === "all" ? `Master for ${escapeHtml(PLATFORM_LABELS[primary])}, then adaptations` : escapeHtml(PLATFORM_LABELS[primary])}</dd></div>
      <div><dt>Target platforms</dt><dd>${targets.map((item) => escapeHtml(PLATFORM_LABELS[item] || humanize(item))).join(", ")}</dd></div>
      <div><dt>Short-form cuts</dt><dd>${Number(config.shortCutCount || 0)}</dd></div>`);
  }

  function familyItemCard(item) {
    const profile = item.adaptation_profile || {};
    const status = item.workflow_status_label || humanize(item.stage || "planned");
    return `<article class="content-card">
      <div class="button-row between"><div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(humanize(item.variant_type))} · ${escapeHtml(PLATFORM_LABELS[item.primary_platform] || humanize(item.primary_platform))}</p></div><span class="status-badge status-${escapeHtml(item.workflow_status || "draft")}">${escapeHtml(status)}</span></div>
      <p>${escapeHtml(item.target_duration_seconds)} seconds · ${escapeHtml(profile.aspect_ratio || "Original ratio")} · ${escapeHtml(profile.dimensions || "Output pending")}</p>
      <div class="button-row" style="margin-top:10px"><a class="primary-button" href="/app/content/${escapeHtml(item.id)}" data-route>Open</a></div>
    </article>`;
  }

  async function enhanceContentFamily() {
    const contentId = currentContentId();
    const tab = $("#content-tab");
    if (!contentId || !tab || $("#p110-content-family") || familyBusy) return;
    familyBusy = true;
    try {
      const family = await window.StudioApi.contentFamily(contentId);
      if (currentContentId() !== contentId || !document.body.contains(tab)) return;
      const section = document.createElement("section");
      section.id = "p110-content-family";
      section.className = "card";
      section.style.marginTop = "18px";
      section.innerHTML = `<div class="card-header"><div><h2>Content family</h2><p>One approved master with linked platform adaptations and separately reviewed short-form cuts.</p></div></div><div class="grid two">${(family.items || []).map(familyItemCard).join("")}</div>`;
      tab.appendChild(section);
    } catch (error) {
      if (error.status !== 404) showToast(errorText(error), "bad");
    } finally {
      familyBusy = false;
    }
  }

  function sourceDraftKey(documentId) {
    return `${SOURCE_DRAFT_PREFIX}${documentId}`;
  }

  function readSourceDraft(documentId) {
    try { return JSON.parse(sessionStorage.getItem(sourceDraftKey(documentId)) || "{}") || {}; }
    catch { return {}; }
  }

  function saveSourceDraft(documentId, patch) {
    sessionStorage.setItem(sourceDraftKey(documentId), JSON.stringify({ ...readSourceDraft(documentId), ...patch }));
  }

  function candidateCard(candidate, run, claims, document, editable) {
    const originalClaimId = String(run?.claim_id || "");
    return `<article class="content-card" data-p110-candidate="${escapeHtml(candidate.id)}">
      <div class="button-row between"><div><h3>${escapeHtml(candidate.title)}</h3><p>${escapeHtml(candidate.publisher || new URL(candidate.canonical_url).hostname)} · Quality ${escapeHtml(candidate.quality_score)}</p></div><span class="status-badge status-${candidate.accepted_at ? "approved" : candidate.rejected_at ? "rejected" : "draft"}">${candidate.accepted_at ? "Attached" : candidate.rejected_at ? "Rejected" : "Candidate"}</span></div>
      <p>${escapeHtml(candidate.relevance_summary)}</p>
      <p><a href="${escapeHtml(candidate.canonical_url)}" target="_blank" rel="noopener noreferrer">Open source</a></p>
      ${editable && !candidate.accepted_at && !candidate.rejected_at ? `
        <div class="form-grid" style="margin-top:12px">
          <fieldset class="wide" style="border:0;padding:0;margin:0"><legend style="font-weight:700;margin-bottom:8px">Attach to claims</legend>${claims.map((claim) => `<label style="display:block;margin:6px 0"><input type="checkbox" data-attach-claim value="${escapeHtml(claim.id)}" ${String(claim.id) === originalClaimId ? "checked" : ""}> ${escapeHtml(claim.claim_text)}</label>`).join("")}</fieldset>
          <label>Support type<select data-support-type><option value="direct">Direct</option><option value="corroborating" selected>Corroborating</option><option value="contextual">Contextual</option><option value="limitation">Limitation</option></select></label>
          <label class="wide">Support note<input data-support-note value="Supports the selected factual claim."></label>
        </div>
        <div class="button-row" style="margin-top:12px"><button class="primary-button" data-attach-source>Validate and attach</button><button class="secondary-button" data-reject-source>Reject candidate</button></div>` : ""}
    </article>`;
  }

  async function enhanceSourceResearch() {
    const contentId = currentContentId();
    if (!contentId || currentTab() !== "script" || !$("#script-action-panel") || $("#p110-source-research") || researchBusy) return;
    researchBusy = true;
    try {
      const [script, currentAccess] = await Promise.all([
        window.StudioApi.scriptForContent(contentId),
        access ? Promise.resolve(access) : window.StudioApi.access()
      ]);
      access = currentAccess;
      const documentData = script.document || {};
      const currentVersionId = String(documentData.current_version_id || "");
      const version = (script.versions || []).find((item) => String(item.id) === currentVersionId) || script.versions?.[0] || {};
      const status = documentData.current_version_status || version.status || "unknown";
      const claims = (script.claims || []).filter((claim) => String(claim.script_version_id) === currentVersionId);
      const needsSource = claims.filter((claim) => !["supported", "not_applicable"].includes(claim.support_status));
      const history = await window.StudioApi.scriptResearch(documentData.id).catch(() => ({ runs: [], candidates: [] }));
      if (currentContentId() !== contentId || currentTab() !== "script") return;
      const target = $(".detail-main", $("#content-tab")) || $("#content-tab");
      if (!target) return;
      const editable = status === "working";
      const draft = readSourceDraft(documentData.id);
      const runs = new Map((history.runs || []).map((run) => [String(run.id), run]));
      const candidates = history.candidates || [];
      const section = document.createElement("section");
      section.id = "p110-source-research";
      section.className = "card";
      section.innerHTML = `<div class="card-header"><div><h2>Research and sources</h2><p>Find real web sources, inspect them, and attach accepted evidence to exact factual claims.</p></div></div>
        ${status === "in_review" ? '<div class="notice warn"><strong>Request changes before editing sources</strong>Submitted versions are immutable. Request source changes, create a revision, then attach evidence to the new working version.</div>' : ""}
        ${["changes_requested", "rejected"].includes(status) ? '<div class="notice warn"><strong>Create the revision first</strong>Source evidence can be added to the new working version after you click Create revision.</div>' : ""}
        ${editable ? (needsSource.length ? `<div class="content-card-list">${needsSource.map((claim) => `<article class="content-card" data-research-claim="${escapeHtml(claim.id)}"><div class="button-row between"><div><h3>${escapeHtml(humanize(claim.support_status))}</h3><p>${escapeHtml(claim.claim_text)}</p></div><button class="primary-button" data-research-web>Research web</button></div><div class="form-grid" style="margin-top:12px"><label class="wide">Editable research query<input data-research-query value="${escapeHtml(draft[`query:${claim.id}`] || claim.claim_text)}"></label><label class="wide">Or add an exact source URL<input data-manual-url type="url" placeholder="https://authoritative-source.example/page" value="${escapeHtml(draft[`url:${claim.id}`] || "")}"></label><label>Source title (optional)<input data-manual-title value="${escapeHtml(draft[`title:${claim.id}`] || "")}"></label><label>Source type<select data-manual-type><option value="primary">Primary</option><option value="government">Government</option><option value="academic">Academic</option><option value="secondary" selected>Secondary</option><option value="news">News</option><option value="expert">Expert</option></select></label></div><div class="button-row" style="margin-top:10px"><button class="secondary-button" data-add-manual-source>Validate URL and add candidate</button></div></article>`).join("")}</div>` : '<div class="notice good"><strong>Evidence gate ready</strong>All current claims are supported or do not require a source.</div>') : ""}
        <div id="p110-research-message" style="margin-top:12px"></div>
        <div class="card-header" style="margin-top:18px"><div><h3>Research candidates</h3><p>Nothing is attached until an operator validates and accepts it.</p></div></div>
        <div id="p110-research-candidates" class="content-card-list">${candidates.length ? candidates.map((candidate) => candidateCard(candidate, runs.get(String(candidate.research_run_id)), needsSource, documentData, editable)).join("") : '<div class="empty-state"><h3>No candidates yet</h3><p>Research an unsupported claim or add an exact source URL.</p></div>'}</div>`;
      const decisionCard = $("#script-action-panel")?.closest("section.card");
      if (decisionCard) decisionCard.insertAdjacentElement("beforebegin", section); else target.appendChild(section);

      const message = $("#p110-research-message", section);
      const setMessage = (text, bad = false) => { message.innerHTML = `<div class="notice ${bad ? "bad" : "good"}">${escapeHtml(text)}</div>`; };
      $$('[data-research-claim]', section).forEach((card) => {
        const claimId = card.dataset.researchClaim;
        const query = $("[data-research-query]", card);
        const url = $("[data-manual-url]", card);
        const title = $("[data-manual-title]", card);
        [query, url, title].forEach((input) => input.addEventListener("input", () => {
          saveSourceDraft(documentData.id, { [`query:${claimId}`]: query.value, [`url:${claimId}`]: url.value, [`title:${claimId}`]: title.value });
        }));
        $("[data-research-web]", card).addEventListener("click", async (event) => {
          const button = event.currentTarget;
          const previous = button.textContent;
          button.disabled = true; button.textContent = "Researching…";
          try {
            const result = await window.StudioApi.researchClaim(documentData.id, { claim_id: claimId, query: query.value.trim() || null, limit: 5 });
            setMessage(result.candidates?.length ? `${result.candidates.length} source candidates found.` : "No suitable source candidates were found.");
            window.setTimeout(() => $("#content-refresh")?.click(), 300);
          } catch (error) { setMessage(errorText(error), true); }
          finally { button.disabled = false; button.textContent = previous; }
        });
        $("[data-add-manual-source]", card).addEventListener("click", async (event) => {
          const button = event.currentTarget;
          if (!url.value.trim()) return setMessage("Enter an exact public HTTPS source URL.", true);
          const previous = button.textContent;
          button.disabled = true; button.textContent = "Validating…";
          try {
            await window.StudioApi.addManualSource(documentData.id, { claim_id: claimId, url: url.value.trim(), title: title.value.trim() || null, source_type: $("[data-manual-type]", card).value });
            setMessage("Source URL validated and added as a candidate.");
            window.setTimeout(() => $("#content-refresh")?.click(), 300);
          } catch (error) { setMessage(errorText(error), true); }
          finally { button.disabled = false; button.textContent = previous; }
        });
      });

      $$('[data-p110-candidate]', section).forEach((card) => {
        const candidateId = card.dataset.p110Candidate;
        $("[data-attach-source]", card)?.addEventListener("click", async (event) => {
          const selectedClaims = $$('[data-attach-claim]:checked', card).map((input) => input.value);
          if (!selectedClaims.length) return setMessage("Select at least one exact claim.", true);
          const button = event.currentTarget;
          const previous = button.textContent;
          button.disabled = true; button.textContent = "Validating source…";
          try {
            await window.StudioApi.attachSource(documentData.id, {
              candidate_id: candidateId,
              claim_ids: selectedClaims,
              expected_lock_version: Number(documentData.lock_version || 0),
              support_type: $("[data-support-type]", card).value,
              support_note: $("[data-support-note]", card).value.trim() || "Supports the selected factual claim.",
              locator: null
            });
            sessionStorage.removeItem(sourceDraftKey(documentData.id));
            setMessage("Source validated, attached, and mapped to the selected claim(s).");
            window.setTimeout(() => $("#content-refresh")?.click(), 300);
          } catch (error) { setMessage(errorText(error), true); }
          finally { button.disabled = false; button.textContent = previous; }
        });
        $("[data-reject-source]", card)?.addEventListener("click", async (event) => {
          const button = event.currentTarget;
          button.disabled = true;
          try {
            await window.StudioApi.rejectResearchCandidate(candidateId, "Rejected during Creator Studio source review.");
            setMessage("Candidate rejected.");
            window.setTimeout(() => $("#content-refresh")?.click(), 300);
          } catch (error) { setMessage(errorText(error), true); }
          finally { button.disabled = false; }
        });
      });

      if (status === "in_review" && isAdmin() && String(version.last_edited_by || "") === String(access?.operator?.operator_id || "")) {
        $("#script-action-panel")?.insertAdjacentHTML("afterbegin", '<div class="notice" style="margin-bottom:14px"><strong>Same-session Admin review</strong>This decision will be explicitly recorded as an Admin self-review under the brand policy. It will not be represented as independent review.</div>');
      }
    } catch (error) {
      if (error.status !== 404) showToast(errorText(error), "bad");
    } finally {
      researchBusy = false;
    }
  }

  async function enhanceReviewPolicies() {
    const view = $("#app-view");
    if (window.location.pathname !== "/app/settings" || !view || $("#p110-review-policies") || policyBusy) return;
    policyBusy = true;
    try {
      access = access || await window.StudioApi.access();
      if (!isAdmin()) return;
      const payload = await window.StudioApi.brands();
      const brands = payload.brands || [];
      const policies = await Promise.all(brands.map(async (brand) => {
        try { return [brand, (await window.StudioApi.reviewPolicy(brand.id)).policy]; }
        catch { return [brand, null]; }
      }));
      if (window.location.pathname !== "/app/settings" || !document.body.contains(view)) return;
      const section = document.createElement("section");
      section.id = "p110-review-policies";
      section.className = "card";
      section.style.marginTop = "18px";
      section.innerHTML = `<div class="card-header"><div><h2>Brand review policy</h2><p>Admins can progress end to end in one session while preserving explicit audit evidence. Independent review remains available.</p></div></div><div class="content-card-list">${policies.map(([brand, policy]) => `<article class="content-card" data-policy-brand="${escapeHtml(brand.id)}"><div class="button-row between"><div><h3>${escapeHtml(brand.display_name)}</h3><p>${escapeHtml(brand.metadata?.facebook_url || brand.source_links?.[0] || "Brand source link not configured")}</p></div><button class="primary-button" data-save-policy>Save policy</button></div><div class="form-grid" style="margin-top:12px"><label>Operating policy<select data-policy-key><option value="independent_review_required">Independent review required</option><option value="admin_self_review_allowed">Admin self-review allowed</option><option value="independent_final_release_required">Admin workflow; independent final release</option></select></label><label style="align-self:end"><input type="checkbox" data-policy-rationale ${policy?.rationale_required_for_override ? "checked" : ""}> Require an override rationale</label></div><div class="notice" data-policy-status style="margin-top:10px"><strong>Current</strong>${escapeHtml(humanize(policy?.policy_key || "not configured"))}${policy?.version ? ` · Version ${escapeHtml(policy.version)}` : ""}</div></article>`).join("")}</div>`;
      view.appendChild(section);
      policies.forEach(([brand, policy]) => {
        const card = $(`[data-policy-brand="${CSS.escape(String(brand.id))}"]`, section);
        if (policy) $("[data-policy-key]", card).value = policy.policy_key;
        $("[data-save-policy]", card).addEventListener("click", async (event) => {
          const button = event.currentTarget;
          const previous = button.textContent;
          button.disabled = true; button.textContent = "Saving…";
          try {
            const result = await window.StudioApi.setReviewPolicy(brand.id, {
              policy_key: $("[data-policy-key]", card).value,
              rationale_required_for_override: $("[data-policy-rationale]", card).checked
            });
            $("[data-policy-status]", card).innerHTML = `<strong>Current</strong>${escapeHtml(humanize(result.policy.policy_key))} · Version ${escapeHtml(result.policy.version)}`;
            showToast("Brand review policy saved.", "good");
          } catch (error) { showToast(errorText(error), "bad"); }
          finally { button.disabled = false; button.textContent = previous; }
        });
      });
    } finally {
      policyBusy = false;
    }
  }

  async function enhance() {
    patchApi();
    enhanceCreateWizard();
    enhanceConfirmation();
    await enhanceContentFamily();
    await enhanceSourceResearch();
    await enhanceReviewPolicies();
  }

  const observer = new MutationObserver(() => window.setTimeout(() => void enhance(), 80));
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", () => window.setTimeout(() => void enhance(), 150));
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-route],#refresh-view,#content-refresh")) window.setTimeout(() => void enhance(), 250);
  }, true);
  window.setTimeout(() => void enhance(), 100);
})();
