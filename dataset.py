"""Pemuatan dan agregasi dataset.

Mendukung dua skema kolom:
  1. retail_store_inventory.csv  -> Date, Store ID, Product ID, Category,
     Inventory Level, Units Sold, Units Ordered, ...
  2. train.csv (Kaggle Store Item Demand) -> date, store, item, sales

Semua dinormalisasi ke kolom internal:
  date, store, item, category, units_sold, units_ordered, inventory
Kolom yang tidak ada di skema 2 (category, units_ordered, inventory) bernilai NaN.
"""
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = ["train.csv", "retail_store_inventory.csv"]

RENAME_RETAIL = {
    "Date": "date", "Store ID": "store", "Product ID": "item",
    "Category": "category", "Units Sold": "units_sold",
    "Units Ordered": "units_ordered", "Inventory Level": "inventory",
}
RENAME_TRAIN = {"date": "date", "store": "store", "item": "item", "sales": "units_sold"}


def find_data_path():
    env = os.environ.get("DATA_PATH")
    if env:
        return env
    for name in CANDIDATES:
        path = os.path.join(BASE_DIR, "data", name)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "Dataset tidak ditemukan. Letakkan train.csv atau retail_store_inventory.csv "
        "di folder data/, atau set variabel lingkungan DATA_PATH."
    )


def load_dataset(path=None):
    path = path or find_data_path()
    raw = pd.read_csv(path)
    if "Units Sold" in raw.columns:
        df = raw.rename(columns=RENAME_RETAIL)
    elif {"date", "store", "item", "sales"}.issubset(raw.columns):
        df = raw.rename(columns=RENAME_TRAIN)
    else:
        raise ValueError(
            "Skema kolom tidak dikenali. Dibutuhkan (date, store, item, sales) "
            "atau kolom retail_store_inventory.csv."
        )
    df["date"] = pd.to_datetime(df["date"])
    df["store"] = df["store"].astype(str)
    df["item"] = df["item"].astype(str)
    for col in ("category", "units_ordered", "inventory"):
        if col not in df.columns:
            df[col] = float("nan") if col != "category" else None
    df = df[["date", "store", "item", "category", "units_sold", "units_ordered", "inventory"]]
    return df.sort_values(["date", "store", "item"]).reset_index(drop=True)


class Data:
    """Pembungkus dataset dengan fungsi filter dan agregasi harian."""

    def __init__(self, df):
        self.df = df
        self.has_inventory = bool(df["inventory"].notna().any())
        self.has_orders = bool(df["units_ordered"].notna().any())
        self.has_category = bool(df["category"].notna().any())

    def meta(self):
        d = self.df
        return {
            "rows": int(len(d)),
            "date_min": d["date"].min().strftime("%Y-%m-%d"),
            "date_max": d["date"].max().strftime("%Y-%m-%d"),
            "stores": sorted(d["store"].unique(), key=_natural),
            "items": sorted(d["item"].unique(), key=_natural),
            "categories": sorted(d["category"].dropna().unique()) if self.has_category else [],
            "has_inventory": self.has_inventory,
            "has_orders": self.has_orders,
            "has_category": self.has_category,
            "order_to_sales_pct": (
                round(float(d["units_ordered"].sum() / d["units_sold"].sum() * 100), 1)
                if self.has_orders else None),
        }

    def subset(self, store="all", item="all", category="all"):
        d = self.df
        if store != "all":
            d = d[d["store"] == store]
        if item != "all":
            d = d[d["item"] == item]
        if category != "all" and self.has_category:
            d = d[d["category"] == category]
        return d

    def daily(self, store="all", item="all", category="all"):
        """Total harian (jumlah seluruh toko/barang terpilih)."""
        d = self.subset(store, item, category)
        if d.empty:
            return pd.DataFrame(columns=["units_sold", "units_ordered", "inventory"])
        agg = d.groupby("date").agg(
            units_sold=("units_sold", "sum"),
            units_ordered=("units_ordered", lambda s: s.sum(min_count=1)),
            inventory=("inventory", lambda s: s.sum(min_count=1)),
        )
        return agg.asfreq("D")


def _natural(value):
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return (len(digits) == 0, int(digits) if digits else 0, str(value))
