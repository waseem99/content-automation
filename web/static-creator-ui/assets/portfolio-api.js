(() => {
  const BASE_KEY = "content-automation.api-base";
  const TOKEN_KEY = "content-automation.operator-key";

  function normalizedBase(value) {
    return String(value || "").trim().replace(/\/+$/, "");
  }

  function initialBase() {
    const configured = document.querySelector('meta[name="content-api-base"]')?.content;
    return normalizedBase(sessionStorage.getItem(BASE_KEY) || configured);
  }

  let base = initialBase();
  let operatorKey = sessionStorage.getItem(TOKEN_KEY) || "";

  async function request(path, options = {}) {
    if (!base || !operatorKey) throw new Error("Portfolio API is not connected.");
    const response = await fetch(`${base}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Operator-Key": operatorKey,
        ...(options.headers || {})
      }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || payload.detail || `API request failed (${response.status})`);
    }
    return payload;
  }

  window.PortfolioApi = {
    configured: () => Boolean(base && operatorKey),
    configuration: () => ({ base, hasOperatorKey: Boolean(operatorKey) }),
    connect(nextBase, nextKey) {
      base = normalizedBase(nextBase);
      operatorKey = String(nextKey || "").trim();
      if (!base || !operatorKey) throw new Error("Both API URL and operator key are required.");
      sessionStorage.setItem(BASE_KEY, base);
      sessionStorage.setItem(TOKEN_KEY, operatorKey);
    },
    disconnect() {
      base = "";
      operatorKey = "";
      sessionStorage.removeItem(BASE_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    },
    health: () => request("/health"),
    brands: () => request("/portfolio/brands"),
    readiness: (monthStart) => request(`/portfolio/readiness?month_start=${encodeURIComponent(monthStart)}`),
    queue: (filters = {}) => {
      const query = new URLSearchParams();
      if (filters.brandId) query.set("brand_id", filters.brandId);
      if (filters.stage) query.set("stage", filters.stage);
      return request(`/portfolio/queue${query.size ? `?${query}` : ""}`);
    },
    approve: (contentId, gate, decision, rationale) => request(`/portfolio/content/${contentId}/approvals`, {
      method: "POST",
      body: JSON.stringify({ gate, decision, rationale })
    })
  };
})();
