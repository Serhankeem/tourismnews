"""Read-only readiness staging and revalidated input for the main transaction.

No downloader, standalone push, approval-file edits or Preview promotion.
Actual publication remains inside the existing main Actions transaction/lock.
"""
import argparse
import contextlib
import io
import datetime as dt
import json
from pathlib import Path
from . import tourgo
from .engine import collect, public_view
from .model import months
from ..collector import write_atomic
from ..pipeline.layout import configuration, copy_data, files, hashes, read, DataError
from ..pipeline.validation import validate

ROOT=Path(__file__).resolve().parents[2]
INITIAL_HASHES=dict(receipts='780465a3e72886e94643dd6da5f2fa03d3f5d0a991200ce29313e969eae51f7d',
    expenditure='c21d857270a37d29251f3f3c0d2314c50b49c1b73259c7fbab50f7eb72e96ff1',
    balance='c2a3bd7ba225db9117fcb5535c0f8957ff80f0440801c18080080a74a3f2f721')
IMPLEMENTATION=('src/macro/tourgo_release.py','src/macro/tourgo.py','src/macro/engine.py',
    'src/macro/balance.py','src/macro/model.py','src/pipeline/runner.py','src/pipeline/store.py',
    'src/pipeline/layout.py','src/pipeline/validation.py','src/pipeline/policy.py','site/macro.js','operating_policy.json','src/macro/tourgo_activation.py',
    'src/macro/tourgo_delivery.py','.github/workflows/pipeline.yml','.github/workflows/tourgo-publish.yml','src/macro/tourgo_staging.py',
    'src/macro/tourgo_update.py','.github/workflows/tourgo-update.yml')


