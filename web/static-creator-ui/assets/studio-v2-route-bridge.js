(() => {
  const campaignsRoot = "/app/campaigns";
  let queued = false;
  let lastRecoveryAt = 0;

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

  function reconcileCampaignRoute() {
    if (!onCampaignRoute() || campaignViewReady() || queued) return;
    const shell = $("#studio-shell");
    const link = $("#campaigns-nav-link") || $('#primary-nav a[href="/app/campaigns"]');
    if (!shell || shell.hidden || !link) return;

    const now = Date.now();
    if (now - lastRecoveryAt < 100) return;
    lastRecoveryAt = now;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (onCampaignRoute() && !campaignViewReady()) link.click();
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
