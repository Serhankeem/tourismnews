"""Build a code-owned JS display registry; never write operational data.

No unapproved Korean drafts belong in this Git-tracked review registry either.
Only current approved public metadata bindings become a site asset. The deployed
pipeline additionally controls which original records the browser can receive.
"""
import hashlib
import copy
import argparse
from datetime import date
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]


def approved_entries(registry, records, allowed_publishers):
    entries=registry['entries'];keys=[(r['kind'],r['url']) for r in entries]
    if len(keys)!=len(set(keys)):raise ValueError('duplicate_localization_key')
    out=[]
    for r in entries:
        if r.get('status')!='approved':
            if r.get('ko_title'):raise ValueError('unapproved_text_in_git_registry')
            continue
        src=records.get((r['kind'],r['url']))
        rights,accuracy=r.get('rights',{}),r.get('accuracy',{})
        if (not src or r['publisher'] not in allowed_publishers.get(r['kind'],set())
                or rights.get('status')!='approved' or accuracy.get('status')!='approved'
                or not rights.get('evidence_url') or not rights.get('basis') or not rights.get('verified_at')
                or not accuracy.get('basis') or not accuracy.get('reviewed_at')
                or rights.get('title_only') is not True or r.get('mode')!='independent_factual_label'):
            continue
        title=src['title'];ko=r.get('ko_title','')
        if (r.get('original_title')!=title or hashlib.sha256(title.encode()).hexdigest()!=r['original_title_sha256']
                or r['publisher']!=src.get('source',src.get('publisher')) or r['published_at']!=src['published_at']
                or re.findall(r'\d+(?:[.,]\d+)*',title)!=re.findall(r'\d+(?:[.,]\d+)*',ko)
                or not re.search('[가-힣]',ko) or not accuracy.get('preserved_tokens')
                or any(t not in title or t not in ko for t in accuracy['preserved_tokens'])):
            raise ValueError('inaccurate_or_stale_heading')
        out.append({k:r[k] for k in ['kind','url','publisher','published_at','original_title','ko_title','mode','note','attribution']}|
                   {'status':'approved','rights_status':'approved','accuracy_status':'approved','evidence_url':rights['evidence_url'],'preserved_tokens':accuracy['preserved_tokens']})
    return out


def build(root=ROOT,snapshot=None):
    read=lambda name:json.loads((root/name).read_text())
    sources=read('sources.json')['sources'];reports=read('reports_sources.json')['sources']
    snapshot=Path(snapshot or root)
    data_read=lambda name:json.loads((snapshot/name).read_text())
    # Reuse current gates, including PR #21 provider rights. A code asset must
    # not retain a caption whose original can no longer be publicly projected.
    import sys
    if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
    from src.visibility import PublicationGate
    from src.pipeline.policy import current_permission
    from src.news_discovery import configuration as providers
    from src.reports.engine import approved
    gate=PublicationGate(sources,current_permission(root),snapshot/'site/data',providers=providers(root))
    current_urls={r['url'] for r in gate.views(data_read('collector_state/archive.json')['articles'])[1]}
    report_cfg={s['id']:s for s in reports};model=read('operating_policy.json')
    report_urls={r['url'] for r in data_read('collector_state/reports_archive.json')['reports']
                 if r.get('publication_status')=='published' and r.get('source_id') in report_cfg
                 and report_cfg[r['source_id']].get('enabled',True) and approved(report_cfg[r['source_id']],model)}
    # Same six/eight-field bootstrap views, never mutated by this generator.
    records={('news',r['url']):r for r in data_read('site/data/newsroom.json')['articles'] if r['url'] in current_urls}
    records.update({('research',r['url']):r for r in data_read('site/data/reports.json')['reports'] if r['url'] in report_urls})
    allowed={'news':{s['name'] for s in sources if s.get('enabled',True) and s.get('publication',{}).get('status')=='approved'},
             'research':{s.get('name',s.get('publisher')) for s in reports if s.get('enabled',True) and s.get('publication',{}).get('status')=='approved'}}
    # Reports name is the registered publishing institution. Do not infer it
    # from language, URLs of search relays, or translated captions.
    for s in reports:
        if s.get('enabled',True) and s.get('publication',{}).get('status')=='approved' and s.get('publisher'):
            allowed['research'].add(s['publisher'])
    publishers=[]
    for s in sources:
        country=s.get('coverage',{}).get('publisher_jurisdiction')
        if country and s['name'] in allowed['news'] and (country=='KR' or (s['coverage'].get('jurisdiction_evidence_url') and s['coverage'].get('jurisdiction_checked_on'))):
            publishers.append({'name':s['name'],'country':country,'source_id':s['id'],
                'domains':s.get('article_domains') or [urlsplit(s['url']).hostname]})
    headings=approved_entries(read('content_localization.json'),records,allowed)
    result={'schema_version':1,'news_publishers':publishers,'headings':headings}
    return json.dumps(result,ensure_ascii=False,indent=2)+'\n'


def withdraw(registry, kind, url, at):
    result=copy.deepcopy(registry)
    entry=next(r for r in result['entries'] if r['kind']==kind and r['url']==url)
    text=entry.pop('ko_title',None)
    entry['status']='withdrawn'
    entry.setdefault('history',[]).append({'at':at,'to':'withdrawn',
        **({'ko_title_sha256':hashlib.sha256(text.encode()).hexdigest()} if text else {})})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--withdraw');parser.add_argument('--snapshot',type=Path);parser.add_argument('--kind',choices=['news','research'],default='research');args=parser.parse_args()
    if args.withdraw:
        path=ROOT/'content_localization.json'
        path.write_text(json.dumps(withdraw(json.loads(path.read_text()),args.kind,args.withdraw,date.today().isoformat()),ensure_ascii=False,indent=2)+'\n')
    (ROOT/'site/assets/content-localization.json').write_text(build(snapshot=args.snapshot))
