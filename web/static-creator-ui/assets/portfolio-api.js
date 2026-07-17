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

  function initialKey() {
    const configured = document.querySelector('meta[name="content-operator-key"]')?.content;
    return String(sessionStorage.getItem(TOKEN_KEY) || configured || "").trim();
  }

  let base = initialBase();
  let operatorKey = initialKey();

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
    content: (contentId) => request(`/portfolio/content/${contentId}`),
    updateWorkspace: (contentId, payload) => request(`/portfolio/content/${contentId}/workspace`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    registerArtifact: (contentId, payload) => request(`/portfolio/content/${contentId}/artifacts`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    mediaUrl: (contentId, artifactId) => `${base}/portfolio/content/${contentId}/artifacts/${artifactId}/media`,
    mediaHeaders: () => ({ "X-Operator-Key": operatorKey }),
    references: (filters = {}) => {
      const query = new URLSearchParams();
      if (filters.brandId) query.set("brand_id", filters.brandId);
      if (filters.platform) query.set("platform", filters.platform);
      if (filters.status) query.set("status", filters.status);
      return request(`/portfolio/references${query.size ? `?${query}` : ""}`);
    },
    reference: (referenceId) => request(`/portfolio/references/${referenceId}`),
    enqueueReference: (payload) => request("/portfolio/references", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    recordReferenceProgress: (jobId, payload) => request(`/portfolio/reference-jobs/${jobId}/progress`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    registerReferenceArtifact: (referenceId, payload) => request(`/portfolio/references/${referenceId}/artifacts`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    assignReferenceBrand: (referenceId, brandId, rationale) => request(`/portfolio/references/${referenceId}/brands`, {
      method: "POST",
      body: JSON.stringify({ brand_id: brandId, rationale })
    }),
    decideReferenceGate: (referenceId, gate, decision, rationale, evidenceDigest) => request(`/portfolio/references/${referenceId}/approvals`, {
      method: "POST",
      body: JSON.stringify({ gate, decision, rationale, evidence_digest: evidenceDigest })
    }),
    linkReferenceIdea: (referenceId, payload) => request(`/portfolio/references/${referenceId}/ideas`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    approve: (contentId, gate, decision, rationale) => request(`/portfolio/content/${contentId}/approvals`, {
      method: "POST",
      body: JSON.stringify({ gate, decision, rationale })
    })
  };
})();
