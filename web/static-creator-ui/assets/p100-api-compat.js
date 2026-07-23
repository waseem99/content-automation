(() => {
  const api = window.PortfolioApi;
  if (!api) return;

  const originalReadiness = api.pilotStartReadiness;
  api.pilotStartReadiness = async (pilotId) => {
    const payload = await originalReadiness(pilotId);
    return {
      ...payload,
      ready_to_start: Boolean(payload.can_start),
      already_running: payload.pilot_status === "running"
    };
  };

  api.controlledStartPilot = async (pilotId, payload) => {
    const configuration = api.configuration();
    const key = String(sessionStorage.getItem("content-automation.operator-key") || "").trim();
    if (!configuration.base || !key) throw new Error("Operator key is required.");
    const response = await fetch(`${configuration.base}/acceptance/pilots/${pilotId}/start-controlled`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Operator-Key": key },
      body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.ok === false) {
      const detail = result.detail;
      const code = typeof detail === "object" && detail ? detail.code : detail;
      throw new Error(result.error || code || `Controlled start failed (${response.status})`);
    }
    return result;
  };
})();
