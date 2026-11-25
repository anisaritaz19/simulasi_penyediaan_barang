const $ = (id) => document.getElementById(id);
let lastResult = null;

/* ---- tampilan form menurut mode ---- */
function syncMode() {
  const mode = document.querySelector('input[name="mode"]:checked').value;
  ["policy", "historical", "manual"].forEach((m) => {
    document.querySelectorAll(".mode-" + m).forEach((el) => {
      const visible = m === mode || [...el.classList].some((c) => c === "mode-" + mode);
      el.classList.toggle("d-none", !visible);
    });
  });
}
document.querySelectorAll('input[name="mode"]').forEach((r) => r.addEventListener("change", syncMode));

function defaultStart() {
  const end = new Date(META.date_max + "T00:00:00Z");
  end.setUTCDate(end.getUTCDate() - (Number($("horizon").value) - 1));
  return end.toISOString().slice(0, 10);
}

function payload() {
  const v = (id) => $(id).value.trim();
  return {
    store: v("store"), item: v("item"),
    category: $("category") ? v("category") : "all",
    start_date: v("start_date"), horizon: v("horizon"),
    initial_stock: v("initial_stock"),
    mode: document.querySelector('input[name="mode"]:checked').value,
    lead_time: v("lead_time"), service_level: v("service_level"), cover_days: v("cover_days"),
    adaptive: $("adaptive").checked,
    manual_inflow: v("manual_inflow"), custom_pct: v("custom_pct"),
  };
}

/* ---- render hasil ---- */
const colorOf = (s) => COLORS[s.key] || COLORS.custom;
const dashOf = (i) => [[], [7, 4], [2, 3], [10, 3, 2, 3]][i] || [];

function renderSummary(r) {
  const p = r.params;
  const modeName = { policy: "kebijakan (s, S)", historical: "historis dari data", manual: "manual" }[p.mode];
  $("run-summary").textContent =
    `Periode ${p.start_date} s.d. ${p.end_date} (${p.horizon} hari). Stok awal ${fmt(p.initial_stock)} unit (${p.initial_source}). ` +
    `Barang masuk: ${modeName}` +
    (p.mode === "manual" ? `, ${fmt(p.manual_inflow)} unit/hari.` : `, lead time ${p.lead_time} hari.`) +
    (p.mode === "policy" ? ` Dihitung dari ${fmt(r.history.n_days)} hari riwayat: rata-rata ${fmt(r.history.mu)} unit/hari, simpangan baku ${fmt(r.history.sigma)}.` : "");
  $("insights").innerHTML = r.insights.map((t) => `<li>${t}</li>`).join("");
}

function renderStock(r) {
  const base = r.scenarios[0];
  const ds = r.scenarios.map((s, i) => ({
    label: s.label, data: s.series.stock, borderColor: colorOf(s), backgroundColor: colorOf(s),
    borderWidth: 2, pointRadius: 0, tension: 0.1, borderDash: dashOf(i),
  }));
  if (r.params.mode === "policy") {
    if (r.params.adaptive) {
      $("stock-note").textContent = "Pengadaan adaptif aktif: s dan S berbeda untuk tiap skenario (lihat tabel).";
    } else {
      const s = base.levels.reorder_point;
      ds.push({ label: "Titik pesan ulang (s)", data: r.dates.map(() => s), borderColor: "#7a8795",
                borderWidth: 1.2, borderDash: [3, 3], pointRadius: 0 });
      $("stock-note").textContent = `Garis abu-abu: titik pesan ulang s = ${fmt(s)} unit; level order-up-to S = ${fmt(base.levels.order_up_to)} unit.`;
    }
  } else {
    $("stock-note").textContent = "";
  }
  drawChart("c-stock", {
    type: "line", data: { labels: r.dates, datasets: ds },
    options: { interaction: { mode: "index", intersect: false },
      scales: { x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } }, y: { min: 0, title: { display: true, text: "stok (unit)" } } } },
  });
}

function renderKpiTable(r) {
  const rows = [
    ["Total permintaan (unit)", (k) => fmt(k.total_demand)],
    ["Penjualan terpenuhi (unit)", (k) => fmt(k.total_sales)],
    ["Permintaan tak terpenuhi (unit)", (k) => `<span class="${k.total_unmet ? "tag-bad" : ""}">${fmt(k.total_unmet)}</span>`],
    ["Fill rate (%)", (k) => `<span class="${k.fill_rate < 95 ? "tag-bad" : "tag-ok"}">${fmt(k.fill_rate, 2)}</span>`],
    ["Hari stok habis", (k) => `<span class="${k.stockout_days ? "tag-bad" : ""}">${fmt(k.stockout_days)}</span>`],
    ["Hari pertama stok habis", (k) => (k.first_stockout_day ? fmt(k.first_stockout_day) : "-")],
    ["Total barang masuk (unit)", (k) => fmt(k.total_inflow)],
    ["Jumlah pesanan dibuat", (k) => fmt(k.orders_placed)],
    ["Stok rata-rata (unit)", (k) => fmt(k.avg_stock)],
    ["Stok minimum (unit)", (k) => fmt(k.min_stock)],
    ["Stok akhir (unit)", (k) => fmt(k.end_stock)],
    ["Cakupan stok rata-rata (hari)", (k) => fmt(k.days_of_cover, 2)],
  ];
  if (r.params.mode === "policy") {
    rows.push(["Titik pesan ulang s (unit)", null, (s) => fmt(s.levels.reorder_point)]);
    rows.push(["Level order-up-to S (unit)", null, (s) => fmt(s.levels.order_up_to)]);
  }
  const head = `<thead><tr><th scope="col">Indikator</th>${r.scenarios.map((s) =>
    `<th scope="col"><span class="swatch" style="background:${colorOf(s)}"></span>${s.label}</th>`).join("")}</tr></thead>`;
  const body = rows.map(([name, f, g]) =>
    `<tr><th scope="row" class="fw-normal">${name}</th>${r.scenarios.map((s) => `<td>${g ? g(s) : f(s.kpi)}</td>`).join("")}</tr>`).join("");
  $("kpi-table").innerHTML = head + `<tbody>${body}</tbody>`;
}

