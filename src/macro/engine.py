"""Independent validated statistics, persistent correction history, safe public view."""
import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
from . import kto, ecos, tourgo, ecos_decimal, decimal_series
from .balance import permitted
from .model import comparisons, months, month_before, valid_period
from .transport import Loader
from ..collector import write_atomic

ROOT=Path(__file__).resolve().parents[2]
KST=dt.timezone(dt.timedelta(hours=9))

def read(path,default=None):
    if not path.exists():return default
    return json.loads(path.read_text())

def public_view(config,archive,now,operating_policy=None):
    series=[]
    tourgo_source=next((s for s in config['sources'] if s['id']==tourgo.SOURCE),{})
    policy=read(ROOT/'operating_policy.json',{}) if operating_policy is None else operating_policy
    tourgo_pair=tourgo.public_pair(tourgo_source,archive,now.date()) if tourgo.terms_confirmed(tourgo_source,policy,now.date()) else {}
    for item in config['indicators']:
        # Private decimal series have no public projection, even if flags change.
        if item.get('value_kind') in decimal_series.KINDS:continue
        source=next((s for s in config['sources'] if s['id']==item['source_id']), {})
        if (not item.get('enabled') or not source.get('enabled')
                or (source.get('requires_approval') and not permitted(source, 'publication', now.date()))
                or (source.get('id') == tourgo.SOURCE and not tourgo.permitted(source,'publication',now.date()))
                or (source.get('method') == 'official_ecos_api' and not ecos.publishable(source))):
            saved={}
        else:
            saved=archive['indicators'].get(item['id'],{})
            if source.get('method')=='official_ecos_api':saved=ecos.public_records(source,item,saved)
            if source.get('id')==tourgo.SOURCE:
                saved=tourgo_pair.get(item['id'],{})
                if (saved.get('unit')!=item.get('unit') or saved.get('definition')!=item.get('definition')
                        or item.get('value_kind')!='money_nonnegative' or item.get('frequency')!='M'):saved={}
        obs=saved.get('observations',{})
        ordered=[dict(period=p,**({k:v for k,v in o.items() if k in tourgo.PUBLIC_RECORD_FIELDS} if source.get('id')==tourgo.SOURCE else o)) for p,o in sorted(obs.items())]
        row={k:v for k,v in item.items() if k not in ('sheet','row_label') and (source.get('id')!=tourgo.SOURCE or k in tourgo.PUBLIC_INDICATOR_FIELDS)}
        if item.get('value_kind')=='money_nonnegative' and item.get('unit')=='US$':row.update(display_unit='백만 US$',display_divisor=1000000)
        row.update(observations=ordered,connected=bool(ordered),latest=None,missing_periods=[],retained_missing_periods=saved.get('latest_snapshot_missing_periods',[]),correction_count=len(saved.get('revisions',[])))
        if ordered:
            latest=ordered[-1];row['latest']=dict(latest,comparisons=comparisons(obs,latest['period'],exact=item.get('value_kind')=='money_nonnegative'))
            row['source_url']=latest['source_url']
            if source.get('method')=='official_ecos_api' or source.get('id')==tourgo.SOURCE:row['publisher']=latest['publisher']
            row['missing_periods']=[p for p in months(ordered[0]['period'],ordered[-1]['period']) if p not in obs]
            row['first_period']=ordered[0]['period'];row['latest_period']=latest['period'];row['months']=len(ordered)
        series.append(row)
    result=dict(schema_version=1,mode='verified_official_statistics',generated_at=now.isoformat(),indicators=series)
    if all(any(i['id']==key and i['source_id']==tourgo.SOURCE and i['connected'] for i in series) for key in tourgo.IDS):
        result['tourism_balance']=tourgo.balance_view(tourgo_pair)
    return result

