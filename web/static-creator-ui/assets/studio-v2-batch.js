(() => {
  const api = window.StudioApi;
  if (!api || api.contentStates) return;

  const pending = new Map();
  let flushScheduled = false;

  function scheduleFlush() {
    if (flushScheduled) return;
    flushScheduled = true;
    window.queueMicrotask(flush);
  }

  async function flush() {
    flushScheduled = false;
    const batch = [...pending.entries()].slice(0, 100);
    if (!batch.length) return;
    batch.forEach(([contentId]) => pending.delete(contentId));
    if (pending.size) scheduleFlush();

    const contentIds = batch.map(([contentId]) => contentId);
    try {
      const payload = await api.request("/studio-v2/content-states", {
        method: "POST",
        body: JSON.stringify({ content_ids: contentIds })
      });
      const states = payload.items || [];
      const byId = new Map(states.map((state) => [String(state?.item?.id || ""), state]));
      batch.forEach(([contentId, listeners]) => {
        const state = byId.get(contentId);
        if (!state) {
          const error = new Error(`Content state was not returned for ${contentId}.`);
          listeners.forEach(({ reject }) => reject(error));
          return;
        }
        listeners.forEach(({ resolve }) => resolve(state));
      });
    } catch (error) {
      batch.forEach(([, listeners]) => listeners.forEach(({ reject }) => reject(error)));
    }
  }

  function contentState(contentId) {
    const key = String(contentId || "").trim();
    if (!key) return Promise.reject(new Error("Content ID is required."));
    return new Promise((resolve, reject) => {
      const listeners = pending.get(key) || [];
      listeners.push({ resolve, reject });
      pending.set(key, listeners);
      scheduleFlush();
    });
  }

  api.contentStates = async (contentIds) => {
    const unique = [...new Set((contentIds || []).map((value) => String(value || "").trim()).filter(Boolean))];
    if (!unique.length) return [];
    const payload = await api.request("/studio-v2/content-states", {
      method: "POST",
      body: JSON.stringify({ content_ids: unique.slice(0, 100) })
    });
    return payload.items || [];
  };
  api.contentState = contentState;
})();
