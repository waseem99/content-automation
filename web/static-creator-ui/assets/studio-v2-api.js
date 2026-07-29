(() => {
  const TOKEN_KEY = "content-automation.operator-key";
  const BASE_KEY = "content-automation.api-base";
  const objectUrls = new Set();

  const normalizedBase = (value) => String(value || "").trim().replace(/\/+$/, "");
  const sameOrigin = () => window.location.origin;
  let base = normalizedBase(sessionStorage.getItem(BASE_KEY) || sameOrigin());
  let operatorKey = String(sessionStorage.getItem(TOKEN_KEY) || "").trim();

  function detailMessage(payload, fallback) {
    const detail = payload?.detail;
    if (typeof detail === "string") return detail.replaceAll("_", " ");
    if (detail && typeof detail === "object") {
      if (detail.message) return String(detail.message);
      if (Array.isArray(detail.blockers) && detail.blockers.length) {
        return detail.blockers.map((item) => item.message || String(item.code || "blocked").replaceAll("_", " ")).join(" ");
      }
      const code = detail.code || detail.error;
      if (code) return String(code).replaceAll("_", " ");
    }
    return payload?.error || fallback;
  }

  async function request(path, options = {}) {
    const auth = options.auth !== false;
    if (!base) throw new Error("Creator Studio API is not configured.");
    if (auth && !operatorKey) throw new Error("Sign in before continuing.");
    const headers = { ...(options.headers || {}) };
    if (!(options.body instanceof FormData) && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
    if (auth) headers["X-Operator-Key"] = operatorKey;
    let response;
    try {
      response = await fetch(`${base}${path}`, { ...options, headers });
    } catch (error) {
      throw new Error(`Cannot reach the local platform: ${error.message}`);
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      const error = new Error(detailMessage(payload, `Request failed (${response.status})`));
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function query(path, params = {}) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      if (Array.isArray(value)) value.filter(Boolean).forEach((item) => search.append(key, String(item)));
      else search.set(key, String(value));
    });
    return `${path}${search.size ? `?${search}` : ""}`;
  }

  async function blobUrl(path) {
    const response = await fetch(`${base}${path}`, { headers: { "X-Operator-Key": operatorKey } });
    if (!response.ok) throw new Error(`Media is not available (${response.status}).`);
    const url = URL.createObjectURL(await response.blob());
    objectUrls.add(url);
    return url;
  }

  window.addEventListener("beforeunload", () => {
    objectUrls.forEach((url) => URL.revokeObjectURL(url));
    objectUrls.clear();
  });

  window.StudioApi = {
    configured: () => Boolean(base && operatorKey),
    configuration: () => ({ base, signedIn: Boolean(operatorKey), sameOrigin: base === sameOrigin() }),
    connect(key, nextBase = sameOrigin()) {
      operatorKey = String(key || "").trim();
      base = normalizedBase(nextBase || sameOrigin());
      if (!operatorKey) throw new Error("Operator key is required.");
      sessionStorage.setItem(TOKEN_KEY, operatorKey);
      sessionStorage.setItem(BASE_KEY, base);
    },
    disconnect() {
      operatorKey = "";
      sessionStorage.removeItem(TOKEN_KEY);
    },
    request,
    health: () => request("/health", { auth: false }),
    ready: () => request("/runtime/ready", { auth: false }),
    access: () => request("/access/me"),
    overview: () => request("/studio-v2/overview"),
    brands: () => request("/portfolio/brands"),
    queue: (filters = {}) => request(query("/portfolio/queue", { brand_id: filters.brandId, stage: filters.stage })),
    content: (contentId) => request(`/portfolio/content/${contentId}`),
    contentState: (contentId) => request(`/studio-v2/content/${contentId}/state`),
    platformProfiles: () => request("/p110/platform-profiles"),
    createContent: (payload) => request("/p110/content", { method: "POST", body: JSON.stringify(payload) }),
    contentFamily: (contentId) => request(`/p110/content/${contentId}/family`),
    generateScript: (contentId) => request(`/p110/content/${contentId}/generate-script`, { method: "POST" }),
    startLocalProduction: (contentId, payload = { include_audio: true, include_visuals: true }) => request(`/p110/content/${contentId}/start-local-production`, { method: "POST", body: JSON.stringify(payload) }),
    reviewPolicy: (brandId) => request(`/p110/brands/${brandId}/review-policy`),
    setReviewPolicy: (brandId, payload) => request(`/p110/brands/${brandId}/review-policy`, { method: "POST", body: JSON.stringify(payload) }),
    jobs: (filters = {}) => request(query("/generation/jobs", {
      content_id: filters.contentId,
      brand_id: filters.brandId,
      status: filters.statuses,
      job_type: filters.jobTypes,
      limit: filters.limit || 100
    })),
    job: (jobId) => request(`/generation/jobs/${jobId}`),
    retryJob: (jobId, delaySeconds = 0) => request(`/generation/jobs/${jobId}/retry`, { method: "POST", body: JSON.stringify({ delay_seconds: delaySeconds }) }),
    cancelJob: (jobId, reason) => request(`/generation/jobs/${jobId}/cancel`, { method: "POST", body: JSON.stringify({ reason }) }),
    jobMediaUrl: (jobId) => blobUrl(`/studio-v2/jobs/${jobId}/media`),
    scriptForContent: (contentId) => request(`/scripts/content/${contentId}`),
    submitScript: (documentId, lockVersion) => request(`/scripts/${documentId}/submit`, { method: "POST", body: JSON.stringify({ expected_lock_version: lockVersion }) }),
    decideScript: (documentId, lockVersion, decision, rationale) => request(`/p110/scripts/${documentId}/decisions`, { method: "POST", body: JSON.stringify({ expected_lock_version: lockVersion, decision, rationale: rationale || "" }) }),
    reviseScript: (documentId, lockVersion, reason) => request(`/scripts/${documentId}/revise`, { method: "POST", body: JSON.stringify({ expected_lock_version: lockVersion, reason }) }),
    scriptResearch: (documentId) => request(`/p110/scripts/${documentId}/research`),
    researchClaim: (documentId, payload) => request(`/p110/scripts/${documentId}/research`, { method: "POST", body: JSON.stringify(payload) }),
    addManualSource: (documentId, payload) => request(`/p110/scripts/${documentId}/manual-source`, { method: "POST", body: JSON.stringify(payload) }),
    attachSource: (documentId, payload) => request(`/p110/scripts/${documentId}/sources/attach`, { method: "POST", body: JSON.stringify(payload) }),
    rejectResearchCandidate: (candidateId, reason) => request(`/p110/research/candidates/${candidateId}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
    audioForContent: (contentId) => request(`/audio/content/${contentId}`),
    selectAudioTake: (productionId, takeId, lockVersion) => request(`/audio/${productionId}/takes/${takeId}/select`, { method: "POST", body: JSON.stringify({ expected_lock_version: lockVersion }) }),
    regenerateAudioParagraph: (productionId, paragraphId, payload) => request(`/audio/${productionId}/paragraphs/${paragraphId}/regenerate`, { method: "POST", body: JSON.stringify(payload) }),
    buildLocalAudioMix: (productionId, lockVersion) => request(`/studio-v2/audio/${productionId}/build-local-mix`, { method: "POST", body: JSON.stringify({ expected_lock_version: lockVersion }) }),
    audioMixMediaUrl: (productionId) => blobUrl(`/studio-v2/audio/${productionId}/mix-media`),
    submitAudio: (productionId, lockVersion) => request(`/audio/${productionId}/submit`, { method: "POST", body: JSON.stringify({ expected_lock_version: lockVersion }) }),
    decideAudio: (productionId, payload) => request(`/audio/${productionId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    visualsForContent: (contentId) => request(`/visuals/content/${contentId}`),
    decideVisualCandidate: (projectId, shotId, versionId, candidateId, payload) => request(`/visuals/${projectId}/shots/${shotId}/versions/${versionId}/candidates/${candidateId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    decideVisualShot: (projectId, shotId, versionId, payload) => request(`/visuals/${projectId}/shots/${shotId}/versions/${versionId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    submitVisualProject: (projectId, payload) => request(`/visuals/${projectId}/submit`, { method: "POST", body: JSON.stringify(payload) }),
    decideVisualProject: (projectId, payload) => request(`/visuals/${projectId}/decisions`, { method: "POST", body: JSON.stringify(payload) }),
    reviewInbox: (filters = {}) => request(query("/review/inbox", {
      brand_id: filters.brandIds,
      stage: filters.stages,
      status: filters.statuses,
      item_type: filters.itemTypes,
      overdue: filters.overdue,
      blocker: filters.blocker,
      limit: filters.limit || 100
    })),
    reviewWorkspace: (contentId) => request(`/review/content/${contentId}`),
    operators: () => request("/admin/operators"),
    upsertOperator: (payload) => request("/admin/operators", { method: "POST", body: JSON.stringify(payload) }),
    teamKeys: () => request("/studio-v2/team-keys"),
    localStatus: () => request("/local-production/status"),
    enqueueLocalScripts: (payload) => request("/local-production/enqueue-scripts", { method: "POST", body: JSON.stringify(payload) }),
    continueApproved: (payload) => request("/local-production/continue-approved", { method: "POST", body: JSON.stringify(payload) }),
    approvedVoices: () => request("/portfolio/approved-voices"),
    brandProfiles: (brandId) => request(`/portfolio/brands/${brandId}/profiles`),
    createBrandProfile: (brandId, payload) => request(`/portfolio/brands/${brandId}/profiles`, { method: "POST", body: JSON.stringify(payload) }),
    activateBrandProfile: (brandId, profileId) => request(`/portfolio/brands/${brandId}/profiles/${profileId}/activate`, { method: "POST" }),
    operations: () => request("/operations/monitoring"),
    releases: (contentId = null) => request(query("/releases", { content_id: contentId, limit: 100 })),
    deliveries: () => request(query("/deliveries", { limit: 100 })),
    acceptanceCandidates: () => request("/acceptance/pilot-candidates?limit_per_brand=50"),
    pilot: (pilotId) => request(`/acceptance/pilots/${pilotId}`),
    pilotReadiness: (pilotId) => request(`/acceptance/pilots/${pilotId}/readiness`),
    conceptBatches: (brandId, monthStart) => request(query("/concepts/batches", { brand_id: brandId, month_start: monthStart, limit: 100 })),
    conceptBatch: (batchId) => request(`/concepts/batches/${batchId}`),
    generateConcepts: (payload) => request("/concepts/batches", { method: "POST", body: JSON.stringify(payload) }),
    authenticatedMediaUrl: (contentId, artifactId) => blobUrl(`/portfolio/content/${contentId}/artifacts/${artifactId}/media`)
  };
})();
