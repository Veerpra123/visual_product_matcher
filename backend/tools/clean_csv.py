import os, pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_PATH = os.path.join(BASE_DIR, "data", "products.csv")

df = pd.read_csv(CSV_PATH, dtype=str)
for col in ["image_path", "name", "category"]:
    if col in df.columns:
        df[col] = df[col].fillna("").map(lambda s: s.strip())
if "price" in df.columns:
    pass
if "id" in df.columns:
    df["id"] = df["id"].astype(int)

df.to_csv(CSV_PATH, index=False)
print(f"Cleaned {CSV_PATH}. Rows: {len(df)}")
