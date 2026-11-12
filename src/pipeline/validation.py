"""Fail closed on corruption/loss; allow documented revisions, never reset state."""
import hashlib
import json
import math
from pathlib import Path
from .layout import read, files, hashes, DataError
from ..publication import PUBLIC_FIELDS
from ..editorial import publication_order
from ..collector import canonical_url


class ValidationError(DataError):
    pass


def rows_by_id(rows):
    result = {a['id']:a for a in rows}
    if len(result) != len(rows):
        raise ValidationError('duplicate_record_id')
    return result


def validate(root, cfg, before=None):
    root = Path(root)
    inventory={str(p.relative_to(root)) for folder in ('site/data','collector_state') for p in (root/folder).rglob('*') if p.is_file()}
    if inventory!=set(files(cfg)):
        raise ValidationError('unexpected_or_missing_data_inventory')
    hashes(root, files(cfg))
    docs = {name:read(root/name) for name in files(cfg)}
    if any(not isinstance(d, dict) for d in docs.values()):
        raise ValidationError('invalid_json_root')
    if any('fixture' in str(d.get('mode','')).lower() or 'demo' in str(d.get('mode','')).lower() for name,d in docs.items() if name.startswith('site/data/')):
        raise ValidationError('fixture_or_demo_public_snapshot_forbidden')
    archive = rows_by_id(docs['collector_state/archive.json']['articles'])
    if len({canonical_url(a['url']) for a in archive.values()}) != len(archive):
        raise ValidationError('duplicate_archive_url')
    public = docs['site/data/newsroom.json']['articles']
    for name in ('news', 'newsroom', 'filings', 'research'):
        doc = docs['site/data/'+name+'.json']
        if doc['count'] != len(doc['articles']):
            raise ValidationError('public_count_mismatch')
        if any(set(a) != set(PUBLIC_FIELDS) for a in doc['articles']):
            raise ValidationError('public_metadata_allowlist')
        if len({canonical_url(a['url']) for a in doc['articles']}) != len(doc['articles']):
            raise ValidationError('duplicate_public_url')
        if any(not a['title'] or not a['published_at'] or not a['url'].startswith(('https://','http://')) for a in doc['articles']):
            raise ValidationError('invalid_public_metadata')
    if public != sorted(public,key=publication_order):
        raise ValidationError('public_chronology_invalid')
    if any(not math.isfinite(publication_order(a)[0]) for a in public):
        raise ValidationError('unverified_public_publication_date')
    if docs['site/data/news.json']['articles'] != public:
        raise ValidationError('inconsistent_news_views')
    for a in public:
        record = next((r for r in archive.values() if r['url']==a['url']), None)
        if not record or record.get('record_type','news')!='news' or record.get('archived_only'):
            raise ValidationError('public_news_not_in_canonical_archive')
    reports = docs['collector_state/reports_archive.json']['reports']
    from ..reports.model import FIELDS
    if any(set(r)!=set(FIELDS) for r in docs['site/data/reports.json']['reports']):
        raise ValidationError('public_report_metadata_allowlist')
    rows_by_id(reports)
    if docs['site/data/reports.json']['count'] != len(docs['site/data/reports.json']['reports']):
        raise ValidationError('report_count_mismatch')
    from ..macro.decimal_series import validate_archive
    try:
        validate_archive(docs['collector_state/macro_archive.json'],
                         read(Path(before)/'collector_state/macro_archive.json') if before is not None else None)
    except (ValueError, TypeError, KeyError):
        raise ValidationError('decimal_macro_ledger_invalid') from None
    macro = docs['collector_state/macro_archive.json']['indicators']
    for item in macro.values():
        if not isinstance(item['observations'],dict) or not isinstance(item['revisions'],list):
            raise ValidationError('macro_ledger_invalid')
    if before is not None:
        old = Path(before)
        prior = rows_by_id(read(old/'collector_state/archive.json')['articles'])
        if not prior.keys() <= archive.keys():
            raise ValidationError('lost_news_record')
        for aid, a in prior.items():
            if any(a.get(k)!=archive[aid].get(k) for k in ('id','url','published_at','first_discovered_at','first_published_by_engine_at')):
                raise ValidationError('news_identity_or_original_date_changed')
        old_discovery = read(old/'collector_state/discovery.json')['candidates']
        new_discovery = docs['collector_state/discovery.json']['candidates']
        if not old_discovery.keys() <= new_discovery.keys():
            raise ValidationError('lost_discovery_record')
        for aid,a in old_discovery.items():
            if a.get('first_discovered_at') != new_discovery[aid].get('first_discovered_at'):
                raise ValidationError('discovery_first_seen_changed')
        prior_reports = rows_by_id(read(old/'collector_state/reports_archive.json')['reports'])
        current_reports = rows_by_id(reports)
        if not prior_reports.keys() <= current_reports.keys():
            raise ValidationError('lost_report')
        for aid,a in prior_reports.items():
            if a['url']!=current_reports[aid]['url']:
                raise ValidationError('report_identity_changed')
            if not all(v in current_reports[aid].get('versions',[]) for v in a.get('versions',[])):
                raise ValidationError('lost_report_revision')
        for key in ('briefings',):
            old_editions = read(old/'site/data/briefing_archive.json')[key]
            new_editions = docs['site/data/briefing_archive.json'][key]
            if not all(e in new_editions for e in old_editions):
                raise ValidationError('confirmed_briefing_changed')
        for file,key in [('briefing_selection.json','runs')]:
            if not all(e in docs['collector_state/'+file][key] for e in read(old/('collector_state/'+file))[key]):
                raise ValidationError('confirmed_selection_changed')
        old_vis=read(old/'collector_state/publication_visibility.json')['records']
        vis=docs['collector_state/publication_visibility.json']['records']
        for aid,r in old_vis.items():
            if aid not in vis or not all(e in vis[aid]['transitions'] for e in r['transitions']):
                raise ValidationError('lost_rights_transition')
        old_macro=read(old/'collector_state/macro_archive.json')['indicators']
        for iid,item in old_macro.items():
            new=macro.get(iid,{})
            if not item['observations'].keys() <= new.get('observations',{}).keys():
                raise ValidationError('lost_macro_period')
            if not all(r in new.get('revisions',[]) for r in item['revisions']):
                raise ValidationError('lost_macro_revision')
            for period,value in item['observations'].items():
                updated=new['observations'][period]
                if value['first_collected_at']!=updated['first_collected_at']:
                    raise ValidationError('macro_first_collection_changed')
                if value['value']!=updated['value'] and len(new['revisions'])<=len(item['revisions']):
                    raise ValidationError('macro_correction_without_history')
    from ..collector import timestamp
    report_dates=[s.get('last_successful_at') for s in docs['collector_state/reports_source_metrics.json']['sources'].values() if s.get('last_successful_at')]
    macro_dates=[s.get('last_successful_check') for s in docs['collector_state/macro_archive.json']['sources'].values() if s.get('last_successful_check')]
    return {'news':len(public),'archive':len(archive),'discovery':len(docs['collector_state/discovery.json']['candidates']),
            'reports':len(docs['site/data/reports.json']['reports']),
            'macro_observations':sum(len(i['observations']) for i in macro.values()),
            'private_decimal_observations':sum(len(i['observations']) for i in docs['collector_state/macro_archive.json'].get('decimal_indicators',{}).values()),
            'last_news_success':docs['site/data/health.json'].get('last_successful_fetch'),
            'last_reports_success':max(report_dates,key=timestamp) if report_dates else None,
            'last_macro_success':max(macro_dates,key=timestamp) if macro_dates else None}
