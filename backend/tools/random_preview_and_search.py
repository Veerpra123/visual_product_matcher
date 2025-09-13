# backend/tools/random_preview_and_search.py
"""
Pick a random image URL from backend/data/products.csv (or accept a URL arg),
preview it locally, call the backend /search endpoint with image_url, then
print the results and open the top-matching image in your default viewer.

Usage:
  # pick a random URL from CSV
  python backend/tools/random_preview_and_search.py

  # or provide a specific URL
  python backend/tools/random_preview_and_search.py "https://res.cloudinary.com/..." 
"""
from pathlib import Path
import random
import sys
import requests
import json
import os
import time

ROOT = Path(__file__).resolve().parents[2]  # project root
CSV = ROOT / "backend" / "data" / "products.csv"
PREVIEW_QUERY = ROOT / "backend" / "data" / "_random_query.jpg"
PREVIEW_TOP = ROOT / "backend" / "data" / "_top_match_preview.jpg"

# change if your backend is at a different host/port
BACKEND_SEARCH = "http://127.0.0.1:8000/search"

def pick_random_url():
    import pandas as pd
    if not CSV.exists():
        raise FileNotFoundError(f"CSV not found: {CSV}")
    df = pd.read_csv(CSV, dtype=str).fillna("")
    # detect likely image column
    img_cols = [c for c in df.columns if any(k in c.lower() for k in ("image","img","url","photo","picture"))]
    if not img_cols:
        raise RuntimeError("No image column detected in CSV.")
    imgcol = img_cols[0]
    urls = [u.strip() for u in df[imgcol].astype(str).tolist() if u and u.strip()]
    if not urls:
        raise RuntimeError("No non-empty image URLs found in CSV.")
    return random.choice(urls)

def download_preview(url, out_path):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        print(f"[preview] saved -> {out_path}")
        # small pause to ensure file write complete
        time.sleep(0.2)
        if os.name == "nt":
            os.startfile(str(out_path))
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            # try to open in background
            try:
                os.system(f"{opener} {str(out_path)} &")
            except Exception:
                print(f"Preview saved — open {out_path} manually.")
    except Exception as e:
        raise RuntimeError(f"Failed to download preview: {e}")

def call_search(image_url, top_k=6, min_similarity=0.0):
    try:
        data = {
            "image_url": image_url,
            "top_k": str(top_k),
            "min_similarity": str(min_similarity),
        }
        r = requests.post(BACKEND_SEARCH, data=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise RuntimeError(f"Search request failed: {e}")

def main():
    # allow passing a URL as argument
    url = sys.argv[1] if len(sys.argv) > 1 else None
    if not url:
        print("Picking a random image URL from CSV...")
        try:
            url = pick_random_url()
        except Exception as e:
            print("Error picking random URL:", e)
            return

    print("\nSelected URL:\n", url, "\n")

    # preview query image
    try:
        print("Downloading preview of the query image...")
        download_preview(url, PREVIEW_QUERY)
    except Exception as e:
        print("Could not preview query image:", e)

    # call backend search
    print("\nCalling backend /search ...")
    try:
        res = call_search(url, top_k=6, min_similarity=0.0)
    except Exception as e:
        print(e)
        return

    # pretty print summary
    print("\nSearch response summary:")
    try:
        # don't dump huge items fully, show counts and keys
        if isinstance(res, dict):
            summary = {k: (v if k != "items" else f"{len(v)} items") for k,v in res.items()}
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(res)
    except Exception:
        print(res)

    items = res.get("items", []) if isinstance(res, dict) else []
    if not items:
        print("\nNo matching items returned.")
        return

    # show top result
    top = items[0]
    print("\nTop match (index 0):")
    print(json.dumps(top, indent=2, ensure_ascii=False))

    top_url = top.get("image_url")
    if top_url:
        print("\nPreviewing top match image:", top_url)
        # download to a separate preview file
        try:
            download_preview(top_url, PREVIEW_TOP)
        except Exception as e:
            print("Failed to download top match preview:", e)
    else:
        print("Top item has no image_url field to preview.")

if __name__ == "__main__":
    main()
