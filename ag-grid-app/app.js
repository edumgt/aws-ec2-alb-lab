// API 기본 주소는 config.js(window.APP_CONFIG.apiBase)에서 읽습니다.
const BE_API = ((window.APP_CONFIG && window.APP_CONFIG.apiBase) || "").replace(/\/$/, "");
const numberFormatter = new Intl.NumberFormat("ko-KR");
const priceFormatter = (params) => params.value == null ? "-" : numberFormatter.format(Number(params.value));
const percentFormatter = (params) => params.value == null ? "-" : `${Number(params.value).toFixed(2)}%`;

const columnDefs = [
  { headerName: "날짜", field: "trade_date", minWidth: 120, pinned: "left", sort: "desc" },
  { headerName: "종목코드", field: "symbol", minWidth: 110 },
  { headerName: "종목명", field: "company_name", minWidth: 140 },
  { headerName: "시가", field: "open_price", minWidth: 110, valueFormatter: priceFormatter, filter: "agNumberColumnFilter" },
  { headerName: "고가", field: "high_price", minWidth: 110, valueFormatter: priceFormatter, filter: "agNumberColumnFilter" },
  { headerName: "저가", field: "low_price", minWidth: 110, valueFormatter: priceFormatter, filter: "agNumberColumnFilter" },
  { headerName: "종가", field: "close_price", minWidth: 110, valueFormatter: priceFormatter, filter: "agNumberColumnFilter" },
  { headerName: "거래량", field: "volume", minWidth: 140, valueFormatter: priceFormatter, filter: "agNumberColumnFilter" },
  { headerName: "등락률", field: "change_rate_pct", minWidth: 110, valueFormatter: percentFormatter },
  { headerName: "외국인 보유율", field: "foreign_ownership_pct", minWidth: 140, valueFormatter: percentFormatter },
];

const gridApi = agGrid.createGrid(document.getElementById("ohlcvGrid"), {
  rowData: [], columnDefs,
  defaultColDef: { flex: 1, sortable: true, filter: true, floatingFilter: true, resizable: true },
  animateRows: true, pagination: true, paginationPageSize: 20, paginationPageSizeSelector: [20, 50, 100],
});

const searchForm = document.getElementById("searchForm");
const stockSearch = document.getElementById("stockSearch");
const startDate = document.getElementById("startDate");
const endDate = document.getElementById("endDate");
const statusMessage = document.getElementById("statusMessage");
const symbolsByCode = new Map();
let symbols = [];

function setStatus(message, type = "") {
  statusMessage.textContent = message;
  statusMessage.className = `status-message ${type}`.trim();
}

function updateMetrics(rows) {
  const latest = rows.at(-1);
  document.getElementById("resultCount").textContent = String(rows.length);
  document.getElementById("lastClose").textContent = latest ? numberFormatter.format(latest.close_price) : "-";
  document.getElementById("totalVolume").textContent = numberFormatter.format(rows.reduce((sum, row) => sum + Number(row.volume || 0), 0));
}

function resolveSymbol(query) {
  const normalized = query.trim().toUpperCase();
  if (!normalized) return null;
  const directCode = normalized.split(" · ")[0];
  if (symbolsByCode.has(directCode)) return symbolsByCode.get(directCode);
  return symbols.find(({ symbol, company_name }) => symbol === normalized || company_name.toUpperCase() === normalized)
    || symbols.find(({ symbol, company_name }) => symbol.includes(normalized) || company_name.toUpperCase().includes(normalized));
}

async function loadOhlcv(symbolInfo) {
  if (startDate.value && endDate.value && startDate.value > endDate.value) {
    setStatus("시작일은 종료일보다 늦을 수 없습니다.", "is-error");
    return;
  }
  const params = new URLSearchParams({ limit: "1000" });
  if (startDate.value) params.set("start_date", startDate.value);
  if (endDate.value) params.set("end_date", endDate.value);
  setStatus(`${symbolInfo.company_name} (${symbolInfo.symbol}) 데이터를 불러오는 중입니다.`);
  try {
    const response = await fetch(`${BE_API}/api/v1/ohlcv/${encodeURIComponent(symbolInfo.symbol)}?${params}`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${response.status}`);
    }
    const rows = await response.json();
    gridApi.setGridOption("rowData", rows);
    updateMetrics(rows);
    document.getElementById("selectedStock").textContent = `${symbolInfo.company_name} (${symbolInfo.symbol})`;
    setStatus(`${rows.length}건의 일봉 데이터를 표시합니다.`, "is-success");
  } catch (error) {
    gridApi.setGridOption("rowData", []);
    updateMetrics([]);
    setStatus(`데이터를 불러오지 못했습니다: ${error.message}`, "is-error");
  }
}

async function loadSymbols() {
  try {
    const response = await fetch(`${BE_API}/api/v1/ohlcv/symbols`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    symbols = await response.json();
    symbols.forEach((item) => symbolsByCode.set(item.symbol.toUpperCase(), item));
    document.getElementById("stockOptions").replaceChildren(...symbols.map((item) => {
      const option = document.createElement("option");
      option.value = `${item.symbol} · ${item.company_name}`;
      option.label = `${item.company_name} (${item.first_trade_date} ~ ${item.last_trade_date})`;
      return option;
    }));
    if (!symbols.length) throw new Error("조회 가능한 종목이 없습니다.");
    stockSearch.value = `${symbols[0].symbol} · ${symbols[0].company_name}`;
    await loadOhlcv(symbols[0]);
  } catch (error) {
    setStatus(`종목 목록을 불러오지 못했습니다: ${error.message}`, "is-error");
  }
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const symbolInfo = resolveSymbol(stockSearch.value);
  if (!symbolInfo) {
    setStatus("종목명 또는 종목코드를 목록에서 선택하거나 정확히 입력해 주세요.", "is-error");
    return;
  }
  stockSearch.value = `${symbolInfo.symbol} · ${symbolInfo.company_name}`;
  loadOhlcv(symbolInfo);
});

document.getElementById("resetFilters").addEventListener("click", () => {
  startDate.value = "";
  endDate.value = "";
  const symbolInfo = resolveSymbol(stockSearch.value) || symbols[0];
  if (symbolInfo) loadOhlcv(symbolInfo);
});

loadSymbols();
