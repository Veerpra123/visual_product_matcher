# backend/api.py
from __future__ import annotations
import io
import os
import json
import logging
from pathlib import Path
from typing import Optional, List
import time
import urllib.request

import numpy as np
import pandas as pd
import requests
from PIL import Image

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

import torch
from transformers import CLIPProcessor, CLIPModel

# ----------------------------
# Logging
# ----------------------------
logger = logging.getLogger("vpm")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)
else:
    logger.handlers = [handler]

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "products.csv"
INDEX_PATH = DATA_DIR / "embeddings.npy"
IDS_PATH = DATA_DIR / "ids.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# FastAPI app & CORS
# ----------------------------
app = FastAPI(title="Visual Product Matcher", version="1.0.0")

default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
env_origins = os.getenv("CORS_ORIGINS")
if env_origins:
    allow_origins = [o.strip() for o in env_origins.split(",") if o.strip()]
else:
    allow_origins = default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# CLIP model (device selection)
# ----------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"[model] using device: {device}")
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# ----------------------------
# Global state
# ----------------------------
df: Optional[pd.DataFrame] = None
embeddings: Optional[np.ndarray] = None
ids: List[str] = []

# ----------------------------
# Network fetch helper (tries headers to avoid 403)
# ----------------------------
def _fetch_image_bytes_with_headers(url: str, timeout: int = 15) -> bytes:
    """
    Robust image fetch helper.

    Tries several header combos and request strategies to avoid 403/forbidden:
    - Uses a requests.Session with a few realistic header sets
    - Streams the response and reads content in chunks
    - Retries a few times with exponential backoff
    - Falls back to urllib.request if requests can't fetch it

    Raises the last meaningful exception when all attempts fail.
    """
    # Prepare realistic header candidates
    header_candidates = [
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        },
        {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.google.com/",
            "Accept": "*/*",
        },
        {
            "User-Agent": "curl/7.64.1",
            "Accept": "*/*",
        },
    ]

    session = requests.Session()
    last_exc = None

    # Give servers a few attempts (with small backoff)
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        for headers in header_candidates:
            # If the server is on a known host, set a Referer derived from the host (helps some CDNs)
            try:
                host = requests.utils.urlparse(url).netloc
                if host and "Referer" not in headers:
                    headers = dict(headers)  # copy
                    headers["Referer"] = f"https://{host}/"
            except Exception:
                pass

            try:
                # use stream to avoid issues on some servers; read content after status check
                with session.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True) as r:
                    r.raise_for_status()
                    # read in chunks into bytes buffer
                    content_chunks = []
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            content_chunks.append(chunk)
                    content = b"".join(content_chunks)
                    if not content:
                        raise Exception("Downloaded content is empty")
                    return content
            except Exception as e:
                last_exc = e
                logger.debug(f"[fetch attempt {attempt}] headers={headers} failed: {e}")

        # small exponential backoff before next attempt
        sleep_time = 0.5 * (2 ** (attempt - 1))
        logger.debug(f"[fetch] attempt {attempt} failed for all header combos; sleeping {sleep_time}s then retrying")
        time.sleep(sleep_time)

    # Final fallback: try urllib.request (sometimes bypasses strict requests behavior)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": f"https://{requests.utils.urlparse(url).netloc}/"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            if not content:
                raise Exception("Downloaded content is empty (urllib fallback)")
            return content
    except Exception as e:
        logger.debug(f"[fetch urllib fallback] failed: {e}")
        last_exc = last_exc or e

    # All attempts failed — raise last meaningful exception
    if last_exc:
        raise last_exc
    raise Exception("Failed to fetch image for unknown reasons")

# ----------------------------
# Helpers
# ----------------------------
def _detect_image_column(dframe: pd.DataFrame) -> str:
    candidates = [c for c in dframe.columns if any(k in c.lower() for k in ("image", "img", "photo", "picture", "url"))]
    for pref in ("image_url", "image", "url", "img", "imageUrl"):
        if pref in dframe.columns:
            return pref
    if candidates:
        return candidates[0]
    raise ValueError("products.csv must contain an image column (e.g. 'image_url', 'image', 'url', 'img')")

