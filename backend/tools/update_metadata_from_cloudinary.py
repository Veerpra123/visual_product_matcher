import csv
import hashlib
from pathlib import Path
import pandas as pd
import cloudinary
import cloudinary.api

# 🔑 Cloudinary Config
cloudinary.config(
    cloud_name="dlm3jzchi",
    api_key="869595393844275",
    api_secret="flvGoYzqPQw0EqecQf53sOLVFfA"
)

# 📂 Paths
CSV_PATH = Path(r"D:\visual_product_matcher\backend\data\products.csv")
BACKUP_PATH = CSV_PATH.with_suffix(".backup.csv")

# 🔧 Helpers
def md5_int(s: str) -> int:
    return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)

def deterministic_price(name: str) -> int:
    """Stable price for each product based on its name"""
    min_p, max_p = 500, 10000
    return min_p + (md5_int(name) % (max_p - min_p + 1))

def deterministic_brand(name: str) -> str:
    brands = ["Acme","Nimbus","Horizon","Orbit","Flux","AeroTech","Zenith","Solace"]
    return brands[md5_int(name) % len(brands)]

# 📥 Load existing CSV if present
if CSV_PATH.exists():
    print(f"📂 Loading existing CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
    next_id = df["id"].astype(int).max() + 1
else:
    print("📂 No existing CSV found, starting fresh.")
    df = pd.DataFrame(columns=["id","name","price","brand","description","image_url"])
    next_id = 1

existing_names = set(df["name"].tolist())
rows = df.to_dict(orient="records")

# 🔍 Fetch images from Cloudinary
print("🔍 Fetching Cloudinary resources...")
new_count = 0
next_cursor = None

while True:
    result = cloudinary.api.resources(
        type="upload", prefix="products/", max_results=500, next_cursor=next_cursor
    )
    for res in result.get("resources", []):
        public_id = res["public_id"]
        url = res["secure_url"]
        name = Path(public_id).name

        if name in existing_names:
            continue

        price = deterministic_price(name)
        brand = deterministic_brand(name)
        description = f"Demo description for {name}."

        rows.append({
            "id": str(next_id),
            "name": name,
            "price": str(price),
            "brand": brand,
            "description": description,
            "image_url": url
        })
        next_id += 1
        new_count += 1
        existing_names.add(name)

    next_cursor = result.get("next_cursor")
    if not next_cursor:
        break

# 💾 Backup old CSV
if CSV_PATH.exists():
    CSV_PATH.replace(BACKUP_PATH)
    print(f"🗂 Backup saved → {BACKUP_PATH}")

# 💾 Save new products.csv
with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=["id","name","price","brand","description","image_url"]
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ products.csv generated with {len(rows)} rows.")
print(f"📄 Saved at: {CSV_PATH}")
