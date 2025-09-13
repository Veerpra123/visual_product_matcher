#!/usr/bin/env python3
"""
build_index.py

- Robust CSV loading (accepts many image column names)
- Preserves string IDs (SKU/UUID) to avoid accidental row drops
- Supports http(s) image URLs and local file paths (relative to backend/data)
- Uses CLIP model to compute image embeddings and saves:
    - data/embeddings.npy
    - data/ids.json

Usage:
    python backend/tools/build_index.py
"""
import io
import json
import requests
from pathlib import Path
from PIL import Image
import numpy as np
import pandas as pd
import torch
from transformers import CLIPProcessor, CLIPModel
from tqdm import tqdm

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]   # backend/
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "products.csv"
INDEX_PATH = DATA_DIR / "embeddings.npy"
IDS_PATH = DATA_DIR / "ids.json"

# ----------------------------
# Device & Model
# ----------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", device)

print("Loading CLIP model (this may take a moment)...")
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
print("Model loaded.")

# ----------------------------
# Load & clean CSV (robust)
# ----------------------------
if not CSV_PATH.exists():
    raise FileNotFoundError(f"{CSV_PATH} not found — place your products.csv at backend/data/products.csv")

df = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8")
print(f"Read CSV rows: {len(df)}")

# require id column
if "id" not in df.columns:
    raise ValueError("products.csv must contain an 'id' column (can be numeric or string)")

df["id"] = df["id"].astype(str).str.strip()

# detect image column
candidate_image_cols = [c for c in df.columns if any(k in c.lower() for k in ("image", "img", "photo", "picture", "url"))]
img_col = None
for pref in ("image_url", "image", "url", "img", "imageUrl"):
    if pref in df.columns:
        img_col = pref
        break
if img_col is None and candidate_image_cols:
    img_col = candidate_image_cols[0]

if img_col is None:
    raise ValueError("products.csv must have an image column (e.g. 'image_url', 'image', 'url', 'img'). Detected: " + ", ".join(candidate_image_cols))

df[img_col] = df[img_col].astype(str).str.strip()

before = len(df)
df = df.dropna(subset=["id", img_col]).copy()
df = df[(df["id"] != "") & (df[img_col] != "")]
df.reset_index(drop=True, inplace=True)
after = len(df)
print(f"✅ Cleaned CSV: {after} valid rows (dropped {before-after} rows)")

print("Sample rows (first 5):")
print(df[["id", img_col]].head(5).to_string(index=False))

# ----------------------------
# NEW: Fix 'nan' IDs by replacing with image filename stem
# ----------------------------
# If all ids are the string "nan" (or many are), replace using the image filename stem
# e.g. https://.../products/a1c700ifht96z00etl4s.jpg -> a1c700ifht96z00etl4s
if (df["id"].str.lower() == "nan").all():
    print("⚠️ All IDs are 'nan' — replacing with filename stems extracted from image URLs")
    df["id"] = df[img_col].apply(lambda x: Path(str(x)).stem if isinstance(x, str) and x.strip() != "" else "unknown")

# ----------------------------
# Build embeddings
# ----------------------------
DATA_DIR.mkdir(parents=True, exist_ok=True)
embs, ids = [], []
skipped = 0

for _, row in tqdm(df.iterrows(), total=len(df), desc="Building embeddings"):
    id_val = row["id"]
    url = row[img_col]
    try:
        if isinstance(url, str) and url.lower().startswith("http"):
            try:
                r = requests.get(url, timeout=15)
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
            except Exception as e:
                skipped += 1
                print(f"⚠️ Skipped {id_val}: failed to download image -> {e} -> {url}")
                continue
        else:
            path = Path(url)
            if not path.is_absolute():
                path = (DATA_DIR / url).resolve()
            if not path.exists():
                skipped += 1
                print(f"⚠️ Skipped {id_val}: local file not found -> {path}")
                continue
            try:
                img = Image.open(path).convert("RGB")
            except Exception as e:
                skipped += 1
                print(f"⚠️ Skipped {id_val}: failed to open local image -> {e} -> {path}")
                continue

        inputs = processor(images=img, return_tensors="pt").to(device)
        with torch.no_grad():
            vec = model.get_image_features(**inputs).cpu().numpy()[0].astype("float32")
        vec = vec / (np.linalg.norm(vec) + 1e-10)

        embs.append(vec)
        ids.append(id_val)
    except Exception as e:
        skipped += 1
        print(f"⚠️ Skipped {id_val}: unexpected error -> {e}")

if not embs:
    raise RuntimeError(
        "No embeddings built — check if your CSV has valid image URLs or local paths.\n"
        "- Ensure backend/data/products.csv has 'id' and an image column.\n"
        "- Run quick_inspect_csv.py or validate_images_csv.py for debugging."
    )

embs = np.vstack(embs).astype("float32")
np.save(INDEX_PATH, embs)
IDS_PATH.write_text(json.dumps(ids, ensure_ascii=False))

print(f"✅ Built index: {len(ids)} items (skipped {skipped})")
print(f"💾 Saved embeddings → {INDEX_PATH} (shape={embs.shape})")
print(f"💾 Saved ids        → {IDS_PATH}")
