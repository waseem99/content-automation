(() => {
  const state = { brief: null, pack: null };
  const $ = (id) => document.getElementById(id);

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

  function buildReviewPack(brief) {
    const topic = brief.topic;
    const platform = platformLabel(brief.platform);
    const audience = brief.audience || "the target audience";
    const monetizationGoal = brief.monetization_goal || "qualified interest";
    const hook = `Most ${audience} lose time on ${topic.toLowerCase()} because the real problem is hidden in the workflow.`;
    const titleOptions = [
      `The Hidden Cost of ${topic}`,
      `Before You Scale, Fix This ${topic} Problem`,
      `${topic}: The 45-Second Audit`,
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
        brief.content_format === "vertical_short" ? "Use fast cuts, subtitles, and a strong first 2 seconds." : "Use chapter-like structure and stronger explanation depth.",
        "Keep visuals original, licensed, or owned."
      ],
      guardrails: guardrails()
    };
  }

  function buildBeats(brief, hook) {
    const points = brief.must_use_points.length ? brief.must_use_points : ["Introduce the problem.", "Show the better workflow.", "Close with a soft CTA."];
    return [
      { time: "0-3s", label: "Hook", direction: hook },
      { time: "3-12s", label: "Problem", direction: points[0] || "Frame the pain clearly." },
      { time: "12-28s", label: "Proof / process", direction: points[1] || "Show the before and after." },
      { time: "28-40s", label: "Value", direction: points[2] || "Give a practical takeaway." },
      { time: "40s+", label: "CTA", direction: `Invite viewers to take the next step toward: ${brief.monetization_goal || "a useful next action"}` }
    ];
  }

  function buildScript(brief, beats) {
    const avoid = brief.avoid.length ? `Avoid: ${brief.avoid.join(" ")}` : "Avoid overclaiming or using unlicensed assets.";
    return [
      `HOOK: ${beats[0].direction}`,
      `PROBLEM: If your team is relying on memory, scattered tools, or manual follow-ups, the leak is probably not one person. It is the system around them.`,
      `PROCESS: Map the lead or customer journey from first touch to final follow-up. Mark every delay, repeated task, missing owner, and message that depends on manual effort.`,
      `VALUE: Once the workflow is visible, you can decide what should be automated, what should stay human, and what should be removed completely.`,
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
        ? "Close-up founder/persona speaking to camera with bold subtitle overlay."
        : index === beats.length - 1
          ? "Clean CTA card with checklist/download/request prompt."
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
      "Suggested CTA asset: checklist, audit request, consultation form, or saved post prompt.",
      "Do not imply guaranteed revenue, savings, conversion, or platform performance."
    ];
  }

  function buildQaChecklist(brief) {
    return [
      "Hook is specific and understandable in the first 2-3 seconds.",
      "Script is practical and avoids generic claims.",
      "Storyboard can be produced with owned or licensed assets.",
      "Copyright and brand/logo risks are identified before production.",
      "CTA matches the monetization goal.",
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
    output.appendChild(card("Export Status", `<div class="badges"><span class="badge">Browser-only</span><span class="badge">Vercel-ready</span><span class="badge">Human review required</span></div>`));
    $("quality-banner").className = "notice ok";
    $("quality-banner").textContent = "Review pack generated. Inspect the content before production; exported files are available below.";
    $("json-preview").textContent = JSON.stringify(pack, null, 2);
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

  $("brief-form").addEventListener("submit", (event) => {
    event.preventDefault();
    state.brief = collectBrief();
    state.pack = buildReviewPack(state.brief);
    renderPack(state.pack);
  });

  $("load-sample").addEventListener("click", () => loadBrief(sampleBrief));
  $("clear-form").addEventListener("click", () => {
    Array.from(document.querySelectorAll("input, textarea")).forEach((el) => { el.value = ""; });
    $("platform").value = "youtube_shorts";
  });

  $("copy-brief").addEventListener("click", () => copyText(JSON.stringify(state.brief || collectBrief(), null, 2)));
  $("download-brief").addEventListener("click", () => download("brief.json", JSON.stringify(state.brief || collectBrief(), null, 2), "application/json"));
  $("copy-pack").addEventListener("click", () => requirePack() && copyText(JSON.stringify(state.pack, null, 2)));
  $("download-pack").addEventListener("click", () => requirePack() && download("review-pack.json", JSON.stringify(state.pack, null, 2), "application/json"));
  $("download-markdown").addEventListener("click", () => requirePack() && download("producer-brief.md", state.pack.exports.producer_brief_md, "text/markdown"));
  $("download-script").addEventListener("click", () => requirePack() && download("script.txt", state.pack.exports.script_txt, "text/plain"));
  $("download-qa").addEventListener("click", () => requirePack() && download("qa-checklist.md", state.pack.exports.qa_checklist_md, "text/markdown"));

  loadBrief(sampleBrief);
})();
