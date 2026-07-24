(() => {
  let busy = false;
  let access = null;

  const humanize = (value) => String(value || "unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  const roles = () => access?.operator?.roles || [];
  const isAdmin = () => Boolean(access?.operator?.portfolio_wide) || roles().includes("admin");
  const canProduce = () => isAdmin() || roles().includes("producer");

  function toast(message, kind = "") {
    const target = document.getElementById("toast-region");
    if (!target) return;
    const node = document.createElement("div");
    node.className = `toast ${kind}`.trim();
    node.textContent = message;
    target.appendChild(node);
    window.setTimeout(() => node.remove(), 5000);
  }

  function errorText(error) {
    const detail = error?.payload?.detail;
    if (typeof detail === "string") return humanize(detail);
    if (detail && typeof detail === "object" && detail.code) return humanize(detail.code);
    return error?.message || "The action could not be completed.";
  }

  function contentIdFromPath() {
    const parts = window.location.pathname.split("/").filter(Boolean);
    return parts[0] === "app" && parts[1] === "content" && parts[2] ? parts[2] : null;
  }

  function refreshContent() {
    const button = document.getElementById("content-refresh");
    if (button) button.click();
    else window.location.reload();
  }

  async function withButton(button, callback) {
    const previous = button.innerHTML;
    button.disabled = true;
    button.innerHTML = "Working…";
    try { return await callback(); }
    catch (error) { toast(errorText(error), "bad"); throw error; }
    finally { button.disabled = false; button.innerHTML = previous; }
  }

  async function mediaUrl(jobId) {
    try { return await window.StudioApi.jobMediaUrl(jobId); }
    catch { return null; }
  }

  function currentMix(audio) {
    return (audio.mixes || []).find((item) => String(item.id) === String(audio.production?.current_mix_version_id)) || null;
  }

  async function selectTake(button, audio, take) {
    await withButton(button, async () => {
      await window.StudioApi.selectAudioTake(audio.production.id, take.id, audio.production.lock_version);
      toast("Narration take selected.", "good");
      refreshContent();
    });
  }

  async function regenerateParagraph(button, audio, paragraph) {
    await withButton(button, async () => {
      await window.StudioApi.regenerateAudioParagraph(audio.production.id, paragraph.id, {
        model_id: audio.production.model_id || "hexgrad/Kokoro-82M",
        preferred_worker_id: "local-producer",
        timeout_seconds: 900,
        max_attempts: 3
      });
      toast("A new local take was queued for this paragraph.", "good");
      refreshContent();
    });
  }

  async function buildMix(button, audio) {
    await withButton(button, async () => {
      await window.StudioApi.buildLocalAudioMix(audio.production.id, audio.production.lock_version);
      toast("Local narration mix built and quality evidence registered.", "good");
      refreshContent();
    });
  }

  async function enhanceAudio(contentId) {
    const target = document.getElementById("audio-review-area");
    if (!target || target.dataset.mediaEnhanced === "true") return;
    let audio;
    try { audio = await window.StudioApi.audioForContent(contentId); }
    catch { return; }
    const production = audio.production;
    if (!production) return;
    const paragraphs = audio.paragraphs || [];
    const takes = (audio.takes || []).filter((take) => take.generation_job_id && ["generated", "selected"].includes(take.status));
    const mix = currentMix(audio);
    const mixReady = Boolean(mix?.final_mix_asset_id);
    const selectedParagraphs = new Set((audio.takes || []).filter((take) => take.status === "selected").map((take) => String(take.paragraph_id)));
    const allSelected = paragraphs.length > 0 && paragraphs.every((paragraph) => selectedParagraphs.has(String(paragraph.id)));

    const prematureSubmit = document.getElementById("submit-audio");
    if (prematureSubmit && !mixReady) {
      prematureSubmit.disabled = true;
      prematureSubmit.title = "Build the narration mix before submitting it for review.";
      prematureSubmit.textContent = "Build mix before submission";
    }

    const heading = document.createElement("div");
    heading.className = `notice ${allSelected ? "good" : "warn"}`;
    heading.style.marginTop = "14px";
    heading.innerHTML = allSelected
      ? `<strong>All paragraph takes selected</strong>${mixReady ? "The narration mix is ready for review." : "Build one normalized local narration mix before submission."}`
      : `<strong>${selectedParagraphs.size}/${paragraphs.length} paragraph takes selected</strong>Listen to each take and select exactly one passing take per paragraph.`;
    target.appendChild(heading);

    const section = document.createElement("div");
    section.className = "media-grid";
    section.style.marginTop = "14px";
    for (const paragraph of paragraphs) {
      const paragraphTakes = takes.filter((take) => String(take.paragraph_id) === String(paragraph.id));
      const card = document.createElement("article");
      card.className = "media-card";
      const body = document.createElement("div");
      body.className = "media-card-body";
      body.innerHTML = `<h4>Paragraph ${escapeHtml(paragraph.sequence)}</h4><p>${escapeHtml(paragraph.source_text)}</p>`;
      if (!paragraphTakes.length) {
        body.innerHTML += '<div class="notice warn"><strong>Generating</strong>No reviewable take is available yet.</div>';
      }
      for (const take of paragraphTakes) {
        const takePanel = document.createElement("div");
        takePanel.className = "evidence-item";
        takePanel.style.marginTop = "10px";
        takePanel.innerHTML = `<div class="button-row between"><strong>Take ${escapeHtml(take.take_version)}</strong><span class="status-badge status-${escapeHtml(take.status)}">${escapeHtml(humanize(take.status))}</span></div><p>QC ${escapeHtml(humanize(take.qc_status))} · ${Number(take.duration_seconds || 0).toFixed(2)}s · ${escapeHtml(humanize(take.timing_source))}</p>`;
        const url = await mediaUrl(take.generation_job_id);
        if (url) {
          const player = document.createElement("audio");
          player.controls = true;
          player.preload = "metadata";
          player.src = url;
          takePanel.appendChild(player);
        }
        if (canProduce() && production.status === "working" && take.status === "generated" && take.qc_status === "pass") {
          const select = document.createElement("button");
          select.className = "secondary-button";
          select.type = "button";
          select.textContent = "Select this take";
          select.addEventListener("click", () => selectTake(select, audio, take));
          takePanel.appendChild(select);
        }
        body.appendChild(takePanel);
      }
      if (canProduce() && ["working", "changes_requested"].includes(production.status)) {
        const regenerate = document.createElement("button");
        regenerate.className = "ghost-button";
        regenerate.type = "button";
        regenerate.textContent = "Generate another take";
        regenerate.addEventListener("click", () => regenerateParagraph(regenerate, audio, paragraph));
        body.appendChild(regenerate);
      }
      card.appendChild(body);
      section.appendChild(card);
    }
    if (section.children.length) target.appendChild(section);

    const controls = document.createElement("div");
    controls.className = "rationale-panel";
    controls.style.marginTop = "14px";
    if (mixReady) {
      controls.innerHTML = '<strong>Normalized narration mix</strong><p>The selected takes were concatenated and normalized locally with FFmpeg at zero external cost.</p>';
      try {
        const mixUrl = await window.StudioApi.audioMixMediaUrl(production.id);
        const player = document.createElement("audio");
        player.controls = true;
        player.preload = "metadata";
        player.src = mixUrl;
        controls.appendChild(player);
      } catch (error) {
        controls.innerHTML += `<div class="notice bad">${escapeHtml(errorText(error))}</div>`;
      }
    } else if (canProduce() && allSelected && production.status === "working") {
      controls.innerHTML = '<strong>Ready to build</strong><p>This creates one local narration mix, records loudness and timing evidence, and unlocks submission.</p>';
      const build = document.createElement("button");
      build.className = "primary-button";
      build.type = "button";
      build.textContent = "Build narration mix";
      build.addEventListener("click", () => buildMix(build, audio));
      controls.appendChild(build);
    } else if (!mixReady) {
      controls.innerHTML = '<strong>Mix blocked</strong><p>Select one QC-passing take for every paragraph first.</p>';
    }
    target.appendChild(controls);
    target.dataset.mediaEnhanced = "true";
  }

  async function enhanceVisuals(contentId) {
    const target = document.getElementById("visual-review-area");
    if (!target || target.dataset.mediaEnhanced === "true") return;
    let visual;
    try { visual = await window.StudioApi.visualsForContent(contentId); }
    catch { return; }
    const candidates = (visual.candidates || []).filter((candidate) => candidate.generation_job_id && ["generated", "selected"].includes(candidate.status));
    if (!candidates.length) return;
    const section = document.createElement("div");
    section.className = "media-grid";
    section.style.marginTop = "14px";
    for (const candidate of candidates) {
      const url = await mediaUrl(candidate.generation_job_id);
      if (!url) continue;
      const version = (visual.versions || []).find((item) => String(item.id) === String(candidate.visual_shot_version_id));
      const shot = (visual.shots || []).find((item) => String(item.id) === String(version?.visual_shot_id));
      const card = document.createElement("article");
      card.className = "media-card";
      card.innerHTML = `<div class="media-preview"><img alt="Generated candidate for scene ${escapeHtml(shot?.sequence || "")}"></div><div class="media-card-body"><h4>Scene ${escapeHtml(shot?.sequence || "")} · Candidate ${escapeHtml(candidate.ordinal || "")}</h4><p>${candidate.status === "selected" ? "Selected candidate" : "Awaiting selection"}</p></div>`;
      card.querySelector("img").src = url;
      section.appendChild(card);
    }
    if (section.children.length) target.appendChild(section);
    target.dataset.mediaEnhanced = "true";
  }

  async function enhance() {
    if (busy || !window.StudioApi?.configured()) return;
    const contentId = contentIdFromPath();
    if (!contentId) return;
    const audioTarget = document.getElementById("audio-review-area");
    const visualTarget = document.getElementById("visual-review-area");
    if (!audioTarget && !visualTarget) return;
    busy = true;
    try {
      if (!access) access = await window.StudioApi.access();
      await Promise.all([enhanceAudio(contentId), enhanceVisuals(contentId)]);
    } finally { busy = false; }
  }

  const observer = new MutationObserver(() => window.setTimeout(enhance, 50));
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", () => window.setTimeout(enhance, 100));
  document.addEventListener("DOMContentLoaded", () => window.setTimeout(enhance, 200), { once: true });
})();
