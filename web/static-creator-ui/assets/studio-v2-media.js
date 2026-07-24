(() => {
  let busy = false;

  function contentIdFromPath() {
    const parts = window.location.pathname.split("/").filter(Boolean);
    return parts[0] === "app" && parts[1] === "content" && parts[2] ? parts[2] : null;
  }

  async function mediaUrl(jobId) {
    try { return await window.StudioApi.jobMediaUrl(jobId); }
    catch { return null; }
  }

  async function enhanceAudio(contentId) {
    const target = document.getElementById("audio-review-area");
    if (!target || target.dataset.mediaEnhanced === "true") return;
    let audio;
    try { audio = await window.StudioApi.audioForContent(contentId); }
    catch { return; }
    const takes = (audio.takes || []).filter((take) => take.generation_job_id && ["generated", "selected"].includes(take.status));
    if (!takes.length) return;
    const section = document.createElement("div");
    section.className = "media-grid";
    section.style.marginTop = "14px";
    for (const take of takes) {
      const url = await mediaUrl(take.generation_job_id);
      if (!url) continue;
      const paragraph = (audio.paragraphs || []).find((item) => String(item.id) === String(take.paragraph_id));
      const card = document.createElement("article");
      card.className = "media-card";
      card.innerHTML = `<div class="media-card-body"><h4>Paragraph ${paragraph?.sequence || ""} · Take ${take.take_version || ""}</h4><p>${paragraph?.source_text || "Generated local narration"}</p></div>`;
      const player = document.createElement("audio");
      player.controls = true;
      player.preload = "metadata";
      player.src = url;
      card.querySelector(".media-card-body").appendChild(player);
      section.appendChild(card);
    }
    if (section.children.length) target.appendChild(section);
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
      card.innerHTML = `<div class="media-preview"><img alt="Generated candidate for scene ${shot?.sequence || ""}"></div><div class="media-card-body"><h4>Scene ${shot?.sequence || ""} · Candidate ${candidate.ordinal || ""}</h4><p>${candidate.status === "selected" ? "Selected candidate" : "Awaiting selection"}</p></div>`;
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
    try { await Promise.all([enhanceAudio(contentId), enhanceVisuals(contentId)]); }
    finally { busy = false; }
  }

  const observer = new MutationObserver(() => window.setTimeout(enhance, 50));
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", () => window.setTimeout(enhance, 100));
  document.addEventListener("DOMContentLoaded", () => window.setTimeout(enhance, 200), { once: true });
})();
