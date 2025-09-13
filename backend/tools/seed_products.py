import os
import shutil
import random
import pandas as pd
from pathlib import Path

# ------------------------
# CONFIG
# ------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]   # project root (2 levels up from tools/)
FULL_IMAGES_DIR = Path(r"D:\download\IMAGES")    # full dataset on your PC
OUTPUT_DIR = ROOT_DIR / "backend" / "data" / "products"   # always correct path
CSV_PATH = ROOT_DIR / "backend" / "data" / "products.csv" # always correct path

TOTAL_IMAGES = 200
IMAGES_PER_PRODUCT = 4
TOTAL_PRODUCTS = TOTAL_IMAGES // IMAGES_PER_PRODUCT


def main():
    print("🧹 Deleting old dataset...")

    # 1. Delete old demo images folder completely
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)   # remove entire products/ folder
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Delete old CSV
    if CSV_PATH.exists():
        CSV_PATH.unlink()

    print("✅ Old products/ folder and products.csv deleted.")

    # 3. Collect all images from full dataset
    all_images = []
    for root, dirs, files in os.walk(FULL_IMAGES_DIR):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")):
                all_images.append(Path(root) / f)

    if len(all_images) < TOTAL_IMAGES:
        raise ValueError(f"Not enough images! Found {len(all_images)}, need {TOTAL_IMAGES}")

    # 4. Randomly sample 200 unique images
    selected = random.sample(all_images, TOTAL_IMAGES)

    # 5. Copy them into OUTPUT_DIR and build metadata
    rows = []
    for i in range(TOTAL_PRODUCTS):
        product_id = i + 1
        product_name = f"Product {product_id}"
        category = Path(selected[i * IMAGES_PER_PRODUCT]).parent.name  # category from folder name

        for j in range(IMAGES_PER_PRODUCT):
            img_src = selected[i * IMAGES_PER_PRODUCT + j]
            img_name = f"product_{product_id}_img{j+1}{img_src.suffix.lower()}"
            img_dst = OUTPUT_DIR / img_name
            shutil.copy(img_src, img_dst)

            rows.append({
                "id": product_id,
                "name": product_name,
                "category": category,
                "image_path": f"products/{img_name}"
            })

    # 6. Write new products.csv
    df = pd.DataFrame(rows)
    df.to_csv(CSV_PATH, index=False)

    print(f"✅ New dataset created → {TOTAL_PRODUCTS} products × {IMAGES_PER_PRODUCT} images = {TOTAL_IMAGES} total")
    print(f"📂 Images saved in: {OUTPUT_DIR}")
    print(f"📝 Metadata saved in: {CSV_PATH}")


if __name__ == "__main__":

    main()
