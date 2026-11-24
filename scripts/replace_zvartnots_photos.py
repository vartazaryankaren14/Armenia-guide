#!/usr/bin/env python3
"""Download two expressly selected authentic Zvartnots photographs from Commons.

Third image in guide is intentionally generated and is not touched here.
"""
import io
import json
import re
from html import unescape
from pathlib import Path

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
API = "https://commons.wikimedia.org/w/api.php"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ArmeniaGuide-FotoSelect/1.0 (https://github.com/vartazaryankaren14/Armenia-guide)"})
SELECTED = [
    (1, "Ruins of Zvartnots Cathedral with Mount Ararat Backdrop - Near Yerevan - Armenia (18805091799).jpg", "Adam Jones", "CC BY-SA 2.0"),
    (2, "Zvartnots-Columns.jpg", "Steven C. Price", "CC BY-SA 4.0"),
]

def main():
    staged = []
    credits = []
    for slot, title, author, license_name in SELECTED:
        response = SESSION.get(API, params={
            "action": "query", "titles": "File:" + title,
            "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": "1600", "format": "json", "formatversion": "2",
        }, timeout=50)
        response.raise_for_status()
        pages = response.json()["query"]["pages"]
        info = pages[0].get("imageinfo", [None])[0]
        if not info or info.get("mime") != "image/jpeg" or info.get("width", 0) < 1100:
            raise ValueError("Invalid Commons photo " + title)
        def clean(s):
            return unescape(re.sub(r"<[^>]*>", "", s or "")).strip()
        license_actual = clean(info.get("extmetadata", {}).get("LicenseShortName", {}).get("value", ""))
        norm = re.sub(r"[^a-z0-9]", "", license_actual.lower())
        expected = re.sub(r"[^a-z0-9]", "", license_name.lower())
        if not norm.startswith(expected):
            raise ValueError(f"Unexpected license {license_actual} for {title}")
        picture = SESSION.get(info.get("thumburl") or info["url"], timeout=90)
        picture.raise_for_status()
        with Image.open(io.BytesIO(picture.content)) as original:
            img = ImageOps.exif_transpose(original).convert("RGB")
            if img.width < 900 or img.height < 600:
                raise ValueError("Low resolution: " + title)
            img.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
            output = ROOT / "images" / "places" / f"ag_045_{slot}.webp"
            tmp = output.with_suffix(".webp.tmp")
            img.save(tmp, "WEBP", quality=84, method=5)
            staged.append((tmp, output))
        source = info.get("descriptionurl") or "https://commons.wikimedia.org/wiki/File:" + title.replace(" ", "_")
        credits.append(f"- **Храм Звартноц**, [ag_045_{slot}.webp]({source}): {author}, {license_name}; преобразовано в WebP для Armenia Guide")
    # All requests and validation succeeded: now apply together.
    for temp, dst in staged:
        temp.replace(dst)
    path = ROOT / "PHOTO_SOURCES.md"
    before = path.read_text("utf-8").splitlines()
    cleaned = [s for s in before if not ("**Храм Звартноц**" in s and "ag_045_" in s)]
    cleaned.extend(credits)
    path.write_text("\n".join(cleaned).rstrip() + "\n", encoding="utf-8")
    print("Approved Zvartnots real photos downloaded, verified, credited")

if __name__ == "__main__":
    main()