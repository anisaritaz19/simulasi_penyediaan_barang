"""Simulasi Sistem Dinamik Pengelolaan Persediaan Barang (Flask)."""
from flask import Flask, jsonify, render_template, request

from dataset import Data, load_dataset
from model import SCENARIOS, parse_params, simulate

app = Flask(__name__)
DATA = Data(load_dataset())
META = DATA.meta()


# ------------------------------------------------------------------ halaman
@app.route("/")
def dashboard():
    return render_template("dashboard.html", meta=META, page="dashboard")


@app.route("/model")
def model_page():
    return render_template("model.html", meta=META, page="model")


@app.route("/simulasi")
def simulasi():
    return render_template("simulasi.html", meta=META, page="simulasi",
                           scenarios=SCENARIOS)


# ---------------------------------------------------------------------- API
@app.get("/api/dashboard")
def api_dashboard():
    store = request.args.get("store", "all")
    item = request.args.get("item", "all")
    category = request.args.get("category", "all")
    sub = DATA.subset(store, item, category)
    if sub.empty:
        return jsonify(error="Tidak ada data untuk filter tersebut."), 404

    daily = DATA.daily(store, item, category)
    n_days = int(daily["units_sold"].notna().sum())
    avg_sold = float(daily["units_sold"].mean())
    kpi = {
        "rows": int(len(sub)),
        "days": n_days,
        "avg_daily_sales": round(avg_sold, 1),
        "total_sales": int(sub["units_sold"].sum()),
    }
    if DATA.has_orders:
        kpi["avg_daily_ordered"] = round(float(daily["units_ordered"].mean()), 1)
        kpi["order_to_sales"] = round(
            float(daily["units_ordered"].sum() / daily["units_sold"].sum()) * 100, 1)
    if DATA.has_inventory:
        kpi["avg_inventory"] = round(float(daily["inventory"].mean()), 1)
        kpi["days_of_cover"] = round(float(daily["inventory"].mean()) / avg_sold, 2)

    def col(name):
        if daily[name].notna().any():
            return [None if v != v else round(float(v), 1) for v in daily[name]]
        return None

    monthly = sub.groupby(sub["date"].dt.to_period("M"))["units_sold"].sum()
    top = sub.groupby("item")["units_sold"].sum().sort_values(ascending=False).head(10)
    payload = {
        "kpi": kpi,
        "daily": {
            "dates": [d.strftime("%Y-%m-%d") for d in daily.index],
            "units_sold": col("units_sold"),
            "units_ordered": col("units_ordered"),
            "inventory": col("inventory"),
        },
        "monthly": {"labels": [str(p) for p in monthly.index],
                    "values": [int(v) for v in monthly.values]},
        "top_items": {"labels": list(top.index), "values": [int(v) for v in top.values]},
        "by_category": None,
    }
    if DATA.has_category:
        cat = sub.groupby("category")["units_sold"].sum().sort_values(ascending=False)
        payload["by_category"] = {"labels": list(cat.index),
                                  "values": [int(v) for v in cat.values]}
    return jsonify(payload)


@app.get("/api/meta")
def api_meta():
    return jsonify(META)


@app.post("/api/simulate")
def api_simulate():
    payload = request.get_json(silent=True) or {}
    try:
        params = parse_params(payload, DATA, META)
        return jsonify(simulate(DATA, params))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


if __name__ == "__main__":
    app.run(debug=True)
