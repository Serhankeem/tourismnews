"""TOURGO's shared official-file adapter, change assessment and package builder.

Private files only. No source activation, credentials, network calls or Git writes.
Hashes provide integrity; only bootstrap's pinned originals or an explicitly
reviewed, protected owner input provide the source trust boundary.
"""
import argparse
import contextlib
import copy
import datetime as dt
import io
import json
from pathlib import Path
import shutil
from . import balance,tourgo
from .model import months
from .tourgo_release import ROOT, INITIAL_HASHES, digest_file, stage
from ..collector import write_atomic
from ..pipeline.layout import read

ORIGINALS=tuple(k+'.xls' for k in balance.KINDS)
SOURCE=dict(schema_version=2,source_id=tourgo.SOURCE,source_url=tourgo.URL,publisher=tourgo.PUBLISHER,
    scope='general_travel_monthly',unit=balance.UNIT,
    acquisition='operator_supplied_official_export',operator_reviewed_source=True)
SOURCE_FILES=(*ORIGINALS,'source.json')


def saved_ledger(archive, now):
    """Recover only previously validated TOURGO values, never ECOS estimates."""
    saved=archive['indicators'];present=[bool(saved.get(k,{}).get('observations')) for k in tourgo.IDS]
    if not any(present):return None
    if not all(present):raise ValueError('tourgo_saved_pair_incomplete')
    series={k:{} for k in balance.KINDS}
    rows=[saved[k]['observations'] for k in tourgo.IDS]
    if set(rows[0])!=set(rows[1]):raise ValueError('tourgo_saved_periods_mismatch')
    for period in rows[0]:
        for kind,key in zip(balance.KINDS,tourgo.IDS):
            o=saved[key]['observations'][period]
            if (o.get('source_id')!=tourgo.SOURCE or o.get('unit')!='US$'
                    or tourgo.usd(o.get('source_value'))!=o.get('value')
                    or o.get('source_unit')!=balance.UNIT or o.get('verification_status')!=tourgo.VERIFICATION):
                raise ValueError('tourgo_saved_source_or_unit_invalid')
            proof=dict(data_origin=o.get('data_origin'),unit=o['source_unit'],source_url=o.get('source_url'),
                collection_method=o.get('collection_method'),sha256_by_kind=copy.deepcopy(o.get('bundle_sha256_by_kind')),finality=o['finality'])
            series[kind][period]=dict(period=period,value=o['source_value'],unit=balance.UNIT,finality=o['finality'],
                first_collected_at=o['first_collected_at'],last_collected_at=o['last_collected_at'],provenance=proof)
        r,e=[row[period] for row in rows]
        if r.get('official_balance_value')!=r['value']-e['value'] or e.get('official_balance_value')!=r['value']-e['value']:
            raise ValueError('tourgo_saved_identity_invalid')
        b=copy.deepcopy(series['receipts'][period]);b['value']=(r['value']-e['value'])//1000
        b['finality']=r['official_balance_finality'];b['provenance']['finality']=b['finality'];series['balance'][period]=b
    result=dict(data_origin='official_export',unit=balance.UNIT,latest_period=max(series['receipts']),series=series,
                revisions=copy.deepcopy(archive.get('sources',{}).get(tourgo.SOURCE,{}).get('import_revisions',[])))
    tourgo.validate_ledger(result,now)
    return result


