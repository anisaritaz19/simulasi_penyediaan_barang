const $ = (id) => document.getElementById(id);
const filterIds = ["f-store", "f-category", "f-item"];

function query() {
  const q = new URLSearchParams();
  const map = { "f-store": "store", "f-category": "category", "f-item": "item" };
  filterIds.forEach((id) => { if ($(id)) q.set(map[id], $(id).value); });
  return q.toString();
}

function renderKpis(k) {
  const items = [
    ["Baris data", fmt(k.rows)],
    ["Jumlah hari", fmt(k.days)],
    ["Rata-rata penjualan/hari", fmt(k.avg_daily_sales), "unit"],
    ["Total penjualan", fmt(k.total_sales), "unit"],
  ];
  if (k.avg_daily_ordered !== undefined) {
    items.push(["Rata-rata pesanan/hari", fmt(k.avg_daily_ordered), "unit"]);
    items.push(["Pesanan / penjualan", fmt(k.order_to_sales, 1) + "%"]);
  }
  if (k.avg_inventory !== undefined) {
    items.push(["Rata-rata stok", fmt(k.avg_inventory), "unit"]);
    items.push(["Cakupan stok", fmt(k.days_of_cover, 2), "hari penjualan"]);
  }
  $("kpis").innerHTML = items.map(([t, v, u]) =>
    `<dl class="kpi mb-0"><dt>${t}</dt><dd>${v}${u ? ` <small>${u}</small>` : ""}</dd></dl>`).join("");
}

function line(label, data, color, dash) {
  return { label, data, borderColor: color, backgroundColor: color, borderWidth: 1.6,
           pointRadius: 0, tension: 0.1, borderDash: dash || [] };
}

async function load() {
  $("alert-box").innerHTML = "";
  try {
    const d = await api("/api/dashboard?" + query());
    renderKpis(d.kpi);

    const ds = [line("Penjualan (Units Sold)", d.daily.units_sold, COLORS.sold)];
    if (d.daily.units_ordered) ds.push(line("Pesanan (Units Ordered)", d.daily.units_ordered, COLORS.ordered, [6, 3]));
    if (d.daily.inventory) ds.push(line("Stok (Inventory Level)", d.daily.inventory, COLORS.inventory, [2, 2]));
    drawChart("c-daily", {
      type: "line",
      data: { labels: d.daily.dates, datasets: ds },
      options: { interaction: { mode: "index", intersect: false },
        scales: { x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } }, y: { beginAtZero: false, title: { display: true, text: "unit" } } } },
    });
    $("daily-note").textContent = d.daily.inventory
      ? "Stok di sini adalah Inventory Level yang tercatat pada data (jumlah seluruh toko/barang terpilih)."
      : "Dataset ini tidak memiliki kolom stok atau pesanan, sehingga hanya penjualan yang ditampilkan.";

    const last = d.daily.dates[d.daily.dates.length - 1];
    $("monthly-note").textContent = Number(last.slice(8)) < 28
      ? `Bulan terakhir (${last.slice(0, 7)}) hanya memuat data sampai tanggal ${Number(last.slice(8))}.` : "";
    drawChart("c-monthly", {
      type: "bar",
      data: { labels: d.monthly.labels, datasets: [{ label: "Penjualan", data: d.monthly.values, backgroundColor: COLORS.sold }] },
      options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { maxRotation: 60 } } } },
    });

    $("cat-col").classList.toggle("d-none", !d.by_category);
    if (d.by_category) {
      drawChart("c-category", {
        type: "bar",
        data: { labels: d.by_category.labels, datasets: [{ label: "Penjualan", data: d.by_category.values, backgroundColor: COLORS.sold }] },
        options: { indexAxis: "y", plugins: { legend: { display: false } } },
      });
    }

    drawChart("c-top", {
      type: "bar",
      data: { labels: d.top_items.labels, datasets: [{ label: "Penjualan", data: d.top_items.values, backgroundColor: COLORS.sold }] },
      options: { plugins: { legend: { display: false } } },
    });
  } catch (err) {
    $("alert-box").innerHTML = `<div class="alert alert-warning" role="alert">${err.message}</div>`;
  }
}

filterIds.forEach((id) => $(id) && $(id).addEventListener("change", load));
load();
