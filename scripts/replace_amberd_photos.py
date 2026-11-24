#!/usr/bin/env python3
"""Install two approved authentic Amberd photos in slots 2 and 3 only.

Download the actual files via Wikimedia Commons API, verify claimed
creator/license and resolution, then encode both images as local WebP.
"""
import io
import re
from html import unescape
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"images"/"places"
API="https://commons.wikimedia.org/w/api.php"
SELECTED=(
    (2, "Amberd fortress and Church St. Astvatsatsin.jpg", "Vladimir Pankratov", "CC BY-SA 2.0"),
    (3, "View of Amberd fortress, Armenia.jpg", "TigranG8403", "CC BY-SA 4.0"),
)
session=requests.Session()
session.headers.update({"User-Agent":"ArmeniaGuide-AmberdPhotoCuration/1.0 (https://github.com/vartazaryankaren14/Armenia-guide)"})
session.mount("https://",HTTPAdapter(max_retries=Retry(total=4,backoff_factor=2,status_forcelist=(429,500,502,503,504))))
def clean(s):
    return unescape(re.sub(r"<[^>]*>","",s or "")).strip()
def norm(s):
    return re.sub(r"[^a-z0-9]","",s.lower())
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    staged=[]
    try:
        for slot,title,author,license_name in SELECTED:
            r=session.get(API,params={"action":"query","titles":"File:"+title,"prop":"imageinfo",
                "iiprop":"url|size|mime|extmetadata","iiurlwidth":"1920",
                "format":"json","formatversion":"2"},timeout=60)
            r.raise_for_status()
            page=r.json()["query"]["pages"][0]
            info=page.get("imageinfo",[None])[0]
            if not info or info.get("mime")!="image/jpeg" or info.get("width",0)<2000:
                raise ValueError("Image missing or low resolution: "+title)
            metadata=info.get("extmetadata",{})
            artist=clean(metadata.get("Artist",{}).get("value",""))
            actual_license=clean(metadata.get("LicenseShortName",{}).get("value",""))
            if norm(license_name)!=norm(actual_license):
                raise ValueError(f"Unexpected license {actual_license} for {title}")
            if norm(author) not in norm(artist):
                raise ValueError(f"Unexpected creator {artist} for {title}")
            img_res=session.get(info.get("thumburl") or info["url"],timeout=90)
            img_res.raise_for_status()
            with Image.open(io.BytesIO(img_res.content)) as orig:
                image=ImageOps.exif_transpose(orig).convert("RGB")
                if image.width<1000 or image.height<750:
                    raise ValueError("Downloaded image too small: "+title)
                image.thumbnail((1920,1500),Image.Resampling.LANCZOS)
                temp=OUT/f"ag_047_{slot}.webp.tmp"
                image.save(temp,format="WEBP",quality=88,method=5)
                if temp.stat().st_size<30000:
                    raise ValueError("Suspiciously small WebP: "+title)
                staged.append((temp,OUT/f"ag_047_{slot}.webp"))
                print(f"Validated {title}: creator={artist}, license={actual_license}, size={image.width}x{image.height}, bytes={temp.stat().st_size}")
        for temp,dest in staged:
            temp.replace(dest)
        print("Installed two Amberd images; slot 1 untouched.")
    except Exception:
        for temp,_ in staged: temp.unlink(missing_ok=True)
        raise
if __name__=="__main__":
    main()
