#!/usr/bin/env python3
"""Source-specific corrections for Armenia Guide. Never uses generated images.
Only replaces a site's set of three images after downloading and verifying
three actual Commons files with supported free licenses and sufficient pixels.
"""
import json, re, sys, time
from pathlib import Path
from io import BytesIO
from html import unescape
import requests
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'photo-curation-reviewed.json').read_text('utf-8'))['sites']
CATALOG={p['id']:p for p in json.loads((ROOT/'catalog.json').read_text('utf-8'))}
OUT=ROOT/'images'/'places'
OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session()
S.headers.update({'User-Agent':'ArmeniaGuide-Curation/1.0 (https://github.com/vartazaryankaren14/Armenia-guide; Wikimedia credit tracking)'})
API='https://commons.wikimedia.org/w/api.php'
def clean(value):
    return unescape(re.sub(r'<[^>]+>','',value or '')).strip()
def md(info,name):
    return clean((info.get('extmetadata',{}).get(name) or {}).get('value',''))
def lookup(filename):
    response=S.get(API,params={
      'action':'query','titles':'File:'+filename,
      'prop':'imageinfo','iiprop':'url|size|mime|extmetadata',
      'iiurlwidth':1800,'format':'json','formatversion':2
    },timeout=40)
    response.raise_for_status()
    page=(response.json().get('query') or {}).get('pages',[{}])[0]
    ii=(page.get('imageinfo') or [None])[0]
    if not ii: raise ValueError('File unavailable: '+filename)
    actual=page['title'].removeprefix('File:')
    if actual.casefold()!=filename.casefold(): raise ValueError('Unexpected redirect: '+actual)
    if ii.get('mime') not in ('image/jpeg','image/png','image/webp'):raise ValueError('Unsupported media')
    if ii.get('width',0)<1100 or ii.get('height',0)<650: raise ValueError('Low resolution')
    license_name=md(ii,'LicenseShortName')
    norm=license_name.lower().replace(' ','').replace('-','')
    if not (norm.startswith('ccby') or norm.startswith('cc0') or norm.startswith('pd') or 'publicdomain' in norm):
        raise ValueError('Unverified permissive license: '+license_name)
    return ii,actual,license_name
def download(ii,dest):
    url=ii.get('thumburl') or ii['url']
    r=S.get(url,timeout=90)
    r.raise_for_status()
    if len(r.content)>22000000:raise ValueError('File too large')
    with Image.open(BytesIO(r.content)) as raw:
        im=ImageOps.exif_transpose(raw).convert('RGB')
        if im.width<1000 or im.height<600:raise ValueError('Fetched image too small')
        im.thumbnail((1600,1200),Image.Resampling.LANCZOS)
        im.save(dest,'WEBP',quality=86,method=5)
def main():
    replacements=[]
    failures=[]
    report=[]
    for ident,spec in DATA.items():
        if ident == 'ag_040':
            print('PRESERVED ag_040: original gallery restored by owner request', flush=True)
            continue
        if ident not in CATALOG or CATALOG[ident]['name']!=spec['name']:
            failures.append(ident+': catalog mismatch')
            continue
        images=[]
        temps=[]
        try:
            if not (3 <= len(spec['files']) <= 5) or len(set(spec['files'])) != len(spec['files']): raise ValueError('Need three to five distinct sources')
            for slot,filename in enumerate(spec['files'],1):
                ii,actual,license_name=lookup(filename)
                target=OUT/f'{ident}_{slot}.webp'
                tmp=OUT/f'{ident}_{slot}.curation.tmp.webp'
                download(ii,tmp)
                temps.append((tmp,target))
                src=ii.get('descriptionurl') or 'https://commons.wikimedia.org/wiki/File:'+actual.replace(' ','_')
                images.append({'slot':slot,'file':actual,'source':src,
                               'author':md(ii,'Artist'),'license':license_name,
                               'license_url':md(ii,'LicenseUrl')})
                time.sleep(.3)
            for tmp,target in temps:tmp.replace(target)
            replacements.append(spec['name'])
            for a in images:
                report.append(f"- **{spec['name']}**, [{ident}_{a['slot']}.webp]({a['source']}): {a['author'] or 'автор — по ссылке'}, {a['license']}")
            print('UPDATED',ident,spec['name'],flush=True)
        except Exception as e:
            failures.append(f"{ident} {spec['name']}: {e}")
            print('SKIPPED',ident,str(e),flush=True)
        finally:
            for tmp,_ in temps:
                if tmp.exists():tmp.unlink()
    # Replace just the attribution entries associated with successfully corrected sites.
    credits=ROOT/'PHOTO_SOURCES.md'
    current=credits.read_text('utf-8').splitlines() if credits.exists() else ['# Источники фото Armenia Guide']
    names=set(replacements)
    kept=[line for line in current if not any(line.startswith('- **'+name+'**,') for name in names)]
    credits.write_text('\n'.join(kept+report)+'\n',encoding='utf-8')
    result={'updated_places':len(replacements),'updated_names':replacements,'failed':failures,
            'note':'Pictures are actual Wikimedia Commons uploads; location supported by source descriptions. Individual visual review is still recommended.'}
    (ROOT/'PHOTO_CURATION_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print('RESULT',json.dumps(result,ensure_ascii=False),flush=True)
    if failures:sys.exit(1)
if __name__=='__main__':main()
