# validate_images_csv.py
# Usage: python backend/tools/validate_images_csv.py path/to/products.csv

import sys, csv, requests, os
from urllib.parse import urlparse
from pathlib import Path

CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/products.csv")

def guess_image_columns(headers):
    candidates = []
    lower = [h.lower() for h in headers]
    for i, h in enumerate(headers):
        if any(k in lower[i] for k in ("image", "img", "photo", "picture", "url")):
            candidates.append(h)
    for name in ("image_url", "image", "img_url", "url"):
        if name in headers and name not in candidates:
            candidates.append(name)
    return list(dict.fromkeys(candidates))

def check_url(u, timeout=6):
    try:
        if not u or not isinstance(u, str):
            return False, "empty"
        u = u.strip()
        parsed = urlparse(u)
        if parsed.scheme not in ("http", "https", "file", ""):
            return False, f"unsupported-scheme:{parsed.scheme}"
        if parsed.scheme in ("http", "https"):
            try:
                r = requests.head(u, allow_redirects=True, timeout=timeout)
                if r.status_code < 400:
                    return True, f"status:{r.status_code}"
                r = requests.get(u, stream=True, timeout=timeout)
                if r.status_code < 400:
                    return True, f"status-get:{r.status_code}"
                return False, f"http-error:{r.status_code}"
            except requests.RequestException as e:
                return False, f"request-except:{e}"
        else:
            path = os.path.expanduser(u)
            if os.path.exists(path):
                return True, "local-file-exists"
            return False, "local-file-missing"
    except Exception as e:
        return False, f"exception:{e}"

if not CSV.exists():
    print("CSV not found:", CSV)
    sys.exit(1)

with open(CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames or []
    print("Headers detected:", headers)
    candidates = guess_image_columns(headers)
    print("Candidate image columns:", candidates)
    rows = list(reader)

if not rows:
    print("CSV has no data rows.")
    sys.exit(0)

if not candidates:
    print("No candidate image column found. First row values:")
    print(rows[0])
    sys.exit(0)

for col in candidates:
    vals = [r.get(col, "") for r in rows]
    nonempty = [v for v in vals if v and v.strip()]
    print(f"\nColumn '{col}': total rows={len(vals)}, non-empty={len(nonempty)}")
    print("First 10 values:", nonempty[:10])

    samples = nonempty[:3]
    for s in samples:
        ok, reason = check_url(s)
        print(f"  Sample: {s}\n    -> ok={ok}, reason={reason}")

valid_count = 0
for r in rows:
    ok_any = False
    for c in candidates:
        ok, _ = check_url(r.get(c, ""))
        if ok:
            ok_any = True
            break
    if ok_any:
        valid_count += 1
print(f"\nRows with at least one reachable image: {valid_count} / {len(rows)}")