def collect(config,data_dir,state_dir,loader=None,now=None,force=False,ecos_client=None,tourgo_ledger=None,only_sources=None,operating_policy=None):
    now=(now or dt.datetime.now(KST)).astimezone(KST);loader=loader or Loader()
    data_dir,state_dir=Path(data_dir),Path(state_dir);data_dir.mkdir(parents=True,exist_ok=True);state_dir.mkdir(parents=True,exist_ok=True)
    archive_path=state_dir/'macro_archive.json';public_path=data_dir/'macro.json'
    health=dict(schema_version=1,checked_at=now.isoformat(),status='failed',sources=[],new_observations=0,unchanged_observations=0,value_corrections=0,status_changes=0)
    try:
        if not archive_path.exists() and public_path.exists() and any(i.get('observations') for i in read(public_path,{}).get('indicators',[])):raise ValueError('archive_missing_with_existing_public_data')
        archive=read(archive_path,dict(schema_version=1,indicators={},sources={}))
        if not isinstance(archive,dict):raise ValueError('archive_schema_invalid')
        if archive.get('schema_version')!=1 or not isinstance(archive.get('indicators'),dict) or not isinstance(archive.get('sources'),dict):raise ValueError('archive_schema_invalid')
        if any(not isinstance(v,dict) for v in archive['sources'].values()):raise ValueError('archive_sources_invalid')
        decimal_series.validate_archive(archive)
        for saved in archive['indicators'].values():
            if not isinstance(saved,dict) or not isinstance(saved.get('observations'),dict) or not isinstance(saved.get('revisions'),list):raise ValueError('archive_records_invalid')
            for period,record in saved['observations'].items():
                valid_period(period)
                if not isinstance(record,dict) or not isinstance(record.get('value'),int) or isinstance(record.get('value'),bool) or record['value']<0 or record['value']>ecos.MAX_INTEGER or not record.get('first_collected_at') or record.get('unit')!=saved.get('unit'):raise ValueError('archive_observation_invalid')
    except (ValueError,TypeError,KeyError,OSError):
        health['error']='archive_invalid_or_missing_existing_data_preserved';write_atomic(data_dir/'macro_health.json',health);return health
    success=0;attempts=0;skipped=0
    for source in config['sources']:
        if only_sources is not None and source['id'] not in only_sources:continue
        sid=source['id'];previous=archive['sources'].get(sid,{})
        result=dict(id=sid,name=source['name'],status='not_connected',reason=source.get('reason'),last_successful_check=previous.get('last_successful_check'))
        if source.get('method') == ecos_decimal.METHOD:
            previous=archive.get('decimal_sources',{}).get(sid,{})
            result.update(last_successful_check=previous.get('last_successful_check'),publication_status='blocked')
            active=[i for i in config['indicators'] if i.get('enabled') and i['source_id']==sid]
            if not source.get('enabled') or not ecos_decimal.reviewed(source):
                result.update(collection_state='disabled' if not source.get('enabled') else 'collection_review_required')
            elif not active:
                result.update(collection_state='indicators_disabled')
            elif not force and previous.get('last_successful_check','')[:10]==now.date().isoformat():
                result.update(status='not_due',collection_state='not_due');skipped+=1
            else:
                attempts+=1
                try:
                    snapshot=ecos_decimal.fetch(source,active,client=ecos_client,now=now)
                    staged,counts=decimal_series.merge(archive,source,active,snapshot,now)
                    archive=staged;success+=1
                    for k,v in counts.items():health[k]+=v
                    result.update(status='ok',reason=None,collection_state='private_validated',
                        reference_period=snapshot['reference_period'],last_successful_check=now.isoformat(),
                        collection_mode=snapshot['collection_mode'],authentication_verified=snapshot['authentication_verified'],
                        observations=sum(len(r) for r in snapshot['records'].values()),**counts)
                except Exception:
                    # Never echo exception text, provider bodies, URLs, or a reflected key.
                    result.update(status='error',collection_state='failed_retained',error_kind='decimal_collection_or_validation_failed',
                        reason='신규 비공개 계열 수집/검증 실패; 기존 검증값 보존',
                        previous_data_preserved=bool(previous))
            health['sources'].append(result);continue
        if sid==tourgo.SOURCE:
            result['collection_state']='manual_input_required' if tourgo.permitted(source,'collection',now.date()) else 'approval_required'
            if not tourgo.permitted(source,'collection',now.date()):
                result.update(reason='collection_approval_required');health['sources'].append(result);continue
        if source.get('requires_approval') and not permitted(source, 'collection', now.date()):
            result.update(status='not_connected', reason='collection_approval_required')
            health['sources'].append(result);continue
        if source.get('method') == 'official_ecos_api':
            result['collection_state']='authentication_required' if not os.environ.get('ECOS_API_KEY') and ecos_client is None else 'mapping_pending' if source.get('mapping',{}).get('status')!='verified' else 'not_configured'
        if not source.get('enabled'):
            if source.get('auth_env'):
                result['credential_status']='configured_pending_mapping' if bool(os.environ.get(source['auth_env'])) else 'not_configured'
            health['sources'].append(result);continue
        if sid==tourgo.SOURCE and tourgo_ledger is None:
            # A schedule is not an import request. Do not refresh success times
            # or turn an approved retained series into a failed daily download.
            result.update(status='manual_update_pending',collection_state='waiting_for_manual_input',
                          reason='공식 XLS 수동 갱신 대기; 이전 검증값 유지',reference_period=previous.get('reference_period'))
            skipped+=1;health['sources'].append(result);continue
        if source.get('method') == 'official_ecos_api' and not os.environ.get('ECOS_API_KEY') and ecos_client is None:
            result.update(credential_status='not_configured', reason='ecos_auth_required');health['sources'].append(result);continue
        if sid!=tourgo.SOURCE and not force and previous.get('last_successful_check','')[:10]==now.date().isoformat():
            result.update(status='not_due',reference_period=previous.get('reference_period'))
            if source.get('method')=='official_ecos_api':result['collection_state']='not_due'
            skipped+=1;health['sources'].append(result);continue
        attempts+=1
        active=[i for i in config['indicators'] if i.get('enabled') and i['source_id']==sid]
        try:
            is_tourgo=sid==tourgo.SOURCE
            if source.get('requires_approval') and not is_tourgo:
                raise ValueError('approved_source_transport_not_activated')
            is_ecos=source.get('method')=='official_ecos_api'
            if is_tourgo or is_ecos:
                expected=tourgo.COLLECTION if is_tourgo else 'official_ecos_api'
                if any(o.get('collection_method')!=expected for i in active for o in archive['indicators'].get(i['id'],{}).get('observations',{}).values()):
                    raise ValueError('financial_source_change_requires_review')
            if is_tourgo:
                if not tourgo.noncommercial(read(ROOT/'operating_policy.json',{}) if operating_policy is None else operating_policy):
                    raise ValueError('tourgo_noncommercial_policy_required')
                snapshot=tourgo.fetch(source,active,tourgo_ledger,now)
                if any(archive['indicators'].get(i['id'],{}).get('observations') for i in active) and not tourgo.public_pair(source,archive,now.date()):
                    raise ValueError('tourgo_existing_archive_validation_failed')
            elif is_ecos:
                # Two independent gates: enabling a source must not bypass the
                # mapping, rights or KTO comparison review.
                if not ecos.publishable(source):
                    raise ecos.EcosError('ecos_publication_approval_required')
                request_source=copy.deepcopy(source)
                # Backfill from configured 2021 start only on the first verified
                # collection. Later refresh the rolling 24 months and any long
                # collection gap, retaining previously checked older months.
                if previous.get('last_successful_check') and all(
                        archive['indicators'].get(i['id'],{}).get('observations') for i in active):
                    lookback=month_before(now.strftime('%Y-%m'))
                    for _ in range(23):lookback=month_before(lookback)
                    previous_period=previous.get('reference_period')
                    if previous_period:lookback=min(lookback,valid_period(previous_period))
                    request_source['start_period']=max(source['start_period'],lookback)
                snapshot=ecos.fetch(request_source,active,ecos_client,now)
            elif source.get('method')=='official_public_xlsx':
                snapshot=kto.fetch(source,active,loader,now)
            else:
                raise ValueError('unsupported_macro_source_method')
            if snapshot['reference_period']<previous.get('reference_period','') or (not is_ecos and not is_tourgo and snapshot['release_published_at']<previous.get('release_published_at','')):
                raise ValueError('older_official_snapshot_rejected')
            staged=copy.deepcopy(archive);counts=dict(new_observations=0,unchanged_observations=0,value_corrections=0,status_changes=0)
            for item in active:
                key=item['id'];values=snapshot['values'][key]
                if item['unit']!=snapshot.get('unit',item['unit']) or item['frequency']!=snapshot.get('frequency',item['frequency']):raise ValueError('source_unit_or_frequency_mismatch')
                saved=staged['indicators'].setdefault(key,dict(unit=item['unit'],definition=item['definition'],observations={},revisions=[]))
                if saved['unit']!=item['unit'] or saved['definition']!=item['definition']:raise ValueError('unit_or_definition_changed_requires_review')
                for period,value in values.items():
                    valid_period(period)
                    if period>=now.strftime('%Y-%m') or not isinstance(value,int) or isinstance(value,bool) or value<0:raise ValueError('observation_validation_failed')
                    old=saved['observations'].get(period)
                    finality=snapshot.get('finality','not_stated')
                    if finality not in ('not_stated','provisional','final'):raise ValueError('unverified_finality_status')
                    if is_tourgo:
                        record=copy.deepcopy(snapshot['records'][key][period])
                        record.update(first_collected_at=old['first_collected_at'] if old else record['first_collected_at'],
                                      revision_status=old.get('revision_status','original') if old else 'original')
                        finality=record['finality']
                    elif is_ecos:
                        detail=snapshot['records'][key][period]
                        record=dict(**detail,unit=item['unit'],frequency=item['frequency'],publisher='한국은행 ECOS',source_url=snapshot['source_url'],release_published_at=None,original_publication_at=None,last_collected_at=now.isoformat(),first_collected_at=old['first_collected_at'] if old else now.isoformat(),revision_status=old.get('revision_status','original') if old else 'original',collection_method=snapshot['method'],response_sha256=snapshot['response_sha256'],rights=snapshot['rights'])
                    else:
                        record=dict(value=value,unit=item['unit'],frequency=item['frequency'],publisher=item['publisher'],source_url=snapshot['source_url'],release_published_at=snapshot['release_published_at'],original_publication_at=None,last_collected_at=now.isoformat(),first_collected_at=old['first_collected_at'] if old else now.isoformat(),finality=finality,revision_status=old.get('revision_status','original') if old else 'original',verification_status='official_file_validated',latest_crosscheck_period=snapshot['reference_period'],collection_method=snapshot['method'],file_url=snapshot['file_url'],file_sha256=snapshot['file_sha256'],sheet=snapshot['locations'][key]['sheet'],cell=snapshot['locations'][key]['cells'][period],rights=snapshot['rights'])
                    if old is None:counts['new_observations']+=1
                    elif old['value']!=value or old['finality']!=finality or (is_tourgo and any(old.get(k)!=record[k] for k in ('official_balance_value','official_balance_finality'))):
                        value_changed=old['value']!=value
                        counts['value_corrections' if value_changed else 'status_changes']+=1
                        if value_changed:record['revision_status']='revised'
                        kind='value_correction' if value_changed else 'finality_change' if old['finality']!=finality else 'balance_crosscheck_change'
                        saved['revisions'].append(dict(period=period,detected_at=now.isoformat(),kind=kind,before=old,after=record.copy()))
                    else:counts['unchanged_observations']+=1
                    saved['observations'][period]=record
                # A rolling ECOS request does not declare older unqueried months
                # missing. Only compare the returned interval; retain old records.
                start_checked,end_checked=(snapshot['queried_ranges'][key] if is_ecos
                    else (source['start_period'],snapshot['reference_period']))
                missing=[p for p in saved['observations'] if start_checked<=p<=end_checked and p not in values]
                saved['latest_snapshot_missing_periods']=missing
                if is_ecos:
                    saved['latest_response_missing_periods']=snapshot['missing_periods'][key]
                    saved['latest_checked_range']=[start_checked,end_checked]
            staged['sources'][sid]={k:v for k,v in snapshot.items() if k not in ('values','locations','records')}
            staged['sources'][sid]['last_successful_check']=now.isoformat()
            archive=staged;success+=1
            for k,v in counts.items():health[k]+=v
            result.update(status='ok',reason=None,reference_period=snapshot['reference_period'],release_published_at=snapshot['release_published_at'],last_successful_check=now.isoformat(),observations=sum(len(v) for v in snapshot['values'].values()),**counts)
            retained=sum(len(archive['indicators'][i['id']].get('latest_snapshot_missing_periods',[])) for i in active)
            if is_ecos:
                gaps={k:v for k,v in snapshot['missing_periods'].items() if v}
                result.update(collection_state='new_data' if counts['new_observations'] or counts['value_corrections'] or counts['status_changes'] else 'no_new_data', missing_periods=gaps)
                if gaps:result.update(status='partial',collection_state='partial_missing',reason='일부 월 미수신; 누락은 0으로 채우지 않고 이전 검증값 보존')
            if is_tourgo:
                result.update(collection_state='manual_import_validated',automatic_download=False)
            if retained:result.update(status='partial',reason='일부 과거 월이 최신 파일에서 누락되어 이전 검증값 보존',retained_missing_observations=retained)
        except Exception as exc:
            # Never serialize raw request/response text or credential-bearing URLs.
            reason=str(exc) if isinstance(exc,ValueError) and len(str(exc))<100 and all(c.isalnum() or c in '_:' for c in str(exc)) else type(exc).__name__
            result.update(status='error',error_kind=reason,reason='실제 수집 또는 검증 실패; 이전 검증 데이터 보존')
            if source.get('method')=='official_ecos_api':
                result['collection_state']='authentication_required' if reason in ('ecos_auth_required','ecos_auth_invalid') else 'mapping_pending' if reason=='ecos_mapping_pending' else 'no_data' if reason=='ecos_no_data' else 'failed_retained'
                result['previous_data_preserved']=bool(any(archive['indicators'].get(i['id'],{}).get('observations') for i in active))
            if sid==tourgo.SOURCE:
                result.update(collection_state='failed_retained',previous_data_preserved=bool(any(archive['indicators'].get(i['id'],{}).get('observations') for i in active)))
        health['sources'].append(result)
    health['status']=('partial' if any(s['status'] in ('error','partial') for s in health['sources']) else 'ok') if success else 'not_due' if skipped and not attempts else 'failed'
    health['successful_sources']=success;health['attempted_sources']=attempts;health['pending_sources']=sum(not s.get('enabled') for s in config['sources'])
    if success:
        # Save canonical history first. An interrupted public export can be retried;
        # missing/corrupt history is never silently recreated from a public subset.
        archive['updated_at']=now.isoformat();write_atomic(archive_path,archive)
        write_atomic(public_path,public_view(config,archive,now,operating_policy))
    view=public_view(config,archive,now,operating_policy)
    health['connected_indicators']=sum(i['connected'] for i in view['indicators'])
    health['connected_primary_indicators']=sum(i['connected'] and i['priority']==1 for i in view['indicators'])
    health['observation_count']=sum(len(i['observations']) for i in view['indicators'])
    health['indicators']=[dict(id=i['id'],connected=i['connected'],first_period=i.get('first_period'),latest_period=i.get('latest_period'),months=i.get('months',0),missing_periods=i['missing_periods']) for i in view['indicators']]
    write_atomic(data_dir/'macro_health.json',health);write_atomic(state_dir/'macro_run_summary.json',health)
    return health

def main():
    parser=argparse.ArgumentParser(description='Official provided statistical files and reviewed ECOS Open API; no internal web APIs')
    parser.add_argument('--sources',type=Path,default=ROOT/'macro_sources.json');parser.add_argument('--data-dir',type=Path,default=ROOT/'site/data');parser.add_argument('--state-dir',type=Path,default=ROOT/'collector_state');parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    result=collect(read(args.sources),args.data_dir,args.state_dir,force=args.force)
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','indicators')},ensure_ascii=False))
    return 1 if result['status']=='failed' else 0
if __name__=='__main__':raise SystemExit(main())
