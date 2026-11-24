#!/usr/bin/env python3
"""Conservative Commons photo curation for the remaining Armenia Guide locations.
Never modifies approved or previously manually curated galleries.
"""
import json, math, re, time, traceback
from html import unescape
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageOps, ImageStat, ImageFilter

ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/"catalog.json").read_text("utf-8"))
QUERIES=json.loads((ROOT/"photo-queries.json").read_text("utf-8"))
CURATED=json.loads((ROOT/"photo-curation-reviewed.json").read_text("utf-8")).get("sites",{})
SOURCE=ROOT/"PHOTO_SOURCES.md"
OUT=ROOT/"images"/"places"
OUT.mkdir(parents=True,exist_ok=True)
API="https://commons.wikimedia.org/w/api.php"
S=requests.Session()
S.headers.update({"User-Agent":"ArmeniaGuideBatchCuration/1.1 (https://github.com/vartazaryankaren14/Armenia-guide; photo sources and licenses)","Accept":"application/json,image/webp,image/jpeg,*/*"})
S.mount("https://",HTTPAdapter(max_retries=Retry(total=4,backoff_factor=1,status_forcelist=[429,500,502,503,504]),pool_connections=5,pool_maxsize=5))
EXEMPT={"Озеро Кари","Ущелье Касах","Монастырь Гегард","Храм Гарни",
        "Вулкан Аждаак","Озеро Севан","Кладбище хачкаров Норатус"}
# These eight places have already been manually updated and approved in the guide.
DONE={"Ущелье Касах","Цахкадзор","Монастырь Гегард","Храм Гарни",
      "Дилижан","Монастырь Макараванк","Озеро Цовер","Степанаванский дендропарк"}
START=next(i for i,x in enumerate(CAT) if x["id"]=="ag_051")+1
TARGETS=[p for p in CAT[START:] if p["name"] not in EXEMPT|DONE and p["name"]!="Гора Димац" and p["id"] not in CURATED]
assert len(TARGETS)==48, "Unexpected target count: "+str(len(TARGETS))
ALIASES={
 "Ангельский каньон":["angel","canyon"],
 "Водохранилище Азат":["azat","reservoir"],
 "Арка Чаренца":["charents"],
 "Симфония камней":["symphony of stones","basalt columns","garni gorge"],
 "Айраванк":["hayravank","airavank"],
 "Монастырь Агарцин":["haghartsin"],
 "Монастырь Гошаванк":["goshavank"],
 "Озеро Гош":["gosh lake","lake gosh"],
 "Монастырь Кобайр":["kobayr","kobair"],
 "Крепость Лори Берд":["lori berd","loriberd"],
 "Чёрная крепость":["black fortress","sev berd"],
 "Орбелянов караван-сарай":["orbelian","selim caravan"],
 "Пещера Арени-1":["areni-1","areni 1","areni cave"],
 "Село Арени":["areni village","village of areni"],
 "Канатная дорога «Крылья Татева»":["wings of tatev","tatev cable"],
 "Караундж (Зорац Карер)":["zorats karer","karahunj"],
 "Хндзореск и подвесной мост":["khndzoresk"],
 "Чертов мост":["devil bridge","devil's bridge","satani kamurj"],
 "Шикахохский заповедник":["shikahogh"],
 "Озеро Парз":["parz"],
 "Севанаванк":["sevanavank"],
 "Монастырь Мармашен":["marmashen"],
 "Монастырь Кечарис":["kecharis"],
 "Водопад Трчкан":["trchkan"],
 "Одзун":["odzun"],
 "Ахпат":["haghpat"],
 "Санаин":["sanahin"],
 "Сагмосаванк":["saghmosavank","sagmosavank"],
 "Двин":["dvin"],
 "Хор Вирап":["khor virap"],
 "Крепость Бжни":["bjni"],
 "Ластивер":["lastiver"],
 "Енокаван":["yenokavan"],
 "Озеро Арпи":["arpi"],
 "Харичаванк":["harichavank"],
 "Гндеванк":["gndevank"],
 "Спитакавор":["spitakavor"],
 "Нораванк":["noravank"],
 "Мегри":["meghri"],
 "Татевский монастырь":["tatev"],
 "Горис":["goris"],
 "Джермук":["jermuk"],
 "Джермукский водопад":["jermuk","waterfall"],
 "Шакинский водопад":["shaki"],
 "Шоржа":["shorzha"],
 "Дебедское ущелье":["debed"],
 "Гюмри":["gyumri"],
 "Ахтала":["akhtala"]
}
NEGATIVE=re.compile(r"\b(map|logo|postcard|flag|signage|portrait|selfie|diagram|painting|poster|stamp|illustration|icon|school|politician|census)\b",re.I)
MAX_FILES=9
def plain(v):
 return unescape(re.sub(r"<[^>]+>","",v or "")).strip()
