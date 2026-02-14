// ====== RADAR CHART FUNCTIONS ======

async function checkStatus() {
  const res = await fetch("/status");
  const data = await res.json();

  if (data.initialized) {
    document.getElementById("setup").style.display = "none";
    document.getElementById("app").style.display = "block";
    document.getElementById("hours-section").style.display = "block";

    loadGraph();
    loadHoursData();
  } else {
    document.getElementById("setup").style.display = "block";
    document.getElementById("app").style.display = "none";
    document.getElementById("hours-section").style.display = "none";
  }
}

async function initApp() {
  const input = document.getElementById("domainInput").value;
  const domains = input.split(",").map((d) => d.trim());

  if (domains.length === 0 || domains[0] === "") {
    alert("Please enter at least one domain!");
    return;
  }

  const res = await fetch("/init", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domains }),
  });

  const data = await res.json();

  document.getElementById("setup").style.display = "none";
  document.getElementById("app").style.display = "block";
  document.getElementById("hours-section").style.display = "block";

  updateGraph(data);
  loadHoursData();
}

async function loadGraph() {
  const res = await fetch("/get-data");
  const data = await res.json();
  updateGraph(data);
}

function updateGraph(data) {
  const plotData = [
    {
      type: "scatterpolar",
      r: data.r,
      theta: data.theta,
      fill: "toself",
      marker: { color: "rgb(106, 168, 79)", size: 10 },
      line: { color: "rgb(106, 168, 79)", width: 3 },
      fillcolor: "rgba(106, 168, 79, 0.3)",
    },
  ];

  const layout = {
    polar: {
      radialaxis: { visible: true, range: [0, 100] },
    },
    showlegend: false,
  };

  Plotly.react("graph", plotData, layout, { responsive: true });

  // Populate modal controls
  const controlsDiv = document.getElementById("modal-controls");
  controlsDiv.innerHTML = "";

  data.theta.forEach((domain, i) => {
    const div = document.createElement("div");
    div.className = "domain-control";
    div.innerHTML = `
      <h3>${domain}</h3>
      <button class="btn-minus" onclick="updateScore(${i}, -1)">-1</button>
      <button class="btn-plus" onclick="updateScore(${i}, +1)">+1</button>
    `;
    controlsDiv.appendChild(div);
  });
}

async function updateScore(index, change) {
  const res = await fetch("/update-score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ index, change }),
  });

  const data = await res.json();
  updateGraph(data);
}

function closeModal() {
  document.getElementById("modal").style.display = "none";
}

document.getElementById("openModalBtn")?.addEventListener("click", () => {
  document.getElementById("modal").style.display = "flex";
});

window.onclick = (e) => {
  const modal = document.getElementById("modal");
  if (e.target === modal) {
    modal.style.display = "none";
  }
};



// ====== HOURS TRACKING FUNCTIONS (Bar Chart) ======

async function loadHoursData() {
  const res = await fetch("/get-hours");
  const data = await res.json();

  updateHoursGraph(data);
  // updateHoursTable(data);
}

function updateHoursGraph(data) {
  if (data.length === 0) {
    document.getElementById("hours-graph").innerHTML =
      "<p style='text-align: center; color: #666;'>No data yet. Add your first entry above!</p>";
    return;
  }

  const dates = data.map((entry) => entry.date);
  const workHours = data.map((entry) => entry.work_hours);
  const studyHours = data.map((entry) => entry.study_hours);

  const trace1 = {
    x: dates,
    y: workHours,
    name: "Work Hours",
    type: "bar",
    marker: { color: "##ffa500" },
  };

  // const trace2 = {
  //   x: dates,
  //   y: studyHours,
  //   name: 'Study Hours',
  //   type: 'bar',
  //   marker: { color: '#2196F3' }
  // };

  const layout = {
    barmode: "group",
    xaxis: { title: "Date" },
    yaxis: { title: "Hours" },
    margin: { t: 20 },
  };

  Plotly.newPlot("hours-graph", [trace1], layout, { responsive: true });
}

// function updateHoursTable(data) {
//   const tbody = document.getElementById('hours-table-body');
//   tbody.innerHTML = '';

//   if (data.length === 0) {
//     tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No entries yet</td></tr>';
//     return;
//   }

//   data.forEach(entry => {
//     const row = `
//       <tr>
//         <td>${entry.date}</td>
//         <td>${entry.work_hours}</td>
//         <td>
//           <button class="delete-btn" onclick="deleteHoursEntry(${entry.id})">Delete</button>
//         </td>
//       </tr>
//     `;
//     tbody.innerHTML += row;
//   });
// }

async function addHoursEntry() {
  const workHours = parseFloat(
    document.getElementById("work-hours-input").value,
  );
  // const studyHours = parseFloat(document.getElementById('study-hours-input').value);

  if (
    isNaN(workHours) ||
    // isNaN(studyHours) ||
    workHours < 0 
    // studyHours < 0
  ) {
    alert("Please enter valid hours (positive numbers)");
    return;
  }

  const res = await fetch("/add-hours", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // body: JSON.stringify({ work_hours: workHours, study_hours: studyHours }),
    body: JSON.stringify({ work_hours: workHours}),

  });

  if (res.ok) {
    // Clear inputs
    document.getElementById("work-hours-input").value = "";
    // document.getElementById('study-hours-input').value = '';

    // Reload data
    loadHoursData();
  }
}

async function deleteHoursEntry(id) {
  if (!confirm("Delete this entry?")) return;

  await fetch(`/delete-hours/${id}`, { method: "DELETE" });
  loadHoursData();
}

// ====== INITIALIZE ON PAGE LOAD ======
checkStatus();
