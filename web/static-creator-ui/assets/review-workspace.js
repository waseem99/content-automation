(() => {
  const state = {
    roles: [],
    operatorId: "",
    brands: [],
    inbox: [],
    workspace: null,
    script: null,
    audio: null,
    visuals: null,
    comparison: null,
    targets: []
  };

  const make = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const hasRole = (role) => state.roles.includes("admin") || state.roles.includes(role);
  const guarded = (task) => Promise.resolve().then(task).catch((error) => setStatus(error.message));
  const setStatus = (message) => {
    const node = document.getElementById("review-workspace-status");
    if (node) node.textContent = message;
  };
  const formatDate = (value) => value ? new Date(value).toLocaleString() : "Not set";
  const normalize = (value) => String(value || "").replaceAll("_", " ");

  function badge(value) {
    const normalized = String(value || "unknown");
    return make("span", `review-workspace-badge ${normalized}`, normalize(normalized));
  }

  function action(text, handler, secondary = false) {
    const button = make("button", secondary ? "secondary" : "", text);
    button.type = "button";
    button.addEventListener("click", () => guarded(handler));
    return button;
  }

  function panel() {
    const section = make("section", "review-workspace-section");
    section.id = "review-workspace-studio";
    section.innerHTML = `
      <div class="review-workspace-heading">
        <div><p class="eyebrow dark-eyebrow">Creator Studio Review Workspace</p>
        <h2>Review inbox, exact versions, comments, and revisions</h2>
        <p>All decisions stay in their canonical script, audio, visual, and workflow records. This workspace only aggregates evidence and assigned revision work.</p></div>
      </div>
      <p id="review-workspace-status" class="review-workspace-status" role="status" aria-live="polite">Connect Data to load your assigned review inbox.</p>
      <div class="review-workspace-layout">
        <aside class="review-inbox-panel" aria-label="Review inbox">
          <div class="review-panel-heading"><h3>Inbox</h3><button id="review-inbox-refresh" type="button" class="secondary">Refresh</button></div>
          <div class="review-filter-grid">
            <label><span>Brand</span><select id="review-filter-brand"><option value="">All assigned brands</option></select></label>
            <label><span>Stage</span><select id="review-filter-stage"><option value="">All stages</option></select></label>
            <label><span>Assignee</span><input id="review-filter-assignee" autocomplete="off" placeholder="operator ID"></label>
            <label><span>Status</span><select id="review-filter-status"><option value="">Any status</option><option>open</option><option>in_progress</option><option>completed</option><option>cancelled</option></select></label>
            <label><span>Due by</span><input id="review-filter-due" type="datetime-local"></label>
            <label class="review-check"><input id="review-filter-blocker" type="checkbox"><span>Blockers only</span></label>
            <label class="review-check"><input id="review-filter-overdue" type="checkbox"><span>Overdue only</span></label>
          </div>
          <div id="review-inbox-items" class="review-inbox-items"></div>
        </aside>
        <main class="review-workspace-main">
          <div class="review-load-bar">
            <label><span>Content UUID</span><input id="review-workspace-content" autocomplete="off"></label>
            <button id="review-workspace-load" type="button">Open workspace</button>
          </div>
          <div id="review-workspace-summary"></div>
          <nav class="review-workspace-tabs" aria-label="Workspace sections">
            <button type="button" data-review-tab="evidence" aria-selected="true">Evidence</button>
            <button type="button" data-review-tab="compare">Compare</button>
            <button type="button" data-review-tab="comments">Comments & tasks</button>
            <button type="button" data-review-tab="history">Decision history</button>
          </nav>
          <section id="review-tab-evidence" class="review-tab-panel"></section>
          <section id="review-tab-compare" class="review-tab-panel" hidden></section>
          <section id="review-tab-comments" class="review-tab-panel" hidden></section>
          <section id="review-tab-history" class="review-tab-panel" hidden></section>
        </main>
      </div>`;
    return section;
  }

  function renderBrandOptions() {
    const select = document.getElementById("review-filter-brand");
    if (!select) return;
    const current = select.value;
    select.replaceChildren(new Option("All assigned brands", ""));
    state.brands.forEach((brand) => select.append(new Option(brand.display_name, brand.id)));
    select.value = current;
  }

  function stageOptions() {
    const stages = [
      "concept_draft", "concept_review", "script_draft", "script_review",
      "audio_generation", "audio_review", "visual_generation", "visual_review",
      "preview_build", "preview_review", "final_package", "final_review", "ready_for_delivery"
    ];
    const select = document.getElementById("review-filter-stage");
    if (!select || select.options.length > 1) return;
    stages.forEach((stage) => select.append(new Option(normalize(stage), stage)));
  }

  function inboxFilters() {
    const brand = document.getElementById("review-filter-brand").value;
    const stage = document.getElementById("review-filter-stage").value;
    const assignee = document.getElementById("review-filter-assignee").value.trim();
    const status = document.getElementById("review-filter-status").value;
    const due = document.getElementById("review-filter-due").value;
    return {
      brandIds: brand ? [brand] : [],
      stages: stage ? [stage] : [],
      assigneeOperatorId: assignee || null,
      statuses: status ? [status] : [],
      dueTo: due ? new Date(due).toISOString() : null,
      blocker: document.getElementById("review-filter-blocker").checked ? true : null,
      overdue: document.getElementById("review-filter-overdue").checked ? true : null,
      limit: 200
    };
  }

  async function loadInbox() {
    const result = await window.PortfolioApi.reviewInbox(inboxFilters());
    state.inbox = result.items || [];
    renderInbox();
    setStatus(`${state.inbox.length} review inbox item${state.inbox.length === 1 ? "" : "s"} loaded.`);
  }

  function renderInbox() {
    const root = document.getElementById("review-inbox-items");
    if (!root) return;
    root.replaceChildren();
    if (!state.inbox.length) {
      root.append(make("p", "review-empty", "No items match these filters."));
      return;
    }
    state.inbox.forEach((item) => {
      const button = make("button", `review-inbox-item ${item.blocker ? "blocker" : ""}`);
      button.type = "button";
      const top = make("span", "review-inbox-top");
      top.append(make("strong", "", item.content_title), badge(item.status));
      const meta = make("span", "review-inbox-meta", `${item.brand_name} · ${normalize(item.stage)} · ${normalize(item.inbox_item_type)}`);
      const due = make("span", item.overdue ? "review-inbox-due overdue" : "review-inbox-due", `Due: ${formatDate(item.due_at)}`);
      button.append(top, meta, due);
      if (item.blocker_reason) button.append(make("span", "review-inbox-reason", item.blocker_reason));
      button.addEventListener("click", () => {
        document.getElementById("review-workspace-content").value = item.portfolio_content_id;
        guarded(loadWorkspace);
      });
      root.append(button);
    });
  }

  function currentContentId() {
    const value = document.getElementById("review-workspace-content").value.trim();
    if (!value) throw new Error("Enter or select a content UUID.");
    return value;
  }

  async function optional(call) {
    try { return await call(); } catch (_) { return null; }
  }

  async function loadWorkspace() {
    const contentId = currentContentId();
    const [workspace, script, audio, visuals] = await Promise.all([
      window.PortfolioApi.reviewWorkspace(contentId),
      optional(() => window.PortfolioApi.scriptForContent(contentId)),
      optional(() => window.PortfolioApi.audioForContent(contentId)),
      optional(() => window.PortfolioApi.visualsForContent(contentId))
    ]);
    state.workspace = workspace;
    state.script = script;
    state.audio = audio;
    state.visuals = visuals;
    state.comparison = null;
    state.targets = collectTargets();
    renderWorkspace();
    setStatus("Canonical script, audio, visual, workflow, task, and decision evidence loaded.");
  }

  function collectTargets() {
    const targets = [];
    const push = (type, id, label) => { if (id) targets.push({ type, id: String(id), label }); };
    const workflow = state.workspace?.workflow;
    push("workflow_version", workflow?.current_version_id, `Workflow v${workflow?.current_version || "current"}`);
    (state.workspace?.script_versions || []).forEach((row) => push("script_version", row.id, `Script v${row.version} · ${normalize(row.status)}`));
    (state.script?.sections || []).forEach((row) => push("script_section", row.id, `Script section ${row.sequence} · ${row.section_type}`));
    (state.audio?.mixes || []).forEach((row) => push("audio_mix_version", row.id, `Audio mix v${row.version} · ${normalize(row.status)}`));
    (state.audio?.paragraphs || []).forEach((row) => push("audio_paragraph", row.id, `Audio paragraph ${row.sequence}`));
    (state.visuals?.versions || []).forEach((row) => push("visual_shot_version", row.id, `Visual shot version ${row.version} · ${normalize(row.status)}`));
    (state.visuals?.candidates || []).forEach((row) => push("visual_candidate", row.id, `Visual candidate ${row.ordinal} · ${normalize(row.status)}`));
    return targets;
  }

  function renderWorkspace() {
    renderSummary();
    renderEvidence();
    renderCompare();
    renderCommentsAndTasks();
    renderDecisionHistory();
  }

  function renderSummary() {
    const root = document.getElementById("review-workspace-summary");
    root.replaceChildren();
    if (!state.workspace) return;
    const content = state.workspace.content;
    const workflow = state.workspace.workflow;
    const card = make("div", "review-workspace-summary-card");
    const copy = make("div");
    copy.append(make("h3", "", content.title));
    const line = make("p");
    line.append(badge(workflow?.status || "not_started"), document.createTextNode(` · ${content.brand_name} · ${normalize(workflow?.current_stage || "no workflow")}`));
    copy.append(line, make("small", "", `Content v${content.version} · workflow lock ${workflow?.lock_version ?? "—"}`));
    card.append(copy);
    const counts = make("div", "review-summary-counts");
    [
      ["Open tasks", (state.workspace.revision_tasks || []).filter((item) => ["open", "in_progress"].includes(item.status)).length],
      ["Blockers", (state.workspace.revision_tasks || []).filter((item) => item.blocker && ["open", "in_progress"].includes(item.status)).length],
      ["Comments", (state.workspace.comments || []).length],
      ["Render jobs", (state.workspace.render_jobs || []).length]
    ].forEach(([label, value]) => {
      const item = make("div", "review-summary-count");
      item.append(make("strong", "", String(value)), make("span", "", label));
      counts.append(item);
    });
    card.append(counts);
    root.append(card);
  }

  function evidenceCard(title, statusValue) {
    const card = make("article", "review-evidence-card");
    const heading = make("div", "review-evidence-heading");
    heading.append(make("h3", "", title));
    if (statusValue) heading.append(badge(statusValue));
    card.append(heading);
    return card;
  }

  function renderEvidence() {
    const root = document.getElementById("review-tab-evidence");
    root.replaceChildren();
    if (!state.workspace) return;
    const grid = make("div", "review-evidence-grid");

    const scriptCard = evidenceCard("Script", state.script?.document?.current_version_status);
    if (!state.script) scriptCard.append(make("p", "review-empty", "No script document is available."));
    else {
      const documentRow = state.script.document;
      const version = (state.script.versions || []).find((item) => String(item.id) === String(documentRow.current_version_id));
      scriptCard.append(make("p", "", `Version ${documentRow.current_version} · ${version?.word_count || 0} words · ${Number(version?.estimated_duration_seconds || 0).toFixed(1)}s`));
      (state.script.sections || []).filter((item) => String(item.script_version_id) === String(documentRow.current_version_id)).forEach((section) => {
        const row = make("div", "review-evidence-row");
        row.append(make("strong", "", `${section.section_type} · ${section.sequence}`), make("p", "", section.text));
        scriptCard.append(row);
      });
      renderScriptActions(scriptCard);
    }

    const audioCard = evidenceCard("Narration & mix", state.audio?.production?.status);
    if (!state.audio) audioCard.append(make("p", "review-empty", "No audio production is available."));
    else {
      const production = state.audio.production;
      const mix = (state.audio.mixes || []).find((item) => String(item.id) === String(production.current_mix_version_id));
      audioCard.append(make("p", "", `${production.provider}/${production.model_id} · ${state.audio.paragraphs.length} paragraphs`));
      const waveform = make("div", "review-waveform");
      waveform.setAttribute("aria-label", "Waveform timeline placeholder for the current exact audio mix");
      const peaks = mix?.waveform_metadata?.peaks || [0.15,0.35,0.6,0.28,0.72,0.42,0.82,0.3,0.55,0.22,0.67,0.4,0.76,0.25,0.5,0.2];
      peaks.slice(0, 64).forEach((peak) => {
        const bar = make("span", "review-waveform-bar");
        bar.style.height = `${Math.max(8, Math.min(100, Number(peak) * 100))}%`;
        waveform.append(bar);
      });
      audioCard.append(waveform, make("small", "", mix ? `${Number(mix.duration_seconds || 0).toFixed(2)}s · ${normalize(mix.alignment_source)} · QC ${normalize(mix.qc_status)}` : "Mix evidence pending"));
      (state.audio.paragraphs || []).forEach((paragraph) => {
        const selected = (state.audio.takes || []).find((take) => String(take.paragraph_id) === String(paragraph.id) && take.status === "selected");
        const row = make("div", "review-evidence-row");
        row.append(make("strong", "", `Paragraph ${paragraph.sequence}`), make("p", "", paragraph.source_text));
        if (selected) row.append(make("small", "", `Take v${selected.take_version} · QC ${selected.qc_status} · ${selected.timing_source}`));
        audioCard.append(row);
      });
      renderAudioActions(audioCard);
    }

    const visualCard = evidenceCard("Shots & retained candidates", state.visuals?.project?.status);
    if (!state.visuals) visualCard.append(make("p", "review-empty", "No visual project is available."));
    else {
      (state.visuals.shots || []).forEach((shot) => {
        const row = make("div", "review-shot-row");
        const title = make("div");
        title.append(make("strong", "", `Shot ${shot.sequence} · ${shot.scene_key}`), make("p", "", shot.visual_brief));
        row.append(title, badge(shot.status));
        const candidates = (state.visuals.candidates || []).filter((item) => String(item.visual_shot_version_id) === String(shot.current_version_id));
        const candidateList = make("div", "review-candidate-list");
        candidates.forEach((candidate) => {
          const candidateRow = make("div", "review-candidate-row");
          candidateRow.append(make("span", "", `Candidate ${candidate.ordinal} · seed ${candidate.seed} · checks ${candidate.checks_status}`), badge(candidate.status));
          if (hasRole("reviewer") && candidate.status === "generated" && candidate.checks_status === "pass") {
            candidateRow.append(action("Accept", () => decideCandidate(shot, candidate, "selected")));
          }
          if (hasRole("reviewer") && candidate.status === "generated") {
            candidateRow.append(action("Return", () => decideCandidate(shot, candidate, "rejected"), true));
          }
          candidateList.append(candidateRow);
        });
        row.append(candidateList);
        if (hasRole("reviewer") && shot.status === "candidates_ready") row.append(action("Request shot changes", () => returnShot(shot), true));
        visualCard.append(row);
      });
      renderVisualProjectActions(visualCard);
    }

    const renderCard = evidenceCard("Render placeholders");
    const jobs = state.workspace.render_jobs || [];
    if (!jobs.length) renderCard.append(make("p", "review-empty", "No preview, assembly, caption, thumbnail, or package job has been registered."));
    jobs.forEach((job) => {
      const row = make("div", "review-render-row");
      row.append(make("strong", "", normalize(job.job_type)), badge(job.status));
      row.append(make("small", "", `${job.provider || "local"}/${job.model_id || "default"} · ${formatDate(job.queued_at)}`));
      renderCard.append(row);
    });

    grid.append(scriptCard, audioCard, visualCard, renderCard);
    root.append(grid);
  }

  function renderScriptActions(card) {
    const documentRow = state.script.document;
    const actions = make("div", "review-actions");
    if (hasRole("reviewer") && documentRow.current_version_status === "in_review") {
      ["approved", "changes_requested", "rejected"].forEach((decision) => actions.append(action(normalize(decision), () => decideScript(decision), decision !== "approved")));
    }
    if (actions.childElementCount) card.append(actions);
  }

  function renderAudioActions(card) {
    const production = state.audio.production;
    const actions = make("div", "review-actions");
    if (hasRole("reviewer") && production.status === "in_review") {
      ["approved", "changes_requested", "rejected"].forEach((decision) => actions.append(action(normalize(decision), () => decideAudio(decision), decision !== "approved")));
    }
    if (actions.childElementCount) card.append(actions);
  }

  function renderVisualProjectActions(card) {
    const project = state.visuals.project;
    const actions = make("div", "review-actions");
    if (hasRole("reviewer") && project.status === "ready_for_review") {
      ["approved", "changes_requested", "rejected"].forEach((decision) => actions.append(action(normalize(decision), () => decideVisualProject(decision), decision !== "approved")));
    }
    if (actions.childElementCount) card.append(actions);
  }

  function targetOption(target) {
    const option = new Option(`${target.label} [${normalize(target.type)}]`, `${target.type}|${target.id}`);
    option.dataset.type = target.type;
    option.dataset.id = target.id;
    return option;
  }

  function populateTargetSelect(select, includeBlank = true) {
    const current = select.value;
    select.replaceChildren();
    if (includeBlank) select.append(new Option("Select exact version or item", ""));
    state.targets.forEach((target) => select.append(targetOption(target)));
    if ([...select.options].some((option) => option.value === current)) select.value = current;
  }

  function parseTarget(value) {
    if (!value || !value.includes("|")) return null;
    const [type, id] = value.split("|", 2);
    return { type, id };
  }

  function renderCompare() {
    const root = document.getElementById("review-tab-compare");
    root.replaceChildren();
    const controls = make("div", "review-compare-controls");
    const currentLabel = make("label");
    currentLabel.append(make("span", "", "Current exact version"));
    const current = make("select"); current.id = "review-compare-current"; populateTargetSelect(current);
    currentLabel.append(current);
    const previousLabel = make("label");
    previousLabel.append(make("span", "", "Optional previous version"));
    const previous = make("select"); previous.id = "review-compare-previous"; populateTargetSelect(previous);
    previousLabel.append(previous);
    controls.append(currentLabel, previousLabel, action("Compare versions", compareVersions));
    root.append(controls);
    const result = make("div", "review-compare-result"); result.id = "review-compare-result"; root.append(result);
    renderComparisonResult();
  }

  function renderComparisonResult() {
    const root = document.getElementById("review-compare-result");
    if (!root) return;
    root.replaceChildren();
    if (!state.comparison) {
      root.append(make("p", "review-empty", "Choose an exact version. Parent comparison is automatic when available."));
      return;
    }
    const columns = make("div", "review-compare-columns");
    columns.append(snapshotCard("Previous", state.comparison.previous), snapshotCard("Current", state.comparison.current));
    const changes = make("article", "review-difference-card");
    changes.append(make("h3", "", "Detected differences"));
    (state.comparison.differences || []).forEach((difference) => {
      const row = make("div", "review-difference-row");
      row.append(make("strong", "", normalize(difference.field)));
      if ("before_count" in difference) row.append(make("span", "", `${difference.before_count} → ${difference.after_count} items`));
      else row.append(make("span", "", `${summarize(difference.before)} → ${summarize(difference.after)}`));
      changes.append(row);
    });
    columns.append(changes);
    root.append(columns);
  }

  function snapshotCard(title, snapshot) {
    const card = make("article", "review-snapshot-card");
    card.append(make("h3", "", title));
    if (!snapshot) { card.append(make("p", "review-empty", "No parent version.")); return card; }
    ["version", "status", "decision", "word_count", "estimated_duration_seconds", "duration_seconds", "qc_status", "alignment_source", "compiled_prompt", "negative_prompt"].forEach((field) => {
      if (snapshot[field] === undefined || snapshot[field] === null) return;
      const row = make("div", "review-snapshot-row");
      row.append(make("strong", "", normalize(field)), make("span", "", summarize(snapshot[field])));
      card.append(row);
    });
    ["sections", "claims", "sources", "tracks", "takes", "candidates", "checks"].forEach((field) => {
      if (!Array.isArray(snapshot[field])) return;
      card.append(make("p", "", `${normalize(field)}: ${snapshot[field].length}`));
    });
    return card;
  }

  function summarize(value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "object") return Array.isArray(value) ? `${value.length} items` : "structured evidence";
    const text = String(value);
    return text.length > 180 ? `${text.slice(0, 177)}…` : text;
  }

  async function compareVersions() {
    const current = parseTarget(document.getElementById("review-compare-current").value);
    const previous = parseTarget(document.getElementById("review-compare-previous").value);
    if (!current) throw new Error("Select the current exact version.");
    if (previous && previous.type !== current.type) throw new Error("Previous and current items must use the same evidence type.");
    state.comparison = await window.PortfolioApi.compareReview({
      target_type: current.type,
      current_id: current.id,
      previous_id: previous?.id || null
    });
    renderComparisonResult();
    setStatus("Exact-version comparison loaded.");
  }

  function renderCommentsAndTasks() {
    const root = document.getElementById("review-tab-comments");
    root.replaceChildren();
    const columns = make("div", "review-comment-columns");
    columns.append(commentForm(), commentsCard(), tasksCard());
    root.append(columns);
  }

  function field(label, control) {
    const wrapper = make("label", "review-form-field");
    wrapper.append(make("span", "", label), control);
    return wrapper;
  }

  function commentForm() {
    const form = make("form", "review-comment-form");
    form.id = "review-comment-form";
    form.append(make("h3", "", "Comment on exact evidence"));
    const target = make("select"); target.id = "review-comment-target"; populateTargetSelect(target);
    const type = make("select"); type.id = "review-comment-type";
    ["general","change_request","factual","tone","timing","continuity","accessibility","rights"].forEach((value) => type.append(new Option(normalize(value), value)));
    const body = document.createElement("textarea"); body.id = "review-comment-body"; body.rows = 4; body.maxLength = 5000;
    form.append(field("Exact target", target), field("Comment type", type), field("Comment", body));

    const timeline = make("div", "review-timeline-fields"); timeline.id = "review-timeline-fields"; timeline.hidden = true;
    const start = document.createElement("input"); start.id = "review-timeline-start"; start.type = "number"; start.min = "0"; start.step = "1"; start.placeholder = "milliseconds";
    const end = document.createElement("input"); end.id = "review-timeline-end"; end.type = "number"; end.min = "1"; end.step = "1"; end.placeholder = "milliseconds";
    timeline.append(field("Start (ms)", start), field("End (ms)", end));
    form.append(timeline);

    const task = make("fieldset", "review-task-fields"); task.id = "review-task-fields"; task.hidden = true;
    task.append(make("legend", "", "Structured revision task"));
    const taskType = make("select"); taskType.id = "review-task-type";
    ["workflow_update","script_edit","factual_support","tone_edit","audio_retake","audio_mix","visual_prompt","visual_candidate","accessibility","rights","general"].forEach((value) => taskType.append(new Option(normalize(value), value)));
    const taskTitle = document.createElement("input"); taskTitle.id = "review-task-title"; taskTitle.maxLength = 300;
    const instructions = document.createElement("textarea"); instructions.id = "review-task-instructions"; instructions.rows = 3; instructions.maxLength = 5000;
    const assignee = document.createElement("input"); assignee.id = "review-task-assignee"; assignee.placeholder = "producer.one";
    const due = document.createElement("input"); due.id = "review-task-due"; due.type = "datetime-local";
    const priority = make("select"); priority.id = "review-task-priority"; ["low","normal","high","urgent"].forEach((value) => priority.append(new Option(value, value)));
    task.append(field("Task type", taskType), field("Title", taskTitle), field("Instructions", instructions), field("Assignee operator ID", assignee), field("Due", due), field("Priority", priority));
    const blocking = make("label", "review-check"); const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.id = "review-task-blocker"; checkbox.checked = true; blocking.append(checkbox, make("span", "", "Blocking revision")); task.append(blocking);
    form.append(task);
    form.append(action("Record comment", submitComment));
    type.addEventListener("change", toggleCommentFields);
    return form;
  }

  function toggleCommentFields() {
    const type = document.getElementById("review-comment-type")?.value;
    document.getElementById("review-timeline-fields").hidden = type !== "timing";
    document.getElementById("review-task-fields").hidden = type !== "change_request";
  }

  function commentsCard() {
    const card = make("article", "review-comments-card");
    card.append(make("h3", "", "Version-bound comments"));
    const comments = state.workspace?.comments || [];
    if (!comments.length) card.append(make("p", "review-empty", "No central comments recorded."));
    comments.forEach((comment) => {
      const row = make("div", `review-comment-row ${comment.blocking ? "blocker" : ""}`);
      const top = make("div", "review-comment-top");
      top.append(make("strong", "", `${comment.author_name} · ${normalize(comment.comment_type)}`), badge(comment.resolved_at ? "resolved" : "open"));
      row.append(top, make("p", "", comment.body), make("small", "", `${normalize(comment.target_type)} · ${formatDate(comment.created_at)}`));
      if (comment.timeline_start_ms !== null && comment.timeline_start_ms !== undefined) row.append(make("small", "", `Timeline ${comment.timeline_start_ms}–${comment.timeline_end_ms} ms`));
      if (!comment.resolved_at && hasRole("reviewer") && !comment.blocking) row.append(action("Resolve", () => resolveComment(comment.id), true));
      card.append(row);
    });
    return card;
  }

  function tasksCard() {
    const card = make("article", "review-tasks-card");
    card.append(make("h3", "", "Assigned revision tasks"));
    const tasks = state.workspace?.revision_tasks || [];
    if (!tasks.length) card.append(make("p", "review-empty", "No structured revisions assigned."));
    tasks.forEach((task) => {
      const row = make("div", `review-task-row ${task.blocker ? "blocker" : ""}`);
      const top = make("div", "review-task-top"); top.append(make("strong", "", task.title), badge(task.status));
      row.append(top, make("p", "", task.instructions), make("small", "", `${task.assignee_name} · ${normalize(task.priority)} · due ${formatDate(task.due_at)} · lock ${task.lock_version}`));
      const actions = make("div", "review-actions");
      const assignedProducer = hasRole("producer") && String(task.assignee_operator_id) === String(state.operatorId);
      if ((assignedProducer || hasRole("reviewer")) && task.status === "open") actions.append(action("Start", () => updateTask(task, { status: "in_progress" })));
      if ((assignedProducer || hasRole("reviewer")) && ["open","in_progress"].includes(task.status)) actions.append(action("Complete", () => updateTask(task, { status: "completed" })));
      if (hasRole("reviewer") && ["open","in_progress"].includes(task.status)) actions.append(action("Set urgent", () => updateTask(task, { priority: "urgent" }), true));
      if (actions.childElementCount) row.append(actions);
      card.append(row);
    });
    return card;
  }

  function renderDecisionHistory() {
    const root = document.getElementById("review-tab-history");
    root.replaceChildren();
    const history = state.workspace?.decision_history || {};
    const grid = make("div", "review-history-grid");
    [
      ["Workflow decisions", history.workflow || []],
      ["Script decisions", history.script || []],
      ["Audio decisions", history.audio || []],
      ["Visual project decisions", history.visual_project || []],
      ["Visual candidate decisions", history.visual_candidate || []]
    ].forEach(([title, rows]) => {
      const card = make("article", "review-history-card"); card.append(make("h3", "", title));
      if (!rows.length) card.append(make("p", "review-empty", "No decision evidence recorded."));
      rows.forEach((decision) => {
        const row = make("div", "review-history-row");
        row.append(badge(decision.decision), make("strong", "", decision.reviewer_name || decision.reviewer_operator_id));
        if (decision.rationale) row.append(make("p", "", decision.rationale));
        row.append(make("small", "", formatDate(decision.created_at)));
        card.append(row);
      });
      grid.append(card);
    });
    root.append(grid);
  }

  async function submitComment(event) {
    event?.preventDefault?.();
    const target = parseTarget(document.getElementById("review-comment-target").value);
    if (!target) throw new Error("Select the exact item receiving this comment.");
    const type = document.getElementById("review-comment-type").value;
    const body = document.getElementById("review-comment-body").value.trim();
    if (!body) throw new Error("Enter a comment.");
    const payload = { target_type: target.type, target_id: target.id, comment_type: type, body, blocking: false };
    if (type === "timing") {
      payload.timeline_start_ms = Number(document.getElementById("review-timeline-start").value);
      payload.timeline_end_ms = Number(document.getElementById("review-timeline-end").value);
    }
    if (type === "change_request") {
      const assignee = document.getElementById("review-task-assignee").value.trim();
      const title = document.getElementById("review-task-title").value.trim();
      const instructions = document.getElementById("review-task-instructions").value.trim();
      if (!assignee || !title || !instructions) throw new Error("Change requests require title, instructions, and an assignee operator ID.");
      const due = document.getElementById("review-task-due").value;
      payload.blocking = document.getElementById("review-task-blocker").checked;
      payload.revision_task = {
        task_type: document.getElementById("review-task-type").value,
        title,
        instructions,
        assignee_operator_id: assignee,
        due_at: due ? new Date(due).toISOString() : null,
        priority: document.getElementById("review-task-priority").value,
        blocker: payload.blocking
      };
    }
    await window.PortfolioApi.createReviewComment(payload);
    await Promise.all([loadWorkspace(), loadInbox()]);
    setStatus(type === "change_request" ? "Change request and assigned revision task recorded atomically." : "Exact-target comment recorded.");
  }

  async function resolveComment(commentId) {
    await window.PortfolioApi.resolveReviewComment(commentId);
    await loadWorkspace();
    setStatus("Comment resolved with retained evidence.");
  }

  async function updateTask(task, mutation) {
    await window.PortfolioApi.mutateRevisionTask(task.id, { expected_lock_version: task.lock_version, ...mutation });
    await Promise.all([loadWorkspace(), loadInbox()]);
    setStatus("Revision task updated with an immutable audit event.");
  }

  function rationale(label) {
    const value = window.prompt(label, "");
    if (value === null) return null;
    const text = value.trim();
    if (text.length < 3) throw new Error("A rationale of at least three characters is required.");
    return text;
  }

  async function decideScript(decision) {
    const note = rationale(`Rationale for script ${normalize(decision)}`); if (note === null) return;
    state.script = await window.PortfolioApi.decideScript(state.script.document.id, { expected_lock_version: state.script.document.lock_version, decision, rationale: note });
    await loadWorkspace();
  }

  async function decideAudio(decision) {
    const note = rationale(`Rationale for audio ${normalize(decision)}`); if (note === null) return;
    state.audio = await window.PortfolioApi.decideAudio(state.audio.production.id, { expected_lock_version: state.audio.production.lock_version, decision, rationale: note });
    await loadWorkspace();
  }

  async function decideVisualProject(decision) {
    const note = rationale(`Rationale for visual project ${normalize(decision)}`); if (note === null) return;
    state.visuals = await window.PortfolioApi.decideVisualProject(state.visuals.project.id, { expected_project_lock_version: state.visuals.project.lock_version, decision, rationale: note });
    await loadWorkspace();
  }

  async function decideCandidate(shot, candidate, decision) {
    const note = rationale(`Rationale for candidate ${normalize(decision)}`); if (note === null) return;
    state.visuals = await window.PortfolioApi.decideVisualCandidate(state.visuals.project.id, shot.id, shot.current_version_id, candidate.id, { expected_shot_lock_version: shot.lock_version, decision, rationale: note });
    await loadWorkspace();
  }

  async function returnShot(shot) {
    const note = rationale("What must change in this shot?"); if (note === null) return;
    state.visuals = await window.PortfolioApi.decideVisualShot(state.visuals.project.id, shot.id, shot.current_version_id, { expected_shot_lock_version: shot.lock_version, decision: "changes_requested", rationale: note });
    await loadWorkspace();
  }

  function activateTab(name) {
    document.querySelectorAll("[data-review-tab]").forEach((button) => button.setAttribute("aria-selected", String(button.dataset.reviewTab === name)));
    document.querySelectorAll(".review-tab-panel").forEach((panel) => { panel.hidden = panel.id !== `review-tab-${name}`; });
  }

  async function refreshAccess() {
    if (!window.PortfolioApi.configured()) return;
    const [access, brands] = await Promise.all([window.PortfolioApi.access(), window.PortfolioApi.brands()]);
    state.roles = access.roles || access.operator?.roles || [];
    state.operatorId = access.operator_id || access.operator?.operator_id || "";
    state.brands = brands.brands || brands.items || [];
    renderBrandOptions();
    await loadInbox();
  }

  async function start() {
    if (!window.PortfolioApi || document.getElementById("review-workspace-studio")) return;
    const root = document.getElementById("portfolio-studio");
    if (!root) return;
    const view = panel();
    root.prepend(view);
    stageOptions();
    document.getElementById("review-inbox-refresh").addEventListener("click", () => guarded(loadInbox));
    ["review-filter-brand","review-filter-stage","review-filter-status","review-filter-blocker","review-filter-overdue"].forEach((id) => document.getElementById(id).addEventListener("change", () => guarded(loadInbox)));
    document.getElementById("review-workspace-load").addEventListener("click", () => guarded(loadWorkspace));
    document.getElementById("review-comment-form")?.addEventListener("submit", (event) => guarded(() => submitComment(event)));
    document.querySelectorAll("[data-review-tab]").forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.reviewTab)));
    document.getElementById("connect-api")?.addEventListener("click", () => setTimeout(() => guarded(refreshAccess), 300));
    if (window.PortfolioApi.configured()) await refreshAccess();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => void start(), { once: true });
  else void start();
})();
