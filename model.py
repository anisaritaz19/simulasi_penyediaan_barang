"""Model Sistem Dinamik (Stock and Flow) pengelolaan persediaan barang.

Persamaan dasar (langkah waktu = 1 hari):

    Stok(t+1)  = Stok(t) + Barang_Masuk(t) - Penjualan(t)
    Penjualan  = min(Permintaan(t), Stok(t) + Barang_Masuk(t))
    Permintaan = Permintaan_Data(t) x (1 + Perubahan_%)

Pengadaan (inflow) mengikuti salah satu dari tiga mode:
  policy     : kebijakan titik pemesanan ulang (s, S) dengan lead time
  historical : memakai Units Ordered pada data, tiba setelah lead time
  manual     : jumlah tetap per hari yang diinput pengguna
"""
import math
from statistics import NormalDist

SCENARIOS = [
    ("baseline", "Baseline (0%)", 0.0),
    ("plus20", "Permintaan +20%", 20.0),
    ("plus50", "Permintaan +50%", 50.0),
]
MODES = ("policy", "historical", "manual")


# ---------------------------------------------------------------- parameter
def parse_params(payload, data, meta):
    """Validasi input pengguna. Melempar ValueError dengan pesan yang jelas."""

    def num(key, default, lo, hi, label, integer=False):
        raw = payload.get(key)
        if raw in (None, ""):
            return default
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{label} harus berupa angka.")
        if math.isnan(val) or not (lo <= val <= hi):
            raise ValueError(f"{label} harus antara {lo:g} dan {hi:g}.")
        return int(round(val)) if integer else val

    p = {
        "store": str(payload.get("store") or "all"),
        "item": str(payload.get("item") or "all"),
        "category": str(payload.get("category") or "all"),
        "mode": str(payload.get("mode") or "policy"),
        "adaptive": bool(payload.get("adaptive", False)),
    }
    if p["store"] != "all" and p["store"] not in meta["stores"]:
        raise ValueError("Toko tidak ditemukan pada dataset.")
    if p["item"] != "all" and p["item"] not in meta["items"]:
        raise ValueError("Barang tidak ditemukan pada dataset.")
    if p["category"] != "all" and p["category"] not in meta["categories"]:
        raise ValueError("Kategori tidak ditemukan pada dataset.")
    if p["mode"] not in MODES:
        raise ValueError("Mode pengadaan tidak valid.")
    if p["mode"] == "historical" and not meta["has_orders"]:
        raise ValueError("Dataset ini tidak memiliki kolom Units Ordered; pilih mode lain.")

    p["horizon"] = num("horizon", 90, 7, 365, "Lama simulasi (hari)", integer=True)
    p["lead_time"] = num("lead_time", 2, 1, 30, "Lead time (hari)", integer=True)
    p["service_level"] = num("service_level", 95, 50, 99.9, "Tingkat layanan (%)")
    p["cover_days"] = num("cover_days", 3, 1, 60, "Cakupan pesanan (hari)", integer=True)
    p["initial_stock"] = num("initial_stock", None, 0, 1e9, "Stok awal")
    p["manual_inflow"] = num("manual_inflow", None, 0, 1e9, "Barang masuk per hari")
    p["custom_pct"] = num("custom_pct", None, -90, 300, "Perubahan permintaan kustom (%)")

    date_min = _ts(meta["date_min"])
    date_max = _ts(meta["date_max"])
    start_raw = payload.get("start_date")
    if start_raw:
        try:
            start = _ts(start_raw)
        except Exception:
            raise ValueError("Tanggal mulai tidak valid (format YYYY-MM-DD).")
    else:
        start = date_max - _days(p["horizon"] - 1)
    if start < date_min:
        raise ValueError(f"Tanggal mulai tidak boleh sebelum {meta['date_min']}.")
    if start + _days(p["horizon"] - 1) > date_max:
        raise ValueError(
            f"Periode simulasi melewati akhir data ({meta['date_max']}). "
            "Majukan tanggal mulai atau perpendek lama simulasi."
        )
    p["start"] = start
    return p