def ext(ii,key):
 return plain((ii.get("extmetadata") or {}).get(key,{}).get("value",""))
def get(params):
 rr=S.get(API,params={**params,"format":"json","formatversion":2},timeout=40)
 rr.raise_for_status()
 return (rr.json().get("query") or {}).get("pages",[])
def specifics(names):
 out=[]
 for st in range(0,len(names),18):
  out+=get({"action":"query","titles":"|".join("File:"+f for f in names[st:st+18]),"prop":"imageinfo","iiprop":"url|mime|size|extmetadata","iiurlwidth":1500})
 return out
def search(query):
 return get({"action":"query","generator":"search","gsrsearch":query,"gsrnamespace":6,"gsrlimit":35,"prop":"imageinfo","iiprop":"url|mime|size|extmetadata","iiurlwidth":1500})
def filename(page):
 return page.get("title","").removeprefix("File:")
def matches(page,place):
 title=filename(page).lower().replace("_"," ")
 desc=plain((page.get("imageinfo") or [{}])[0].get("extmetadata",{}).get("ImageDescription",{}).get("value","")).lower()
 aliases=ALIASES.get(place["name"])
 if not aliases:
  q=QUERIES.get(place["name"],"").lower()
  aliases=[w for w in re.findall(r"[a-z]{4,}",q) if w not in {"armenia","monastery","church","lake","waterfall","fortress","mount","cave","village","tour","park","reserve","bridge","temple","city","mountain","yerevan","national"}]
  aliases=aliases[:2]
 if not aliases: return False
 text=title+" "+desc[:450]
 # Some specific landmarks need both tokens, not just the shared city name.
 if place["name"]=="Джермукский водопад": return "jermuk" in text and ("waterfall" in text or "cascade" in text)
 if place["name"]=="Джермук": return "jermuk" in text and "waterfall" not in title
 if place["name"]=="Водохранилище Азат": return "azat" in text and ("reservoir" in text or "lake" in text)
 if place["name"]=="Пещера Арени-1": return "areni" in text and ("cave" in text or "karst" in text)
 if place["name"]=="Село Арени": return "areni" in text and "cave" not in title
 if place["name"]=="Озеро Арпи": return "arpi" in text and ("lake" in text or "լիճ" in text)
 if place["name"]=="Озеро Гош": return "gosh" in text and ("lake" in text or "լիճ" in text)
 if place["name"]=="Чертов мост": return any(a in text for a in aliases) and ("armenia" in text or "tatev" in text or "syunik" in text)
 return any(a in text for a in aliases)
def acceptable(page,place):
 ii=(page.get("imageinfo") or [None])[0]
 if not ii or ii.get("mime") not in {"image/jpeg","image/png","image/webp"}:return False
 w,h=ii.get("width",0),ii.get("height",0)
 if w<1600 or h<850 or w/h<1.06 or w/h>2.75:return False
 if NEGATIVE.search(filename(page)):return False
 license=ext(ii,"LicenseShortName").lower().replace(" ","").replace("-","")
 if not (license.startswith(("ccby","cc0","pd")) or "publicdomain" in license):return False
 return matches(page,place)
def page_score(page):
 ii=page["imageinfo"][0]
 w,h=ii["width"],ii["height"]; ratio=w/h
 title=filename(page).lower()
 score=math.log2(w*h/1000000+1)*1.7
 score+=2 if 1.25<=ratio<=2.0 else 0
 if any(x in title for x in ("panorama","aerial","drone","sunset","view","landscape")):score+=0.8
 if any(x in title for x in ("interior","detail","entrance","door","facade")):score+=0.7
 if any(x in title for x in ("2024","2025","2026")):score+=0.3
 return score
def angle(page):
 t=filename(page).lower()
 for group,keys in [("interior",["interior","inside","hall","vault"]),("aerial",["aerial","drone","from above"]),("detail",["detail","facade","door","gate","khachkar"]),("wide",["panorama","landscape","general view"]),("evening",["sunset","sunrise","dusk","night"]),("winter",["winter","snow"])]:
  if any(k in t for k in keys):return group
 return "view"
