let dashboardWidgets = [];
let pendingInsertAfterId = null;

const dashboardEl = document.getElementById("dashboard");
const emptyStateEl = document.getElementById("empty-state");
const widgetModalEl = document.getElementById("widget-modal");
const widgetFormEl = document.getElementById("widget-form");
const widgetFormContentEl = document.getElementById("widget-form-content");
const widgetFormErrorEl = document.getElementById("widget-form-error");
const widgetModalTitleEl = document.getElementById("widget-modal-title");

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || data.message || "Request failed");
  }

  return data;
}

async function loadDashboard() {
  const data = await fetchJson("/dashboard-data");
  dashboardWidgets = data.widgets || [];
  renderDashboard();
}

function renderDashboard() {
  dashboardEl.innerHTML = "";
  emptyStateEl.hidden = dashboardWidgets.length !== 0;

  dashboardWidgets.forEach((widget) => {
    const card = document.createElement("article");
    card.className = "widget-card";
    card.dataset.widgetId = widget.id;

    const graphId = `widget-graph-${widget.id}`;

    card.innerHTML = `
      <div class="widget-header">
        <div>
          <p class="widget-type">${widget.type}</p>
          <h2>${widget.title}</h2>
        </div>
      </div>
      <div id="${graphId}" class="widget-graph"></div>
      <div class="widget-actions" id="widget-actions-${widget.id}"></div>
      <button class="add-under-button" type="button" onclick="openAddWidgetModal(${widget.id})">+ Add Graphic Here</button>
    `;

    dashboardEl.appendChild(card);

    if (widget.type === "radar") {
      renderRadarWidget(graphId, widget);
      renderRadarActions(widget.id, widget.config.domains);
    } else if (widget.type === "bar") {
      renderBarWidget(graphId, widget);
      renderBarActions(widget.id, widget.config);
    }
  });

  if (dashboardWidgets.length > 0) {
    const trailingAddCard = document.createElement("article");
    trailingAddCard.className = "add-card";
    trailingAddCard.innerHTML = `
      <p>Add another graphic</p>
      <button class="btn-plus big-add-button" type="button" onclick="openAddWidgetModal()">+</button>
    `;
    dashboardEl.appendChild(trailingAddCard);
  }
}

function renderRadarWidget(graphId, widget) {
  const plotData = [
    {
      type: "scatterpolar",
      r: widget.plot.r,
      theta: widget.plot.theta,
      fill: "toself",
      marker: { color: "rgb(106, 168, 79)", size: 10 },
      line: { color: "rgb(106, 168, 79)", width: 3 },
      fillcolor: "rgba(106, 168, 79, 0.3)",
    },
  ];

  const layout = {
    margin: { t: 20, r: 30, b: 20, l: 30 },
    polar: {
      radialaxis: { visible: true, range: [0, 100] },
    },
    showlegend: false,
  };

  Plotly.react(graphId, plotData, layout, {
    responsive: true,
    displayModeBar: false,
  });
}

function renderRadarActions(widgetId, domains) {
  const actionsEl = document.getElementById(`widget-actions-${widgetId}`);
  actionsEl.innerHTML = `
    <div class="domain-controls">
      ${domains
        .map(
          (domain, index) => `
            <div class="domain-control">
              <span>${domain}</span>
              <div class="score-buttons">
                <button class="btn-minus" type="button" onclick="updateRadarScore(${widgetId}, ${index}, -1)">-1</button>
                <button class="btn-plus" type="button" onclick="updateRadarScore(${widgetId}, ${index}, 1)">+1</button>
              </div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderBarWidget(graphId, widget, maxDays = 30) {
  const entries = widget.entries || [];
  const values = entries.map((entry) => entry.value);
  const labels = Array.from({ length: maxDays }, (_, index) => `day ${index + 1}`);
  const paddedValues = Array.from({ length: maxDays }, (_, index) => values[index] ?? 0);

  const trace = {
    x: labels,
    y: paddedValues,
    name: widget.config.metric_name,
    type: "bar",
    marker: { color: "#f59e0b" },
  };

  const yAxisTitle = widget.config.unit
    ? `${widget.config.metric_name} (${widget.config.unit})`
    : widget.config.metric_name;

  Plotly.react(
    graphId,
    [trace],
    {
      margin: { t: 20, r: 20, b: 50, l: 50 },
      xaxis: { title: "Days", type: "category" },
      yaxis: { title: yAxisTitle },
      bargap: 0.35,
    },
    {
      responsive: true,
      displayModeBar: false,
    },
  );
}

function renderBarActions(widgetId, config) {
  const actionsEl = document.getElementById(`widget-actions-${widgetId}`);
  const unitLabel = config.unit ? ` (${config.unit})` : "";

  actionsEl.innerHTML = `
    <form class="bar-entry-form" onsubmit="submitBarEntry(event, ${widgetId})">
      <label for="bar-input-${widgetId}">Add ${config.metric_name}${unitLabel}</label>
      <div class="bar-entry-row">
        <input id="bar-input-${widgetId}" type="number" min="0" step="0.5" placeholder="Enter a number" />
        <button class="btn-plus" type="submit">Add Entry</button>
      </div>
    </form>
  `;
}

async function updateRadarScore(widgetId, index, change) {
  try {
    const data = await fetchJson(`/widgets/${widgetId}/radar/update-score`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index, change }),
    });

    const widget = dashboardWidgets.find((item) => item.id === widgetId);
    if (!widget) {
      return;
    }

    widget.plot = {
      theta: data.theta,
      r: data.r,
    };
    widget.config.scores = data.scores;

    renderRadarWidget(`widget-graph-${widgetId}`, widget);
  } catch (error) {
    alert(error.message);
  }
}