def _ts(value):
    import pandas as pd
    return pd.Timestamp(value)


def _days(n):
    import pandas as pd
    return pd.Timedelta(days=int(n))


# ---------------------------------------------------------------- simulasi
def simulate(data, p):
    daily = data.daily(p["store"], p["item"], p["category"])
    if daily.empty or daily["units_sold"].dropna().empty:
        raise ValueError("Tidak ada data untuk kombinasi filter tersebut.")
    sold = daily["units_sold"].interpolate().bfill().ffill()

    start, horizon, lt = p["start"], p["horizon"], p["lead_time"]
    window = sold.loc[start:start + _days(horizon - 1)]
    base_demand = [float(v) for v in window.values]
    dates = [d.strftime("%Y-%m-%d") for d in window.index]

    # Statistik permintaan harian dari riwayat SEBELUM periode simulasi
    # (agar tidak "mengintip" masa depan); jika riwayat < 30 hari pakai seluruh data.
    history = sold.loc[:start - _days(1)]
    if len(history) < 30:
        history = sold
    mu = float(history.mean())
    sigma = float(history.std(ddof=0))
    z = NormalDist().inv_cdf(p["service_level"] / 100.0)

    # Stok awal: Inventory Level aktual pada tanggal mulai (jika ada)
    cover = p["cover_days"]
    default_policy = policy_levels(mu, sigma, lt, z, cover)
    initial = p["initial_stock"]
    initial_source = "input pengguna"
    if initial is None:
        inv = daily["inventory"].reindex([start]).iloc[0] if data.has_inventory else float("nan")
        if inv == inv:
            initial, initial_source = float(inv), "Inventory Level aktual pada tanggal mulai"
        else:
            initial = default_policy["order_up_to"]
            initial_source = "asumsi: sebesar level order-up-to (S)"

    manual_inflow = p["manual_inflow"]
    if manual_inflow is None:
        manual_inflow = round(mu)

    orders_hist = None
    if p["mode"] == "historical":
        o = daily["units_ordered"].interpolate().bfill().ffill()
        orders_hist = [float(v) for v in o.loc[start:start + _days(horizon - 1)].values]
        prior = o.loc[:start - _days(1)].tail(lt)
        prior = [float(v) for v in prior.values] if len(prior) == lt else [float(o.mean())] * lt
    else:
        prior = [mu] * lt  # kondisi tunak: pesanan sebelum simulasi ~ permintaan rata-rata

    scenarios = [(k, lbl, pct) for k, lbl, pct in SCENARIOS]
    if p["custom_pct"] is not None and p["custom_pct"] not in (0, 20, 50):
        scenarios.append(("custom", f"Permintaan {p['custom_pct']:+g}% (kustom)", p["custom_pct"]))

    results = []
    for key, label, pct in scenarios:
        f = 1 + pct / 100.0
        demand = [round(v * f) for v in base_demand]
        if p["adaptive"]:
            levels = policy_levels(mu * f, sigma * f, lt, z, cover)
        else:
            levels = default_policy
        rows = run_stock_flow(
            demand, initial, p["mode"], lt, levels["reorder_point"], levels["order_up_to"],
            manual_inflow, orders_hist, prior,
        )
        results.append({
            "key": key, "label": label, "pct": pct,
            "levels": {k: round(v, 1) for k, v in levels.items()},
            "kpi": summarize(rows),
            "series": {
                "demand": [r["demand"] for r in rows],
                "inflow": [round(r["inflow"], 1) for r in rows],
                "sales": [r["sales"] for r in rows],
                "unmet": [r["unmet"] for r in rows],
                "stock": [round(r["stock"], 1) for r in rows],
                "order": [round(r["order"], 1) for r in rows],
            },
        })

    return {
        "dates": dates,
        "params": {
            "store": p["store"], "item": p["item"], "category": p["category"],
            "mode": p["mode"], "adaptive": p["adaptive"], "horizon": horizon,
            "start_date": dates[0], "end_date": dates[-1], "lead_time": lt,
            "service_level": p["service_level"], "cover_days": cover,
            "initial_stock": round(initial, 1), "initial_source": initial_source,
            "manual_inflow": manual_inflow,
        },
        "history": {"mu": round(mu, 1), "sigma": round(sigma, 1), "z": round(z, 3),
                    "n_days": int(len(history))},
        "scenarios": results,
        "insights": build_insights(results, p),
    }


