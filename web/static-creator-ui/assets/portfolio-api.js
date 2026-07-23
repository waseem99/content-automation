(() => {
  const BASE_KEY = "content-automation.api-base";
  const TOKEN_KEY = "content-automation.operator-key";
  const PILOT_KEY = "content-automation.p100-pilot-id";
  const scriptBase = document.currentScript?.src || window.location.href;

  function normalizedBase(value) {
    return String(value || "").trim().replace(/\/+$/, "");
  }

  function sameOriginDefault() {
    const mode = document.querySelector('meta[name="content-api-mode"]')?.content;
    return mode === "same-origin" ? window.location.origin : "";
  }

  let base = normalizedBase(
    sessionStorage.getItem(BASE_KEY) ||
    document.querySelector('meta[name="content-api-base"]')?.content ||
    sameOriginDefault()
  );
  let operatorKey = String(
    sessionStorage.getItem(TOKEN_KEY) ||
    document.querySelector('meta[name="content-operator-key"]')?.content ||
    ""
  ).trim();

  async function request(path, options = {}) {
    if (!base) throw new Error("Creator Studio API origin is not configured.");
    if (!operatorKey && options.auth !== false) throw new Error("Operator key is required.");
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (operatorKey && options.auth !== false) headers["X-Operator-Key"] = operatorKey;
    const response = await fetch(`${base}${path}`, { ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      const detail = payload.detail;
      const code = typeof detail === "object" && detail ? detail.code : detail;
      const error = new Error(payload.error || code || `API request failed (${response.status})`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function appendMany(query, name, values) {
    (values || []).filter(Boolean).forEach((value) => query.append(name, String(value)));
  }

  const api = {
    configured: () => Boolean(base && operatorKey),
    configuration: () => ({ base, hasOperatorKey: Boolean(operatorKey), sameOrigin: base === window.location.origin }),
    connect(nextBase, nextKey) {
      base = normalizedBase(nextBase || sameOriginDefault() || window.location.origin);
      operatorKey = String(nextKey || "").trim();
      if (!base || !operatorKey) throw new Error("Operator key is required.");
      sessionStorage.setItem(BASE_KEY, base);
      sessionStorage.setItem(TOKEN_KEY, operatorKey);
    },
    disconnect() {
      operatorKey = "";
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(PILOT_KEY);
      if (document.querySelector('meta[name="content-api-mode"]')?.content !== "same-origin") {
        base = "";
        sessionStorage.removeItem(BASE_KEY);
      }
    },
    savedPilotId: () => sessionStorage.getItem(PILOT_KEY),
    savePilotId: (pilotId) => pilotId ? sessionStorage.setItem(PILOT_KEY, pilotId) : sessionStorage.removeItem(PILOT_KEY),
    health: () => request("/health", { auth: false }),
    runtimeReady: () => request("/runtime/ready", { auth: false }),
    runtimeConfig: () => request("/runtime/config", { auth: false }),
    runtimeObservability: () => request("/runtime/observability", { auth: false }),
    studioStatus: () => request("/studio/status", { auth: false }),
    access: () => request("/access/me"),
    brands: () => request("/portfolio/brands"),
    approvedVoices: () => request("/portfolio/approved-voices"),
    brandProfiles: (brandId) => request(`/portfolio/brands/${brandId}/profiles`),
    createBrandProfile: (brandId, payload) => request(`/portfolio/brands/${brandId}/profiles`, { method: "POST", body: JSON.stringify(payload) }),
    activateBrandProfile: (brandId, profileId) => request(`/portfolio/brands/${brandId}/profiles/${profileId}/activate`, { method: "POST" }),
    narrationSelection: (brandId, filters = {}) => {
      const query = new URLSearchParams();
      if (filters.language) query.set("language", filters.language);
      if (filters.formatName) query.set("format_name", filters.formatName);
      if (filters.topicType) query.set("topic_type", filters.topicType);
      return request(`/portfolio/brands/${brandId}/narration-selection${query.size ? `?${query}` : ""}`);
    },
    pinNarrationSelection: (contentId, presetId) => request(`/portfolio/content/${contentId}/narration-selection`, { method: "POST", body: JSON.stringify({ preset_id: presetId }) }),
    readiness: (monthStart) => request(`/portfolio/readiness?month_start=${encodeURIComponent(monthStart)}`),
    queue: (filters = {}) => {
      const query = new URLSearchParams();
      if (filters.brandId) query.set("brand_id", filters.brandId);
      if (filters.stage) query.set("stage", filters.stage);
      return request(`/portfolio/queue${query.size ? `?${query}` : ""}`);
    },
    content: (contentId) => request(`/portfolio/content/${contentId}`),
    updateWorkspace: (contentId, payload) => request(`/portfolio/content/${contentId}/workspace`, { method: "POST", body: JSON.stringify(payload) }),
    registerArtifact: (contentId, payload) => request(`/portfolio/content/${contentId}/artifacts`, { method: "POST", body: JSON.stringify(payload) }),
    mediaUrl: (contentId, artifactId) => `${base}/portfolio/content/${contentId}/artifacts/${artifactId}/media`,
    mediaHeaders: () => ({ "X-Operator-Key": operatorKey }),
    generationJobs: (filters = {}) => {
      const query = new URLSearchParams();
      if (filters.brandId) query.set("brand_id", filters.brandId);
      appendMany(query, "status", Array.isArray(filters.status) ? filters.status : [filters.status]);
      appendMany(query, "job_type", Array.isArray(filters.jobType) ? filters.jobType : [filters.jobType]);
      if (filters.workerId) query.set("worker_id", filters.workerId);
      if (filters.contentId) query.set("content_id", filters.contentId);
      if (filters.limit) query.set("limit", String(filters.limit));
      return request(`/generation/jobs${query.size ? `?${query}` : ""}`);
    },
    generationJob: (jobId) => request(`/generation/jobs/${jobId}`),
    references: (filters = {}) => {
      const query = new URLSearchParams();
      if (filters.brandId) query.set("brand_id", filters.brandId);
      if (filters.platform) query.set("platform", filters.platform);
      if (filters.status) query.set("status", filters.status);
      return request(`/portfolio/references${query.size ? `?${query}` : ""}`);
    },
    reference: (referenceId) => request(`/portfolio/references/${referenceId}`),
    approve: (contentId, gate, decision, rationale) => request(`/portfolio/content/${contentId}/approvals`, { method: "POST", body: JSON.stringify({ gate, decision, rationale }) }),
    ensureWorkflow: (contentId) => request(`/production/content/${contentId}/workflow`, { method: "POST" }),
    workflowForContent: (contentId) => request(`/production/content/${contentId}/workflow`),
    decideWorkflowStage: (workflowId, payload) => request(`/production/workflows/${workflowId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    scriptForContent: (contentId) => request(`/scripts/content/${contentId}`),
    initializeScript: (contentId, payload) => request(`/scripts/content/${contentId}`, { method: "POST", body: JSON.stringify(payload) }),
    submitScript: (documentId, payload) => request(`/scripts/${documentId}/submit`, { method: "POST", body: JSON.stringify(payload) }),
    decideScript: (documentId, payload) => request(`/scripts/${documentId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    reviseScript: (documentId, payload) => request(`/scripts/${documentId}/revise`, { method: "POST", body: JSON.stringify(payload) }),
    audioForContent: (contentId) => request(`/audio/content/${contentId}`),
    initializeAudio: (contentId, modelId = "kokoro-v1.0") => request(`/audio/content/${contentId}`, { method: "POST", body: JSON.stringify({ model_id: modelId }) }),
    regenerateAudioParagraph: (productionId, paragraphId, modelId) => request(`/audio/${productionId}/paragraphs/${paragraphId}/regenerate`, { method: "POST", body: JSON.stringify({ model_id: modelId }) }),
    decideAudio: (productionId, payload) => request(`/audio/${productionId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    visualsForContent: (contentId) => request(`/visuals/content/${contentId}`),
    initializeVisuals: (contentId, payload) => request(`/visuals/content/${contentId}`, { method: "POST", body: JSON.stringify(payload) }),
    decideVisualCandidate: (projectId, shotId, versionId, candidateId, payload) => request(`/visuals/${projectId}/shots/${shotId}/versions/${versionId}/candidates/${candidateId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    decideVisualShot: (projectId, shotId, versionId, payload) => request(`/visuals/${projectId}/shots/${shotId}/versions/${versionId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    reviseVisualShot: (projectId, shotId, payload) => request(`/visuals/${projectId}/shots/${shotId}/revise`, { method: "POST", body: JSON.stringify(payload) }),
    submitVisualProject: (projectId, payload) => request(`/visuals/${projectId}/submit`, { method: "POST", body: JSON.stringify(payload) }),
    decideVisualProject: (projectId, payload) => request(`/visuals/${projectId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    reviewInbox: (filters = {}) => {
      const query = new URLSearchParams();
      appendMany(query, "brand_id", filters.brandIds);
      appendMany(query, "stage", filters.stages);
      appendMany(query, "status", filters.statuses);
      appendMany(query, "item_type", filters.itemTypes);
      if (filters.assigneeOperatorId) query.set("assignee_operator_id", filters.assigneeOperatorId);
      if (filters.dueFrom) query.set("due_from", filters.dueFrom);
      if (filters.dueTo) query.set("due_to", filters.dueTo);
      if (filters.blocker !== undefined && filters.blocker !== null) query.set("blocker", String(filters.blocker));
      if (filters.overdue !== undefined && filters.overdue !== null) query.set("overdue", String(filters.overdue));
      if (filters.limit) query.set("limit", String(filters.limit));
      return request(`/review/inbox${query.size ? `?${query}` : ""}`);
    },
    reviewWorkspace: (contentId) => request(`/review/content/${contentId}`),
    compareReview: (payload) => request("/review/compare", { method: "POST", body: JSON.stringify(payload) }),
    createReviewComment: (payload) => request("/review/comments", { method: "POST", body: JSON.stringify(payload) }),
    resolveReviewComment: (commentId) => request(`/review/comments/${commentId}/resolve`, { method: "POST" }),
    mutateRevisionTask: (taskId, payload) => request(`/review/tasks/${taskId}`, { method: "POST", body: JSON.stringify(payload) }),
    currentRouting: (contentId) => request(`/routing/content/${contentId}/current`),
    submitRouting: (planId, payload) => request(`/routing/plans/${planId}/submit`, { method: "POST", body: JSON.stringify(payload) }),
    decideRouting: (planId, payload) => request(`/routing/plans/${planId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    enqueueManagedRoute: (planId, payload) => request(`/routing/plans/${planId}/managed-jobs`, { method: "POST", body: JSON.stringify(payload) }),
    releases: (contentId = null, limit = 100) => request(`/releases?${new URLSearchParams({ ...(contentId ? { content_id: contentId } : {}), limit: String(limit) })}`),
    release: (releaseId) => request(`/releases/${releaseId}`),
    releaseProfiles: () => request("/release-profiles"),
    deliveries: (statuses = [], limit = 100) => {
      const query = new URLSearchParams({ limit: String(limit) });
      appendMany(query, "status", statuses);
      return request(`/deliveries?${query}`);
    },
    deliveryTargets: () => request("/delivery-targets"),
    performanceDashboard: (brandId) => request(`/performance/dashboard/${brandId}`),
    performanceObservations: (limit = 100) => request(`/performance/observations?latest_per_delivery=true&limit=${limit}`),
    operationsSnapshot: () => request("/operations/monitoring"),
    acceptanceCandidates: (limit = 50) => request(`/acceptance/pilot-candidates?limit_per_brand=${limit}`),
    bootstrapPilot: (payload) => request("/acceptance/pilots/bootstrap-draft", { method: "POST", body: JSON.stringify(payload) }),
    pilot: (pilotId) => request(`/acceptance/pilots/${pilotId}`),
    pilotReadiness: (pilotId) => request(`/acceptance/pilots/${pilotId}/readiness`),
    pilotStartReadiness: (pilotId) => request(`/acceptance/pilots/${pilotId}/start-readiness`),
    controlledStartPilot: (pilotId, payload) => request(`/acceptance/pilots/${pilotId}/start-controlled`, { method: "POST", body: JSON.stringify(payload) })
  };

  window.PortfolioApi = api;

  const modules = [
    ["brand-profile-admin", "brand-profile-admin.css", "brand-profile-admin.js"],
    ["generation-queue", "generation-queue.css", "generation-queue.js"],
    ["concept-slate", "concept-slate.css", "concept-slate.js"],
    ["script-review", "script-review.css", "script-review.js"],
    ["audio-review", "audio-review.css", "audio-review.js"],
    ["visual-candidates", "visual-candidates.css", "visual-candidates.js"],
    ["review-workspace", "review-workspace.css", "review-workspace.js"],
    ["review-stage-actions", "review-stage-actions.css", "review-stage-actions.js"],
    ["routing-spend", "routing-spend.css", "routing-spend.js"]
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
