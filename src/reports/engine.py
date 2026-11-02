"""Independent weekly report metadata collection and publication.

Only reports*.json state/public files are written. Existing Newsroom, KOSIS and
filing databases are never collection inputs or mutation targets.
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
import urllib.parse
from pathlib import Path
from .. import collector as c
from .adapters import discover, verify
from .model import FIELDS, ACCESS, CATEGORIES, TYPES, classify, cutoff_months, normalize, parse_date, public
from .transport import CatalogLoader

ROOT=c.ROOT

def approved(source, model):
    policy=source.get('publication',{})
    return (policy.get('status')=='approved' and policy.get('scope')=='bibliographic_metadata_only'
            and bool(policy.get('basis')) and bool(policy.get('terms_url'))
            and (not policy.get('noncommercial_only') or
                 isinstance(model,dict) and model.get('mode')=='noncommercial' and model.get('ads_enabled') is False and model.get('paid_access') is False))

def identity(source,candidate):
    return hashlib.sha256((source['id']+'|'+str(candidate.get('provider_id') or candidate['url'])).encode()).hexdigest()[:24]

def valid_url(source,url):
    value=c.canonical_url(url);parts=urllib.parse.urlsplit(value)
    if parts.scheme!='https' or parts.hostname not in source['allowed_hosts'] or parts.username or parts.password:raise ValueError('unapproved_original_report_url')
    if any(word in parts.path.casefold() for word in ('download','pdfviewer','/upload/')) or parts.path.casefold().endswith(('.pdf','.jpg','.png','.xlsx','.zip')):raise ValueError('report_binary_link_not_landing_page')
    return value

def source_runtime(source,at):
    result=json.loads(json.dumps(source))
    for request in result.get('catalog_requests',[]):
        request['form']={k:v.format(current_year=at.year,previous_year=at.year-1,two_years_ago=at.year-2) if isinstance(v,str) else v for k,v in request['form'].items()}
    return result

def collect(sources,data_dir,state_dir,at=None,force=False,loader_factory=None,progress=None,manual=None,only_sources=None):
    if only_sources and set(only_sources)-{s['id'] for s in sources}:raise ValueError('unknown_report_source_selection')
    at=at or c.now_kst();today=at.date();data_dir=Path(data_dir);state_dir=Path(state_dir)
    archive_path=state_dir/'reports_archive.json';public_path=data_dir/'reports.json'
    original=c.read_json(archive_path,None) if archive_path.exists() else {'reports':[]}
    if not isinstance(original,dict) or not isinstance(original.get('reports'),list):raise ValueError('invalid_reports_archive_stop_without_data_replacement')
    if not archive_path.exists() and c.read_json(public_path,{}).get('count',0):raise ValueError('missing_reports_archive_public_view_is_not_backup')
    records={r['id']:r for r in original['reports']};original_ids=set(records);starting_ids=set(records)
    ledger=c.read_json(state_dir/'reports_candidates.json',{}).get('candidates',{})
    old_ledger_ids=set(ledger);seen=set()
    stats=c.read_json(state_dir/'reports_source_metrics.json',{}).get('sources',{})
    model=c.read_json(ROOT/'operating_policy.json',{})
    rows=[];errors=[];verified_now=0;excluded_now=0;duplicate_now=0;merged_now=0;successful=False
    by_id={s['id']:s for s in sources}
    manual=manual or []
    for configured in sources:
        source=source_runtime(configured,at);sid=source['id'];metric=stats.setdefault(sid,{'attempts':0,'successes':0,'errors':0})
        row={'id':sid,'publisher':source['name'],'status':'not_attempted','candidate_reports':0,'access_verified_candidates':0,'rights_reviewed_candidates':0,'verified_reports':0,'verified_candidates':0,'catalog_entries':0,'excluded_reports':0,'duplicate_observations':0,'duplicate_editions_merged':0,'new_reports':0,'detail_errors':0,'date_holds':0,'rights_holds':0}
        rows.append(row)
        if not source.get('enabled') or not source.get('adapter') or not approved(source,model):
            row.update(status='blocked',reason=source.get('blocking_reason','metadata_publication_not_approved_for_current_operating_model'));continue
        if only_sources and sid not in only_sources:
            row.update(status='not_due',reason='not_selected_for_this_run');continue
        last=metric.get('last_attempt_at')
        interval=source.get('interval_days',7)
        not_due=bool(last and (c.timestamp(last).isocalendar()[:2]==at.isocalendar()[:2] if interval==7 else c.timestamp(last)>at-dt.timedelta(days=interval)+dt.timedelta(hours=1)))
        if not force and not_due:
            row.update(status='not_due',last_attempt_at=last);continue
        metric['attempts']+=1;metric['last_attempt_at']=c.iso(at)
        loader=(loader_factory(source) if loader_factory else CatalogLoader(source['allowed_hosts'],[r['url'] for r in source.get('catalog_requests',[])]))
        if progress:progress({'source':sid,'phase':'catalog'})
        try:
            candidates=list(discover(source,loader))
            row['catalog_entries']=len(candidates)
            if len(candidates)>source.get('max_details',100):
                row['deferred_candidates']=len(candidates)-source['max_details'];candidates=candidates[:source['max_details']]
            for index,candidate in enumerate(candidates):
                candidate['url']=valid_url(source,candidate['url']);aid=identity(source,candidate)
                if aid in seen:row['duplicate_observations']+=1;duplicate_now+=1;continue
                seen.add(aid);row['candidate_reports']+=1
                if aid in old_ledger_ids:row['duplicate_observations']+=1;duplicate_now+=1
                entry={'id':aid,'source_id':sid,'url':candidate['url'],'provider_id':candidate['provider_id'],
                       'first_discovered_at':ledger.get(aid,{}).get('first_discovered_at',c.iso(at)),
                       'last_seen_at':c.iso(at),'catalog_url':candidate['catalog_url'],'discovery_method':'automatic'}
                try:
                    payload=loader(candidate['url']);row['access_verified_candidates']+=1;entry['access_status']='verified';metadata=verify(source,candidate,payload)
                    entry['metadata_response_sha256']=hashlib.sha256(payload).hexdigest()
                    if not metadata.get('title') or len(metadata['title'])>1000:raise ValueError('missing_or_invalid_original_title')
                    if metadata['title'].strip().casefold() in ('not found','access denied','login','sign in','page not found'):raise ValueError('not_a_report_landing')
                    date,precision,start,end=parse_date(metadata.get('published_at'),today)
                    taxonomy=classify(metadata['title'],source,candidate)
                    if not taxonomy:raise ValueError('not_a_research_publication')
                    if metadata.get('date_kind')=='registered' and not source.get('allow_registered_date'):
                        row['date_holds']+=1;raise ValueError('registration_date_not_verified_as_publication_date')
                    entry.update(verification_status='verified',last_verified_at=c.iso(at),date_kind=metadata['date_kind'],date_precision=precision)
                    verified_now+=1;row['verified_candidates']+=1
                    if (sid=='kcti' or source.get('requires_kogl')) and metadata.get('kogl_type') not in (1,2,3,4):
                        raise ValueError('missing_per_record_KOGL_scope')
                    row['rights_reviewed_candidates']+=1;entry['rights_status']='reviewed'
                    if start<cutoff_months(today,source.get('lookback_months',12)):raise ValueError('outside_or_uncertain_initial_date_window')
                    record={'id':aid,'source_id':sid,'provider_id':candidate['provider_id'],'publisher':source['name'],
                            'title':metadata['title'],'published_at':date,'url':candidate['url'],**taxonomy,
                            'access_type':metadata.get('access_type','미확인'),'region':source['region'],
                            'date_kind':metadata['date_kind'],'date_precision':precision,
                            'metadata_evidence':{'url':candidate['url'],'catalog_url':candidate['catalog_url'],'sha256':entry['metadata_response_sha256'],
                                                 'kogl_type':metadata.get('kogl_type'),'authors':metadata.get('authors',''),**({'doi':metadata['doi']} if metadata.get('doi') else {})},
                            'first_discovered_at':entry['first_discovered_at'],'last_verified_at':c.iso(at),
                            'discovery_method':'automatic','access_method':'official_catalog_post_then_landing_get' if sid=='kcti' else 'official_catalog_get_then_landing_get','verification_status':'verified','publication_status':'published',
                            'publication_policy':source['publication']}
                    if record['access_type'] not in ACCESS:raise ValueError('invalid_access_type')
                    # Distinct language/repost URLs with the same institution,
                    # title and edition date merge without merging new editions.
                    duplicate=next((r for r in records.values() if r['source_id']==sid and
                                    (r['url']==record['url'] or r['provider_id']==record['provider_id'] or
                                     normalize(r['title'])==normalize(record['title']) and r['published_at']==date)),None)
                    if duplicate:
                        record['id']=duplicate['id'];record['first_discovered_at']=duplicate['first_discovered_at'];record['discovery_method']=duplicate['discovery_method']
                        record['aliases']=sorted(set(duplicate.get('aliases',[])+[duplicate['url'],candidate['url']]))
                        if duplicate['id']!=aid:
                            merged_now+=1;row['duplicate_editions_merged']+=1
                            # Keep a stable primary original link for the same edition.
                            record.update(public(duplicate));record.update({k:duplicate[k] for k in ('provider_id','metadata_evidence')})
                        record['versions']=duplicate.get('versions',[])
                        if any(duplicate[k]!=record[k] for k in FIELDS):
                            record['versions']=record['versions']+[{'metadata':public(duplicate),'last_verified_at':duplicate['last_verified_at']}]
                    records[record['id']]=record;entry['publication_status']='published';entry['canonical_report_id']=record['id']
                    if record['id'] not in original_ids:row['new_reports']+=1;original_ids.add(record['id'])
                except (OSError,ValueError,KeyError,TypeError) as exc:
                    entry['publication_status']='hold';entry['reason']=str(exc)[:200]
                    if entry.get('verification_status')!='verified':entry['verification_status']='not_verified'
                    excluded_now+=1;row['excluded_reports']+=1
                    if isinstance(exc,OSError) or str(exc) in ('report_title_mismatch','koti_bibliographic_panel_missing','koti_publication_date_or_authors_missing','oecd_bibliographic_metadata_missing','oecd_publication_date_mismatch','oecd_publisher_unverified'):row['detail_errors']+=1
                    if str(exc)=='missing_per_record_KOGL_scope':
                        row['rights_holds']+=1
                        for existing in records.values():
                            if existing['source_id']==sid and (existing['provider_id']==candidate['provider_id'] or existing['url']==candidate['url']):
                                existing['publication_status']='rights_review_required'
                    errors.append({'source_id':sid,'url':candidate['url'],'error':str(exc)[:200]})
                ledger[aid]=entry
                if progress and (index+1)%20==0:progress({'source':sid,'phase':'verified_metadata','checked':index+1,'total':len(candidates)})
            row['verified_reports']=len({e.get('canonical_report_id',e['id']) for e in ledger.values() if e['source_id']==sid and e.get('last_seen_at')==c.iso(at) and e.get('verification_status')=='verified'})
            row['status']='partial' if row['detail_errors'] else 'ok';successful=True
            metric['last_catalog_success_at']=c.iso(at)
            if row['status']=='ok':metric['last_successful_at']=c.iso(at)
            metric['successes']+=row['status']=='ok';metric['errors']+=row['status']=='partial'
        except (OSError,ValueError,KeyError,TypeError) as exc:
            row.update(status='error',error=str(exc)[:220]);metric['errors']+=1
            errors.append({'source_id':sid,'error':str(exc)[:220]})
        row['last_successful_at']=metric.get('last_successful_at')
        row['success_rate']=metric['successes']/metric['attempts']
        if progress:progress(row)
    # Manual imports are explicit operator attestations, never automatic results.
    for item in manual:
        source=by_id.get(item.get('source_id'))
        if not source or not approved(source,model):raise ValueError('manual_source_metadata_scope_not_approved')
        if not item.get('verified_by') or not item.get('verification_note') or not item.get('evidence_url'):raise ValueError('manual_verification_evidence_required')
        record={k:item[k] for k in FIELDS}
        if not all(isinstance(record[k],str) and record[k].strip() for k in FIELDS if k!='keywords') or not isinstance(record['keywords'],list) or len(record['keywords'])>10 or not all(isinstance(k,str) and k.strip() for k in record['keywords']):raise ValueError('invalid_manual_metadata_fields')
        if (source['id']=='kcti' or source.get('requires_kogl')) and (item.get('kogl_type') not in (1,2,3,4) or not item.get('authors')):raise ValueError('manual_KOGL_scope_required')
        record['url']=valid_url(source,record['url'])
        if valid_url(source,item['evidence_url'])!=record['url']:raise ValueError('manual_evidence_must_be_original_landing')
        date,precision,start,end=parse_date(record['published_at'],today);record['published_at']=date
        if record['publisher']!=source['name'] or record['access_type'] not in ACCESS:raise ValueError('manual_source_metadata_mismatch')
        if record['report_type'] not in TYPES or record['category'] not in CATEGORIES:raise ValueError('invalid_manual_taxonomy')
        aid=identity(source,{'url':record['url']});existing=next((r for r in records.values() if r['url']==record['url']),None)
        if existing:aid=existing['id']
        records[aid]={**record,'id':aid,'source_id':source['id'],'provider_id':item.get('provider_id',existing['provider_id'] if existing else record['url']),
                      'region':source['region'],'date_kind':'operator_verified_publication','date_precision':precision,
                      'discovery_method':existing['discovery_method'] if existing else 'manual','verification_status':'operator_attested',
                      'publication_status':'published','first_discovered_at':existing['first_discovered_at'] if existing else c.iso(at),
                      'last_verified_at':c.iso(at),'publication_policy':source['publication'],
                      'access_method':'operator_manual_verification','metadata_evidence':{**{k:item[k] for k in ('verified_by','verification_note','evidence_url')},'kogl_type':item.get('kogl_type'),'authors':item.get('authors','')}}
        if existing:
            records[aid]['versions']=existing.get('versions',[])
            if any(existing[k]!=record[k] for k in FIELDS):
                records[aid]['versions']=records[aid]['versions']+[{'metadata':public(existing),'last_verified_at':existing['last_verified_at'],'reason':'operator_metadata_update'}]
        successful=True
    reports=sorted(records.values(),key=lambda r:r['published_at'],reverse=True)
    visible=[r for r in reports if r.get('publication_status')=='published' and r['source_id'] in by_id and approved(by_id[r['source_id']],model)]
    recent30=lambda r: parse_date(r['published_at'],today)[2]>=today-dt.timedelta(days=30) and r.get('date_kind')!='registered'
    manual_verified_ids={r['id'] for r in reports if r.get('verification_status')=='operator_attested'}
    automatic_verified_ids={e.get('canonical_report_id',e['id']) for e in ledger.values() if e.get('verification_status')=='verified'}-manual_verified_ids
    summary={'version':'0.5','checked_at':c.iso(at),'status':'ok' if all(r['status'] in ('ok','not_due','blocked') for r in rows) and successful else 'partial' if successful else 'no_due_sources' if all(r['status'] in ('blocked','not_due') for r in rows) else 'failed',
             'target_sources':len(sources),'source_coverage':sum(bool(s.get('investigation')) for s in sources),
             'connected_sources':sum(bool(s.get('enabled') and s.get('adapter') and approved(s,model)) for s in sources),
             'publishing_sources':len({r['source_id'] for r in visible}),'candidate_reports':len(ledger)+sum(r['discovery_method']=='manual' for r in reports),
             'candidates_this_run':sum(r['candidate_reports'] for r in rows),'verified_candidates_this_run':verified_now,'verified_this_run':sum(r['verified_reports'] for r in rows),
             'verified_reports':len(automatic_verified_ids|manual_verified_ids),
             'verified_automatic_reports':len(automatic_verified_ids),'verified_manual_reports':len(manual_verified_ids),
             'excluded_this_run':excluded_now,'duplicate_reports':merged_now,'duplicate_observations':duplicate_now,'published_reports':len(visible),
             'archived_reports':len(reports),'new_reports_this_run':sum(r['id'] not in starting_ids for r in reports),
             'new_automatic_reports_this_run':sum(r['id'] not in starting_ids and r['discovery_method']=='automatic' for r in reports),'new_manual_reports_this_run':sum(r['id'] not in starting_ids and r['discovery_method']=='manual' for r in reports),
             'new_reports_last30d':sum(recent30(r) for r in visible),
             'automatic_reports':sum(r['discovery_method']=='automatic' for r in visible),'manual_reports':sum(r['discovery_method']=='manual' for r in visible),
             'by_publisher':{s['name']:{'published':sum(r['source_id']==s['id'] for r in visible),
                                'new_last30d':sum(r['source_id']==s['id'] and recent30(r) for r in visible),
                                'latest_publication':max((r['published_at'] for r in visible if r['source_id']==s['id'] and r.get('date_kind')!='registered'),default=None),
                                'latest_registration':max((r['published_at'] for r in visible if r['source_id']==s['id'] and r.get('date_kind')=='registered'),default=None),
                                'last_collection':stats.get(s['id'],{}).get('last_attempt_at'),'last_successful_collection':stats.get(s['id'],{}).get('last_successful_at'),
                                'success_rate':stats[s['id']]['successes']/stats[s['id']]['attempts'] if stats.get(s['id'],{}).get('attempts') else None} for s in sources},
             'category_counts':{cat:sum(r['category']==cat for r in visible) for cat in CATEGORIES},
               'sources':rows,'errors':errors,'stage_counts_this_run':{'candidate':sum(r['candidate_reports'] for r in rows),'access_verified':sum(r['access_verified_candidates'] for r in rows),'metadata_verified':verified_now,'rights_reviewed':sum(r['rights_reviewed_candidates'] for r in rows),'newly_published':sum(r['id'] not in starting_ids for r in visible)}}
    rights_changed=any(r.get('publication_status')=='published' and (r['source_id'] not in by_id or not approved(by_id[r['source_id']],model)) for r in reports)
    if successful or rights_changed:
        c.write_atomic(archive_path,{'version':'0.5','updated_at':c.iso(at),'count':len(reports),'reports':reports})
        c.write_atomic(public_path,{'schema_version':1,'mode':'verified_official_metadata','generated_at':c.iso(at),'count':len(visible),
                                   'reports':[public(r) for r in visible],
                                   'publishers':{s['name']:{'region':s['region'],'homepage':s['homepage']} for s in sources},
                                   'date_basis':{r['url']:{'kind':r['date_kind'],'precision':r['date_precision']} for r in visible},
                                   'attributions':{r['url']:{'authors':r.get('metadata_evidence',{}).get('authors',''),'kogl_type':r.get('metadata_evidence',{}).get('kogl_type')} for r in visible if r.get('metadata_evidence',{}).get('kogl_type')}})
    c.write_atomic(state_dir/'reports_candidates.json',{'version':'0.5','candidates':ledger})
    c.write_atomic(state_dir/'reports_source_metrics.json',{'version':'0.5','sources':stats})
    c.write_atomic(state_dir/'reports_run_summary.json',summary)
    c.write_atomic(data_dir/'reports_health.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description='Research metadata only; never downloads PDFs or report bodies')
    parser.add_argument('--data-dir',default=str(ROOT/'site/data'))
    parser.add_argument('--state-dir',default=str(ROOT/'collector_state'))
    parser.add_argument('--sources',default=str(ROOT/'reports_sources.json'))
    parser.add_argument('--only-source',action='append',help='Limit actual requests; preserve all configured sources and records')
    parser.add_argument('--force',action='store_true',help='Ignore weekly due dates, not permissions/robots')
    parser.add_argument('--import-manual',type=Path)
    parser.add_argument('--progress',action='store_true')
    args=parser.parse_args()
    sources=c.read_json(Path(args.sources),{})['sources']
    manual=c.read_json(args.import_manual,{})['reports'] if args.import_manual else None
    progress=(lambda row:print(json.dumps(row,ensure_ascii=False),file=sys.stderr,flush=True)) if args.progress else None
    summary=collect(sources,args.data_dir,args.state_dir,force=args.force,progress=progress,manual=manual,only_sources=args.only_source)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('sources','errors')},ensure_ascii=False))
    return 1 if summary['status']=='failed' else 0

if __name__=='__main__':raise SystemExit(main())
