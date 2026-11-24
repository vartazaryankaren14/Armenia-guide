#!/usr/bin/env python3
"""Install exactly two distinct authentic Tegher Monastery images, no other photos."""
from __future__ import annotations
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
    (2,"Tegher Gavit Dome.JPG"),
    (3,"Tegher Monastery from Aragats.jpg"),
)
session=requests.Session()
session.headers.update({"User-Agent":"ArmeniaGuide-TegherCurated/1.0 (https://github.com/vartazaryankaren14/Armenia-guide)"})
session.mount("https://",HTTPAdapter(max_retries=Retry(total=5,backoff_factor=2,status_forcelist=(429,500,502,503,504))))

def plain(x):
    return unescape(re.sub(r"<[^>]*>","",x or "")).strip()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    staged=[]
    try:
        for slot,name in SELECTED:
            r=session.get(API,params={
                "action":"query","titles":"File:"+name,"prop":"imageinfo",
                "iiprop":"url|size|mime|extmetadata","iiurlwidth":"1920",
                "format":"json","formatversion":"2"
            },timeout=65)
            r.raise_for_status()
            page=r.json()["query"]["pages"][0]
            info=page.get("imageinfo",[None])[0]
            if not info or info.get("mime")!="image/jpeg" or info.get("width",0)<1900 or info.get("height",0)<1200:
                raise ValueError("Invalid source photo or insufficient resolution "+name)
            meta=info.get("extmetadata",{})
            license_name=plain(meta.get("LicenseShortName",{}).get("value",""))
            artist=plain(meta.get("Artist",{}).get("value",""))
            if not re.fullmatch(r"CC BY(?:-SA)? [2-4]\.0",license_name):
                raise ValueError(f"Unexpected non-CC attribution license {license_name!r} for {name}")
            if not artist:
                raise ValueError("Missing creator for "+name)
            photo=session.get(info.get("thumburl") or info["url"],timeout=95)
            photo.raise_for_status()
            with Image.open(io.BytesIO(photo.content)) as original:
                image=ImageOps.exif_transpose(original).convert("RGB")
                if image.width<1050 or image.height<800:
                    raise ValueError("Low downloaded image resolution for "+name)
                image.thumbnail((1920,1600),Image.Resampling.LANCZOS)
                temp=OUT/f"ag_099_{slot}.webp.tmp"
                image.save(temp,format="WEBP",quality=88,method=6)
                if temp.stat().st_size<25000:
                    raise ValueError("Unexpectedly small output for "+name)
                staged.append((temp,OUT/f"ag_099_{slot}.webp"))
                print(f"TEGHER_SLOT_{slot}: source={name}; artist={artist}; license={license_name}; original={info.get('width')}x{info.get('height')}; installed={image.width}x{image.height}; bytes={temp.stat().st_size}",flush=True)
        for temp,path in staged:
            temp.replace(path)
        print("TEGHER_OK: replaced slots 2 and 3 only; slot 1 unchanged",flush=True)
    except Exception:
        for temp,_ in staged:
            temp.unlink(missing_ok=True)
        raise

if __name__=="__main__":
    main()