def get_image(page):
 ii=page["imageinfo"][0]
 response=S.get(ii.get("thumburl") or ii["url"],timeout=65)
 response.raise_for_status()
 if len(response.content)>20_000_000: raise ValueError("oversized image")
 with Image.open(BytesIO(response.content)) as orig:
  img=ImageOps.exif_transpose(orig).convert("RGB")
  if img.width<900 or img.height<540:raise ValueError("small downloaded image")
  img.thumbnail((1500,1150),Image.Resampling.LANCZOS)
  return img
def dhash(image):
 im=image.convert("L").resize((9,8))
 pix=list(im.getdata())
 return sum((1<<(y*8+x)) for y in range(8) for x in range(8) if pix[y*9+x]>pix[y*9+x+1])
def aesthetic(im):
 small=im.resize((220,160),Image.Resampling.BILINEAR)
 gray=small.convert("L")
 st=ImageStat.Stat(gray)
 mean=st.mean[0]
 contrast=st.stddev[0]
 edge=ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).stddev[0]
 return (min(contrast,70)/70)*1.2+(min(edge,52)/52)*0.7-(1.2 if mean<47 or mean>215 else 0)
def old_file_list(name,lines):
 items={}
 for line in lines:
  if line.startswith("- **"+name+"**,"):
   m=re.search(r"\[([^\]]+)\]\((https://commons\.wikimedia\.org/wiki/File:[^)]+)\)",line)
   if m:
    n=re.search(r"_(\d+)\.webp",m.group(1))
    if n:items[int(n.group(1))]=unquote(m.group(2).split("/wiki/File:",1)[1]).replace("_"," ")
 return items
def metadata(p):
 ii=p["imageinfo"][0]
 return {"file":filename(p),"source":ii.get("descriptionurl") or "https://commons.wikimedia.org/wiki/File:"+filename(p).replace(" ","_"),
         "author":ext(ii,"Artist"),"license":ext(ii,"LicenseShortName"),"license_url":ext(ii,"LicenseUrl")}
def write_image(im,path):
 im.save(path,"WEBP",quality=86,method=5)
def choose(place,credits):
 original=old_file_list(place["name"],credits)
 pages={}
 try:
  for p in specifics(list(original.values())):
   if acceptable(p,place):pages[filename(p)]=p
 except Exception as exc:print("WARN original metadata:",place["name"],str(exc),flush=True)
 q=QUERIES.get(place["name"],place["name"]+" Armenia")
 try:
  for p in search(q):
   if acceptable(p,place):pages.setdefault(filename(p),p)
 except Exception as exc:print("WARN Commons search:",place["name"],str(exc),flush=True)
 if len(pages)<3: return None,"Not enough verified high-resolution Commons photos"
 origfiles=set(original.values())
 ranked=sorted(pages.values(),key=lambda p:page_score(p)+(1.5 if filename(p) in origfiles else 0),reverse=True)[:MAX_FILES]
 candidates=[]
 for p in ranked:
  try:
   im=get_image(p)
   candidates.append({"p":p,"im":im,"hash":dhash(im),"score":page_score(p)+aesthetic(im)+(1.5 if filename(p) in origfiles else 0),"angle":angle(p),"author":ext(p["imageinfo"][0],"Artist")})
  except Exception as exc:print("WARN preview:",filename(p),str(exc),flush=True)
  time.sleep(.12)
 if len(candidates)<3: return None,"Not enough validated downloaded photos"
 selected=[]
 while candidates and len(selected)<3:
  valid=[c for c in candidates if not selected or all((c["hash"]^x["hash"]).bit_count()>=9 for x in selected)]
  if not valid:break
  def val(c):
   bonus=0.0
   if selected:
    bonus+=1.0 if c["angle"] not in [x["angle"] for x in selected] else -0.8
    bonus+=0.5 if c["author"] not in [x["author"] for x in selected] else -0.3
    bonus+= min(1.2,min((c["hash"]^x["hash"]).bit_count() for x in selected)/30)
   return c["score"]+bonus
  choice=max(valid,key=val)
  selected.append(choice)
  candidates.remove(choice)
 if len(selected)<3:return None,"Three different photos not available (perceptual similarity)"
 # Place an already selected existing file in its original slot, to preserve original images where good.
 assigned={}
 for slot,oldname in original.items():
  for s in selected:
   if s["p"] and filename(s["p"])==oldname and slot in (1,2,3):
    assigned[slot]=s
 used={id(x) for x in assigned.values()}
 for item in selected:
  if id(item) in used:continue
  for slot in (1,2,3):
   if slot not in assigned:
    assigned[slot]=item;used.add(id(item));break
 return assigned,None
