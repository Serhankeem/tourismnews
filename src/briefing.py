"""Metadata-only briefing selection after the existing publication gate.

No body processing. Same-event detection is conservative title similarity, not
an assertion that matching keywords establish a shared event.
"""
import datetime as dt
import re
import json
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit
if __package__:
    from . import collector as c
    from .publication import public_record
else:
    import collector as c
    from publication import public_record


def recent_news(newsroom, at):
    """Count verified publication instants independently of editorial tier."""
    rows = []
    for a in newsroom:
        raw = a.get('published_at', '')
        if (a.get('record_type', 'news') != 'news' or a.get('archived_only')
                or a.get('date_precision') == 'date' or a.get('publication_time_verified_for_news') is False
                or not re.search(r'T\d{2}:\d{2}', raw)
                or not re.search(r'(Z|[+-]\d{2}:?\d{2})$', raw)):
            continue
        if at-dt.timedelta(hours=24) <= c.timestamp(raw, dt.datetime.min.replace(tzinfo=c.KST)) <= at:
            rows.append(a)
    return rows


def select(newsroom, at):
    eligible=[]; decisions=[]
    for a in newsroom:
        if (a.get('record_type','news')!='news' or a.get('archived_only')
                or a.get('date_precision')=='date' or a.get('publication_time_verified_for_news') is False
                or a.get('editorial',{}).get('tier') not in ('korea_direct','global_major')):
            continue
        raw=a.get('published_at','')
        # Explicit time and zone required; never invent midnight for date-only.
        if not re.search(r'T\d{2}:\d{2}',raw) or not re.search(r'(Z|[+-]\d{2}:?\d{2})$',raw):continue
        date=c.timestamp(raw,dt.datetime.min.replace(tzinfo=c.KST))
        if not at-dt.timedelta(hours=24)<=date<=at:continue
        if not a.get('title','').strip() or not a.get('source') or urlsplit(a.get('url','')).scheme not in ('http','https'):continue
        eligible.append(a)
    eligible.sort(key=lambda a:(a['editorial']['tier']!='korea_direct',-c.timestamp(a['published_at']).timestamp(),a.get('id','')))
    chosen=[];seen=set();categories=set()
    while eligible and len(chosen)<5:
        # Korea priority remains stronger than diversity; within a tier diversify.
        eligible.sort(key=lambda a:(a['editorial']['tier']!='korea_direct',a['category'] in categories,-c.timestamp(a['published_at']).timestamp()))
        a=eligible.pop(0);p=urlsplit(a['url']);url=urlunsplit((p.scheme,p.netloc.lower(),p.path,p.query,''))
        title=re.sub(r'\W+','',a['title']).casefold()
        duplicate=url in seen or any(SequenceMatcher(None,title,re.sub(r'\W+','',b['title']).casefold()).ratio()>=.90 for b in chosen)
        decisions.append(dict(article_id=a.get('id'),decision='duplicate' if duplicate else 'selected',tier=a['editorial']['tier'],category=a['category'],new_category=a['category'] not in categories,age_hours=round((at-c.timestamp(a['published_at'])).total_seconds()/3600,2),published_at=a['published_at'],basis=['authorized_newsroom','verified_timestamp_last24h','korea_priority_then_category_diversity','conservative_title_similarity']))
        if duplicate:continue
        chosen.append(a);seen.add(url);categories.add(a['category'])
    return chosen,decisions


def save(newsroom, data_dir, state_dir, at, last_success, mode='live_rss', collection=None):
    selected,decisions=select(newsroom,at)
    recent=recent_news(newsroom,at)
    selection_status='candidates_ready' if selected else 'no_eligible_recent_articles' if recent else 'no_recent_articles'
    sources=(collection or {}).get('sources', [])
    failed=sum(row.get('status') != 'ok' for row in sources)
    coverage={'status': 'partial' if failed and failed < len(sources) else 'failed' if failed else 'complete' if sources else 'unknown',
              'successful_sources': len(sources)-failed, 'source_count': len(sources), 'failed_sources': failed}
    # Rejection evidence stays internal; public article records retain six fields.
    selected_ids={a.get('id') for a in selected}
    for a in recent:
        if a.get('id') not in selected_ids and a.get('editorial',{}).get('tier') not in ('korea_direct','global_major'):
            decisions.append({'article_id': a.get('id'), 'decision': 'editorial_ineligible',
                              'tier': a.get('editorial',{}).get('tier'), 'published_at': a['published_at']})
    current=dict(schema_version=5,generated_at=c.iso(at),briefing_date=at.astimezone(c.KST).date().isoformat(),
                 last_successful_fetch=last_success,status=selection_status,
                 recent_news_count=len(recent), selected_count=len(selected), collection=coverage,
                 mode=mode,title='관광산업 주요 뉴스 브리핑 후보',items=[public_record(a) for a in selected],
                 notice='메타데이터 기반 후보 선별 · 본문 요약·실제 발송·구독은 제공하지 않습니다.')
    path=data_dir/'briefing_archive.json'
    # Corrupt existing history must fail closed, never silently reset to empty.
    history=json.loads(path.read_text()) if path.exists() else {'schema_version':1,'mode':mode,'briefings':[]}
    if history.get('mode')!=mode:raise ValueError('briefing_fixture_live_mix_forbidden')
    if not isinstance(history.get('briefings'),list):raise ValueError('invalid_briefing_archive')
    # First successful run at/after 10:30 KST creates an immutable daily record.
    # Earlier runs update live candidates only; no invented previous days.
    local=at.astimezone(c.KST)
    due=(local.hour,local.minute)>=(10,30)
    if due and not any(b['briefing_date']==current['briefing_date'] for b in history['briefings']):
        internal_path=state_dir/'briefing_selection.json'
        internal=json.loads(internal_path.read_text()) if internal_path.exists() else {'schema_version':1,'runs':[]}
        if not isinstance(internal.get('runs'),list):raise ValueError('invalid_briefing_selection_history')
        if not any(r['briefing_date']==current['briefing_date'] for r in internal['runs']):
            internal['runs'].append(dict(briefing_date=current['briefing_date'],generated_at=current['generated_at'],mode=mode,decisions=decisions))
        # Evidence first; interrupted archive write can safely retry by date.
        c.write_atomic(internal_path,internal)
        history['briefings'].append(current)
        c.write_atomic(path,history)
    c.write_atomic(state_dir/'briefing_latest_selection.json',dict(generated_at=current['generated_at'],mode=mode,decisions=decisions))
    c.write_atomic(data_dir/'briefing.json',current)
    return current