async function submitBarEntry(event, widgetId) {
  event.preventDefault();

  const input = document.getElementById(`bar-input-${widgetId}`);
  const value = Number.parseFloat(input.value);

  if (Number.isNaN(value) || value < 0) {
    alert("Please enter a valid positive number.");
    return;
  }

  try {
    const data = await fetchJson(`/widgets/${widgetId}/bar/entries`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });

    const widget = dashboardWidgets.find((item) => item.id === widgetId);
    if (!widget) {
      return;
    }

    widget.entries = data.entries;
    renderBarWidget(`widget-graph-${widgetId}`, widget);
    input.value = "";
  } catch (error) {
    alert(error.message);
  }
}

function openAddWidgetModal(insertAfterId = null) {
  pendingInsertAfterId = insertAfterId;
  widgetModalEl.style.display = "flex";
  widgetModalTitleEl.textContent = "Add Graphic";
  widgetFormErrorEl.hidden = true;
  widgetFormErrorEl.textContent = "";
  renderWidgetTypeStep();
}

function closeWidgetModal() {
  widgetModalEl.style.display = "none";
  widgetFormEl.dataset.step = "";
  widgetFormEl.dataset.widgetType = "";
  widgetFormContentEl.innerHTML = "";
  pendingInsertAfterId = null;
}

function renderWidgetTypeStep() {
  widgetFormEl.dataset.step = "choose-type";
  widgetModalTitleEl.textContent = "Choose a Graphic";
  widgetFormContentEl.innerHTML = `
    <div class="type-grid">
      <label class="type-option">
        <input type="radio" name="widgetType" value="radar" checked />
        <span>Radar chart</span>
        <small>Track several growth domains at once.</small>
      </label>
      <label class="type-option">
        <input type="radio" name="widgetType" value="bar" />
        <span>Bar chart</span>
        <small>Track one daily habit or metric.</small>
      </label>
    </div>
  `;
}

function renderWidgetConfigStep(widgetType) {
  widgetFormEl.dataset.step = "configure";
  widgetFormEl.dataset.widgetType = widgetType;
  widgetModalTitleEl.textContent = "Graphic Parameters";

  if (widgetType === "radar") {
    widgetFormContentEl.innerHTML = `
      <label class="field-label" for="widget-title">Graphic title</label>
      <input id="widget-title" name="title" type="text" placeholder="Optional title for this radar" />

      <label class="field-label" for="radar-domains">Radar domains</label>
      <textarea
        id="radar-domains"
        name="domains"
        rows="5"
        placeholder="Enter at least three domain names, separated by commas. Example: Sport, Focus, Learning"
      ></textarea>
      <p class="field-help">Enter the number and name of at least three domains.</p>
    `;
    return;
  }

  widgetFormContentEl.innerHTML = `
    <label class="field-label" for="widget-title">Graphic title</label>
    <input id="widget-title" name="title" type="text" placeholder="Optional title for this bar chart" />

    <label class="field-label" for="metric-name">Habit or metric name</label>
    <input id="metric-name" name="metric_name" type="text" placeholder="Examples: Reading, Pushups, Deep Work" />

    <label class="field-label" for="metric-unit">Unit</label>
    <input id="metric-unit" name="unit" type="text" placeholder="Examples: pages, reps, hours" />
  `;
}

widgetFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();

  const step = widgetFormEl.dataset.step;
  widgetFormErrorEl.hidden = true;
  widgetFormErrorEl.textContent = "";

  if (step === "choose-type") {
    const selectedType = widgetFormEl.querySelector('input[name="widgetType"]:checked')?.value;
    renderWidgetConfigStep(selectedType);
    return;
  }

  const widgetType = widgetFormEl.dataset.widgetType;
  const payload = {
    type: widgetType,
    insert_after_id: pendingInsertAfterId,
    title: document.getElementById("widget-title")?.value.trim() || "",
  };

  if (widgetType === "radar") {
    const rawDomains = document.getElementById("radar-domains").value;
    payload.domains = rawDomains.split(",").map((domain) => domain.trim());
  } else if (widgetType === "bar") {
    payload.metric_name = document.getElementById("metric-name").value.trim();
    payload.unit = document.getElementById("metric-unit").value.trim();
  }

  try {
    await fetchJson("/widgets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    closeWidgetModal();
    await loadDashboard();
  } catch (error) {
    widgetFormErrorEl.hidden = false;
    widgetFormErrorEl.textContent = error.message;
  }
});

window.addEventListener("click", (event) => {
  if (event.target === widgetModalEl) {
    closeWidgetModal();
  }
});

loadDashboard().catch((error) => {
  emptyStateEl.hidden = false;
  emptyStateEl.querySelector("p").textContent = error.message;
});
