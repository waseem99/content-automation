(() => {
  function enhanceSuperAdminReviewNotice() {
    const session = document.querySelector("#session-card");
    if (!session || !/super admin/i.test(session.textContent || "")) return;
    const notices = [...document.querySelectorAll(".notice")];
    const notice = notices.find((item) => /same-session admin review/i.test(item.textContent || ""));
    if (!notice || notice.querySelector("[data-p111-super-admin-override]")) return;
    const message = document.createElement("p");
    message.dataset.p111SuperAdminOverride = "true";
    message.style.margin = "8px 0 0";
    message.textContent = "One-click approval is enabled. Any remaining unsupported factual claims will be accepted as an explicit Super Admin override and preserved in the audit history.";
    notice.appendChild(message);
  }

  const observer = new MutationObserver(() => {
    window.setTimeout(enhanceSuperAdminReviewNotice, 50);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", () => window.setTimeout(enhanceSuperAdminReviewNotice, 100));
  document.addEventListener("click", () => window.setTimeout(enhanceSuperAdminReviewNotice, 100), true);
  window.setTimeout(enhanceSuperAdminReviewNotice, 100);
})();
