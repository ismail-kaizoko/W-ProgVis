// Global variables
let domains = [];

// Initialize the app when user submits domains
function initApp() {
  const input = document.getElementById("domainInput").value;

  domains = input
    .split(",")
    .map((d) => d.trim())
    .filter((d) => d.length > 0);

  if (domains.length < 3) {
    alert("Please enter at least 3 domains.");
    return;
  }

  document.getElementById("setup").style.display = "none";
  document.getElementById("app").style.display = "block";

  initServerData();
}

// Initialize data on the server
function initServerData() {
  fetch("/init", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domains: domains }),
  })
    .then((res) => res.json())
    .then((data) => updateGraph(data));
}

// Update the radar chart with new data
function updateGraph(data) {
  var plotData = [
    {
      type: "scatterpolar",
      r: data.r,
      theta: data.theta,
      fill: "toself",
      name: "Your Progress",
      marker: {
        color: "rgb(106, 168, 79)",
        size: 8,
      },
      line: {
        color: "rgb(106, 168, 79)",
        width: 2,
      },
    },
  ];

  var layout = {
    polar: {
      radialaxis: {
        visible: true,
        range: [0, 110],
      },
    },
    showlegend: false,
  };

  // Create or update the graph with animation
  Plotly.react("graph", plotData, layout);
}

// Update score for a specific domain
function updateScore(domainIndex, change) {
  // Send request to Flask backend
  fetch("/update-score", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      index: domainIndex,
      change: change,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      // Update the graph with new data
      updateGraph(data);
    });
}

// Modal Functions
function openModal() {
  document.getElementById("modal").style.display = "flex";
  generateModalControls();
}

function closeModal() {
  document.getElementById("modal").style.display = "none";
}

function generateModalControls() {
  const container = document.getElementById("modal-controls");
  container.innerHTML = "";

  domains.forEach((domain, index) => {
    const div = document.createElement("div");
    div.className = "modal-domain";

    div.innerHTML = `
            <span>${domain}</span>
            <div>
                <button onclick="updateScore(${index}, -1)">−</button>
                <button onclick="updateScore(${index}, 1)">+</button>
            </div>
        `;

    container.appendChild(div);
  });
}

// Event Listeners
document.getElementById("openModalBtn").addEventListener("click", openModal);

// Close modal when clicking outside of it
window.onclick = function (event) {
  const modal = document.getElementById("modal");
  if (event.target === modal) {
    closeModal();
  }
};
