const BE_API = "http://43.203.255.251:8000";

const statusRank = {
  Healthy: 0,
  Warning: 1,
  Critical: 2,
};

function currencyCompact(value) {
  return new Intl.NumberFormat("ko-KR").format(value);
}

function statusCellRenderer(params) {
  const status = params.value || "Healthy";
  const normalized = status.toLowerCase();
  return `<span class="status-pill is-${normalized}">${status}</span>`;
}

function progressCellRenderer(params) {
  const value = Number(params.value || 0);
  return `
    <div>
      <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:0.82rem;">
        <span>${value}%</span>
        <span style="color:#61708a;">deploy</span>
      </div>
      <div class="progress-track">
        <div class="progress-bar" style="width:${value}%"></div>
      </div>
    </div>
  `;
}

const columnDefs = [
  { headerName: "Service", field: "service", minWidth: 170, pinned: "left" },
  { headerName: "Region", field: "region", minWidth: 150 },
  { headerName: "Owner", field: "owner", minWidth: 130 },
  {
    headerName: "Status",
    field: "status",
    minWidth: 140,
    cellRenderer: statusCellRenderer,
    comparator: (a, b) => statusRank[a] - statusRank[b],
  },
  {
    headerName: "Deploy Progress",
    field: "progress",
    minWidth: 190,
    sort: "desc",
    cellRenderer: progressCellRenderer,
  },
  {
    headerName: "Instances",
    field: "instances",
    maxWidth: 130,
    filter: "agNumberColumnFilter",
  },
  {
    headerName: "Traffic / min",
    field: "traffic",
    minWidth: 140,
    valueFormatter: (params) => currencyCompact(params.value),
    filter: "agNumberColumnFilter",
  },
  {
    headerName: "Updated",
    field: "updatedAt",
    minWidth: 170,
  },
];

const gridOptions = {
  rowData: [],
  columnDefs,
  defaultColDef: {
    flex: 1,
    sortable: true,
    filter: true,
    floatingFilter: true,
    resizable: true,
  },
  animateRows: true,
  rowHeight: 74,
  pagination: true,
  paginationPageSize: 6,
  paginationPageSizeSelector: [6, 10, 20],
};

const gridElement = document.getElementById("serviceGrid");
const gridApi = agGrid.createGrid(gridElement, gridOptions);

function updateMetrics(rowData) {
  const activeServices = rowData.length;
  const avgProgress = rowData.length
    ? Math.round(rowData.reduce((sum, row) => sum + row.progress, 0) / rowData.length)
    : 0;
  const urgentItems = rowData.filter((row) => row.status !== "Healthy").length;

  document.getElementById("activeServices").textContent = String(activeServices);
  document.getElementById("avgProgress").textContent = `${avgProgress}%`;
  document.getElementById("urgentItems").textContent = String(urgentItems);
}

async function loadServices() {
  try {
    const response = await fetch(`${BE_API}/api/services`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    gridApi.setGridOption("rowData", data);
    updateMetrics(data);
  } catch (err) {
    console.error("서비스 데이터 로딩 실패:", err);
  }
}

function setStatusFilter(status) {
  if (status === "all") {
    gridApi.setFilterModel(null);
    return;
  }

  gridApi.setFilterModel({
    status: {
      filterType: "text",
      type: "equals",
      filter:
        status === "healthy"
          ? "Healthy"
          : status === "warning"
            ? "Warning"
            : "Critical",
    },
  });
}

document.getElementById("quickFilter").addEventListener("input", (event) => {
  gridApi.setGridOption("quickFilterText", event.target.value);
});

document.querySelectorAll("[data-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    document
      .querySelectorAll("[data-filter]")
      .forEach((chip) => chip.classList.remove("is-active"));
    button.classList.add("is-active");
    setStatusFilter(button.dataset.filter);
  });
});

document.getElementById("resetFilters").addEventListener("click", () => {
  document.getElementById("quickFilter").value = "";
  gridApi.setFilterModel(null);
  gridApi.setGridOption("quickFilterText", "");
  document
    .querySelectorAll("[data-filter]")
    .forEach((chip) => chip.classList.remove("is-active"));
  document.querySelector('[data-filter="all"]').classList.add("is-active");
});

loadServices();
