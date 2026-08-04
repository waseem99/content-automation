(() => {
  const campaignsRoot = "/app/campaigns";
  let queued = false;
  let lastRecoveryAt = 0;
  let recoveryAttempts = 0;

  const $ = (selector) => document.querySelector(selector);

  function onCampaignRoute() {
    return window.location.pathname === campaignsRoot || window.location.pathname.startsWith(`${campaignsRoot}/`);
  }

  function campaignViewReady() {
    const title = $("#page-title")?.textContent?.trim() || "";
    const view = $("#app-view");
    if (!view) return false;
    if (title === "Page not found") return false;
    return view.dataset.campaignReady === "true"
      || /Production campaigns|Unable to load campaigns|Automatic pre-generation control center/i.test(view.textContent || "");
  }

  function requestCampaignRender() {
    // The campaign module already owns the popstate extension route. Replaying
    // that event asks it to render the current pathname without navigating back
    // to /app/campaigns and losing a campaign-detail deep link.
    window.dispatchEvent(new PopStateEvent("popstate", { state: history.state }));
  }

  function reconcileCampaignRoute() {
    if (!onCampaignRoute()) {
      recoveryAttempts = 0;
      return;
    }
    if (campaignViewReady()) {
      recoveryAttempts = 0;
      return;
    }
    if (queued || recoveryAttempts >= 40) return;
    const shell = $("#studio-shell");
    if (!shell || shell.hidden) return;

    const now = Date.now();
    if (now - lastRecoveryAt < 100) return;
    lastRecoveryAt = now;
    recoveryAttempts += 1;
    queued = true;
    queueMicrotask(() => {
      if (onCampaignRoute() && !campaignViewReady()) requestCampaignRender();
      queued = false;
      if (onCampaignRoute() && !campaignViewReady()) {
        window.setTimeout(reconcileCampaignRoute, 125);
      }
    });
  }

  const observer = new MutationObserver(reconcileCampaignRoute);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["hidden"]
  });

  window.addEventListener("DOMContentLoaded", reconcileCampaignRoute);
  window.addEventListener("popstate", reconcileCampaignRoute);
})();
