/**
 * Chore Tracker Card
 * A Home Assistant Lovelace card to track household chore minutes for children.
 */

class ChoreTrackerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._activeChild = null;
    this._unsubscribe = null;
  }

  setConfig(config) {
    if (!config.children || !Array.isArray(config.children) || config.children.length === 0) {
      throw new Error("Please define a list of children in the card config.");
    }
    this._config = {
      title: config.title || "Chore Tracker",
      children: config.children,
    };
    this._activeChild = this._config.children[0];
    this._render();
  }

  set hass(hass) {
    const firstHass = !this._hass;
    const connectionChanged =
      this._hass && this._hass.connection !== hass.connection;
    this._hass = hass;

    // HA supplies a new hass object frequently. Rebuilding the card DOM on
    // every update replaces the inputs and steals focus while the user types.
    if (connectionChanged && this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
      this._subscribeEvents();
    }
    if (firstHass) {
      this._render();
    }
  }

  connectedCallback() {
    // Subscribe to chore_tracker_updated events via WebSocket
    if (this._hass && !this._unsubscribe) {
      this._subscribeEvents();
    }
  }

  disconnectedCallback() {
    if (this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
    }
  }

  async _subscribeEvents() {
    if (!this._hass) return;
    try {
      this._unsubscribe = await this._hass.connection.subscribeEvents(
        () => this._render(),
        "chore_tracker_updated"
      );
    } catch (e) {
      console.warn("ChoreTracker: could not subscribe to events", e);
    }
  }

  _getData() {
    if (!this._hass) return {};
    // Read from hass.data via the REST API shadow — we poll via hass.callApi
    return {};
  }

  async _fetchData() {
    if (!this._hass) return null;
    try {
      const result = await this._hass.callWS({
        type: "chore_tracker/get_data",
      });
      return result;
    } catch (e) {
      return null;
    }
  }

  async _addEntry() {
    const input = this.shadowRoot.querySelector("#minutes-input");
    const noteInput = this.shadowRoot.querySelector("#note-input");
    const minutes = parseInt(input.value, 10);
    if (!minutes || minutes <= 0) {
      this._showMessage("Bitte eine gültige Minutenzahl eingeben.", "error");
      return;
    }
    try {
      await this._hass.callService("chore_tracker", "add_entry", {
        child: this._activeChild,
        minutes: minutes,
        note: noteInput ? noteInput.value : "",
      });
      input.value = "";
      if (noteInput) noteInput.value = "";
      this._showMessage(`${minutes} Min. für ${this._activeChild} hinzugefügt!`, "success");
      setTimeout(() => this._render(), 300);
    } catch (e) {
      this._showMessage("Fehler beim Hinzufügen: " + e.message, "error");
    }
  }

  async _resetChild() {
    if (!confirm(`Alle Einträge für ${this._activeChild} zurücksetzen?`)) return;
    try {
      await this._hass.callService("chore_tracker", "reset_child", {
        child: this._activeChild,
      });
      this._showMessage(`${this._activeChild} zurückgesetzt.`, "success");
      setTimeout(() => this._render(), 300);
    } catch (e) {
      this._showMessage("Fehler beim Zurücksetzen: " + e.message, "error");
    }
  }

  _showMessage(text, type) {
    const msg = this.shadowRoot.querySelector("#status-msg");
    if (!msg) return;
    msg.textContent = text;
    msg.className = "status-msg " + type;
    clearTimeout(this._msgTimer);
    this._msgTimer = setTimeout(() => {
      if (msg) msg.textContent = "";
    }, 3000);
  }

  async _render() {
    if (!this._config) return;

    // Fetch stored data from HA storage via the custom WS command or REST
    let storedData = null;
    if (this._hass) {
      try {
        storedData = await this._hass.callWS({ type: "chore_tracker/get_data" });
      } catch (_) {
        storedData = null;
      }
    }

    const children = this._config.children;
    const childData = (storedData && storedData.children) ? storedData.children : {};

    const styles = `
      :host {
        display: block;
        font-family: var(--paper-font-body1_-_font-family, sans-serif);
      }
      ha-card {
        padding: 16px;
      }
      .card-header {
        font-size: 1.4em;
        font-weight: bold;
        color: var(--primary-text-color);
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .card-header .icon { font-size: 1.3em; }
      .section-title {
        font-size: 1em;
        font-weight: 600;
        color: var(--secondary-text-color);
        margin: 16px 0 8px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      .input-row {
        display: flex;
        gap: 8px;
        align-items: center;
        flex-wrap: wrap;
      }
      .input-row input[type=number] {
        width: 90px;
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 1em;
      }
      .input-row input[type=text] {
        flex: 1;
        min-width: 120px;
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 1em;
      }
      .btn {
        padding: 8px 18px;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-size: 0.95em;
        font-weight: 600;
        transition: opacity 0.2s;
      }
      .btn:hover { opacity: 0.85; }
      .btn-add {
        background: var(--primary-color, #03a9f4);
        color: #fff;
      }
      .btn-reset {
        background: var(--error-color, #f44336);
        color: #fff;
      }
      .status-msg {
        margin-top: 8px;
        font-size: 0.9em;
        min-height: 20px;
        padding: 4px 0;
        font-weight: 500;
      }
      .status-msg.success { color: var(--success-color, #4caf50); }
      .status-msg.error { color: var(--error-color, #f44336); }

      /* Summary grid */
      .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
        gap: 10px;
        margin-top: 8px;
      }
      .summary-card {
        background: var(--primary-color, #03a9f4);
        color: #fff;
        border-radius: 12px;
        padding: 12px;
        text-align: center;
        cursor: pointer;
        transition: transform 0.15s, opacity 0.15s;
      }
      .summary-card:hover { transform: scale(1.04); }
      .summary-card .child-name {
        font-size: 0.95em;
        font-weight: 600;
        margin-bottom: 4px;
        word-break: break-word;
      }
      .summary-card .minutes-total {
        font-size: 2em;
        font-weight: bold;
        line-height: 1.1;
      }
      .summary-card .minutes-label {
        font-size: 0.75em;
        opacity: 0.85;
      }
      .summary-card.active {
        outline: 3px solid var(--accent-color, #ff9800);
      }

      /* Entries list */
      .entries-list {
        margin-top: 8px;
        max-height: 260px;
        overflow-y: auto;
        border: 1px solid var(--divider-color, #eee);
        border-radius: 8px;
      }
      .entry-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        border-bottom: 1px solid var(--divider-color, #eee);
        font-size: 0.9em;
      }
      .entry-item:last-child { border-bottom: none; }
      .entry-item:nth-child(odd) {
        background: var(--secondary-background-color, #f5f5f5);
      }
      .entry-minutes {
        font-weight: bold;
        color: var(--primary-color, #03a9f4);
        min-width: 50px;
      }
      .entry-note {
        flex: 1;
        color: var(--secondary-text-color);
        padding: 0 8px;
        font-style: italic;
      }
      .entry-time {
        color: var(--disabled-text-color, #aaa);
        font-size: 0.82em;
        white-space: nowrap;
      }
      .no-entries {
        padding: 20px;
        text-align: center;
        color: var(--secondary-text-color);
        font-style: italic;
      }
      .action-row {
        display: flex;
        justify-content: flex-end;
        margin-top: 12px;
      }
    `;

    const activeChildEntries = (childData[this._activeChild] && childData[this._activeChild].entries) || [];
    const activeChildTotal = (childData[this._activeChild] && childData[this._activeChild].total_minutes) || 0;

    const summaryHtml = children.map(child => {
      const total = (childData[child] && childData[child].total_minutes) || 0;
      const isActive = child === this._activeChild;
      return `
        <div class="summary-card ${isActive ? "active" : ""}" data-child="${child}">
          <div class="child-name">${child}</div>
          <div class="minutes-total">${total}</div>
          <div class="minutes-label">Minuten</div>
        </div>
      `;
    }).join("");

    const entriesHtml = activeChildEntries.length === 0
      ? `<div class="no-entries">Noch keine Einträge für ${this._activeChild}.</div>`
      : [...activeChildEntries].reverse().map(e => {
          const d = new Date(e.timestamp);
          const timeStr = d.toLocaleDateString() + " " + d.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
          return `
            <div class="entry-item">
              <span class="entry-minutes">+${e.minutes} min</span>
              <span class="entry-note">${e.note || ""}</span>
              <span class="entry-time">${timeStr}</span>
            </div>
          `;
        }).join("");

    const html = `
      <style>${styles}</style>
      <ha-card>
        <div class="card-header">
          <span class="icon">🧹</span>
          ${this._config.title}
        </div>

        <div class="section-title">Übersicht</div>
        <div class="summary-grid">${summaryHtml}</div>

        <div class="section-title">Eintrag hinzufügen — ${this._activeChild}</div>
        <div class="input-row">
          <input id="minutes-input" type="number" min="1" max="480" placeholder="Minuten" />
          <input id="note-input" type="text" placeholder="Notiz (optional)" />
          <button class="btn btn-add" id="add-btn">Hinzufügen</button>
        </div>
        <div id="status-msg" class="status-msg"></div>

        <div class="section-title">Einträge — ${this._activeChild} (${activeChildTotal} Min. gesamt)</div>
        <div class="entries-list">${entriesHtml}</div>

        <div class="action-row">
          <button class="btn btn-reset" id="reset-btn">${this._activeChild} zurücksetzen</button>
        </div>
      </ha-card>
    `;

    this.shadowRoot.innerHTML = html;

    // Wire up events
    this.shadowRoot.querySelector("#add-btn").addEventListener("click", () => this._addEntry());
    this.shadowRoot.querySelector("#reset-btn").addEventListener("click", () => this._resetChild());

    this.shadowRoot.querySelector("#minutes-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._addEntry();
    });

    this.shadowRoot.querySelectorAll(".summary-card").forEach(card => {
      card.addEventListener("click", () => {
        this._activeChild = card.dataset.child;
        this._render();
      });
    });

    // Re-subscribe if needed
    if (this._hass && !this._unsubscribe) {
      this._subscribeEvents();
    }
  }

  getCardSize() {
    return 5;
  }

  static getConfigElement() {
    return document.createElement("chore-tracker-card-editor");
  }

  static getStubConfig() {
    return {
      title: "Haushaltsaufgaben",
      children: ["Emma", "Luca"],
    };
  }
}

