let dashboardWidgets = [];

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
    const graphClass = widget.type === "radar" ? "widget-graph widget-graph-radar" : "widget-graph";

    card.innerHTML = `
      <div class="widget-header">
        <div>
          <p class="widget-type">${widget.type}</p>
          <h2>${widget.title}</h2>
        </div>
        <button class="btn-danger widget-remove-button" type="button" onclick="removeWidget(${widget.id})">
          Remove Widget
        </button>
      </div>
      <div class="widget-body">
        <div id="${graphId}" class="${graphClass}"></div>
        <div class="widget-actions" id="widget-actions-${widget.id}"></div>
      </div>
    `;

    dashboardEl.appendChild(card);

    if (widget.type === "radar") {
      renderRadarWidget(graphId, widget);
      renderRadarActions(widget.id, widget.config.domains, widget.config.today_deltas);
    } else if (widget.type === "bar") {
      renderBarWidget(graphId, widget);
      renderBarActions(widget.id, widget.config, widget.today_entry);
    } else if (widget.type === "pie") {
      renderPieWidget(graphId, widget);
      renderPieActions(widget.id, widget);
    }
  });

  const addButtonWrap = document.createElement("div");
  addButtonWrap.className = "dashboard-add-wrap";
  addButtonWrap.innerHTML = `
    <button class="btn-plus dashboard-add-button" type="button" onclick="openAddWidgetModal()">
      + Add Graphic
    </button>
  `;
  dashboardEl.appendChild(addButtonWrap);
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

function renderRadarActions(widgetId, domains, todayDeltas = []) {
  const actionsEl = document.getElementById(`widget-actions-${widgetId}`);
  actionsEl.innerHTML = `
    <div class="daily-note">For each domain, today's net change can only end at -1, 0, or +1.</div>
    <div class="domain-controls">
      ${domains
        .map((domain, index) => {
          const delta = todayDeltas[index] ?? 0;
          const deltaLabel = delta > 0 ? `+${delta}` : `${delta}`;
          return `
            <div class="domain-control">
              <div>
                <span>${domain}</span>
                <p class="domain-hint">Today's net change: ${deltaLabel}</p>
              </div>
              <div class="score-buttons">
                <button class="btn-minus" type="button" onclick="updateRadarScore(${widgetId}, ${index}, -1)">-1</button>
                <button class="btn-plus" type="button" onclick="updateRadarScore(${widgetId}, ${index}, 1)">+1</button>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderBarWidget(graphId, widget) {
  const series = widget.series || { labels: [], values: [] };
  const trace = {
    x: series.labels,
    y: series.values,
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
      xaxis: { title: "Last 30 days", type: "category" },
      yaxis: { title: yAxisTitle },
      bargap: 0.35,
    },
    {
      responsive: true,
      displayModeBar: false,
    },
  );
}

function renderBarActions(widgetId, config, todayEntry) {
  const actionsEl = document.getElementById(`widget-actions-${widgetId}`);
  const unitLabel = config.unit ? ` (${config.unit})` : "";
  const buttonLabel = todayEntry ? "Update Today" : "Add Today";
  const inputValue = todayEntry ? todayEntry.value : "";

  actionsEl.innerHTML = `
    <div class="daily-note">You can only create or update today's bar. Past days lock after midnight.</div>
    <form class="bar-entry-form" onsubmit="submitBarEntry(event, ${widgetId})">
      <label for="bar-input-${widgetId}">Today's ${config.metric_name}${unitLabel}</label>
      <div class="bar-entry-row">
        <input id="bar-input-${widgetId}" type="number" min="0" step="0.5" placeholder="Enter today's value" value="${inputValue}" />
        <button class="btn-plus" type="submit">${buttonLabel}</button>
      </div>
    </form>
  `;
}

function formatPieValue(hours, unitMode) {
  if (unitMode === "minutes") {
    const totalMinutes = Math.round(hours * 60);
    const displayHours = Math.floor(totalMinutes / 60);
    const displayMinutes = totalMinutes % 60;
    return `${displayHours}h ${displayMinutes.toString().padStart(2, "0")}m`;
  }

  return `${Number.parseFloat(hours || 0).toFixed(2)}`;
}

function formatPieInputValue(hours, unitMode) {
  if (unitMode === "minutes") {
    const totalMinutes = Math.round((hours || 0) * 60);
    const displayHours = Math.floor(totalMinutes / 60);
    const displayMinutes = totalMinutes % 60;
    return totalMinutes === 0 ? "" : `${displayHours.toString().padStart(2, "0")}:${displayMinutes.toString().padStart(2, "0")}`;
  }

  return hours ? `${hours}` : "";
}

