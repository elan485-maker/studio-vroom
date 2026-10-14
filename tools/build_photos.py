#!/usr/bin/env python3
"""
Studio Vroom — inventory photo builder

Usage (from the repo root):
    python3 tools/build_photos.py            # process every original folder
    python3 tools/build_photos.py --force    # re-process even if output exists

How it works
  1. Drop original photos into   cars/<Year Make Model>/        e.g. cars/2019 Audi Q5/
     (folder names with spaces = originals; they are git-ignored so the big files never get pushed)
  2. Run this script. It writes web-sized copies to   cars/<year-make-model>/01.jpg, 01-thumb.jpg, ...
     (max 1600px, ~150-300 KB each) and updates   cars/manifest.json
  3. In the Google Sheet, put the slug (e.g. 2019-audi-q5) in the Photo column — or leave it blank;
     index.html / car.html auto-match the folder by year/make/model.
  4. git add cars/<slug> cars/manifest.json && git commit && git push

Cover photo: the first file (sorted by name) is the cover. To use another one, rename it so it sorts
first, or edit "cover" in cars/manifest.json (e.g. "cover": "02.jpg").

Requires Pillow:  pip3 install pillow
"""
import json, os, re, sys

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is missing. Run:  pip3 install pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARS = os.path.join(ROOT, "cars")
MANIFEST = os.path.join(CARS, "manifest.json")
MAXW, THUMBW = 1600, 480
EXTS = (".jpg", ".jpeg", ".png", ".heic")
FORCE = "--force" in sys.argv


# Folder names may use short brand names; the Google Sheet uses the full make, so map them.
ALIASES = {"vw": "volkswagen", "chevy": "chevrolet", "merc": "mercedes-benz", "mercedes": "mercedes-benz", "benz": "mercedes-benz"}


def slug(s):
    words = [ALIASES.get(w, w) for w in re.sub(r"[^a-z0-9]+", " ", s.lower()).split()]
    return "-".join(words)


manifest = {}
if os.path.exists(MANIFEST):
    with open(MANIFEST) as fh:
        manifest = json.load(fh)

for folder in sorted(os.listdir(CARS)):
    src = os.path.join(CARS, folder)
    if not os.path.isdir(src) or folder.startswith(".") or " " not in folder.strip():
        continue  # only "Year Make Model" original folders
    if folder.strip().lower().startswith("untitled"):
        continue
    files = sorted(f for f in os.listdir(src) if f.lower().endswith(EXTS))
    if not files:
        print(f"skip  {folder}/ (no photos)")
        continue
    key = slug(folder)
    out = os.path.join(CARS, key)
    if os.path.isdir(out) and not FORCE and manifest.get(key, {}).get("photos"):
        print(f"ok    {key}/ already built ({len(manifest[key]['photos'])} photos) — use --force to redo")
        continue
    os.makedirs(out, exist_ok=True)
    names = []
    for i, f in enumerate(files, 1):
        try:
            im = ImageOps.exif_transpose(Image.open(os.path.join(src, f))).convert("RGB")
        except Exception as e:  # HEIC without pillow-heif, corrupt file, etc.
            print(f"warn  {folder}/{f}: {e}")
            continue
        big = im.copy(); big.thumbnail((MAXW, MAXW))
        big.save(os.path.join(out, f"{i:02d}.jpg"), "JPEG", quality=82, optimize=True, progressive=True)
        th = im.copy(); th.thumbnail((THUMBW, THUMBW))
        th.save(os.path.join(out, f"{i:02d}-thumb.jpg"), "JPEG", quality=80, optimize=True)
        names.append(f"{i:02d}.jpg")
    prev = manifest.get(key, {})
    manifest[key] = {
        "title": folder.strip(),
        "photos": names,
        "cover": prev.get("cover") if prev.get("cover") in names else names[0],
    }
    print(f"built {key}/ ({len(names)} photos)")

with open(MANIFEST, "w") as fh:
    json.dump(manifest, fh, indent=1)
print(f"\nmanifest: {len(manifest)} cars → cars/manifest.json")
