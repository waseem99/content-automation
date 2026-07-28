(() => {
  let currentPublicRole = "";

  function publicRole(roles = []) {
    const values = new Set((roles || []).map(String));
    if (values.has("super_admin")) return "super_admin";
    if (values.has("admin")) return "admin";
    if (values.has("reviewer") || values.has("producer") || values.has("publisher")) return "reviewer";
    return "";
  }

  function publicRoles(roles = []) {
    const value = publicRole(roles);
    return value ? [value] : [];
  }

  function humanize(value) {
    return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function normalizeAccess(payload) {
    const operator = payload?.operator || payload;
    if (!operator || typeof operator !== "object") return payload;
    const internalRoles = operator.internal_roles || operator.roles || payload?.roles || [];
    operator.internal_roles = [...internalRoles];
    operator.public_roles = publicRoles(internalRoles);
    operator.public_role = operator.public_roles[0] || "";
    currentPublicRole = operator.public_role;
    // Keep internal capability roles available to the existing UI gates. The
    // session label and team editor use public_role/public_roles instead.
    operator.roles = [...internalRoles];
    return payload;
  }

  function normalizeOperators(payload) {
    if (!payload || !Array.isArray(payload.users)) return payload;
    payload.users = payload.users.map((user) => {
      const internalRoles = user.internal_roles || user.roles || [];
      return {
        ...user,
        internal_roles: [...internalRoles],
        roles: publicRoles(internalRoles),
        public_role: publicRole(internalRoles)
      };
    });
    return payload;
  }

  function wrapApi(api) {
    if (!api || api.__simplifiedRolesInstalled) return;
    api.__simplifiedRolesInstalled = true;

    if (typeof api.access === "function") {
      const originalAccess = api.access.bind(api);
      api.access = async (...args) => normalizeAccess(await originalAccess(...args));
    }

    if (typeof api.operators === "function") {
      const originalOperators = api.operators.bind(api);
      api.operators = async (...args) => normalizeOperators(await originalOperators(...args));
    }

    if (typeof api.deliveries === "function") {
      const originalDeliveries = api.deliveries.bind(api);
      api.deliveries = async (...args) => {
        // Reviewer is the complete content workflow role. Its internal
        // publisher capability is retained for the backend delivery contract.
        const accessRoles = api.__lastInternalRoles || [];
        if (accessRoles.length && !accessRoles.includes("publisher") && !accessRoles.includes("admin") && !accessRoles.includes("super_admin")) {
          return {
            ok: true,
            items: [],
            count: 0,
            role_limited: true,
            required_role: "reviewer"
          };
        }
        return originalDeliveries(...args);
      };
    }

    if (typeof api.access === "function") {
      const normalizedAccess = api.access.bind(api);
      api.access = async (...args) => {
        const payload = await normalizedAccess(...args);
        const operator = payload?.operator || payload || {};
        api.__lastInternalRoles = operator.internal_roles || operator.roles || [];
        return payload;
      };
    }
  }

  wrapApi(window.PortfolioApi);
  wrapApi(window.StudioApi);

  function refreshVisibleRoleLabel() {
    if (!currentPublicRole) return;
    const label = document.querySelector("#session-card span");
    if (label && label.textContent !== humanize(currentPublicRole)) {
      label.textContent = humanize(currentPublicRole);
    }
  }

  const observer = new MutationObserver(refreshVisibleRoleLabel);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("DOMContentLoaded", refreshVisibleRoleLabel);
})();
