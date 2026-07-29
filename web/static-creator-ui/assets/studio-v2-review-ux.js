(() => {
  const DRAFT_PREFIX = "studio-v2.script-rationale.";
  const $ = (selector, root = document) => root.querySelector(selector);
  const humanize = (value) => String(value || "unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

  function contentIdFromPath() {
    const match = window.location.pathname.match(/^\/app\/content\/([^/]+)/);
    return match ? match[1] : "";
  }

  function draftKey(contentId) {
    return `${DRAFT_PREFIX}${contentId}`;
  }

  function toast(message, kind = "") {
    const target = $("#toast-region");
    if (!target) return;
    const node = document.createElement("div");
    node.className = `toast ${kind}`.trim();
    node.textContent = message;
    target.appendChild(node);
    window.setTimeout(() => node.remove(), 6000);
  }

  function errorText(error) {
    const detail = error?.payload?.detail;
    if (detail && typeof detail === "object") {
      if (Array.isArray(detail.blockers) && detail.blockers.length) {
        return detail.blockers.map((item) => item.message || humanize(item.code)).join(" ");
      }
      if (detail.message) return detail.message;
      if (detail.code) return humanize(detail.code);
    }
    return error?.message || "The decision could not be saved.";
  }

  function normalizedRationale(decision, rawValue) {
    const value = String(rawValue || "").trim();
    if (value.length >= 3) return value;
    if (value) return `${value}.`;
    return {
      approved: "Approved",
      changes_requested: "Changes requested",
      rejected: "Rejected"
    }[decision] || "Decision recorded";
  }

  function enhanceRationale() {
    const textarea = $("#script-rationale");
    const contentId = contentIdFromPath();
    if (!textarea || !contentId || textarea.dataset.optionalReviewEnhanced === "true") return;

    textarea.dataset.optionalReviewEnhanced = "true";
    textarea.placeholder = "Optional note — a single word is enough.";
    const label = textarea.closest("label");
    if (label) {
      const textNode = [...label.childNodes].find((node) => node.nodeType === Node.TEXT_NODE);
      if (textNode) textNode.textContent = "Decision note (optional)";
    }

    const stored = sessionStorage.getItem(draftKey(contentId));
    if (stored !== null) textarea.value = stored;
    textarea.addEventListener("input", () => {
      sessionStorage.setItem(draftKey(contentId), textarea.value);
    });
  }

  async function handleDecision(event) {
    const button = event.target.closest("[data-script-decision]");
    const textarea = $("#script-rationale");
    const contentId = contentIdFromPath();
    if (!button || !textarea || !contentId || !window.StudioApi?.configured()) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const original = button.innerHTML;
    const decision = button.dataset.scriptDecision;
    button.disabled = true;
    button.innerHTML = "Working…";
    try {
      const script = await window.StudioApi.scriptForContent(contentId);
      const documentRecord = script.document;
      if (!documentRecord?.id) throw new Error("The current script version could not be resolved.");
      const rationale = normalizedRationale(decision, textarea.value);
      await window.StudioApi.decideScript(
        documentRecord.id,
        Number(documentRecord.lock_version || 0),
        decision,
        rationale
      );
      sessionStorage.removeItem(draftKey(contentId));
      toast(`Script ${humanize(decision).toLowerCase()}.`, "good");
      window.setTimeout(() => window.location.reload(), 250);
    } catch (error) {
      toast(errorText(error), "bad");
      button.disabled = false;
      button.innerHTML = original;
    }
  }

  document.addEventListener("click", handleDecision, true);
  const observer = new MutationObserver(() => window.setTimeout(enhanceRationale, 0));
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", () => window.setTimeout(enhanceRationale, 0));
  window.setTimeout(enhanceRationale, 0);
})();
