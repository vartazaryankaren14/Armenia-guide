#!/usr/bin/env python3
"""Download and install three user-approved authentic Mount Aragats images from Commons.

Only files images/places/ag_049_{1,2,3}.webp are modified. Validate all
image sources and licenses before replacing any live file.
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
OUT = ROOT / "images" / "places"
SELECTED = (
    (1, "View from Lake Kari to Mount Aragats.jpg", "Wowan1978", "CC BY-SA 4.0"),
    (2, "Aragats crater 05.jpg", "Albero", "CC BY-SA 4.0"),
    (3, "Mount Aragats 2020-05-11.jpg", "Armenak Margarian", "CC BY-SA 4.0"),
)
session = requests.Session()
session.headers.update({"User-Agent":"ArmeniaGuide-CuratedAragats/1.0 (https://github.com/vartazaryankaren14/Armenia-guide)"})
session.mount("https://",HTTPAdapter(max_retries=Retry(total=4,backoff_factor=2,status_forcelist=(429,500,502,503,504))))

def clean(html):
    return unescape(re.sub(r"<[^>]*>","",html or "")).strip()

def norm(text):
    return re.sub(r"[^a-z0-9]","",text.lower())

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    staged=[]
    try:
        for slot,title,author,license_name in SELECTED:
            r=session.get(API,params={
                "action":"query","titles":"File:"+title,"prop":"imageinfo",
                "iiprop":"url|size|mime|extmetadata","iiurlwidth":"1920",
                "format":"json","formatversion":"2",
            },timeout=65)
            r.raise_for_status()
            info=r.json()["query"]["pages"][0].get("imageinfo",[None])[0]
            if not info or info.get("mime")!="image/jpeg" or info.get("width",0)<1700:
                raise ValueError("Unusable Commons source: "+title)
            meta=info.get("extmetadata",{})
            actual_license=clean(meta.get("LicenseShortName",{}).get("value",""))
            actual_artist=clean(meta.get("Artist",{}).get("value",""))
            if norm(actual_license)!=norm(license_name):
                raise ValueError(f"Unexpected license for {title}: {actual_license}")
            if norm(author) not in norm(actual_artist):
                raise ValueError(f"Unexpected artist for {title}: {actual_artist}")
            url=info.get("thumburl") or info["url"]
            photo=session.get(url,timeout=95)
            photo.raise_for_status()
            with Image.open(io.BytesIO(photo.content)) as original:
                img=ImageOps.exif_transpose(original).convert("RGB")
                if img.width<1000 or img.height<850:
                    raise ValueError("Insufficient image resolution: "+title)
                img.thumbnail((1920,1500),Image.Resampling.LANCZOS)
                tmp=OUT/f"ag_049_{slot}.webp.tmp"
                img.save(tmp,format="WEBP",quality=88,method=5)
                if tmp.stat().st_size<30000:
                    raise ValueError("Unexpectedly small output: "+title)
                staged.append((tmp,OUT/f"ag_049_{slot}.webp"))
                print(f"Validated {title}; author={actual_artist}; license={actual_license}; size={img.size}; webp_bytes={tmp.stat().st_size}")
        for tmp,dst in staged:
            tmp.replace(dst)
        print("Installed exactly three approved Aragats photos")
    except Exception:
        for tmp,_ in staged:
            tmp.unlink(missing_ok=True)
        raise

if __name__=="__main__":
    main()