customElements.define("chore-tracker-card", ChoreTrackerCard);

// ─── Card Editor ────────────────────────────────────────────────────────────

class ChoreTrackerCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    this._config = {
      type: config.type || "custom:chore-tracker-card",
      title: config.title || "Haushaltsaufgaben",
      children: config.children || [],
    };
    this._render();
  }

  // Called by HA when user changes something; we fire this ourselves too
  _dispatchChange() {
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: { type: "custom:chore-tracker-card", ...this._config } },
      bubbles: true,
      composed: true,
    }));
  }

  _render() {
    const styles = `
      :host { display: block; padding: 4px 0; }
      .row {
        display: flex;
        flex-direction: column;
        gap: 4px;
        margin-bottom: 16px;
      }
      label {
        font-size: 0.85em;
        font-weight: 600;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      input[type=text] {
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 1em;
        width: 100%;
        box-sizing: border-box;
      }
      .children-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-bottom: 8px;
      }
      .child-row {
        display: flex;
        gap: 8px;
        align-items: center;
      }
      .child-row input {
        flex: 1;
        padding: 7px 10px;
        border-radius: 8px;
        border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 0.95em;
      }
      .btn-icon {
        background: none;
        border: none;
        cursor: pointer;
        font-size: 1.2em;
        padding: 4px 6px;
        border-radius: 6px;
        color: var(--secondary-text-color);
        transition: background 0.15s;
      }
      .btn-icon:hover { background: var(--secondary-background-color, #eee); }
      .btn-icon.delete { color: var(--error-color, #f44336); }
      .btn-icon.up, .btn-icon.down { color: var(--primary-color, #03a9f4); }
      .btn-add-child {
        display: flex;
        align-items: center;
        gap: 6px;
        background: none;
        border: 2px dashed var(--primary-color, #03a9f4);
        color: var(--primary-color, #03a9f4);
        border-radius: 8px;
        padding: 7px 14px;
        cursor: pointer;
        font-size: 0.95em;
        font-weight: 600;
        width: 100%;
        justify-content: center;
        transition: background 0.15s;
      }
      .btn-add-child:hover { background: var(--primary-color-light, #e1f5fe); }
    `;

    const childrenHtml = this._config.children.map((child, i) => `
      <div class="child-row" data-index="${i}">
        <input type="text" class="child-name-input" value="${child}" data-index="${i}" />
        <button class="btn-icon up" data-index="${i}" title="Nach oben">↑</button>
        <button class="btn-icon down" data-index="${i}" title="Nach unten">↓</button>
        <button class="btn-icon delete" data-index="${i}" title="Entfernen">✕</button>
      </div>
    `).join("");

    this.shadowRoot.innerHTML = `
      <style>${styles}</style>

      <div class="row">
        <label>Titel</label>
        <input type="text" id="title-input" value="${this._config.title}" placeholder="Haushaltsaufgaben" />
      </div>

      <div class="row">
        <label>Kinder</label>
        <div class="children-list" id="children-list">
          ${childrenHtml}
        </div>
        <button class="btn-add-child" id="add-child-btn">+ Kind hinzufügen</button>
      </div>
    `;

    // Title change
    this.shadowRoot.querySelector("#title-input").addEventListener("change", (e) => {
      this._config = { ...this._config, title: e.target.value };
      this._dispatchChange();
    });

    // Add child
    this.shadowRoot.querySelector("#add-child-btn").addEventListener("click", () => {
      this._config = { ...this._config, children: [...this._config.children, ""] };
      this._render();
      // Focus the new input
      const inputs = this.shadowRoot.querySelectorAll(".child-name-input");
      if (inputs.length) inputs[inputs.length - 1].focus();
    });

    // Child name edits, delete, reorder
    this.shadowRoot.querySelectorAll(".child-name-input").forEach(input => {
      input.addEventListener("change", (e) => {
        const idx = parseInt(e.target.dataset.index, 10);
        const children = [...this._config.children];
        children[idx] = e.target.value.trim();
        this._config = { ...this._config, children };
        this._dispatchChange();
      });
    });

    this.shadowRoot.querySelectorAll(".btn-icon.delete").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.index, 10);
        const children = [...this._config.children];
        children.splice(idx, 1);
        this._config = { ...this._config, children };
        this._dispatchChange();
        this._render();
      });
    });

    this.shadowRoot.querySelectorAll(".btn-icon.up").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.index, 10);
        if (idx === 0) return;
        const children = [...this._config.children];
        [children[idx - 1], children[idx]] = [children[idx], children[idx - 1]];
        this._config = { ...this._config, children };
        this._dispatchChange();
        this._render();
      });
    });

    this.shadowRoot.querySelectorAll(".btn-icon.down").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.index, 10);
        const children = [...this._config.children];
        if (idx >= children.length - 1) return;
        [children[idx], children[idx + 1]] = [children[idx + 1], children[idx]];
        this._config = { ...this._config, children };
        this._dispatchChange();
        this._render();
      });
    });
  }
}

customElements.define("chore-tracker-card-editor", ChoreTrackerCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "chore-tracker-card",
  name: "Haushaltsaufgaben",
  description: "Minuten für Haushaltsaufgaben pro Kind erfassen.",
  documentationURL: "https://github.com/anomalyco/chore-tracker",
});

console.info(
  "%c CHORE-TRACKER-CARD %c v1.0.0 ",
  "color: white; background: #03a9f4; font-weight: 700;",
  "color: #03a9f4; background: white; font-weight: 700;"
);
