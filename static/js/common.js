/* Utilitas bersama: format angka, fetch JSON, warna, default Chart.js */
const fmt = (n, d = 0) =>
  n === null || n === undefined || Number.isNaN(n)
    ? "-" : Number(n).toLocaleString("id-ID", { maximumFractionDigits: d, minimumFractionDigits: d });

const COLORS = {
  baseline: "#2f5d8a", plus20: "#b87409", plus50: "#b3372f", custom: "#2e7d5b",
  sold: "#2f5d8a", ordered: "#b87409", inventory: "#2e7d5b", grid: "#e3e7ec", text: "#5c6877",
};

async function api(url, options) {
  const res = await fetch(url, options);
  let body = null;
  try { body = await res.json(); } catch (e) { /* respons bukan JSON */ }
  if (!res.ok) throw new Error((body && body.error) || `Permintaan gagal (${res.status}).`);
  return body;
}

if (window.Chart) {
  Chart.defaults.font.family = '"Segoe UI", system-ui, -apple-system, Arial, sans-serif';
  Chart.defaults.color = COLORS.text;
  Chart.defaults.borderColor = COLORS.grid;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.locale = "id-ID";
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
}

/* Buat ulang chart pada canvas yang sama tanpa kebocoran memori */
const charts = {};
function drawChart(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
  return charts[id];
}
