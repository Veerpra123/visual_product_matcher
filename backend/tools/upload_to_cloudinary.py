import os, csv, cloudinary, cloudinary.uploader
from pathlib import Path
from dotenv import load_dotenv

# Load Cloudinary credentials from .env
load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "dlm3jzchi"),
    api_key=os.getenv("CLOUDINARY_API_KEY", "869595393844275"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", "flvGoYzqPQw0EqecQf53sOLVFfA")
)

# 📂 Paths
DATASET_DIR = Path(r"D:\download\IMAGES")   # <-- your source images
CSV_PATH = Path(r"D:\visual_product_matcher\backend\data\products.csv")
CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = (".jpg", ".jpeg", ".png", ".webp")

# ✅ Load existing uploaded images
uploaded_files = set()
if CSV_PATH.exists():
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        uploaded_files = {row["image_url"] for row in reader}

print(f"📊 Already in CSV: {len(uploaded_files)}")

rows = []
product_id = len(uploaded_files) + 1

# ✅ Walk through all images in D:\download\IMAGES
for root, _, files in os.walk(DATASET_DIR):
    category = Path(root).name  # folder = category
    for file in files:
        if file.lower().endswith(ALLOWED_EXT):
            file_path = Path(root) / file
            if not file_path.exists() or os.path.getsize(file_path) == 0:
                continue

            file_name = Path(file).stem
            print(f"⬆️ Uploading → {file_name} ({category})")

            try:
                result = cloudinary.uploader.upload(
                    str(file_path),
                    folder="products",         # upload to Cloudinary/products/
                    public_id=file_name,
                    overwrite=False,
                    unique_filename=True
                )
                url = result["secure_url"]

                if url in uploaded_files:
                    print(f"⏭️ Skipped (already in CSV) → {file_name}")
                    continue

                rows.append({
                    "id": product_id,
                    "name": file_name,
                    "category": category,
                    "image_url": url
                })
                product_id += 1
                print(f"✔ Uploaded → {file_name}")

            except Exception as e:
                print(f"❌ Failed → {file_name}: {e}")

# ✅ Save new rows to CSV
if rows:
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "category", "image_url"])
        if f.tell() == 0:
            writer.writeheader()
        writer.writerows(rows)

print(f"\n✅ Finished. Added {len(rows)} new images.")
print(f"📄 CSV saved at: {CSV_PATH}")
