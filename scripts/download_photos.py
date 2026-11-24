#!/usr/bin/env python3
"""Download genuine photos for Armenia Guide from Wikimedia Commons.

Runs in GitHub Actions (GitHub runner has Internet). It never invents filenames:
Commons API gives the actual image URL and source/credit metadata.
"""
from pathlib import Path
from html import unescape
from io import BytesIO
import json, os, re, time, sys
from urllib.parse import quote
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/'catalog.json').read_text(encoding='utf8'))
QUERIES=json.loads((ROOT/'photo-queries.json').read_text(encoding='utf8'))
VERIFIED=json.loads((ROOT/'photo-verified.json').read_text(encoding='utf8'))
OUT=ROOT/'images'/'places'
OUT.mkdir(parents=True,exist_ok=True)
API='https://commons.wikimedia.org/w/api.php'
ua='ArmeniaGuideBot/2.0 (https://github.com/vartazaryankaren14/Armenia-guide; public tour guide image attribution)' 
S=requests.Session()
S.headers.update({'User-Agent':ua,'Accept':'application/json,image/webp,image/jpeg,image/png,*/*;q=0.5'})
retry=Retry(total=4,backoff_factor=2,status_forcelist=[429,500,502,503,504],allowed_methods=['GET'])
S.mount('https://',HTTPAdapter(max_retries=retry,pool_connections=3,pool_maxsize=3))

def get_pages(q):
    params={'action':'query','generator':'search','gsrsearch':q,'gsrnamespace':'6','gsrlimit':'20',
            'prop':'imageinfo','iiprop':'url|size|mime|extmetadata','iiurlwidth':'1200','format':'json','formatversion':'2'}
    data=S.get(API,params=params,timeout=30)
    data.raise_for_status()
    return (data.json().get('query') or {}).get('pages',[])

def get_specific(files):
    if not files:return []
    params={'action':'query','titles':'|'.join('File:'+f for f in files),'prop':'imageinfo',
            'iiprop':'url|size|mime|extmetadata','iiurlwidth':'1200','format':'json','formatversion':'2'}
    data=S.get(API,params=params,timeout=30)
    data.raise_for_status()
    return (data.json().get('query') or {}).get('pages',[])

def score(page,query):
    title=page.get('title','').casefold()
    words=[w.casefold() for w in re.findall(r'[A-Za-z]{4,}',query) if w.lower() not in ('armenia','monastery','yerevan','lake','church','temple','fortress','park')]
    match=sum(w in title for w in words)
    return match*4 + (2 if 'armenia' in title else 0)

def acceptable(page):
    ii=(page.get('imageinfo') or [{}])[0]
    if 'missing' in page or not ii.get('thumburl') and not ii.get('url'):return False
    if ii.get('mime') not in ('image/jpeg','image/png','image/webp'):return False
    if ii.get('width',0)<1000 or ii.get('height',0)<450:return False
    title=page.get('title','').lower()
    if re.search(r'\.(svg|gif)$|logo|flag|coat.of.arms|map.of|emblem|vector|graphic|floor.plan|postcard|stamp|badge|icon',title):return False
    return True

def tidy(html):
    return unescape(re.sub(r'<[^>]+>','',html or '')).strip()[:180]

def save_image(page,path):
    ii=page['imageinfo'][0]
    src=ii.get('thumburl') or ii['url']
    response=S.get(src,timeout=50)
    response.raise_for_status()
    if len(response.content)>16_000_000:raise ValueError('image >16MB')
    with Image.open(BytesIO(response.content)) as im:
        im=ImageOps.exif_transpose(im).convert('RGB')
        if im.width<800 or im.height<400:raise ValueError('image too small')
        im.thumbnail((1200,1000),Image.Resampling.LANCZOS)
        im.save(path,'WEBP',quality=80,method=5)
    md=ii.get('extmetadata') or {}
    def meta(key): return tidy((md.get(key) or {}).get('value',''))
    return {
        'source':ii.get('descriptionurl') or 'https://commons.wikimedia.org/wiki/'+quote(page['title'].replace(' ','_')),
        'file':page.get('title',''),
        'author':meta('Artist'),
        'license':meta('LicenseShortName'),
        'license_url':meta('LicenseUrl'),
    }