def _load_csv_filtered() -> pd.DataFrame:
    """
    Loads CSV, normalizes image column, preserves string IDs if present.
    If the 'id' column is missing or all IDs are null-like, will extract filename stems.
    """
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"{CSV_PATH} not found")

    dframe = pd.read_csv(CSV_PATH, dtype=str)
    dframe = dframe.fillna("")  # keep everything as strings for robustness

    # detect image column
    img_col = _detect_image_column(dframe)
    # normalize column name to 'image_url' internally
    if img_col != "image_url":
        dframe = dframe.rename(columns={img_col: "image_url"})
        img_col = "image_url"

    dframe["image_url"] = dframe["image_url"].astype(str).str.strip()
    # drop rows without image
    dframe = dframe[dframe["image_url"] != ""].copy()
    dframe.reset_index(drop=True, inplace=True)

    # Ensure ID handling:
    if "id" not in dframe.columns:
        # no id column: try to use 'sku' if present, else derive from filename
        if "sku" in dframe.columns and dframe["sku"].astype(str).str.strip().any():
            dframe["id"] = dframe["sku"].astype(str).str.strip()
        else:
            # extract stems as ids
            dframe["id"] = dframe["image_url"].apply(lambda x: Path(str(x)).stem if str(x).strip() else "")
    else:
        # preserve string ids where possible; treat common null tokens as missing
        id_series = dframe["id"].astype(str).str.strip()
        null_mask = id_series.str.lower().isin(["", "nan", "none", "null"])
        if null_mask.all():
            # all missing -> extract from filename stems
            logger.warning("[csv] All IDs missing/invalid — extracting from image filename stems")
            dframe["id"] = dframe["image_url"].apply(lambda x: Path(str(x)).stem if str(x).strip() else "")
        else:
            # keep original ids (strings). If some are null, fill those from filename stems
            dframe["id"] = id_series
            if null_mask.any():
                dframe.loc[null_mask, "id"] = dframe.loc[null_mask, "image_url"].apply(lambda x: Path(str(x)).stem if str(x).strip() else "")

    # final cleanup: ensure id is string and non-empty
    dframe["id"] = dframe["id"].astype(str).str.strip()
    # drop rows that still don't have id or image
    dframe = dframe[(dframe["id"] != "") & (dframe["image_url"] != "")]
    dframe.reset_index(drop=True, inplace=True)

    return dframe

def _open_image_from_url_or_path(value: str, timeout: int = 15) -> Image.Image:
    s = str(value).strip()
    if s.lower().startswith("http://") or s.lower().startswith("https://"):
        # fetch bytes using header-trying helper
        img_bytes = _fetch_image_bytes_with_headers(s, timeout=timeout)
        raw = Image.open(io.BytesIO(img_bytes))
    else:
        p = Path(s)
        # try relative to project root or base dir
        cand_paths = [p, ROOT_DIR / s, BASE_DIR / s]
        found = None
        for cand in cand_paths:
            if cand.exists():
                found = cand
                break
        if not found:
            raise FileNotFoundError(f"Local image not found: {s}")
        raw = Image.open(found)

    # robust conversion: handle palette and alpha properly
    try:
        if raw.mode == "P":
            img = raw.convert("RGBA").convert("RGB")
        elif raw.mode in ("RGBA", "LA"):
            background = Image.new("RGB", raw.size, (255, 255, 255))
            background.paste(raw, mask=raw.split()[-1])
            img = background
        else:
            img = raw.convert("RGB")
    except Exception:
        img = raw.convert("RGB")
    return img

def _img_to_vec(img: Image.Image) -> np.ndarray:
    inputs = clip_processor(images=img, return_tensors="pt").to(device)
    with torch.no_grad():
        v = clip_model.get_image_features(**inputs).cpu().numpy()[0].astype("float32")
    v = v / (np.linalg.norm(v) + 1e-10)
    return v

def _row_to_payload(row: pd.Series, score: Optional[float] = None) -> dict:
    payload = {
        "id": row["id"],
        "name": str(row.get("title") or row.get("name") or ""),
        "image_url": str(row.get("image_url", "")),
    }
    if "price" in row.index and str(row.get("price")).strip() != "":
        try:
            payload["price"] = float(row["price"])
        except Exception:
            payload["price"] = row["price"]
    if "brand" in row.index:
        payload["brand"] = str(row["brand"])
    if "description" in row.index:
        payload["description"] = str(row["description"])
    if score is not None:
        payload["score"] = float(score)
    return payload

