(() => {
  const state = { brands: [], voices: [], currentBrandId: "" };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function csv(value) {
    return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
  }

  function jsonField(id) {
    const raw = document.getElementById(id).value.trim();
    if (!raw) return {};
    const value = JSON.parse(raw);
    if (!value || Array.isArray(value) || typeof value !== "object") {
      throw new Error(`${id.replace("brand-profile-", "")} must be a JSON object.`);
    }
    return value;
  }

  function profileDialog() {
    const dialog = document.createElement("dialog");
    dialog.id = "brand-profile-dialog";
    dialog.className = "brand-profile-dialog";
    dialog.innerHTML = `
      <form method="dialog" class="review-close-row">
        <button class="review-close" aria-label="Close brand settings"><span aria-hidden="true">&times;</span></button>
      </form>
      <div class="brand-profile-head">
        <div><p class="eyebrow dark-eyebrow">Administration</p><h2>Brand profile and fixed narration</h2></div>
        <p>Changes create a new draft version. Activation retires the previous profile without rewriting older content.</p>
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
        <div class="brand-preset-heading">
          <div><h3>Approved narration presets</h3><p>Enable one to three. Exactly one must be the default.</p></div>
        </div>
        <div id="brand-preset-rows" class="brand-preset-rows"></div>
        <div class="brand-profile-actions">
          <button type="submit">Save new draft version</button>
          <span id="brand-profile-message" role="status" aria-live="polite"></span>
        </div>
      </form>
      <section class="brand-profile-history" aria-labelledby="brand-profile-history-heading">
        <h3 id="brand-profile-history-heading">Version history</h3>
        <div id="brand-profile-history-list"></div>
      </section>`;
    return dialog;
  }

  function presetRow(index) {
    const roles = ["primary", "energetic", "serious"];
    const role = roles[index];
    const row = element("fieldset", "brand-preset-row");
    row.dataset.index = String(index);
    row.innerHTML = `
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
      <label class="preset-default"><input type="radio" name="default-narration-preset" value="${index}" ${index === 0 ? "checked" : ""}> Default</label>`;
    return row;
  }

  function fillSelect(select, rows, valueKey, label) {
    select.replaceChildren();
    rows.forEach((row) => {
      const option = document.createElement("option");
      option.value = String(row[valueKey]);
      option.textContent = label(row);
      select.appendChild(option);
    });
  }

  function populateChoices(dialog) {
    const brandSelect = dialog.querySelector("#brand-profile-brand");
    fillSelect(brandSelect, state.brands, "id", (brand) => brand.display_name);
    if (state.currentBrandId && state.brands.some((brand) => String(brand.id) === state.currentBrandId)) {
      brandSelect.value = state.currentBrandId;
    }
    dialog.querySelectorAll('[data-field="approved_voice_id"]').forEach((select) => {
      fillSelect(select, state.voices, "id", (voice) => `${voice.display_name} · ${voice.provider}`);
    });
  }

  function collectPresets(dialog) {
    const defaultIndex = Number(dialog.querySelector('input[name="default-narration-preset"]:checked')?.value ?? -1);
    const presets = [];
    dialog.querySelectorAll(".brand-preset-row").forEach((row) => {
      const index = Number(row.dataset.index);
      if (!row.querySelector('[data-field="enabled"]').checked) return;
      const get = (field) => row.querySelector(`[data-field="${field}"]`).value;
      const style = JSON.parse(get("style") || "{}");
      const pronunciation = JSON.parse(get("pronunciation_rules") || "{}");
      presets.push({
        preset_key: get("preset_key").trim(),
        display_name: get("display_name").trim(),
        role: get("role"),
        approved_voice_id: get("approved_voice_id"),
        language: get("language").trim(),
        speed: Number(get("speed")),
        style,
        pronunciation_rules: pronunciation,
        format_filters: csv(get("format_filters")),
        topic_filters: csv(get("topic_filters")),
        is_default: index === defaultIndex
      });
    });
    if (!presets.length) throw new Error("Enable at least one narration preset.");
    if (presets.filter((item) => item.is_default).length !== 1) {
      throw new Error("Choose one enabled narration preset as the default.");
    }
    return presets;
  }

  function collectProfile(dialog) {
    return {
      default_language: dialog.querySelector("#brand-profile-language").value.trim(),
      audience: jsonField("brand-profile-audience"),
      tone: dialog.querySelector("#brand-profile-tone").value.trim(),
      visual_rules: jsonField("brand-profile-visual"),
      content_restrictions: jsonField("brand-profile-restrictions"),
      cadence: jsonField("brand-profile-cadence"),
      platforms: csv(dialog.querySelector("#brand-profile-platforms").value),
      budget: jsonField("brand-profile-budget"),
      presets: collectPresets(dialog)
    };
  }

  async function renderHistory(dialog) {
    const brandId = dialog.querySelector("#brand-profile-brand").value;
    state.currentBrandId = brandId;
    const target = dialog.querySelector("#brand-profile-history-list");
    target.textContent = "Loading versions…";
    try {
      const payload = await window.PortfolioApi.brandProfiles(brandId);
      target.replaceChildren();
      if (!payload.profiles.length) {
        target.appendChild(element("p", "", "No profile versions yet."));
        return;
      }
      payload.profiles.forEach((profile) => {
        const card = element("article", "brand-profile-version");
        const header = element("div", "brand-profile-version-head");
        header.appendChild(element("strong", "", `Version ${profile.version} · ${profile.status}`));
        header.appendChild(element("span", "", profile.default_language));
        card.appendChild(header);
        card.appendChild(element("p", "", profile.tone));
        card.appendChild(element("small", "", `${profile.presets.length} preset(s): ${profile.presets.map((item) => item.display_name).join(", ")}`));
        if (profile.status === "draft") {
          const activate = element("button", "secondary", "Activate this version");
          activate.type = "button";
          activate.addEventListener("click", async () => {
            activate.disabled = true;
            try {
              await window.PortfolioApi.activateBrandProfile(brandId, profile.id);
              await renderHistory(dialog);
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

  async function openDialog(button, dialog) {
    button.disabled = true;
    try {
      const [access, brands, voices] = await Promise.all([
        window.PortfolioApi.access(),
        window.PortfolioApi.brands(),
        window.PortfolioApi.approvedVoices()
      ]);
      if (!access.operator.roles.includes("admin")) throw new Error("Administrator access is required.");
      state.brands = brands.brands;
      state.voices = voices.voices;
      if (!state.brands.length) throw new Error("No active brands are available.");
      if (!state.voices.length) throw new Error("No currently approved narration voices are available.");
      populateChoices(dialog);
      dialog.showModal();
      await renderHistory(dialog);
    } catch (error) {
      window.alert(error.message);
    } finally {
      button.disabled = false;
    }
  }

  async function refreshVisibility(button) {
    button.hidden = true;
    if (!window.PortfolioApi?.configured()) return;
    try {
      const access = await window.PortfolioApi.access();
      button.hidden = !access.operator.roles.includes("admin");
    } catch (_) {
      button.hidden = true;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (!window.PortfolioApi) return;
    const toolbar = document.querySelector(".portfolio-toolbar");
    if (!toolbar) return;
    const button = element("button", "secondary", "Brand Settings");
    button.id = "brand-profile-settings";
    button.type = "button";
    button.hidden = true;
    toolbar.insertBefore(button, document.getElementById("data-mode"));

    const dialog = profileDialog();
    const rows = dialog.querySelector("#brand-preset-rows");
    for (let index = 0; index < 3; index += 1) rows.appendChild(presetRow(index));
    document.body.appendChild(dialog);

    button.addEventListener("click", () => openDialog(button, dialog));
    dialog.querySelector("#brand-profile-brand").addEventListener("change", () => renderHistory(dialog));
    dialog.querySelector("#brand-profile-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = dialog.querySelector("#brand-profile-message");
      message.textContent = "Saving draft…";
      try {
        const brandId = dialog.querySelector("#brand-profile-brand").value;
        await window.PortfolioApi.createBrandProfile(brandId, collectProfile(dialog));
        message.textContent = "Draft version saved. Review it below before activation.";
        await renderHistory(dialog);
      } catch (error) {
        message.textContent = error.message;
      }
    });
    document.getElementById("connect-api")?.addEventListener("click", () => setTimeout(() => refreshVisibility(button), 250));
    refreshVisibility(button);
  });
})();