def main():
    totals={'places':len(CATALOG),'images':0,'places_with_images':0,'missing':[]}
    credit=['# Источники изображений Armenia Guide','','Фотографии взяты из Wikimedia Commons. Перед публикацией соблюдайте условия соответствующей лицензии.','']
    # Preserve manually curated and AI-generated images when this job is rerun.
    protected_ids={'ag_034','ag_035','ag_036','ag_037','ag_038','ag_039'}
    curated=ROOT/'photo-curation-reviewed.json'
    if curated.exists():
        try:
            protected_ids.update(json.loads(curated.read_text('utf8')).get('sites',{}))
        except Exception as exc:
            print('WARN curated metadata could not be read:',exc,flush=True)
    # Never overwrite photo galleries curated through the conservative batch workflow.
    batch=ROOT/'PHOTO_BATCH_RESULT.json'
    if batch.exists():
        try:
            protected_ids.update(json.loads(batch.read_text('utf8')).get('updated_slots',{}))
        except Exception as exc:
            print('WARN batch metadata could not be read:',exc,flush=True)
    # Individual editorial choices must survive an unrelated generic downloader run.
    for reference in ('photo-selection-manual.json', 'PHOTO_MANUAL_PROGRESS.json'):
        source=ROOT/reference
        if source.exists():
            try:
                manual=json.loads(source.read_text('utf8'))
                protected_ids.update(manual.get('sites',{}))
                protected_ids.update(manual.get('successful',{}))
            except Exception as exc:
                print('WARN manual curation protections:',exc,flush=True)
    # Protect every individually reviewed gallery, including untouched original
    # images retained for aesthetics after manual review.
    editorial_review=ROOT/'PHOTO_VISUAL_REVIEW_2026-11-25.json'
    if editorial_review.exists():
        try:
            protected_ids.update(x['id'] for x in json.loads(editorial_review.read_text('utf8')).get('galleries',[]))
            protected_ids.add('ag_106')
        except Exception as exc:
            print('WARN editorial review protections:',exc,flush=True)
    previous_credits=(ROOT/'PHOTO_SOURCES.md').read_text('utf8').splitlines() if (ROOT/'PHOTO_SOURCES.md').exists() else []
    for k,p in enumerate(CATALOG,1):
        if p['id'] in protected_ids:
            preserved=[OUT/(p['id']+'_'+str(i)+'.webp') for i in (1,2,3)]
            count=sum(f.exists() for f in preserved)
            totals['images']+=count
            if count: totals['places_with_images']+=1
            else: totals['missing'].append(p['name'])
            credit.extend(line for line in previous_credits if line.startswith('- **'+p['name']+'**,'))
            print(f'[{k:02d}/{len(CATALOG)}] PRESERVED {p["name"]}: {count}/3 photos',flush=True)
            continue
        name=p['name'];q=QUERIES.get(name) or name+' Armenia'
        # The first image for Garni and Geghard is an AI-generated illustration embedded in index.html.
        goal=2 if name in ('Храм Гарни','Монастырь Гегард') else 3
        candidates=[]
        try: candidates+=get_specific(VERIFIED.get(name,[]))
        except Exception as e:print('WARN verified Commons lookup:',name,str(e),flush=True)
        try: candidates+=get_pages(q)
        except Exception as e:print('WARN Commons search:',name,str(e),flush=True)
        if len(candidates)<goal:
            try: candidates+=get_pages(name+' Armenia')
            except Exception as e:print('WARN alternate search:',name,str(e),flush=True)
        unique={}
        for page in candidates:
            if acceptable(page):unique.setdefault(page.get('title'),page)
        rank=list(unique.values())
        rank.sort(key=lambda x:score(x,q),reverse=True)
        selected=[]
        for page in rank:
            if len(selected)>=goal:break
            target=OUT/(p['id']+'_'+str(len(selected)+1)+'.webp')
            try:
                metadata=save_image(page,target)
            except Exception as e:
                print('Could not fetch:',page.get('title'),e,flush=True)
                continue
            selected.append((target,metadata))
            time.sleep(0.45)
        totals['images']+=len(selected)
        if selected:totals['places_with_images']+=1
        else:totals['missing'].append(name)
        for path,metadata in selected:
            credit.append(f"- **{name}**, [{path.name}]({metadata['source']}): {metadata['author'] or 'автор — по ссылке'}, {metadata['license'] or 'лицензия — по ссылке'}")
        print(f'[{k:02d}/{len(CATALOG)}] {name}: {len(selected)}/{goal} photos',flush=True)
        time.sleep(0.65)
    (ROOT/'PHOTO_SOURCES.md').write_text('\n'.join(credit)+'\n',encoding='utf8')
    (ROOT/'PHOTO_STATUS.json').write_text(json.dumps(totals,ensure_ascii=False,indent=2),encoding='utf8')
    print('SUMMARY',json.dumps(totals,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
