#!/usr/bin/env python3
"""Install specific editorially selected real photographs without touching other slots.

The manifest is curated by hand. This deliberately does NOT run the generic
automatic search/ranking task that was rejected by the owner.
"""
import json, re, time
from html import unescape
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
import requests
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"photo-selection-manual.json"
DATA=json.loads(MANIFEST.read_text("utf-8"))
CATALOG=ROOT/"catalog.json"
INDEX=ROOT/"index.html"
SOURCES=ROOT/"PHOTO_SOURCES.md"
REPORT=ROOT/"PHOTO_MANUAL_PROGRESS.json"
IMAGES=ROOT/"images"/"places"
API="https://commons.wikimedia.org/w/api.php"
S=requests.Session()
S.headers["User-Agent"]="ArmeniaGuideManualPhotoEditor/1.0 (https://github.com/vartazaryankaren14/Armenia-guide; CC image licensing)"
DO_NOT_TOUCH={"Озеро Кари","Ущелье Касах","Монастырь Гегард","Храм Гарни",
 "Вулкан Аждаак","Озеро Севан","Кладбище хачкаров Норатус",
 "Эчмиадзинский кафедральный собор","Ованаванк",
 "Цахкадзор","Дилижан","Монастырь Макараванк","Озеро Цовер",
 "Степанаванский дендропарк","Бюраканская обсерватория","Гора Арагац",
 "Крепость Амберд","Монастырь Тегер"}
def tidy(html):return unescape(re.sub(r"<[^>]+>","",html or "")).strip()
def field(info,name):return tidy((info.get("extmetadata") or {}).get(name,{}).get("value",""))
def commons(name):
 r=S.get(API,params={"action":"query","titles":"File:"+name,
  "prop":"imageinfo","iiprop":"url|size|mime|extmetadata",
  "iiurlwidth":1600,"format":"json","formatversion":2},timeout=40)
 r.raise_for_status()
 p=(r.json().get("query") or {}).get("pages",[{}])[0]
 info=(p.get("imageinfo") or [None])[0]
 if not info:raise ValueError("Commons file not found: "+name)
 actual=p.get("title","").removeprefix("File:")
 if actual.casefold()!=name.casefold():raise ValueError("Unexpected Commons filename: "+actual)
 if info.get("mime") not in ("image/jpeg","image/png","image/webp"):raise ValueError("Unsupported MIME: "+name)
 if info.get("width",0)<1200 or info.get("height",0)<650:raise ValueError("Low resolution: "+name)
 license=field(info,"LicenseShortName")
 normalized=license.lower().replace("-","").replace(" ","")
 if not (normalized.startswith(("ccby","cc0","pd")) or "publicdomain" in normalized):
  raise ValueError("License not accepted: "+license+" "+name)
 return actual,info,license
def install_photo(info,target):
 url=info.get("thumburl") or info["url"]
 resp=S.get(url,timeout=95)
 resp.raise_for_status()
 if len(resp.content)>23_000_000:raise ValueError("Photo download >23 MB")
 with Image.open(BytesIO(resp.content)) as original:
  im=ImageOps.exif_transpose(original).convert("RGB")
  if im.width<900 or im.height<500:raise ValueError("Downloaded image too small")
  im.thumbnail((1600,1300),Image.Resampling.LANCZOS)
  im.save(target,"WEBP",quality=87,method=5)
def main():
 places=json.loads(CATALOG.read_text("utf-8"))
 by_id={p["id"]:p for p in places}
 html=INDEX.read_text("utf-8")
 credits=SOURCES.read_text("utf-8").splitlines()
 successes=[];errors=[]
 for ident,entry in DATA["sites"].items():
  item=by_id.get(ident)
  if not item or item["name"]!=entry["name"]:
   errors.append({"id":ident,"reason":"Catalog identity mismatch"});continue
  if item["name"] in DO_NOT_TOUCH:
   errors.append({"id":ident,"reason":"This card is protected"});continue
  if ident=="ag_106" and set(entry["slots"].keys())!={"3"}:
   errors.append({"id":ident,"reason":"Dimats: third image only"});continue
  staged=[];meta=[]
  try:
   for slot,value in sorted(entry["slots"].items(),key=lambda t:int(t[0])):
    slot=int(slot)
    if slot not in (1,2,3):raise ValueError("Unexpected photo slot")
    desired=f"images/places/{ident}_{slot}.webp"
    if not any(p.split("?")[0]==desired for p in item["photos"]):
     raise ValueError("Slot missing from gallery: "+desired)
    fname,info,lic=commons(value)
    temp=IMAGES/f"{ident}_{slot}.manual.tmp.webp"
    install_photo(info,temp)
    staged.append((temp,IMAGES/f"{ident}_{slot}.webp"))
    meta.append((slot,fname,info,lic))
    time.sleep(.1)
   for tmp,target in staged:tmp.replace(target)
   version="handpicked-20261125"
   for slot,fname,info,lic in meta:
    base=f"images/places/{ident}_{slot}.webp"
    new=base+"?v="+version
    item["photos"]=[new if p.split("?")[0]==base else p for p in item["photos"]]
    # Same gallery references are embedded in the standalone Telegram Mini App.
    html,n=re.subn(re.escape(base)+r"(?:\?v=[A-Za-z0-9_-]+)?",lambda _:new,html)
    if not n:raise ValueError("Mini App HTML does not reference "+base)
    marker=f"[{ident}_{slot}.webp]"
    credits=[c for c in credits if not
      (c.startswith("- **"+item["name"]+"**,") and marker in c)]
    uri="https://commons.wikimedia.org/wiki/File:"+quote(fname.replace(" ","_"),safe="-_/.:")
    artist=field(info,"Artist") or "автор указан на Wikimedia Commons"
    credits.append(f"- **{item['name']}**, {marker}({uri}): {artist}, {lic}. Исходное изображение уменьшено и перекодировано в WebP.")
   successes.append({"id":ident,"name":item["name"],"changed_slots":[m[0] for m in meta],
       "files":[m[1] for m in meta]})
   print("UPDATED",item["name"],[m[0] for m in meta],flush=True)
  except Exception as exc:
   errors.append({"id":ident,"name":item["name"],"reason":str(exc)})
   print("SKIPPED",ident,str(exc),flush=True)
  finally:
   for tmp,_ in staged:
    if tmp.exists():tmp.unlink()
 CATALOG.write_text(json.dumps(places,ensure_ascii=False,indent=2)+"\n","utf-8")
 INDEX.write_text(html,"utf-8")
 SOURCES.write_text("\n".join(credits)+"\n","utf-8")
 prev={}
 if REPORT.exists():
  try:prev=json.loads(REPORT.read_text("utf-8")).get("successful",{})
  except Exception:pass
 for x in successes:prev[x["id"]]=x
 REPORT.write_text(json.dumps({"successful":prev,"last_run_errors":errors,
    "do_not_touch":sorted(DO_NOT_TOUCH),"editorial_policy":"Manually approved Wikimedia filenames, exact slots only. Original photo preserved in all other slots. Generated art requires explicit labels."},
    ensure_ascii=False,indent=2)+"\n","utf-8")
 print("SUMMARY",len(successes),"cards; errors:",len(errors),flush=True)

if __name__=="__main__":main()
