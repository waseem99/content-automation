(() => {
  const api = window.PortfolioApi;
  if (!api) return;

  let authenticatedRoles = [];
  const originalAccess = api.access.bind(api);
  const originalDeliveries = api.deliveries.bind(api);

  api.access = async (...args) => {
    const payload = await originalAccess(...args);
    authenticatedRoles = payload?.roles || payload?.operator?.roles || [];
    return payload;
  };

  api.deliveries = async (...args) => {
    if (!authenticatedRoles.includes("publisher")) {
      return {
        ok: true,
        items: [],
        count: 0,
        role_limited: true,
        required_role: "publisher"
      };
    }
    return originalDeliveries(...args);
  };
})();