class OfficialFiles:
    """Concrete adapter used by bootstrap AND recurring file-based updates."""
    def __init__(self, paths, expected_hashes=None):
        self.paths={k:Path(p) for k,p in paths.items()}
        self.expected=expected_hashes

    def load(self, archive, profile, now):
        if profile not in ('initial','update') or set(self.paths)!=set(balance.KINDS):raise ValueError('tourgo_file_profile_invalid')
        for p in self.paths.values():
            if not p.is_file() or p.is_symlink() or p.stat().st_size>4*1024*1024:raise ValueError('tourgo_original_file_invalid')
        hashes={k:digest_file(p) for k,p in self.paths.items()}
        expected=self.expected if self.expected is not None else (INITIAL_HASHES if profile=='initial' else hashes)
        if hashes!=expected:raise ValueError('tourgo_original_hash_mismatch')
        previous=saved_ledger(archive,now)
        if (profile=='initial')==bool(previous):raise ValueError('tourgo_initial_update_state_mismatch')
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            parsed=tourgo.from_files(self.paths,expected,now)
        periods=set(parsed['series']['receipts'])
        if min(periods)<'2021-01' or periods!=set(months(min(periods),max(periods))):raise ValueError('tourgo_missing_or_out_of_scope_period')
        if profile=='initial' and periods!=set(months('2021-01','2026-09')):raise ValueError('tourgo_initial_69_months_required')
        if previous:
            if not set(previous['series']['receipts'])<=periods:raise ValueError('tourgo_original_lost_existing_periods')
            values=tourgo.validate_ledger(parsed,now)
            proof=copy.deepcopy(parsed['series']['receipts'][parsed['latest_period']]['provenance'])
            parsed=balance.merge_ledger(previous,values,proof,now)
        tourgo.validate_ledger(parsed,now)
        return parsed,expected


def assess(ledger, archive, profile, now):
    """Data quality only. VALID here never substitutes for publication approval."""
    if profile not in ('initial','update'):raise ValueError('tourgo_file_profile_invalid')
    values=tourgo.validate_ledger(ledger,now);old=saved_ledger(archive,now)
    if (profile=='initial')==bool(old):raise ValueError('tourgo_initial_update_state_mismatch')
    periods=set(values['receipts'])
    if profile=='initial' and periods!=set(months('2021-01','2026-09')):raise ValueError('tourgo_initial_69_months_required')
    if periods!=set(months(min(periods),max(periods))):raise ValueError('tourgo_missing_period')
    new=periods-set(old['series']['receipts'] if old else ())
    revisions=0;anomalies=0
    if old:
        if not set(old['series']['receipts'])<=periods:raise ValueError('tourgo_lost_existing_periods')
        for kind in balance.KINDS:
            for period,o in old['series'][kind].items():
                current=ledger['series'][kind][period]
                revisions+=int((o['value'],o['finality'])!=(current['value'],current['finality']))
        for kind in ('receipts','expenditure'):
            for period in new:
                prior=values[kind].get(balance.month_before(period))
                if prior is not None and abs(values[kind][period]-prior)*100>abs(prior)*75:anomalies+=1
    reasons=[]
    if revisions:reasons.append('historical_revision_requires_review')
    if anomalies:reasons.append('large_monthly_change_requires_review')
    status='REVIEW_REQUIRED' if reasons else 'UNCHANGED' if not new else 'VALID'
    return dict(status=status,data_status=status,reasons=reasons,profile=profile,new_months=len(new),
        revised_observations=revisions,anomaly_count=anomalies,first_period=min(periods),latest_period=max(periods),
        official_identity_months=len(periods),publication_allowed=False)


def gates(config,policy,now):
    """Terms, collection and publication are independent, persistent grants."""
    source=next(s for s in config['sources'] if s['id']==tourgo.SOURCE)
    terms=tourgo.terms_confirmed(source,policy,now.date())
    def grant(action):
        g=source.get('approval',{}).get(action,{})
        return bool(terms and tourgo.permitted(source,action,now.date()) and g.get('valid_until')
            and g['valid_until']!='9999-12-31' and not str(g.get('evidence_ref','')).startswith(('staging-only','isolated-preview','PENDING')))
    return dict(terms_verified=terms,collection_allowed=grant('collection'),publication_allowed=grant('publication'))


def external_directory(target):
    target=Path(target).resolve()
    if target.exists() or target==ROOT or ROOT in target.parents:raise ValueError('tourgo_new_external_directory_required')
    target.mkdir(mode=0o700,parents=True)
    return target


def manifest(root,names,profile,schema):
    doc=dict(schema_version=schema,profile=profile,files={name:digest_file(root/name) for name in names})
    write_atomic(root/'manifest.json',doc);(root/'manifest.json').chmod(0o600)
    return doc


