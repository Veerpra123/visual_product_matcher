import os
import csv
import cloudinary
import cloudinary.api
from pathlib import Path

# 🔑 Configure Cloudinary
cloudinary.config(
    cloud_name="dlm3jzchi",
    api_key="869595393844275",
    api_secret="flvGoYzqPQw0EqecQf53sOLVFfA"
)

# 📂 Where to save CSV for backend
CSV_PATH = Path(r"D:\visual_product_matcher\backend\data\products.csv")
CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

rows = []
product_id = 1
next_cursor = None

print("📊 Fetching all images from Cloudinary folder: products/ ...")

# ✅ Loop through all uploaded images in Cloudinary (pagination)
while True:
    result = cloudinary.api.resources(
        type="upload",
        prefix="products/",   # only inside products/ folder
        max_results=500,
        next_cursor=next_cursor
    )

    for res in result.get("resources", []):
        public_id = res["public_id"]  # e.g., products/airplane_001
        url = res["secure_url"]
        file_name = Path(public_id).name

        # Infer category from subfolder name, else fallback
        parts = public_id.split("/")
        category = parts[1] if len(parts) > 2 else "uncategorized"

        rows.append({
            "id": product_id,
            "name": file_name,
            "category": category,
            "image_url": url
        })
        product_id += 1

    next_cursor = result.get("next_cursor")
    if not next_cursor:
        break

# ✅ Save CSV
with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["id", "name", "category", "image_url"])
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ Built products.csv with {len(rows)} images.")
print(f"📄 Saved at: {CSV_PATH}")
