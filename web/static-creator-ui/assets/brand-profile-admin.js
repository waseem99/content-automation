(() => {
  const state = { brands: [], voices: [], brandId: "" };

  const node = (tag, className, text) => {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined) value.textContent = text;
    return value;
  };

  const csv = (value) => String(value || "").split(",").map((item) => item.trim()).filter(Boolean);

  function objectValue(id) {
    const raw = document.getElementById(id).value.trim() || "{}";
    const parsed = JSON.parse(raw);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      throw new Error(`${id.replace("brand-profile-", "")} must be a JSON object.`);
    }
    return parsed;
  }

  function installStyles() {
    if (document.querySelector('link[data-brand-profile-admin="true"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.dataset.brandProfileAdmin = "true";
    link.href = new URL("brand-profile-admin.css", document.currentScript?.src || window.location.href).href;
    document.head.appendChild(link);
  }

  function presetMarkup(index, role) {
    const roles = ["primary", "energetic", "serious"];
    return `
      <fieldset class="brand-preset-row" data-index="${index}">
        <legend>Preset ${index + 1}</legend>
        <label class="preset-enabled"><input type="checkbox" data-field="enabled" ${index === 0 ? "checked" : ""}> Enabled</label>
        <label>Key<input data-field="preset_key" value="${role}" pattern="[a-z0-9][a-z0-9_-]+" required></label>
        <label>Name<input data-field="display_name" value="${role[0].toUpperCase()}${role.slice(1)} Narrator" required></label>
        <label>Role<select data-field="role">${roles.map((value) => `<option value="${value}" ${value === role ? "selected" : ""}>${value}</option>`).join("")}</select></label>
        <label>Approved voice<select data-field="approved_voice_id" required></select></label>
        <label>Language<input data-field="language" value="en-US" required></label>
        <label>Speed<input data-field="speed" type="number" min="0.5" max="2" step="0.01" value="${index === 1 ? "1.08" : index === 2 ? "0.92" : "1.00"}"></label>
        <label>Format filters<input data-field="format_filters" placeholder="vertical_short"></label>
        <label>Topic filters<input data-field="topic_filters" placeholder="myth, conservation"></label>
        <label>Style JSON<textarea data-field="style">{}</textarea></label>
        <label>Pronunciation JSON<textarea data-field="pronunciation_rules">{}</textarea></label>
        <label class="preset-default"><input type="radio" name="default-narration-preset" value="${index}" ${index === 0 ? "checked" : ""}> Default</label>
      </fieldset>`;
  }

  function createDialog() {
    const dialog = document.createElement("dialog");
    dialog.id = "brand-profile-dialog";
    dialog.className = "brand-profile-dialog";
    dialog.innerHTML = `
      <form method="dialog" class="review-close-row"><button class="review-close" aria-label="Close brand settings"><span aria-hidden="true">&times;</span></button></form>
      <div class="brand-profile-head">
        <div><p class="eyebrow dark-eyebrow">Administration</p><h2>Brand profile and fixed narration</h2></div>
        <p>Each save creates a draft version. Activation retires the previous version without rewriting existing content.</p>
      </div>
      <form id="brand-profile-form" class="brand-profile-form">
        <div class="brand-profile-grid">
          <label>Brand<select id="brand-profile-brand" required></select></label>
          <label>Default language<input id="brand-profile-language" value="en-US" required></label>
          <label class="wide">Tone<textarea id="brand-profile-tone" required>clear, credible, brand-consistent</textarea></label>
          <label>Platforms<input id="brand-profile-platforms" value="facebook" required><small>Comma-separated</small></label>
          <label>Audience JSON<textarea id="brand-profile-audience">{}</textarea></label>
          <label>Visual rules JSON<textarea id="brand-profile-visual">{}</textarea></label>
          <label>Restrictions JSON<textarea id="brand-profile-restrictions">{}</textarea></label>
          <label>Cadence JSON<textarea id="brand-profile-cadence">{}</textarea></label>
          <label>Budget JSON<textarea id="brand-profile-budget">{"monthly_local_usd":0,"monthly_managed_usd":0}</textarea></label>
        </div>
        <div class="brand-preset-heading"><div><h3>Approved narration presets</h3><p>Enable one to three and choose exactly one default.</p></div></div>
        <div id="brand-preset-rows" class="brand-preset-rows">${["primary", "energetic", "serious"].map((role, index) => presetMarkup(index, role)).join("")}</div>
        <div class="brand-profile-actions"><button type="submit">Save new draft version</button><span id="brand-profile-message" role="status" aria-live="polite"></span></div>
      </form>
      <section class="brand-profile-history" aria-labelledby="brand-profile-history-heading"><h3 id="brand-profile-history-heading">Version history</h3><div id="brand-profile-history-list"></div></section>`;
    return dialog;
  }

  function fill(select, rows, label) {
    select.replaceChildren();
    rows.forEach((row) => {
      const option = document.createElement("option");
      option.value = String(row.id);
      option.textContent = label(row);
      select.appendChild(option);
    });
  }

  function populate(dialog) {
    const brand = dialog.querySelector("#brand-profile-brand");
    fill(brand, state.brands, (item) => item.display_name);
    if (state.brandId && state.brands.some((item) => String(item.id) === state.brandId)) brand.value = state.brandId;
    dialog.querySelectorAll('[data-field="approved_voice_id"]').forEach((select) => {
      fill(select, state.voices, (voice) => `${voice.display_name} · ${voice.provider}`);
    });
  }

  function collectPresets(dialog) {
    const defaultIndex = Number(dialog.querySelector('input[name="default-narration-preset"]:checked')?.value ?? -1);
    const presets = [];
    dialog.querySelectorAll(".brand-preset-row").forEach((row) => {
      if (!row.querySelector('[data-field="enabled"]').checked) return;
      const index = Number(row.dataset.index);
      const get = (field) => row.querySelector(`[data-field="${field}"]`).value;
      presets.push({
        preset_key: get("preset_key").trim(),
        display_name: get("display_name").trim(),
        role: get("role"),
        approved_voice_id: get("approved_voice_id"),
        language: get("language").trim(),
        speed: Number(get("speed")),
        style: JSON.parse(get("style") || "{}"),
        pronunciation_rules: JSON.parse(get("pronunciation_rules") || "{}"),
        format_filters: csv(get("format_filters")),
        topic_filters: csv(get("topic_filters")),
        is_default: index === defaultIndex
      });
    });
    if (!presets.length) throw new Error("Enable at least one narration preset.");
    if (presets.filter((item) => item.is_default).length !== 1) throw new Error("Choose one enabled preset as default.");
    return presets;
  }

  function payload(dialog) {
    return {
      default_language: dialog.querySelector("#brand-profile-language").value.trim(),
      audience: objectValue("brand-profile-audience"),
      tone: dialog.querySelector("#brand-profile-tone").value.trim(),
      visual_rules: objectValue("brand-profile-visual"),
      content_restrictions: objectValue("brand-profile-restrictions"),
      cadence: objectValue("brand-profile-cadence"),
      platforms: csv(dialog.querySelector("#brand-profile-platforms").value),
      budget: objectValue("brand-profile-budget"),
      presets: collectPresets(dialog)
    };
  }

  async function history(dialog) {
    const brandId = dialog.querySelector("#brand-profile-brand").value;
    state.brandId = brandId;
    const target = dialog.querySelector("#brand-profile-history-list");
    target.textContent = "Loading versions…";
    try {
      const result = await window.PortfolioApi.brandProfiles(brandId);
      target.replaceChildren();
      if (!result.profiles.length) return target.appendChild(node("p", "", "No profile versions yet."));
      result.profiles.forEach((profile) => {
        const card = node("article", "brand-profile-version");
        const head = node("div", "brand-profile-version-head");
        head.append(node("strong", "", `Version ${profile.version} · ${profile.status}`), node("span", "", profile.default_language));
        card.append(head, node("p", "", profile.tone), node("small", "", `${profile.presets.length} preset(s): ${profile.presets.map((item) => item.display_name).join(", ")}`));
        if (profile.status === "draft") {
          const activate = node("button", "secondary", "Activate this version");
          activate.type = "button";
          activate.addEventListener("click", async () => {
            activate.disabled = true;
            try {
              await window.PortfolioApi.activateBrandProfile(brandId, profile.id);
              await history(dialog);
            } catch (error) {
              dialog.querySelector("#brand-profile-message").textContent = error.message;
            } finally {
              activate.disabled = false;
            }
          });
          card.appendChild(activate);
        }
        target.appendChild(card);
      });
    } catch (error) {
      target.textContent = error.message;
    }
  }

  async function open(button, dialog) {
    button.disabled = true;
    try {
      const [access, brands, voices] = await Promise.all([window.PortfolioApi.access(), window.PortfolioApi.brands(), window.PortfolioApi.approvedVoices()]);
      if (!access.operator.roles.includes("admin")) throw new Error("Administrator access is required.");
      state.brands = brands.brands;
      state.voices = voices.voices;
      if (!state.brands.length) throw new Error("No active brands are available.");
      if (!state.voices.length) throw new Error("No currently approved narration voices are available.");
      populate(dialog);
      dialog.showModal();
      await history(dialog);
    } catch (error) {
      window.alert(error.message);
    } finally {
      button.disabled = false;
    }
  }

  async function visibility(button) {
    button.hidden = true;
    if (!window.PortfolioApi?.configured()) return;
    try {
      const access = await window.PortfolioApi.access();
      button.hidden = !access.operator.roles.includes("admin");
    } catch (_) {
      button.hidden = true;
    }
  }

  function initialize() {
    if (!window.PortfolioApi || document.getElementById("brand-profile-settings")) return;
    const toolbar = document.querySelector(".portfolio-toolbar");
    if (!toolbar) return;
    installStyles();
    const button = node("button", "secondary", "Brand Settings");
    button.id = "brand-profile-settings";
    button.type = "button";
    button.hidden = true;
    toolbar.insertBefore(button, document.getElementById("data-mode"));
    const dialog = createDialog();
    document.body.appendChild(dialog);
    button.addEventListener("click", () => open(button, dialog));
    dialog.querySelector("#brand-profile-brand").addEventListener("change", () => history(dialog));
    dialog.querySelector("#brand-profile-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = dialog.querySelector("#brand-profile-message");
      message.textContent = "Saving draft…";
      try {
        const brandId = dialog.querySelector("#brand-profile-brand").value;
        await window.PortfolioApi.createBrandProfile(brandId, payload(dialog));
        message.textContent = "Draft saved. Review the version below before activation.";
        await history(dialog);
      } catch (error) {
        message.textContent = error.message;
      }
    });
    document.getElementById("connect-api")?.addEventListener("click", () => setTimeout(() => visibility(button), 250));
    visibility(button);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
})();