def main():
 credits=SOURCE.read_text("utf8").splitlines()
 output=[]; replaced_ids={};preserved=[];failures=[]
 for idx,p in enumerate(TARGETS,1):
  print(f"[{idx}/{len(TARGETS)}] {p['name']}",flush=True)
  try:
   selected,reason=choose(p,credits)
   if selected is None:
    failures.append({"id":p["id"],"name":p["name"],"reason":reason});continue
   previous=old_file_list(p["name"],credits)
   changed=[]
   for slot,item in sorted(selected.items()):
    if filename(item["p"])!=previous.get(slot):
     temp=OUT/f"{p['id']}_{slot}.batch.tmp.webp"
     write_image(item["im"],temp)
     changed.append((slot,temp,OUT/f"{p['id']}_{slot}.webp"))
   if not changed:
    preserved.append(p["name"])
    continue
   for _,tmp,dest in changed:tmp.replace(dest)
   replaced_ids[p["id"]]=[s for s,_,_ in changed]
   credits=[s for s in credits if not s.startswith("- **"+p["name"]+"**,")]
   for slot,item in sorted(selected.items()):
    m=metadata(item["p"])
    credits.append(f"- **{p['name']}**, [{p['id']}_{slot}.webp]({m['source']}): {m['author'] or 'автор на странице источника'}, {m['license']} (масштабировано и перекодировано)")
   print("  UPDATED slots",replaced_ids[p["id"]],flush=True)
  except Exception as exc:
   failures.append({"id":p["id"],"name":p["name"],"reason":str(exc)})
   print("  SKIPPED",str(exc),flush=True)
 # Precisely replace Dimats slot 3; leave slots 1 and 2 untouched.
 dim=next(x for x in CAT if x["id"]=="ag_106")
 try:
  files=specifics(["View of Mount Dimats in Dilijan National Park.jpg"])
  p=next(p for p in files if filename(p)=="View of Mount Dimats in Dilijan National Park.jpg" and acceptable(p,{"name":"Гора Димац"}))
  im=get_image(p)
  tmp=OUT/"ag_106_3.batch.tmp.webp";write_image(im,tmp);tmp.replace(OUT/"ag_106_3.webp")
  replaced_ids["ag_106"]=[3]
  credits=[s for s in credits if not (s.startswith("- **Гора Димац**,") and "[ag_106_3.webp]" in s)]
  m=metadata(p)
  credits.append(f"- **Гора Димац**, [ag_106_3.webp]({m['source']}): {m['author'] or 'автор на странице источника'}, {m['license']} (масштабировано и перекодировано)")
  print("Dimats third image updated.",flush=True)
 except Exception as exc:
  failures.append({"id":"ag_106","name":"Гора Димац","reason":"slot 3: "+str(exc)})
  print("DIMATS SKIPPED",str(exc),flush=True)
 # Cache-bust only changed photo slots; all other galleries are untouched.
 htmlp=ROOT/"index.html"
 html=htmlp.read_text("utf8")
 for ident,slots in replaced_ids.items():
  item=next(x for x in CAT if x["id"]==ident)
  for slot in slots:
   bare=f"images/places/{ident}_{slot}.webp"
   new=bare+"?v=curated-20261125"
   for j,path in enumerate(item.get("photos",[])):
    if path.split("?")[0]==bare:item["photos"][j]=new
   html=re.sub(re.escape(bare)+r"(?:\?v=[\w-]+)?",new,html)
 (ROOT/"catalog.json").write_text(json.dumps(CAT,ensure_ascii=False,indent=2)+"\n","utf8")
 htmlp.write_text(html,"utf8")
 SOURCE.write_text("\n".join(credits)+"\n","utf8")
 report={"total_candidates":len(TARGETS),"galleries_with_updates":sum(1 for x in replaced_ids if x!="ag_106"),
   "unchanged_quality_preserved":preserved,"updated_slots":replaced_ids,"failures":failures,
   "excluded":sorted(EXEMPT|DONE),"message":"Only files identified as correct places, sufficient resolution and Wikimedia open license were considered; visual editorial review remains advisable."}
 (ROOT/"PHOTO_BATCH_RESULT.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n","utf8")
 print("BATCH RESULT",json.dumps({"updated":len(replaced_ids),"unchanged":len(preserved),"failed":len(failures)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
