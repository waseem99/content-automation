(() => {
  const BASE_KEY = "content-automation.api-base";
  const TOKEN_KEY = "content-automation.operator-key";
  const scriptBase = document.currentScript?.src || window.location.href;

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
      const detail = payload.detail;
      const message = typeof detail === "object" && detail ? detail.code : detail;
      throw new Error(payload.error || message || `API request failed (${response.status})`);
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
    access: () => request("/access/me"),
    brands: () => request("/portfolio/brands"),
    approvedVoices: () => request("/portfolio/approved-voices"),
    brandProfiles: (brandId) => request(`/portfolio/brands/${brandId}/profiles`),
    createBrandProfile: (brandId, payload) => request(`/portfolio/brands/${brandId}/profiles`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    activateBrandProfile: (brandId, profileId) => request(`/portfolio/brands/${brandId}/profiles/${profileId}/activate`, {
      method: "POST"
    }),
    narrationSelection: (brandId, filters = {}) => {
      const query = new URLSearchParams();
      if (filters.language) query.set("language", filters.language);
      if (filters.formatName) query.set("format_name", filters.formatName);
      if (filters.topicType) query.set("topic_type", filters.topicType);
      return request(`/portfolio/brands/${brandId}/narration-selection${query.size ? `?${query}` : ""}`);
    },
    pinNarrationSelection: (contentId, presetId) => request(`/portfolio/content/${contentId}/narration-selection`, {
      method: "POST",
      body: JSON.stringify({ preset_id: presetId })
    }),
    readiness: (monthStart) => request(`/portfolio/readiness?month_start=${encodeURIComponent(monthStart)}`),
    queue: (filters = {}) => {
      const query = new URLSearchParams();
      if (filters.brandId) query.set("brand_id", filters.brandId);
      if (filters.stage) query.set("stage", filters.stage);
      return request(`/portfolio/queue${query.size ? `?${query}` : ""}`);
    },
    generationJobs: (filters = {}) => {
      const query = new URLSearchParams();
      if (filters.brandId) query.set("brand_id", filters.brandId);
      if (filters.status) query.append("status", filters.status);
      if (filters.jobType) query.append("job_type", filters.jobType);
      if (filters.workerId) query.set("worker_id", filters.workerId);
      if (filters.contentId) query.set("content_id", filters.contentId);
      if (filters.limit) query.set("limit", String(filters.limit));
      return request(`/generation/jobs${query.size ? `?${query}` : ""}`);
    },
    generationJob: (jobId) => request(`/generation/jobs/${jobId}`),
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
    }),
    audioForContent: (contentId) => request(`/audio/content/${contentId}`),
    initializeAudio: (contentId, modelId = "kokoro-v1.0") => request(`/audio/content/${contentId}`, {
      method: "POST",
      body: JSON.stringify({ model_id: modelId })
    }),
    regenerateAudioParagraph: (productionId, paragraphId, modelId) => request(`/audio/${productionId}/paragraphs/${paragraphId}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ model_id: modelId })
    }),
    visualsForContent: (contentId) => request(`/visuals/content/${contentId}`),
    initializeVisuals: (contentId, payload) => request(`/visuals/content/${contentId}`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    decideVisualCandidate: (projectId, shotId, versionId, candidateId, payload) => request(`/visuals/${projectId}/shots/${shotId}/versions/${versionId}/candidates/${candidateId}/decisions`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    decideVisualShot: (projectId, shotId, versionId, payload) => request(`/visuals/${projectId}/shots/${shotId}/versions/${versionId}/decisions`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    reviseVisualShot: (projectId, shotId, payload) => request(`/visuals/${projectId}/shots/${shotId}/revise`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    submitVisualProject: (projectId, payload) => request(`/visuals/${projectId}/submit`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    decideVisualProject: (projectId, payload) => request(`/visuals/${projectId}/decisions`, {
      method: "POST",
      body: JSON.stringify(payload)
    })
  };

  const modules = [
    ["brand-profile-admin", "brand-profile-admin.css", "brand-profile-admin.js"],
    ["generation-queue", "generation-queue.css", "generation-queue.js"],
    ["concept-slate", "concept-slate.css", "concept-slate.js"],
    ["script-review", "script-review.css", "script-review.js"],
    ["audio-review", "audio-review.css", "audio-review.js"],
    ["visual-candidates", "visual-candidates.css", "visual-candidates.js"]
  ];
  modules.forEach(([key, css, js]) => {
    if (!document.querySelector(`link[data-studio-module="${key}"]`)) {
      const style = document.createElement("link");
      style.rel = "stylesheet";
      style.href = new URL(css, scriptBase).href;
      style.dataset.studioModule = key;
      document.head.appendChild(style);
    }
    void import(new URL(js, scriptBase).href);
  });
})();