def source_package(paths,output,reviewed):
    """One upload per month: originals + generated provenance/manifest, no ledger."""
    if reviewed is not True:raise ValueError('tourgo_operator_source_review_required')
    target=external_directory(output)
    try:
        if set(paths)!=set(balance.KINDS):raise ValueError('tourgo_three_originals_required')
        for kind,p in paths.items():
            p=Path(p)
            if p.is_symlink() or not p.is_file() or p.stat().st_size>4*1024*1024:raise ValueError('tourgo_original_file_invalid')
            original_hash=digest_file(p)
            shutil.copyfile(p,target/(kind+'.xls'));(target/(kind+'.xls')).chmod(0o600)
            if digest_file(p)!=original_hash or digest_file(target/(kind+'.xls'))!=original_hash:
                raise ValueError('tourgo_original_changed_during_packaging')
        write_atomic(target/'source.json',SOURCE);(target/'source.json').chmod(0o600)
        return manifest(target,SOURCE_FILES,'update',2)
    except Exception:
        shutil.rmtree(target);raise


def release_package(paths,baseline,output,profile,now,reviewed,code=ROOT):
    """Bootstrap/review exception: generate all old 6-file handoff automatically."""
    if reviewed is not True:raise ValueError('tourgo_operator_source_review_required')
    target=external_directory(output)
    try:
        ledger,expected=OfficialFiles(paths).load(read(Path(baseline)/'collector_state/macro_archive.json'),profile,now)
        stage(ledger,baseline,target/'staging',expected,profile,now,code=code)
        package=target/'input';package.mkdir(mode=0o700)
        for name,src in [('ledger.json',target/'staging/validated-input.json'),('receipt.json',target/'staging/readiness.json')]+[(k+'.xls',Path(p)) for k,p in paths.items()]:
            shutil.copyfile(src,package/name);(package/name).chmod(0o600)
        return manifest(package,('ledger.json','receipt.json',*ORIGINALS),profile,1)
    except Exception:
        shutil.rmtree(target);raise


def main():
    p=argparse.ArgumentParser(description='Offline TOURGO packaging/staging; no activation or publishing')
    p.add_argument('operation',choices=['source-package','release-package','inspect'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline-root',type=Path)
    p.add_argument('--profile',choices=['initial','update'],default='update');p.add_argument('--official-source-reviewed',action='store_true')
    for kind in balance.KINDS:p.add_argument('--'+kind,type=Path,required=True)
    args=p.parse_args();paths={k:getattr(args,k) for k in balance.KINDS};now=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    try:
        if args.operation=='source-package':
            source_package(paths,args.output,args.official_source_reviewed)
            print('tourgo_private_source_package_created; no_publication')
        elif args.operation=='release-package':
            if args.baseline_root is None:raise ValueError('tourgo_baseline_required')
            release_package(paths,args.baseline_root,args.output,args.profile,now,args.official_source_reviewed)
            print('tourgo_private_release_package_created; review_staging_before_publication')
        else:
            if args.baseline_root is None:raise ValueError('tourgo_baseline_required')
            archive=read(args.baseline_root/'collector_state/macro_archive.json')
            ledger,_=OfficialFiles(paths).load(archive,args.profile,now)
            report=assess(ledger,archive,args.profile,now)
            rights=gates(read(ROOT/'macro_sources.json'),read(ROOT/'operating_policy.json'),now);report.update(rights)
            if not rights['collection_allowed'] or not rights['publication_allowed']:
                report['status']='REVIEW_REQUIRED';report['reasons']+=['operating_approval_required']
            if rights['collection_allowed'] and rights['publication_allowed']:
                from .tourgo_release import operating_configuration
                try:operating_configuration(read(ROOT/'macro_sources.json'),read(ROOT/'operating_policy.json'),now)
                except ValueError:
                    report['status']='REVIEW_REQUIRED';report['reasons'].append('operating_mapping_not_activated')
            target=external_directory(args.output)
            report['publication_allowed']=report['publication_allowed'] and report['status']=='VALID'
            write_atomic(target/'quality.json',report);(target/'quality.json').chmod(0o600)
            print(json.dumps(report,ensure_ascii=False))
        return 0
    except Exception:
        print('tourgo_staging_rejected; previous_data_unchanged')
        return 1


if __name__=='__main__':raise SystemExit(main())
