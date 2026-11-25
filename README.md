# Simulasi Sistem Dinamik Pengelolaan Persediaan Barang

Website Flask untuk mensimulasikan persediaan dengan model Stock and Flow
(stok, barang masuk, penjualan) memakai data asli, termasuk skenario permintaan +20% dan +50%.

## Menjalankan

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Buka http://127.0.0.1:5000. Bootstrap dan Chart.js sudah disertakan di `static/vendor`, jadi tidak perlu internet.

## Halaman

| Halaman | Isi |
|---|---|
| Dashboard | KPI dan grafik data asli (penjualan, pesanan, stok, per bulan, kategori, 10 barang teratas) dengan filter toko, kategori, barang |
| Model Stock & Flow | Diagram, persamaan, dan asumsi stok serta pengadaan |
| Simulasi Skenario | Input stok awal, barang masuk, permintaan; hasil baseline, +20%, +50% (opsional skenario kustom); grafik stok; unduh CSV |

## Dataset

Aplikasi membaca file di folder `data/` (urutan: `train.csv`, lalu `retail_store_inventory.csv`)
atau path dari variabel lingkungan `DATA_PATH`. Dua skema didukung:

* `retail_store_inventory.csv`: Date, Store ID, Product ID, Category, Inventory Level, Units Sold, Units Ordered, ...
* `train.csv`: date, store, item, sales (tanpa kolom stok dan pesanan, sehingga stok awal diasumsikan sebesar level S
  dan mode "historis" tidak tersedia)

## Struktur

```
app.py            route halaman dan API (/api/dashboard, /api/simulate)
dataset.py        pemuatan, normalisasi, dan agregasi data
model.py          model Stock and Flow, kebijakan (s, S), skenario, validasi input
templates/        base, dashboard, model, simulasi
static/           css/style.css, js/*.js, vendor/ (Bootstrap, Chart.js)
data/             dataset
requirements.txt
```