def digest_file(path):return tourgo.digest(Path(path).read_bytes())
def canonical(value):return tourgo.digest(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
def implementation(code):return canonical({p:digest_file(Path(code)/p) for p in IMPLEMENTATION})


def activation_candidate(config, now):
    """Ephemeral staging settings. Never written over macro_sources.json."""
    config=tourgo.select_source(config)
    source=next(s for s in config['sources'] if s['id']==tourgo.SOURCE)
    source['enabled']=True
    for action in ('collection','publication'):
        source['approval'][action]=dict(approved=True,scope='general_travel_monthly',
            evidence_ref='staging-only-not-operating-approval',valid_from=now.date().isoformat())
    for i in config['indicators']:
        if i['id'] in tourgo.IDS:
            i.update(enabled=True,reason='공식 XLS 수동 갱신; 자동 다운로드 미사용')
    return config


def verified_profile(ledger, expected_hashes, profile, baseline, now):
    values=tourgo.validate_ledger(ledger,now)
    if profile not in ('initial','update') or not tourgo.hashes_valid(expected_hashes):
        raise ValueError('tourgo_release_profile_invalid')
    existing=any(baseline['indicators'].get(key,{}).get('observations') for key in tourgo.IDS)
    if (profile=='initial' and existing) or (profile=='update' and not existing):
        raise ValueError('tourgo_release_initial_update_state_mismatch')
    if profile=='initial':
        if expected_hashes!=INITIAL_HASHES or set(values['receipts'])!=set(months('2021-01','2026-09')):
            raise ValueError('tourgo_initial_69_months_or_hashes_mismatch')
    # Each new vintage must use the independently reviewed three original hashes.
    for kind,records in ledger['series'].items():
        for o in records.values():
            if profile=='initial' or o['period']==ledger['latest_period']:
                if o['provenance']['sha256_by_kind']!=expected_hashes:
                    raise ValueError('tourgo_reviewed_original_hashes_mismatch')
    return values


def public_financial(view):
    return dict(indicators=[i for i in view['indicators'] if i['id'] in tourgo.IDS],
                tourism_balance=view.get('tourism_balance'))


def assert_public_contract(view):
    financial=public_financial(view)
    for i in financial['indicators']:
        if not i['connected']:raise ValueError('tourgo_staging_financial_not_connected')
        for o in i['observations']:
            if set(o)-tourgo.PUBLIC_RECORD_FIELDS-{'period'}:
                raise ValueError('tourgo_private_metadata_in_public_output')
        if set(i['latest'])-tourgo.PUBLIC_RECORD_FIELDS-{'period','comparisons'}:
            raise ValueError('tourgo_private_metadata_in_public_output')
    if not financial['tourism_balance'] or not financial['tourism_balance']['official_identity_verified']:
        raise ValueError('tourgo_staging_balance_unverified')


def stage(ledger, baseline, output, expected_hashes, profile, now, code=ROOT):
    code,baseline,output=Path(code).resolve(),Path(baseline).resolve(),Path(output).resolve()
    if output.exists() or any(output==p or p in output.parents or output in p.parents for p in (ROOT,code)):
        raise ValueError('tourgo_staging_new_directory_outside_checkout_required')
    cfg=configuration(code);validate(baseline,cfg)
    if not tourgo.noncommercial(read(code/'operating_policy.json')):raise ValueError('tourgo_noncommercial_policy_required')
    archive=read(baseline/'collector_state/macro_archive.json')
    verified_profile(ledger,expected_hashes,profile,archive,now)
    proposed=activation_candidate(read(code/'macro_sources.json'),now)
    output.mkdir(parents=True,mode=0o700)
    candidate=output/'candidate';copy_data(baseline,candidate,cfg)
    before=hashes(baseline,files(cfg))
    result=collect(proposed,candidate/'site/data',candidate/'collector_state',now=now,
                   force=True,tourgo_ledger=ledger,only_sources={tourgo.SOURCE},operating_policy=read(code/'operating_policy.json'))
    if not result['successful_sources'] or result['status'] not in ('ok','partial'):
        raise ValueError('tourgo_staging_import_failed')
    # Staging imports only TOURGO. Retain other providers' real check times so
    # omitting a KTO request cannot appear as either new success or lost health.
    health=read(candidate/'site/data/macro_health.json')
    retained=[]
    for original in read(baseline/'site/data/macro_health.json').get('sources',[]):
        if original['id']==tourgo.SOURCE:continue
        row=dict(original,checked_in_this_run=False)
        if row.get('status')=='ok':row['status']='not_due'
        retained.append(row)
    health['sources']+=retained
    if any(s.get('status') in ('error','partial') for s in retained):health['status']='partial'
    write_atomic(candidate/'site/data/macro_health.json',health)
    write_atomic(candidate/'collector_state/macro_run_summary.json',health)
    saved=read(candidate/'collector_state/macro_archive.json')
    # Source-specific staging cannot refresh or rewrite KTO records/revisions.
    for key,series in archive['indicators'].items():
        if key not in tourgo.IDS and saved['indicators'].get(key)!=series:
            raise ValueError('tourgo_staging_changed_existing_statistics')
    changed=[p for p,h in before.items() if digest_file(candidate/p)!=h]
    allowed={'site/data/macro.json','site/data/macro_health.json','collector_state/macro_archive.json','collector_state/macro_run_summary.json'}
    if set(changed)-allowed:raise ValueError('tourgo_staging_changed_other_engine_data')
    counts=validate(candidate,cfg,before=baseline)
    view=read(candidate/'site/data/macro.json');assert_public_contract(view)
    from ..pipeline.runner import compose
    compose(code,candidate,output/'pages',cfg,macro_config=proposed)
    index=output/'pages/index.html'
    index.write_text(index.read_text().replace('<body>','<body><div role="status" style="padding:12px;background:#fff2b3;color:#663900;text-align:center;font-weight:700">TOURGO 검토용 staging · 운영 게시 아님</div>',1))
    # The validated input stays outside Pages and is hash-bound for revalidation.
    write_atomic(output/'validated-input.json',ledger);(output/'validated-input.json').chmod(0o600)
    receipt=dict(schema_version=1,kind='tourgo_release_readiness',profile=profile,
        operating_approval=False,created_at=now.isoformat(),implementation_sha256=implementation(code),
        input_sha256=digest_file(output/'validated-input.json'),expected_original_hashes=expected_hashes,
        baseline_macro_sha256=digest_file(baseline/'collector_state/macro_archive.json'),
        financial_projection_sha256=canonical(public_financial(view)),
        first_period=min(ledger['series']['receipts']),latest_period=ledger['latest_period'],
        financial_observations=sum(len(i['observations']) for i in view['indicators'] if i['id'] in tourgo.IDS),
        existing_nonfinancial_observations=sum(len(i['observations']) for k,i in archive['indicators'].items() if k not in tourgo.IDS),
        projected_total_observations=counts['macro_observations'],changed_files=changed)
    write_atomic(output/'readiness.json',receipt);(output/'readiness.json').chmod(0o600)
    return receipt


def operating_configuration(config, policy, now):
    """Actual dated approval, separate from the ephemeral staging candidate."""
    source=next(s for s in config['sources'] if s['id']==tourgo.SOURCE)
    if not source.get('enabled') or not all(tourgo.permitted(source,a,now.date()) for a in ('collection','publication')):
        raise ValueError('production_approval_required')
    if any(not source['approval'][a].get('valid_until') or str(source['approval'][a].get('evidence_ref','')).startswith(('staging-only','isolated-preview')) for a in ('collection','publication')):
        raise ValueError('dated_operating_approval_required')
    if not tourgo.terms_confirmed(source,policy,now.date()):raise ValueError('tourgo_terms_or_noncommercial_policy_required')
    if any(s.get('enabled') for s in config['sources'] if s['id'].startswith('ecos_')):
        raise ValueError('ecos_must_remain_inactive')
    expected=activation_candidate(config,now)
    for key in tourgo.IDS:
        actual=next(i for i in config['indicators'] if i['id']==key)
        target=next(i for i in expected['indicators'] if i['id']==key)
        if any(actual.get(k)!=target.get(k) for k in tourgo.PUBLIC_INDICATOR_FIELDS):
            raise ValueError('production_mapping_requires_review')
    return config


class ReleaseRequest:
    """Used only by the existing main Actions transaction; never copies staging."""
    def __init__(self, ledger_path, ledger_hash, receipt_path, receipt_hash, originals=None):
        self.ledger_path,self.ledger_hash=Path(ledger_path),ledger_hash
        self.receipt_path,self.receipt_hash=Path(receipt_path),receipt_hash
        self.originals=originals

    def validate(self, baseline, code, now):
        code=Path(code).resolve()
        for p in (self.ledger_path,self.receipt_path):
            if code==p.resolve() or code in p.resolve().parents or ROOT in p.resolve().parents:
                raise DataError('tourgo_release_input_must_be_outside_checkout')
        try:
            if not isinstance(self.receipt_hash,str) or digest_file(self.receipt_path)!=self.receipt_hash:
                raise ValueError('receipt_mismatch')
            receipt=read(self.receipt_path)
            if (receipt.get('kind')!='tourgo_release_readiness' or receipt.get('schema_version')!=1
                    or receipt.get('operating_approval') is not False
                    or receipt.get('implementation_sha256')!=implementation(code)
                    or receipt.get('input_sha256')!=self.ledger_hash
                    or receipt.get('baseline_macro_sha256')!=digest_file(Path(baseline)/'collector_state/macro_archive.json')):
                raise ValueError('stale_or_wrong_receipt')
            ledger=tourgo.from_private_ledger(self.ledger_path,self.ledger_hash,now)
            if self.originals is not None:
                # XLS libraries may print diagnostics containing workbook text.
                # Keep even their warning streams out of public Actions logs.
                with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    originals=tourgo.from_files(self.originals,receipt['expected_original_hashes'],now)
                if (tourgo.validate_ledger(originals,now)!=tourgo.validate_ledger(ledger,now)
                        or any(originals['series'][k][p]['finality']!=o['finality']
                               for k,records in ledger['series'].items() for p,o in records.items())):
                    raise ValueError('tourgo_original_ledger_mismatch')
            verified_profile(ledger,receipt['expected_original_hashes'],receipt['profile'],read(Path(baseline)/'collector_state/macro_archive.json'),now)
            operating_configuration(read(code/'macro_sources.json'),read(code/'operating_policy.json'),now)
            self.receipt=receipt
            return ledger
        except Exception:
            # No raw ledger strings, filenames, paths or parser exception text.
            raise DataError('tourgo_release_input_receipt_or_approval_invalid') from None

    def verify_projection(self, stage_root):
        view=read(Path(stage_root)/'site/data/macro.json');assert_public_contract(view)
        if canonical(public_financial(view))!=self.receipt['financial_projection_sha256']:
            raise DataError('tourgo_release_projection_differs_from_reviewed_staging')


def main():
    p=argparse.ArgumentParser(description='Prepare private TOURGO readiness staging; never push or deploy')
    p.add_argument('--baseline-root',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--profile',choices=['initial','update'],required=True)
    p.add_argument('--ledger',type=Path);p.add_argument('--ledger-sha256')
    for key in INITIAL_HASHES:p.add_argument('--'+key,type=Path)
    p.add_argument('--hash-manifest',type=Path,help='Independently reviewed three original hashes; required for update')
    args=p.parse_args();now=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    try:
        expected=read(args.hash_manifest) if args.hash_manifest else INITIAL_HASHES
        if args.profile=='update' and not args.hash_manifest:p.error('update requires a reviewed hash-manifest')
        if args.ledger:
            if any(getattr(args,k) for k in INITIAL_HASHES):p.error('choose ledger OR original files')
            ledger=tourgo.from_private_ledger(args.ledger,args.ledger_sha256,now)
        else:
            if not all(getattr(args,k) for k in INITIAL_HASHES):p.error('three original files are required')
            ledger=tourgo.from_files({k:getattr(args,k) for k in INITIAL_HASHES},expected,now)
        receipt=stage(ledger,args.baseline_root,args.output,expected,args.profile,now)
        print(json.dumps({k:receipt[k] for k in ('operating_approval','first_period','latest_period','financial_observations','existing_nonfinancial_observations','projected_total_observations')},ensure_ascii=False))
        return 0
    except Exception:
        print('tourgo_readiness_validation_failed; production unchanged')
        return 1


if __name__=='__main__':raise SystemExit(main())