def _build_index_from_csv():
    """
    Build embeddings from CSV and save embeddings.npy + ids.json.
    Returns info dict.
    """
    global df, embeddings, ids
    dframe = _load_csv_filtered()
    logger.info(f"[build_index] indexing {len(dframe)} rows from CSV")
    vecs = []
    ids_local: List[str] = []
    skipped = 0

    for _, row in dframe.iterrows():
        try:
            img = _open_image_from_url_or_path(row["image_url"])
            v = _img_to_vec(img)
            vecs.append(v)
            ids_local.append(str(row["id"]))
        except Exception as e:
            skipped += 1
            logger.warning(f"[build_index] skipped id={row.get('id','?')}: {e}")

    if not vecs:
        raise RuntimeError("No images could be indexed. Check your CSV and image URLs/paths.")

    embeddings_arr = np.vstack(vecs).astype("float32")
    np.save(INDEX_PATH, embeddings_arr)
    IDS_PATH.write_text(json.dumps([str(x) for x in ids_local], ensure_ascii=False))
    # update globals
    df = dframe
    embeddings = embeddings_arr
    ids = [str(x) for x in ids_local]

    logger.info(f"[build_index] built index size={len(ids)} skipped={skipped}")
    return {"status": "index built", "count": len(ids), "skipped": skipped}

# ----------------------------
# Startup: load CSV, load or build index
# ----------------------------
@app.on_event("startup")
def on_startup():
    global df, embeddings, ids
    # try load CSV (best-effort)
    try:
        df = _load_csv_filtered()
        logger.info(f"[startup] products.csv loaded rows={len(df)}")
    except Exception as e:
        logger.warning(f"[startup] failed to load CSV: {e}")
        df = None

    # try load existing index
    if INDEX_PATH.exists() and IDS_PATH.exists():
        try:
            embeddings_loaded = np.load(INDEX_PATH).astype("float32")
            ids_loaded = json.loads(IDS_PATH.read_text())
            embeddings = embeddings_loaded
            ids = [str(x) for x in ids_loaded]
            logger.info(f"[startup] loaded index items={len(ids)} shape={embeddings.shape}")
            # print sample fixed ids for quick verification
            logger.info(f"[startup] sample ids: {ids[:6]}")
            return
        except Exception as e:
            logger.warning(f"[startup] failed to load existing index: {e}")

    # otherwise build index
    try:
        info = _build_index_from_csv()
        logger.info(f"[startup] index build finished: {info}")
    except Exception as e:
        logger.error(f"[startup] index build failed: {e}")

# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "rows": 0 if df is None else int(len(df)),
        "indexed": 0 if embeddings is None else int(embeddings.shape[0]),
        "device": device,
        "csv_exists": CSV_PATH.exists(),
        "index_exists": INDEX_PATH.exists(),
        "ids_exists": IDS_PATH.exists(),
        "cors_origins": allow_origins,
    }

@app.post("/build_index")
def build_index():
    try:
        info = _build_index_from_csv()
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
def search(
    image_url: Optional[str] = Form(default=None),
    top_k: int = Form(default=12),
    min_similarity: float = Form(default=0.0),
    file: UploadFile = File(default=None),
):
    if embeddings is None or df is None or embeddings.shape[0] == 0:
        raise HTTPException(status_code=400, detail="Index not built — call /build_index first.")

    if not (0.0 <= min_similarity <= 1.0):
        raise HTTPException(status_code=422, detail="min_similarity must be in [0,1].")

    # load query image
    try:
        if file and file.filename:
            content = file.file.read()
            img_raw = Image.open(io.BytesIO(content))
            # robust conversion like in loader
            if img_raw.mode == "P":
                query_img = img_raw.convert("RGBA").convert("RGB")
            elif img_raw.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", img_raw.size, (255, 255, 255))
                bg.paste(img_raw, mask=img_raw.split()[-1])
                query_img = bg
            else:
                query_img = img_raw.convert("RGB")
            query_meta = {"source": "file", "filename": file.filename}
        elif image_url:
            # use header-aware fetch to avoid 403 on some hosts
            try:
                query_img = _open_image_from_url_or_path(image_url)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to load query image: {e}")
            query_meta = {"source": "url_or_path", "value": image_url}
        else:
            raise HTTPException(status_code=422, detail="Provide 'image_url' form field or upload a file.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load query image: {e}")

    # embed query and search
    qvec = _img_to_vec(query_img)
    sims = embeddings @ qvec  # embeddings normalized -> dot = cosine
    order = np.argsort(-sims)

    results: List[dict] = []
    for idx in order:
        score = float(sims[idx])
        if score < min_similarity:
            continue
        # get the id and row
        pid = ids[idx]
        row = df.loc[df["id"] == pid]
        if not row.empty:
            results.append(_row_to_payload(row.iloc[0], score=score))
        if len(results) >= top_k:
            break

    return {"query": query_meta, "count": len(results), "items": results}
