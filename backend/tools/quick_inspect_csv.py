# quick_inspect_csv.py
# Quick human-readable CSV inspection

import pandas as pd
from pathlib import Path

CSV = Path("data/products.csv")
if not CSV.exists():
    print("CSV not found at:", CSV)
    raise SystemExit(1)

df = pd.read_csv(CSV, encoding="utf-8", dtype=str)
print("Headers:", df.columns.tolist())
print("\nFirst 5 rows (raw):")
print(df.head(5).to_string(index=False))
print("\nColumn dtypes:")
print(df.dtypes)

if "id" in df.columns:
    print("\nUnique id sample (first 10):", df["id"].head(10).tolist())

for col in df.columns:
    if any(k in col.lower() for k in ("image", "img", "url", "photo", "picture")):
        print(f"\nFirst 10 {col} values:")
        print(df[col].astype(str).head(10).tolist())
