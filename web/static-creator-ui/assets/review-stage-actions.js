(() => {
  const REVIEW_STAGES = new Set([
    "concept_review",
    "script_review",
    "narration_review",
    "storyboard_review",
    "local_preview_review",
    "spend_approval",
    "final_review",
    "package_approval"
  ]);
  const EXCLUDED_STAGES = new Set(["publication", "published"]);
  let roles = [];
  let currentWorkflow = null;
  let refreshing = false;

  const make = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const canReview = () => roles.includes("admin") || roles.includes("reviewer");
  const contentId = () => document.getElementById("review-workspace-content")?.value.trim() || "";
  const status = (message) => {
    const node = document.getElementById("review-workspace-status");
    if (node) node.textContent = message;
  };

  function ensurePanel() {
    const summary = document.getElementById("review-workspace-summary");
    if (!summary) return null;
    let panel = document.getElementById("review-stage-actions");
    if (!panel) {
      panel = make("section", "review-stage-actions");
      panel.id = "review-stage-actions";
      panel.setAttribute("aria-label", "Canonical workflow stage decision");
      summary.insertAdjacentElement("afterend", panel);
    }
    return panel;
  }

  function render() {
    const panel = ensurePanel();
    if (!panel) return;
    panel.replaceChildren();
    const workflow = currentWorkflow;
    const stage = String(workflow?.current_stage || "");
    const reviewable = workflow
      && workflow.current_version_status === "in_review"
      && REVIEW_STAGES.has(stage)
      && !EXCLUDED_STAGES.has(stage)
      && canReview();
    if (!reviewable) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    const copy = make("div");
    copy.append(
      make("strong", "", `Canonical stage decision · ${stage.replaceAll("_", " ")}`),
      make("p", "", "This uses the existing P86 workflow decision and advances or returns the exact workflow version. Publication is intentionally unavailable here.")
    );
    const actions = make("div", "review-stage-action-buttons");
    [
      ["Approve stage", "approved", false],
      ["Request stage changes", "changes_requested", true],
      ["Reject stage", "rejected", true]
    ].forEach(([label, decision, secondary]) => {
      const button = make("button", secondary ? "secondary" : "", label);
      button.type = "button";
      button.addEventListener("click", () => void decide(decision));
      actions.append(button);
    });
    panel.append(copy, actions);
  }

  async function refresh() {
    if (refreshing || !window.PortfolioApi?.configured() || !contentId()) return;
    refreshing = true;
    try {
      const [access, workspace] = await Promise.all([
        window.PortfolioApi.access(),
        window.PortfolioApi.reviewWorkspace(contentId())
      ]);
      roles = access.roles || access.operator?.roles || [];
      currentWorkflow = workspace.workflow || null;
      render();
    } catch (_) {
      currentWorkflow = null;
      render();
    } finally {
      refreshing = false;
    }
  }

  async function decide(decision) {
    if (!currentWorkflow || EXCLUDED_STAGES.has(String(currentWorkflow.current_stage))) return;
    const value = window.prompt(`Rationale for ${decision.replaceAll("_", " ")}`, "");
    if (value === null) return;
    const rationale = value.trim();
    if (rationale.length < 3) {
      status("A rationale of at least three characters is required.");
      return;
    }
    try {
      await window.PortfolioApi.decideWorkflowStage(currentWorkflow.id, {
        expected_lock_version: currentWorkflow.lock_version,
        decision,
        rationale
      });
      status(`Workflow stage ${decision.replaceAll("_", " ")} through the canonical P86 gate.`);
      document.getElementById("review-workspace-load")?.click();
      await refresh();
    } catch (error) {
      status(error.message);
    }
  }

  async function start() {
    const workspace = document.getElementById("review-workspace-studio");
    if (!workspace || document.getElementById("review-stage-actions")) return;
    ensurePanel();
    const summary = document.getElementById("review-workspace-summary");
    new MutationObserver(() => void refresh()).observe(summary, { childList: true });
    document.getElementById("review-workspace-load")?.addEventListener("click", () => setTimeout(() => void refresh(), 250));
    document.getElementById("connect-api")?.addEventListener("click", () => setTimeout(() => void refresh(), 400));
    await refresh();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => void start(), { once: true });
  } else {
    void start();
  }
})();
