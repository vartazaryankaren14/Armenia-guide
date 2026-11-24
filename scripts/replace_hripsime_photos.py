#!/usr/bin/env python3
"""Install ONLY the two user-approved real Saint Hripsime Church photos.

Slot 1 is deliberately never modified. Sources are Wikimedia Commons files
and are checked against their actual license before installation.
"""
import io
import re
from html import unescape
from pathlib import Path

import requests
from PIL import Image, ImageOps
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
API = "https://commons.wikimedia.org/w/api.php"
PHOTO_DIR = ROOT / "images" / "places"
SELECTED = (
    (2, "Vagharshapat-St Hripsime-22-innen-2019-gje.jpg", "CC BY-SA 4.0"),
    (3, "Hripsime church aerial 2023.jpg", "CC BY 4.0"),
)
session = requests.Session()
session.headers.update({"User-Agent": "ArmeniaGuide-CuratedPhotos/1.0 (https://github.com/vartazaryankaren14/Armenia-guide)"})
retry = Retry(total=4, backoff_factor=2, status_forcelist=(429,500,502,503,504))
session.mount("https://", HTTPAdapter(max_retries=retry))

def clean(s):
    return unescape(re.sub(r"<[^>]*>", "", s or "")).strip()

def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

def main():
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    staged = []
    for slot, title, expected_license in SELECTED:
        response = session.get(API, params={
            "action":"query", "titles":"File:"+title,
            "prop":"imageinfo", "iiprop":"url|size|mime|extmetadata",
            "iiurlwidth":"1920", "format":"json", "formatversion":"2",
        }, timeout=60)
        response.raise_for_status()
        page = response.json()["query"]["pages"][0]
        info = page.get("imageinfo", [None])[0]
        if not info or info.get("mime")!="image/jpeg" or info.get("width",0)<1300:
            raise ValueError("Missing, incorrect, or low-resolution photo: "+title)
        actual_license = clean(info.get("extmetadata",{}).get("LicenseShortName",{}).get("value",""))
        if not norm(actual_license).startswith(norm(expected_license)):
            raise ValueError(f"Unexpected license {actual_license} for {title}")
        # Use the actual Commons API image URL, never guessed upload path/hash.
        url = info.get("thumburl") or info["url"]
        result = session.get(url, timeout=90)
        result.raise_for_status()
        with Image.open(io.BytesIO(result.content)) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            if max(image.size) < 1300 or min(image.size) < 700:
                raise ValueError("Downloaded image too small: "+title)
            image.thumbnail((1920, 1600), Image.Resampling.LANCZOS)
            destination = PHOTO_DIR / f"ag_046_{slot}.webp"
            temp = PHOTO_DIR / f"ag_046_{slot}.webp.tmp"
            image.save(temp, format="WEBP", quality=88, method=6)
            if temp.stat().st_size < 25000:
                temp.unlink(missing_ok=True)
                raise ValueError("Processed image suspiciously small: "+title)
            print(f"Verified {title}: {image.width}x{image.height}, {temp.stat().st_size} bytes, {actual_license}")
            staged.append((temp, destination))
    # Do not install either photo unless BOTH have been validated.
    for temp, destination in staged:
        temp.replace(destination)
    print("Updated ag_046 slots 2 and 3 only. Slot 1 unchanged.")

if __name__=="__main__":
    main()
