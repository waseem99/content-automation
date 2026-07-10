(() => {
  const stages = [
    {
      id: "brief",
      number: "01",
      title: "Brief & Intent Capture",
      modules: ["P59 Local Creator Studio", "P60 Custom Brief Adapter", "P61 Single-Brief Runner"],
      tools: ["Static HTML form", "Browser JavaScript", "JSON schema", "Python adapters for local pipeline"],
      input: "Topic, platform, audience, tone, duration, monetization goal, must-use points, avoid list, source notes.",
      output: "Normalized creator brief and full-cycle input package.",
      gate: "Required fields present; monetization objective and prohibited claims are explicit.",
      status: "Live now",
      objectives: { engagement: "Audience, hook direction and format are fixed before generation.", policy: "Avoid list and rights notes enter the pipeline at source.", monetization: "A specific business outcome and CTA path are captured." }
    },
    {
      id: "strategy",
      number: "02",
      title: "Content Strategy & Platform Adaptation",
      modules: ["P40 Content Package", "P48 Platform Templates", "P49 Pilot Batch"],
      tools: ["Platform rules", "Content templates", "Deterministic planning logic", "Future LLM strategy layer"],
      input: "Normalized brief plus platform constraints.",
      output: "Concept, content angle, title options, format plan and platform notes.",
      gate: "The concept must fit the platform, audience and production reality.",
      status: "Deterministic MVP",
      objectives: { engagement: "Platform-specific opening pattern, duration and pacing are selected.", policy: "Risky content types and unsupported proof are excluded early.", monetization: "The content angle supports the intended funnel rather than vanity views only." }
    },
    {
      id: "generation",
      number: "03",
      title: "Hook, Script & Storyboard Generation",
      modules: ["P40 Content Package", "P43 Production Handoff", "P46 Producer Export"],
      tools: ["Current browser generator", "Python content package generator", "Future secure LLM API", "Structured JSON/Markdown exports"],
      input: "Approved concept and platform plan.",
      output: "Hook, titles, retention beats, script, storyboard and producer brief.",
      gate: "Every script must have a clear first-second hook, value progression and production-ready visual direction.",
      status: "Live deterministic; AI next",
      objectives: { engagement: "Hook, open loops, proof/value beats and CTA are explicitly sequenced.", policy: "Claims and asset directions stay traceable to the brief.", monetization: "CTA is embedded into the script and storyboard, not added at the end as an afterthought." }
    },
    {
      id: "rights",
      number: "04",
      title: "Rights, Safety & Policy Gate",
      modules: ["P41 Rights/Safety", "P50 Creative QA", "P55 Demo Gallery"],
      tools: ["Rights checklist", "Claim-risk rules", "Platform policy matrix", "Human reviewer"],
      input: "Script, storyboard, sources, asset plan and claims.",
      output: "Rights notes, blocked items, required evidence and safe-production instructions.",
      gate: "No unlicensed music/footage, celebrity likeness, unsupported business claim or prohibited platform tactic proceeds.",
      status: "Live guardrails + human gate",
      objectives: { engagement: "Risk controls protect the concept without stripping away the hook.", policy: "Copyright, brand, likeness, claims and platform restrictions are checked.", monetization: "Advertiser-sensitive and demonetization-prone choices are identified before production." }
    },
    {
      id: "engagement",
      number: "05",
      title: "Engagement & Retention Scoring",
      modules: ["P42 Engagement/Retention", "P50 Creative QA", "P53 Before/After Comparator"],
      tools: ["Hook checklist", "Retention beat scoring", "Clarity and pacing rules", "Before/after comparison"],
      input: "Hook, script, storyboard and target platform.",
      output: "Engagement findings, revision prompts and comparative improvement notes.",
      gate: "The opening, pacing, proof, novelty and CTA must each be understandable and intentional.",
      status: "Live rules; predictive scoring future",
      objectives: { engagement: "Directly measures hook strength, pacing, payoff, clarity and replay/save triggers.", policy: "Engagement tactics cannot rely on deception, false urgency or misleading claims.", monetization: "High-intent actions such as click, save, follow, lead or purchase are matched to the funnel." }
    },
    {
      id: "monetization",
      number: "06",
      title: "Monetization Readiness",
      modules: ["P44 Monetization Readiness", "P45 Orchestration", "P46 Producer Export"],
      tools: ["CTA mapping", "Offer-fit checklist", "Platform revenue rules", "Funnel alignment"],
      input: "Audience intent, platform, content promise, CTA and commercial goal.",
      output: "Primary monetization path, CTA asset, conversion action and revenue-risk notes.",
      gate: "The content must generate a useful commercial action without making prohibited guarantees.",
      status: "Live planning layer",
      objectives: { engagement: "The CTA follows naturally from the value delivered.", policy: "No guaranteed earnings, misleading scarcity or unsupported financial outcome.", monetization: "Lead generation, affiliate, product sale, sponsorship or platform revenue is selected deliberately." }
    },
    {
      id: "production",
      number: "07",
      title: "Production Handoff & Batch Execution",
      modules: ["P43 Production Handoff", "P46 Producer Export", "P47 Folder Runner"],
      tools: ["Producer brief", "Shot list", "Storyboard", "Folder runner", "Editor checklist"],
      input: "Approved content pack.",
      output: "Editor-ready pack with scenes, narration, asset rules, subtitles, CTA and QA instructions.",
      gate: "Every frame must be producible with owned/licensed assets and a clear responsibility.",
      status: "Live local workflow",
      objectives: { engagement: "Editing instructions preserve pacing, subtitles and visual pattern changes.", policy: "Asset provenance and restricted elements remain visible to production.", monetization: "CTA visuals and conversion asset are included in the final shot plan." }
    },
    {
      id: "review",
      number: "08",
      title: "Human Review, Feedback & Revision",
      modules: ["P54 Review Workspace", "P56 Feedback Queue", "P57 Feedback Regeneration", "P58 Review Cycle"],
      tools: ["Local review workspace", "Feedback JSON", "Revision queue", "Regeneration gallery", "Human approval"],
      input: "First-pass content pack and reviewer feedback.",
      output: "Approve/revise/reject decision, requested changes and revised pack.",
      gate: "No item is considered production-ready without human approval.",
      status: "Live local review cycle",
      objectives: { engagement: "Reviewers can reject generic, weak or confusing creative.", policy: "Human judgment remains the final compliance gate.", monetization: "Commercial relevance and CTA quality are reviewed alongside creative quality." }
    },
    {
      id: "export",
      number: "09",
      title: "Export, Measurement & Learning Loop",
      modules: ["P51 Revision Planner", "P52 Regeneration", "P53 Comparator", "P62 Static Creator UI"],
      tools: ["JSON/Markdown/TXT export", "Comparison report", "Future analytics connectors", "Future platform APIs"],
      input: "Approved or revised content pack plus later performance data.",
      output: "Producer files today; future performance feedback for next-generation briefs.",
      gate: "Publishing and analytics ingestion remain separate controlled steps.",
      status: "Exports live; analytics loop future",
      objectives: { engagement: "Future watch-time, retention, saves and comments feed the next brief.", policy: "Policy incidents and rights issues become reusable prevention rules.", monetization: "Revenue, lead quality and conversion signals guide future content choices." }
    }
  ];

  const platforms = {
    youtube_shorts: { label: "YouTube Shorts", hook: "0–2s visual/verbal interruption", pacing: "Fast cuts; clear payoff by 30–45s", compliance: "Avoid reused-content signals, copyrighted media and misleading metadata", money: "Channel growth, product/lead CTA, Shorts revenue where eligible" },
    instagram_reels: { label: "Instagram Reels", hook: "Immediate visual context + bold on-screen line", pacing: "Pattern change every 2–4s; save/share utility", compliance: "Branded content disclosure, music/asset rights, no deceptive before/after claims", money: "DM/lead magnet, product discovery, brand partnerships, profile conversion" },
    tiktok: { label: "TikTok", hook: "Native spoken hook; creator-led opening", pacing: "Conversational, rapid proof, loop-friendly ending", compliance: "Commercial disclosure, sensitive-claim rules, no copied trends/assets without rights", money: "Shop/product path, affiliate, lead capture, creator monetization where eligible" },
    youtube_long: { label: "YouTube Longform", hook: "Promise + stakes in first 15–30s", pacing: "Chapters, evidence, periodic open loops and resets", compliance: "Copyright/Content ID, advertiser suitability, claim substantiation", money: "Ads, sponsorship, affiliate, product, memberships and qualified leads" },
    linkedin_video: { label: "LinkedIn Video", hook: "Business tension or evidence-led insight", pacing: "Dense but clear; credibility before promotion", compliance: "Professional accuracy, disclosure, permission for client data/logos", money: "B2B authority, inbound leads, consultation and enterprise pipeline" }
  };

  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

  function renderStages() {
    const rail = $("engine-stage-rail");
    rail.innerHTML = stages.map((stage, index) => `
      <button class="engine-stage${index === 0 ? " active" : ""}" data-stage="${stage.id}" type="button">
        <span class="engine-stage-number">${stage.number}</span>
        <span><strong>${escapeHtml(stage.title)}</strong><small>${escapeHtml(stage.status)}</small></span>
      </button>`).join("");
    rail.querySelectorAll("[data-stage]").forEach((button) => button.addEventListener("click", () => selectStage(button.dataset.stage)));
    selectStage(stages[0].id);
  }

  function selectStage(id) {
    const stage = stages.find((item) => item.id === id) || stages[0];
    document.querySelectorAll(".engine-stage").forEach((item) => item.classList.toggle("active", item.dataset.stage === stage.id));
    $("engine-detail").innerHTML = `
      <div class="engine-detail-head"><div><span class="engine-kicker">Stage ${stage.number}</span><h3>${escapeHtml(stage.title)}</h3></div><span class="status-pill">${escapeHtml(stage.status)}</span></div>
      <div class="engine-detail-grid">
        <article><h4>Code/modules</h4>${tagList(stage.modules)}</article>
        <article><h4>Tools used</h4>${tagList(stage.tools)}</article>
        <article><h4>Input</h4><p>${escapeHtml(stage.input)}</p></article>
        <article><h4>Output</h4><p>${escapeHtml(stage.output)}</p></article>
      </div>
      <div class="engine-gate"><strong>Decision gate</strong><span>${escapeHtml(stage.gate)}</span></div>
      <div class="objective-detail-grid">
        ${objectiveCard("Engagement", stage.objectives.engagement, "engagement")}
        ${objectiveCard("Policy compliance", stage.objectives.policy, "policy")}
        ${objectiveCard("Monetization", stage.objectives.monetization, "money")}
      </div>`;
  }

  function tagList(items) {
    return `<div class="engine-tags">${items.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`;
  }

  function objectiveCard(title, text, key) {
    return `<article class="objective-mini ${key}"><span>${escapeHtml(title)}</span><p>${escapeHtml(text)}</p></article>`;
  }

  function renderPlatform(platformId) {
    const platform = platforms[platformId] || platforms.youtube_shorts;
    $("platform-detail").innerHTML = `
      <div class="platform-heading"><span>Selected platform</span><h3>${escapeHtml(platform.label)}</h3></div>
      <div class="platform-rule-grid">
        <article><strong>Hook</strong><p>${escapeHtml(platform.hook)}</p></article>
        <article><strong>Pacing</strong><p>${escapeHtml(platform.pacing)}</p></article>
        <article><strong>Policy focus</strong><p>${escapeHtml(platform.compliance)}</p></article>
        <article><strong>Monetization path</strong><p>${escapeHtml(platform.money)}</p></article>
      </div>`;
  }

  function bindObjectiveFilters() {
    document.querySelectorAll("[data-objective]").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll("[data-objective]").forEach((item) => item.classList.toggle("active", item === button));
        document.body.dataset.objective = button.dataset.objective;
      });
    });
  }

  function init() {
    if (!$("engine-stage-rail")) return;
    renderStages();
    bindObjectiveFilters();
    const select = $("engine-platform");
    select.addEventListener("change", () => renderPlatform(select.value));
    renderPlatform(select.value);
  }

  init();
})();