def policy_levels(mu, sigma, lead_time, z, cover_days):
    safety = z * sigma * math.sqrt(lead_time)
    rop = mu * lead_time + safety
    return {
        "mu": mu, "sigma": sigma, "safety_stock": safety,
        "reorder_point": rop, "order_up_to": rop + mu * cover_days,
    }


def run_stock_flow(demand, initial, mode, lead_time, rop, order_up_to,
                   manual_inflow, orders_hist, prior_orders):
    """Satu putaran simulasi Stock and Flow harian."""
    n = len(demand)
    arrivals = [0.0] * (n + lead_time + 2)
    # pesanan sebelum periode simulasi yang masih dalam perjalanan
    for k, qty in enumerate(prior_orders):  # prior_orders[k] dipesan (lead_time - k) hari lalu
        arrivals[k] += qty
    if mode == "manual":
        for t in range(n):
            arrivals[t] += manual_inflow

    stock, rows = float(initial), []
    for t in range(n):
        inflow = arrivals[t]
        available = stock + inflow
        sales = min(demand[t], available)
        stock = available - sales
        order = 0.0
        if mode == "policy":
            position = stock + sum(arrivals[t + 1:])
            if position <= rop:
                order = order_up_to - position
        elif mode == "historical":
            order = orders_hist[t]
        if order > 0:
            arrivals[t + lead_time] += order
        rows.append({"demand": demand[t], "inflow": inflow, "sales": sales,
                     "unmet": demand[t] - sales, "stock": stock, "order": order})
    return rows


def summarize(rows):
    n = len(rows)
    demand = sum(r["demand"] for r in rows)
    sales = sum(r["sales"] for r in rows)
    stockouts = [i for i, r in enumerate(rows) if r["unmet"] > 0]
    avg_stock = sum(r["stock"] for r in rows) / n
    return {
        "total_demand": round(demand),
        "total_sales": round(sales),
        "total_unmet": round(demand - sales),
        "fill_rate": round(100 * sales / demand, 2) if demand else 100.0,
        "stockout_days": len(stockouts),
        "first_stockout_day": stockouts[0] + 1 if stockouts else None,
        "total_inflow": round(sum(r["inflow"] for r in rows)),
        "orders_placed": sum(1 for r in rows if r["order"] > 0),
        "avg_stock": round(avg_stock),
        "min_stock": round(min(r["stock"] for r in rows)),
        "end_stock": round(rows[-1]["stock"]),
        "days_of_cover": round(avg_stock / (sales / n), 2) if sales else None,
    }


def _id(n):
    """Format angka gaya Indonesia: 1.234.567"""
    return f"{n:,}".replace(",", ".")


def build_insights(results, p):
    out = []
    base = results[0]["kpi"]
    for r in results[1:]:
        k = r["kpi"]
        txt = (f"{r['label']}: fill rate {k['fill_rate']:.1f}% "
               f"(baseline {base['fill_rate']:.1f}%), stok habis {k['stockout_days']} hari, "
               f"permintaan tak terpenuhi {_id(k['total_unmet'])} unit, "
               f"stok rata-rata {_id(k['avg_stock'])} unit.")
        if k["first_stockout_day"]:
            txt += f" Kehabisan stok pertama terjadi pada hari ke-{k['first_stockout_day']}."
        out.append(txt)
    if p["mode"] == "policy" and not p["adaptive"]:
        out.append("Parameter kebijakan (ROP dan S) dikunci pada kondisi baseline, sehingga "
                   "kenaikan permintaan tidak diikuti penyesuaian parameter. Aktifkan "
                   "\"Pengadaan adaptif\" untuk melihat dampak jika parameter disesuaikan.")
    return out
