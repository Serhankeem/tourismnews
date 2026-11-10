"""Main-only transactional collection + validated Pages assembly.

Production refs are never changed by tests/PR jobs. The Store class is tested
against local bare repositories; this CLI requires the main Actions context.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import tempfile
from pathlib import Path
from .layout import ROOT, CONTROL, MANIFEST, configuration, files, hashes, copy_data, read, owner, DataError
from .store import Store, StoreError, Conflict, git
from .validation import validate, ValidationError
from .schedule import pending
from .policy import project, verify_public
from ..collector import write_atomic, now_kst, iso


def invoke(engine, stage, force, days):
    import subprocess
    import sys
    command=[sys.executable,'-m','src.pipeline.collect',engine,'--stage',str(stage),'--days',str(days)]
    if force:command.append('--force')
    # Keep a slow engine from consuming the whole shared lock. No provider
    # error payload or credential-bearing traceback is copied into public logs.
    result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout={'news':900,'reports':1200,'macro':600}[engine])
    if result.returncode not in (0,1):raise RuntimeError('collector_process_failed')
    return result.returncode==0


def compose(code, snapshot, output, cfg, macro_config=None):
    # Code's frozen main data is excluded, even if newer files were added there.
    validate(snapshot,cfg)
    verify_public(snapshot,code,macro_config=macro_config)
    output=Path(output)
    if output.exists():shutil.rmtree(output)
    shutil.copytree(Path(code)/'site',output,ignore=shutil.ignore_patterns('data','collector_state','*.pyc','__pycache__'))
    for name in cfg['public_files']:
        dest=output/Path(name).relative_to('site');dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(Path(snapshot)/name,dest)
    if (output/'collector_state').exists() or set(p.name for p in (output/'data').iterdir())!={Path(p).name for p in cfg['public_files']}:
        raise ValidationError('unexpected_pages_tree')
    # No unapproved extra files, symlinks or internal ledgers in the artifact.
    if any(p.is_symlink() for p in output.rglob('*')):
        raise ValidationError('pages_symlink_forbidden')
    return hashes(snapshot,cfg['public_files'])


def transact(code, remote, work, output, requested='none', force=False, days=90, collector=invoke, at=None, max_attempts=3, result=None, tourgo_request=None):
    code,work=Path(code),Path(work);cfg=configuration(code);work.mkdir(parents=True,exist_ok=True)
    code_commit=git(code,'rev-parse','HEAD').stdout.strip()
    if result is None:result={}
    if tourgo_request is not None and requested!='macro':raise DataError('tourgo_manual_import_requires_macro_transaction')
    result.update(phase='load',main_auto_commit=False,code_commit=code_commit,engines={},ready=False,requested=requested)
    for attempt in range(max_attempts):
        attempt_dir=work/('attempt-'+str(attempt));attempt_dir.mkdir()
        write_atomic(work/'result.json',result)
        store=Store(attempt_dir/'snapshot',remote,cfg)
        if store.tip('main')!=code_commit:
            raise StoreError('main_changed_retry_latest_code')
        initialized=store.load(code,code_commit)
        stage=attempt_dir/'stage';copy_data(store.path,stage,cfg)
        shutil.copyfile(store.path/CONTROL,stage/CONTROL)
        before=attempt_dir/'before';copy_data(stage,before,cfg)
        clock=at or now_kst();control=read(stage/CONTROL)
        # Re-read and revalidate the reviewed private input against each freshly
        # restored snapshot, including after a normal fast-forward conflict.
        manual_ledger=tourgo_request.validate(stage,code,clock) if tourgo_request is not None else None
        due=pending(control,clock,requested)
        result.update(phase='collect',bootstrap=initialized,engines={},attempt=attempt+1)
        for engine,slot in due.items():
            checkpoint=attempt_dir/('before-'+engine);copy_data(stage,checkpoint,cfg)
            pre=hashes(stage,files(cfg))
            result['engines'][engine]={'status':'running'}
            write_atomic(work/'result.json',result)
            try:
                if engine=='macro' and tourgo_request is not None:
                    from ..macro.engine import collect as collect_macro
                    health=collect_macro(read(code/'macro_sources.json'),stage/'site/data',stage/'collector_state',
                        now=clock,force=force,tourgo_ledger=manual_ledger,operating_policy=read(code/'operating_policy.json'))
                    # A healthy KTO response must not mask an explicitly failed
                    # manual TOURGO import as a successful partial collection.
                    from ..macro.tourgo import SOURCE
                    success=next((s.get('status')=='ok' for s in health['sources'] if s['id']==SOURCE),False)
                    if success:tourgo_request.verify_projection(stage)
                else:
                    success=collector(engine,stage,force and engine==requested,days)
                after=hashes(stage,files(cfg))
                if any(pre[p]!=after[p] and owner(p)!=engine for p in pre):
                    raise ValidationError('engine_wrote_other_dataset')
                validate(stage,cfg,before=checkpoint)
            except Exception as exc:
                shutil.rmtree(stage)
                copy_data(checkpoint,stage,cfg)
                result['engines'][engine]={'status':'failed','error_kind':type(exc).__name__,
                    'error':str(exc) if isinstance(exc,DataError) else 'collector_failed_or_timed_out',
                    'previous_data_preserved':True}
                continue
            health_name={'news':'health','reports':'reports_health','macro':'macro_health'}[engine]
            health=read(stage/('site/data/'+health_name+'.json'))
            observed=health.get('discovery',{}).get('discovery_status') if engine=='news' else health.get('status')
            status=(observed if observed in ('partial','not_due') else 'ok') if success else 'failed'
            result['engines'][engine]={'status':status,'slot':slot,'health_file':'site/data/'+health_name+'.json'}
            if success:control['completed_slots'][engine]=slot
        if tourgo_request is not None and result['engines'].get('macro',{}).get('status')=='failed':
            raise DataError('tourgo_manual_transaction_failed_no_data_committed')
        write_atomic(stage/CONTROL,control)
        result['phase']='validate'
        projection_clock=at or now_kst()
        project(stage,code,projection_clock)
        counts=validate(stage,cfg,before=before);verify_public(stage,code)
        old_ids={a['id'] for a in read(before/'collector_state/archive.json')['articles']}
        old_reports={a['id'] for a in read(before/'collector_state/reports_archive.json')['reports']}
        old_macro=read(before/'collector_state/macro_archive.json')['indicators']
        new_records={
            'news':sum(a['id'] not in old_ids and a.get('record_type','news')=='news' for a in read(stage/'collector_state/archive.json')['articles']),
            'reports':sum(a['id'] not in old_reports for a in read(stage/'collector_state/reports_archive.json')['reports']),
            'macro_observations':sum(len(set(a['observations'])-set(old_macro.get(i,{}).get('observations',{}))) for i,a in read(stage/'collector_state/macro_archive.json')['indicators'].items())}
        if store.tip('main')!=code_commit:
            raise StoreError('main_changed_retry_latest_code')
        result['phase']='persist'
        try:
            data_commit,changed=store.commit(stage,code_commit,before)
        except Conflict:
            if attempt+1==max_attempts:raise
            continue  # Reload latest snapshot, then recollect. No JSON overwrite.
        result.update(data_commit=data_commit,data_committed=changed,counts=counts,new_records=new_records)
        if store.tip('main')!=code_commit or store.tip()!=data_commit:
            raise StoreError('newer_code_or_data_no_stale_deployment')
        result['phase']='assemble'
        public_hashes=compose(code,store.path,output,cfg)
        write_atomic(work/'deployment.json',{'code_commit':code_commit,'data_commit':data_commit,'public_files':public_hashes,'policy_evaluated_on':projection_clock.date().isoformat()})
        result.update(phase='ready_for_pages',ready=True,data_commit=data_commit,data_committed=changed,counts=counts)
        result['collection_ok']=all(r['status'] in ('ok','partial','not_due') for r in result['engines'].values())
        return result
    raise StoreError('conflict_retry_exhausted')


def require_main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REF')!='refs/heads/main' or os.environ.get('GITHUB_EVENT_NAME') not in ('push','schedule','workflow_dispatch'):
        raise StoreError('production_operation_requires_main_actions')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('operation',choices=['run','guard'])
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--output',type=Path)
    p.add_argument('--requested',choices=['none','news','reports','macro'],default='none')
    p.add_argument('--force',action='store_true')
    p.add_argument('--days',choices=[30,60,90],type=int,default=90)
    p.add_argument('--tourgo-ledger',type=Path);p.add_argument('--tourgo-ledger-sha256')
    p.add_argument('--tourgo-receipt',type=Path);p.add_argument('--tourgo-receipt-sha256')
    p.add_argument('--tourgo-input-dir',type=Path)
    args=p.parse_args();args.work.mkdir(parents=True,exist_ok=True)
    result={'phase':'authorization','ready':False,'main_auto_commit':False}
    try:
        require_main()
        manual=(args.tourgo_ledger,args.tourgo_ledger_sha256,args.tourgo_receipt,args.tourgo_receipt_sha256)
        request=None
        if args.tourgo_input_dir is not None:
            if any(v is not None for v in manual) or args.operation!='run' or args.requested!='macro':
                raise DataError('tourgo_manual_import_arguments_invalid')
            from ..macro.tourgo_delivery import request as protected_request
            request=protected_request(args.tourgo_input_dir,os.environ.get('TOURGO_MANIFEST_SHA256',''))
        elif any(v is not None for v in manual):
            if not all(manual) or args.operation!='run' or args.requested!='macro':
                raise DataError('tourgo_manual_import_arguments_invalid')
            from ..macro.tourgo_release import ReleaseRequest
            request=ReleaseRequest(*manual)
        remote=git(ROOT,'remote','get-url','origin').stdout.strip()
        if args.operation=='guard':
            if (args.work/'result.json').exists():result=read(args.work/'result.json')
            result['phase']='deployment_guard'
            proof=read(args.work/'deployment.json')
            if proof['policy_evaluated_on']!=now_kst().date().isoformat():
                raise StoreError('policy_day_changed_retry_before_deploy')
            tip=git(ROOT,'ls-remote','origin','refs/heads/main','refs/heads/data/live').stdout
            found={line.split()[1]:line.split()[0] for line in tip.splitlines()}
            if found.get('refs/heads/main')!=proof['code_commit'] or found.get('refs/heads/data/live')!=proof['data_commit']:
                raise StoreError('newer_snapshot_do_not_deploy_stale_artifact')
            return 0
        result=transact(ROOT,remote,args.work,args.output,args.requested,args.force,args.days,result=result,tourgo_request=request)
        write_atomic(args.work/'result.json',result)
        if result['ready'] and os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('ready=true\n')
        return 0 if result['collection_ok'] else 1
    except Exception as exc:
        # Never expose endpoint queries/credential-bearing exception payloads.
        result.update(error_kind=type(exc).__name__,error=str(exc) if isinstance(exc,(StoreError,DataError)) else 'validation_or_execution_failed',ready=False)
        write_atomic(args.work/'result.json',result)
        return 1


if __name__=='__main__':raise SystemExit(main())
