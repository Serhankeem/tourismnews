"""Recheck current code's permissions even for non-news/code-only deployments."""
import hashlib
from pathlib import Path
from .layout import read
from .validation import ValidationError
from ..collector import write_atomic, iso
from ..briefing import recent_news
from ..collector import timestamp
import datetime as dt
from ..visibility import PublicationGate
from ..engine import permission
from ..publication import public_record
from ..briefing import select
from ..reports.engine import approved
from ..reports.model import public as public_report
from ..coverage import coverage
from ..macro.engine import public_view


def current_permission(code):
    model=read(Path(code)/'operating_policy.json')
    def allowed(source):
        policy=source.get('publication',{})
        if policy.get('noncommercial_only') and (model.get('mode')!='noncommercial' or model.get('ads_enabled') is not False or model.get('paid_access') is not False):
            return False
        return permission({**source,'publication':{**policy,'noncommercial_only':False}})
    return allowed


def project(root, code, at):
    root,code=Path(root),Path(code)
    data=root/'site/data';state=root/'collector_state'
    sources=read(code/'sources.json')['sources']
    gate=PublicationGate(sources,current_permission(code),data)
    archive=read(state/'archive.json')['articles']
    stored,news,filings,other=gate.views(archive)
    changed=False
    for name,records in [('news',news),('newsroom',news),('filings',filings),('research',other)]:
        path=data/(name+'.json');old=read(path);articles=[public_record(a) for a in records]
        if old['articles']!=articles:
            write_atomic(path,{**old,'count':len(articles),'articles':articles})
            changed=True
    need=gate.needs_reprojection(archive,state)
    gate.write_manifest(archive,data,at)
    if changed or need:
        gate.write_history(archive,state,at)
        current=read(data/'briefing.json')
        from ..collector import timestamp
        selected,_=select(news,timestamp(current['generated_at']))
        write_atomic(data/'briefing.json',{**current,'items':[public_record(a) for a in selected],
                     'selected_count':len(selected),'status':'candidates_ready' if selected else 'no_eligible_recent_articles'})
        h=read(data/'health.json');h['pipeline_policy']={'checked_at':iso(at),'public_news':len(news),'held_news':sum(a.get('record_type','news')=='news' and not gate.allows(a) for a in archive)}
        if 'discovery' in h:
            s=h['discovery'];q=s.get('quality',{})
            counts={sid:sum(a['source_id']==sid for a in news) for sid in {a['source_id'] for a in news}}
            s.update(newsroom_count=len(news),newsroom_korea_direct_count=sum(a['editorial']['tier']=='korea_direct' for a in news))
            s['newsroom_tier_counts']={k:sum(a['editorial']['tier']==k for a in news) for k in ('korea_direct','global_major','reference')}
            from ..relevance import CATEGORIES
            s['newsroom_category_counts']={k:sum(a['category']==k for a in news) for k in CATEGORIES}
            recent7=lambda a:a.get('date_precision')!='date' and a.get('publication_time_verified_for_news') is not False and at-dt.timedelta(days=7)<=timestamp(a['published_at'])<=at
            s['newsroom_by_source']={sid:{'count':n,'korea_direct':sum(a['source_id']==sid and a['editorial']['tier']=='korea_direct' for a in news),'originally_published_last7d':sum(a['source_id']==sid and recent7(a) for a in news),'new_this_run':0} for sid,n in counts.items()}
            s['newsroom_originally_published_last24h']=len(recent_news(news,at))
            s['newsroom_originally_published_last7d']=sum(recent7(a) for a in news)
            s['newsroom_korea_direct_last7d']=sum(recent7(a) and a['editorial']['tier']=='korea_direct' for a in news)
            s['total_published']=len(news+filings+other)
            q.update(published_news_articles=len(news),publishing_sources=len(counts),news_by_source=counts,
                     rights_held_news_count=h['pipeline_policy']['held_news'],public_metrics_as_of=iso(at),
                     domestic_coverage=coverage(news,sources,at,news),public_record_count=len(news+filings+other))
            q['rights_held_news_by_source']={sid:sum(a.get('record_type','news')=='news' and a.get('source_id')==sid and not gate.allows(a) for a in archive) for sid in {a.get('source_id') for a in archive if a.get('record_type','news')=='news' and not gate.allows(a)}}
            q['public_news_relevance_counts']={k:sum(a.get('relevance_label')==k for a in news) for k in ('Direct','Indirect','Irrelevant')}
            q['public_news_direct_ratio']=q['public_news_relevance_counts']['Direct']/len(news) if news else None
            q['originally_published_last24h']=s['newsroom_originally_published_last24h']
            q['originally_published_last7d']=s['newsroom_originally_published_last7d']
            write_atomic(state/'run_summary.json',s)
        write_atomic(data/'health.json',h)
    model=read(code/'operating_policy.json')
    report_cfg={s['id']:s for s in read(code/'reports_sources.json')['sources']}
    records=sorted(read(state/'reports_archive.json')['reports'],key=lambda r:r['published_at'],reverse=True)
    visible=[public_report(r) for r in records if r.get('publication_status')=='published' and r.get('source_id') in report_cfg and approved(report_cfg[r['source_id']],model)]
    path=data/'reports.json';doc=read(path)
    if doc['reports']!=visible:write_atomic(path,{**doc,'count':len(visible),'reports':visible})
    config=read(code/'macro_sources.json');old=read(data/'macro.json');view=public_view(config,read(state/'macro_archive.json'),at)
    if old['indicators']!=view['indicators']:write_atomic(data/'macro.json',view)
    return news


def verify_public(root,code):
    data=Path(root)/'site/data';state=Path(root)/'collector_state'
    gate=PublicationGate(read(Path(code)/'sources.json')['sources'],current_permission(code),data)
    archive=read(state/'archive.json')['articles']
    _,news,filings,other=gate.views(archive)
    for name,rows in [('news',news),('newsroom',news),('filings',filings),('research',other)]:
        if read(data/(name+'.json'))['articles']!=[public_record(a) for a in rows]:
            raise ValidationError('publication_gate_projection_mismatch')
    blocked={hashlib.sha256(a['url'].encode()).hexdigest() for a in archive if not gate.allows(a)}
    if blocked and not blocked<=set(read(data/'publication_visibility.json')['blocked_url_hashes']):
        raise ValidationError('historical_display_gate_missing')
    if any(a['url'] not in {r['url'] for r in news} for a in read(data/'briefing.json')['items']):
        raise ValidationError('briefing_rights_gate_mismatch')