function renderSideCharts(r) {
  const last = r.scenarios[r.scenarios.length - 1];
  const ds = r.scenarios.map((s, i) => ({
    label: s.label, data: s.series.demand, borderColor: colorOf(s), borderWidth: 1.4, pointRadius: 0, borderDash: dashOf(i),
  }));
  ds.push({ label: `Terpenuhi (${last.label})`, data: last.series.sales, borderColor: "#1d2733",
            borderWidth: 1.2, pointRadius: 0, borderDash: [1, 2] });
  drawChart("c-demand", {
    type: "line", data: { labels: r.dates, datasets: ds },
    options: { scales: { x: { ticks: { maxTicksLimit: 5, maxRotation: 0 } }, y: { title: { display: true, text: "unit/hari" } } },
               plugins: { legend: { position: "bottom", labels: { font: { size: 10 }, boxWidth: 6 } } } },
  });
  drawChart("c-kpi", {
    type: "bar",
    data: { labels: r.scenarios.map((s) => s.label.replace("Permintaan ", "")), datasets: [
      { label: "Fill rate (%)", data: r.scenarios.map((s) => s.kpi.fill_rate), backgroundColor: COLORS.baseline, yAxisID: "y" },
      { label: "Hari stok habis", data: r.scenarios.map((s) => s.kpi.stockout_days), backgroundColor: COLORS.plus50, yAxisID: "y2" },
    ] },
    options: { scales: {
      x: { ticks: { autoSkip: false, maxRotation: 0, font: { size: 10 } } },
      y: { min: 0, max: 100, title: { display: true, text: "fill rate (%)" } },
      y2: { position: "right", beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: "hari" } } },
      plugins: { legend: { position: "bottom" } } },
  });
}

function renderDaily() {
  const r = lastResult;
  const s = r.scenarios[Number($("daily-scn").value)];
  const head = `<thead><tr><th>Hari</th><th>Tanggal</th><th>Permintaan</th><th>Barang masuk</th><th>Penjualan</th><th>Tak terpenuhi</th><th>Stok akhir</th><th>Pesanan dibuat</th></tr></thead>`;
  const body = r.dates.map((d, i) =>
    `<tr><td>${i + 1}</td><td>${d}</td><td>${fmt(s.series.demand[i])}</td><td>${fmt(s.series.inflow[i])}</td>` +
    `<td>${fmt(s.series.sales[i])}</td><td>${fmt(s.series.unmet[i])}</td><td>${fmt(s.series.stock[i])}</td><td>${fmt(s.series.order[i])}</td></tr>`).join("");
  $("daily-table").innerHTML = head + `<tbody>${body}</tbody>`;
}

function downloadCsv() {
  const r = lastResult;
  const lines = ["skenario,hari,tanggal,permintaan,barang_masuk,penjualan,tak_terpenuhi,stok_akhir,pesanan_dibuat"];
  r.scenarios.forEach((s) => r.dates.forEach((d, i) => lines.push([
    `"${s.label}"`, i + 1, d, s.series.demand[i], s.series.inflow[i], s.series.sales[i],
    s.series.unmet[i], s.series.stock[i], s.series.order[i]].join(","))));
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "hasil_simulasi_persediaan.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

function render(r) {
  lastResult = r;
  $("placeholder").classList.add("d-none");
  $("out").classList.remove("d-none");
  renderSummary(r); renderStock(r); renderKpiTable(r); renderSideCharts(r);
  $("daily-scn").innerHTML = r.scenarios.map((s, i) => `<option value="${i}">${s.label}</option>`).join("");
  renderDaily();
}

async function run(ev) {
  if (ev) ev.preventDefault();
  const err = $("form-error"), btn = $("run-btn");
  err.classList.add("d-none");
  btn.disabled = true; btn.textContent = "Menghitung...";
  try {
    render(await api("/api/simulate", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()),
    }));
  } catch (e) {
    err.textContent = e.message; err.classList.remove("d-none");
    $("placeholder").textContent = "Simulasi belum dapat dijalankan. Periksa input di sebelah kiri.";
  } finally {
    btn.disabled = false; btn.textContent = "Jalankan simulasi";
  }
}

$("sim-form").addEventListener("submit", run);
$("daily-scn").addEventListener("change", renderDaily);
$("csv-btn").addEventListener("click", downloadCsv);
$("start_date").value = defaultStart();
$("horizon").addEventListener("change", () => { $("start_date").value = defaultStart(); });
syncMode();
run();