function parsePieInputValue(rawValue, unitMode) {
  const value = (rawValue || "").trim();
  if (!value) {
    return 0;
  }

  if (unitMode !== "minutes") {
    return Number.parseFloat(value);
  }

  const match = value.match(/^(\d{1,2}):([0-5]\d)$/);
  if (!match) {
    return Number.NaN;
  }

  const hours = Number.parseInt(match[1], 10);
  const minutes = Number.parseInt(match[2], 10);

  return hours + minutes / 60;
}

function renderPieWidget(graphId, widget) {
  const plot = widget.plot || { labels: [], values: [], colors: [], has_entries: false };
  const graphEl = document.getElementById(graphId);

  if (!plot.has_entries) {
    Plotly.purge(graphEl);
    graphEl.innerHTML = `
      <div class="pie-empty-state">
        <strong>No entries for today yet</strong>
        <p>Enter this day's activities to display the pie chart.</p>
      </div>
    `;
    return;
  }

  Plotly.purge(graphEl);
  graphEl.innerHTML = "";

  const categoryCount = widget.config.categories.length;
  const pull = plot.labels.map((_, index) => (index === categoryCount ? 0.06 : 0));

  Plotly.react(
    graphId,
    [
      {
        type: "pie",
        labels: plot.labels,
        values: plot.values,
        hole: 0.4,
        pull,
        sort: false,
        marker: {
          colors: plot.colors,
          line: { color: "#ffffff", width: 2 },
        },
        textinfo: "label+percent",
        hovertemplate: "%{label}<br>%{value:.2f} hours (%{percent})<extra></extra>",
      },
    ],
    {
      margin: { t: 20, r: 20, b: 20, l: 20 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      showlegend: true,
      legend: {
        x: 1,
        y: 0.5,
        font: { size: 12 },
      },
      font: {
        family: "Georgia, Times New Roman, serif",
        size: 14,
        color: "#333",
      },
    },
    {
      responsive: true,
      displayModeBar: false,
    },
  );
}

function renderPieActions(widgetId, widget) {
  const actionsEl = document.getElementById(`widget-actions-${widgetId}`);
  const categories = widget.config.categories || [];
  const unitMode = widget.config.unit_mode || "numbers";
  const todayEntries = widget.today_entries || [];
  const trackedLabel = formatPieValue(widget.plot.total_tracked || 0, unitMode);
  const wastedLabel = formatPieValue(widget.plot.wasted_hours || 0, unitMode);
  const helperText =
    unitMode === "minutes"
      ? "Enter today's durations in hours and minutes. The built-in field cursor moves by 5 minutes."
      : "Enter today's values. The total day cannot exceed 24 hours.";
  const inputPlaceholder = unitMode === "minutes" ? "Example: 1:30" : "Enter today's value";

  actionsEl.innerHTML = `
    <div class="daily-note">Each day starts blank. Enter this day's activities to build the pie chart.</div>
    <div class="wasted-highlight">
      <span>Wasted Time</span>
      <strong>${wastedLabel}</strong>
      <small>${trackedLabel} tracked today</small>
    </div>
    <form class="pie-entry-form" onsubmit="submitPieEntry(event, ${widgetId})">
      <p class="field-help">${helperText}</p>
      ${categories
        .map((category, index) => {
          const hours = todayEntries[index] ?? "";
          if (unitMode === "minutes") {
            return `
              <label class="field-label" for="pie-input-${widgetId}-${index}">${category}</label>
              <input
                id="pie-input-${widgetId}-${index}"
                type="time"
                min="00:00"
                max="23:55"
                step="300"
                placeholder="${inputPlaceholder}"
                value="${formatPieInputValue(hours, unitMode)}"
              />
            `;
          }

          return `
            <label class="field-label" for="pie-input-${widgetId}-${index}">${category}</label>
            <input
              id="pie-input-${widgetId}-${index}"
              type="number"
              min="0"
              max="24"
              step="0.25"
              placeholder="${inputPlaceholder}"
              value="${formatPieInputValue(hours, unitMode)}"
            />
          `;
        })
        .join("")}
      <button class="btn-plus pie-save-button" type="submit">Save Today</button>
    </form>
    <form class="pie-add-domain-form" onsubmit="submitPieCategory(event, ${widgetId})">
      <label class="field-label" for="pie-new-category-${widgetId}">Add a new activity</label>
      <div class="bar-entry-row">
        <input id="pie-new-category-${widgetId}" type="text" placeholder="Example: Studying" />
        <button class="btn-secondary" type="submit">Add</button>
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
    widget.config.today_deltas = data.today_deltas;

    renderRadarWidget(`widget-graph-${widgetId}`, widget);
    renderRadarActions(widget.id, widget.config.domains, widget.config.today_deltas);
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

  const widget = dashboardWidgets.find((item) => item.id === widgetId);
  if (!widget) {
    return;
  }

  const method = widget.today_entry ? "PUT" : "POST";

  try {
    const data = await fetchJson(`/widgets/${widgetId}/bar/entry`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });

    Object.assign(widget, data.widget);
    renderBarWidget(`widget-graph-${widgetId}`, widget);
    renderBarActions(widget.id, widget.config, widget.today_entry);
  } catch (error) {
    alert(error.message);
  }
}

async function submitPieEntry(event, widgetId) {
  event.preventDefault();

  const widget = dashboardWidgets.find((item) => item.id === widgetId);
  if (!widget) {
    return;
  }

  const unitMode = widget.config.unit_mode || "numbers";
  const hours = widget.config.categories.map((_, index) => {
    const input = document.getElementById(`pie-input-${widgetId}-${index}`);
    return parsePieInputValue(input.value, unitMode);
  });

  if (hours.some((value) => Number.isNaN(value) || value < 0)) {
    alert("Please enter valid values.");
    return;
  }

  const total = hours.reduce((sum, value) => sum + value, 0);
  if (total > 24) {
    alert("Tracked time cannot exceed 24 hours.");
    return;
  }

  try {
    await fetchJson(`/widgets/${widgetId}/pie/entry`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hours }),
    });

    await loadDashboard();
  } catch (error) {
    alert(error.message);
  }
}

async function submitPieCategory(event, widgetId) {
  event.preventDefault();

  const input = document.getElementById(`pie-new-category-${widgetId}`);
  const category = input.value.trim();
  if (!category) {
    alert("Please enter a new activity name.");
    return;
  }

  const widget = dashboardWidgets.find((item) => item.id === widgetId);
  if (!widget) {
    return;
  }

  try {
    await fetchJson(`/widgets/${widgetId}/pie/category`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category }),
    });

    await loadDashboard();
  } catch (error) {
    alert(error.message);
  }
}

async function removeWidget(widgetId) {
  const widget = dashboardWidgets.find((item) => item.id === widgetId);
  if (!widget) {
    return;
  }

  const confirmed = window.confirm(`Are you sure you want to remove "${widget.title}"? This will delete its saved data.`);
  if (!confirmed) {
    return;
  }

  try {
    await fetchJson(`/widgets/${widgetId}`, {
      method: "DELETE",
    });
    dashboardWidgets = dashboardWidgets.filter((item) => item.id !== widgetId);
    renderDashboard();
  } catch (error) {
    alert(error.message);
  }
}

function openAddWidgetModal() {
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
      <label class="type-option">
        <input type="radio" name="widgetType" value="pie" />
        <span>Pie chart</span>
        <small>Track this day's time distribution.</small>
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

  if (widgetType === "pie") {
    widgetFormContentEl.innerHTML = `
      <label class="field-label" for="widget-title">Graphic title</label>
      <input id="widget-title" name="title" type="text" placeholder="Optional title for this pie chart" />

      <label class="field-label" for="pie-categories">Activities</label>
      <textarea
        id="pie-categories"
        name="categories"
        rows="5"
        placeholder="Enter activities separated by commas. Example: Work, Transport, Sleep, Cooking"
      ></textarea>
      <p class="field-help">You will still be able to add new activities later from the widget.</p>

      <label class="field-label">Input style</label>
      <div class="type-grid compact-grid">
        <label class="type-option">
          <input type="radio" name="pieUnitMode" value="numbers" checked />
          <span>Numbers</span>
          <small>Use decimal values such as 7.5 hours.</small>
        </label>
        <label class="type-option">
          <input type="radio" name="pieUnitMode" value="minutes" />
          <span>Minutes</span>
          <small>Use sliders with 5-minute steps.</small>
        </label>
      </div>
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
    title: document.getElementById("widget-title")?.value.trim() || "",
  };

  if (widgetType === "radar") {
    const rawDomains = document.getElementById("radar-domains").value;
    payload.domains = rawDomains.split(",").map((domain) => domain.trim());
  } else if (widgetType === "bar") {
    payload.metric_name = document.getElementById("metric-name").value.trim();
    payload.unit = document.getElementById("metric-unit").value.trim();
  } else if (widgetType === "pie") {
    const rawCategories = document.getElementById("pie-categories").value;
    payload.categories = rawCategories.split(",").map((category) => category.trim());
    payload.unit_mode = widgetFormEl.querySelector('input[name="pieUnitMode"]:checked')?.value || "numbers";
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
