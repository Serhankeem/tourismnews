"""Offline Step 7 originals replay in a NEW directory outside the app checkout.

No network, workflow, activation or public export. Real values/files remain
private. The in-memory collection grants below are test scaffolding, not rights
evidence or operator permission. Production configuration is never written.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
from src.macro import aviation, aviation_series
from src.macro.engine import collect, public_view
from src.pipeline.validation import validate

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root, relative):
    path = Path(relative)
    target = (root/path).resolve()
    if path.is_absolute() or '..' in path.parts or root not in target.parents:
        raise ValueError('aviation_evidence_path_invalid')
    return target


def private_config():
    cfg = json.loads((ROOT/'macro_sources.json').read_text())
    return dict(sources=[s for s in cfg['sources'] if s['id']==aviation.SOURCE],
                indicators=[i for i in cfg['indicators'] if i['source_id']==aviation.SOURCE])


def test_config(config, now):
    """Explicit offline-only simulated approvals, never an activation artifact."""
    config = copy.deepcopy(config)
    source = config['sources'][0];source['enabled']=True
    for review in aviation.REVIEWS:
        source[review] = dict(status='verified',evidence_url='https://example.invalid/offline-test-only',
                              verified_at=now.date().isoformat())
    source['approval']['collection'] = dict(approved=True,scope=aviation.SOURCE,
        evidence_ref='isolated-test-only-not-operator-approval',valid_from=now.date().isoformat(),
        valid_until=(now+dt.timedelta(days=7)).date().isoformat(),
        period_from=source['start_period'],period_through=source['end_period'])
    for item in config['indicators']:
        item['enabled']=True
    return config


def load_evidence(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder/'manifest.json').read_text())['files']
    registry_path = folder/'processed/file-manifest.json'
    if digest(registry_path) != manifest['processed/file-manifest.json']['sha256']:
        raise ValueError('aviation_research_manifest_hash_mismatch')
    files = json.loads(registry_path.read_text());bundle=[]
    for meta in files:
        path = safe_path(folder,meta['path']);pin=manifest[meta['path']]
        if (digest(path) != meta['sha256'] or digest(path) != pin['sha256']
                or path.stat().st_size != meta['bytes'] or path.stat().st_size != pin['bytes']):
            raise ValueError('aviation_original_hash_mismatch')
        if meta['kind'] in ('national_time_series_original','national_airport_breakdown_original'):
            stem = path.stem if meta['kind']=='national_time_series_original' else path.name[:6]
            filters_path = path.parent/(stem+'-filters.json')
            relative = str(filters_path.relative_to(folder))
            if digest(filters_path) != manifest[relative]['sha256']:
                raise ValueError('aviation_filter_evidence_hash_mismatch')
            bundle.append(dict(payload=path.read_bytes(),metadata=dict(meta,filters=json.loads(filters_path.read_text()))))
    kinds = [m['kind'] for m in files]
    if (len(files)!=6 or len(bundle)!=4 or kinds.count('national_time_series_original')!=2
            or kinds.count('national_airport_breakdown_original')!=2
            or kinds.count('incheon_independent_crosscheck_original')!=2):
        raise ValueError('aviation_step7_file_inventory_mismatch')
    references = {}
    for name in ('national-monthly.json','national-yoy.json'):
        path = folder/'processed'/name;relative=str(path.relative_to(folder))
        if digest(path) != manifest[relative]['sha256']:
            raise ValueError('aviation_research_reference_hash_mismatch')
        references[name] = json.loads(path.read_text())
    return bundle,files,references


def run(evidence, baseline, work, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    evidence,baseline,work = (Path(p).resolve() for p in (evidence,baseline,work))
    if (work.exists() or work in (ROOT,evidence,baseline)
            or any(root in work.parents or work in root.parents for root in (ROOT,evidence,baseline))):
        raise ValueError('fresh_external_isolation_directory_required')
    config=private_config();source=config['sources'][0]
    if (source['enabled'] or any(i['enabled'] for i in config['indicators'])
            or any(source['approval'][k]['approved'] for k in ('collection','publication'))):
        raise ValueError('aviation_production_flags_must_remain_disabled')
    bundle,files,refs = load_evidence(evidence)
    snapshot = aviation.snapshot(source,config['indicators'],bundle,now)
    expected = {(r['indicator'],r['period']):r for r in refs['national-monthly.json']}
    if len(expected)!=140 or len(refs['national-monthly.json'])!=140:
        raise ValueError('aviation_research_observation_count_mismatch')
    rates=[]
    for metric,key in aviation.IDS.items():
        obs=snapshot['records'][key]
        if len(obs)!=70:
            raise ValueError('aviation_reproduction_count_mismatch')
        for period,r in obs.items():
            reference=expected[(metric,period)]
            if any(r[k]!=reference[k] for k in ('value','arrivals','departures','unit','retrieved_at','excel_row')) or r['file_sha256']!=reference['source_sha256']:
                raise ValueError('aviation_original_reproduction_mismatch')
            rate=aviation_series.comparisons(obs,period)['yoy_pct']
            if rate is not None:
                rates.append(dict(indicator=metric,period=period,prior_year_period=f'{int(period[:4])-1:04}-{period[5:]}',value_pct=rate))
    if len(rates)!=116 or sorted(rates,key=lambda r:(r['indicator'],r['period'])) != sorted(refs['national-yoy.json'],key=lambda r:(r['indicator'],r['period'])):
        raise ValueError('aviation_yoy_reproduction_mismatch')
    # All inputs are validated before writing the fresh isolated copy.
    prior=json.loads((baseline/'collector_state/macro_archive.json').read_text())
    public_hashes={str(p.relative_to(baseline)):digest(p) for p in (baseline/'site/data').rglob('*') if p.is_file()}
    work.mkdir(parents=True,mode=0o700);target=work/'snapshot'
    shutil.copytree(baseline,target)
    cfg=test_config(config,now)
    args=dict(config=cfg,data_dir=target/'site/data',state_dir=target/'collector_state',
              only_sources={aviation.SOURCE},force=True,aviation_bundle=bundle)
    health=collect(**args,now=now)
    if health['successful_sources']!=1 or health['new_observations']!=140:
        raise ValueError('aviation_engine_replay_failed')
    archive_path=target/'collector_state/macro_archive.json';archive=json.loads(archive_path.read_text())
    full_config=json.loads((ROOT/'macro_sources.json').read_text())
    if public_view(full_config,archive,now)!=public_view(full_config,prior,now):
        raise ValueError('aviation_public_view_changed')
    if any(digest(target/name)!=sha for name,sha in public_hashes.items()):
        raise ValueError('aviation_public_files_changed')
    if any(archive.get(k)!=prior.get(k) for k in ('indicators','sources','decimal_indicators','decimal_sources')):
        raise ValueError('aviation_legacy_macro_changed')
    again=collect(**args,now=now+dt.timedelta(days=1))
    repeated=json.loads(archive_path.read_text())
    if (again['new_observations']!=0 or again['unchanged_observations']!=140
            or repeated['aviation_indicators']!=archive['aviation_indicators']
            or repeated['aviation_sources'][aviation.SOURCE]['vintages']!=archive['aviation_sources'][aviation.SOURCE]['vintages']):
        raise ValueError('aviation_repeat_not_idempotent')
    bad=copy.deepcopy(bundle);bad[0]['payload']=b'not an official XLSX'
    before_failure=archive_path.read_bytes();args['aviation_bundle']=bad
    failed=collect(**args,now=now+dt.timedelta(days=2))
    if failed['successful_sources'] or archive_path.read_bytes()!=before_failure or any(digest(target/name)!=sha for name,sha in public_hashes.items()):
        raise ValueError('aviation_failure_preservation_failed')
    validation=validate(target,json.loads((ROOT/'pipeline.json').read_text()),before=baseline)
    report=dict(mode='offline_original_replay_with_test_only_in_memory_grants',
        original_statistical_files_integrity_checked=len(files),national_xlsx_parsed=len(bundle),
        auxiliary_xls_hash_checked=2,auxiliary_xls_values_reparsed=False,
        observations=140,yoy_observations=116,first_period='2021-01',latest_period='2026-10',
        yoy_first_period='2022-01',yoy_latest_period='2026-10',scope=aviation.SCOPE,
        units=aviation.UNITS,raw_files_committed=False,production_approvals_changed=False,
        automatic_download=False,publication_allowed=False,independent_full_crosscheck_complete=False,
        repeat_idempotent=True,failed_input_preserves_archive_and_public=True,
        legacy_macro_equal=True,public_files_byte_identical=True,pipeline_validation=validation,
        original_files=[{k:m[k] for k in ('path','kind','bytes','sha256')} for m in files])
    (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-dir',type=Path,required=True)
    p.add_argument('--baseline-root',type=Path,required=True,help='Read-only local data/live snapshot')
    p.add_argument('--work',type=Path,required=True,help='New isolated directory outside the application checkout')
    args=p.parse_args()
    try:
        report=run(args.evidence_dir,args.baseline_root,args.work)
        print(json.dumps({k:report[k] for k in ('mode','observations','yoy_observations','public_files_byte_identical','publication_allowed')},ensure_ascii=False))
        return 0
    except Exception:
        # Fixed diagnostics: no file bytes, private paths or parser excerpts.
        print('aviation_offline_validation_failed; existing production data and approvals unchanged')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
