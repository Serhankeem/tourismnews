"""Explicit offline integration preview OUTSIDE the checkout. Never a deploy step."""
import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
from . import tourgo
from .balance import KINDS
from .engine import collect
from ..collector import write_atomic

ROOT = Path(__file__).resolve().parents[2]


def preview(ledger, output, baseline_root, now):
    tourgo.require_ledger_scope(tourgo.configured_source(),'collection',ledger)
    tourgo.validate_ledger(ledger, now)
    output, baseline_root = Path(output).resolve(), Path(baseline_root).resolve()
    if output == ROOT or ROOT in output.parents or output in ROOT.parents or output.exists():
        raise ValueError('tourgo_preview_requires_new_directory_outside_repository')
    # No input is ever fetched. The baseline must be an explicit local snapshot.
    archive = baseline_root/'collector_state/macro_archive.json'
    if not archive.is_file():
        raise ValueError('tourgo_preview_baseline_archive_required')
    config = tourgo.select_source(json.loads((ROOT/'macro_sources.json').read_text()))
    source = next(s for s in config['sources'] if s['id'] == tourgo.SOURCE)
    source['enabled'] = True
    for action in ('collection','publication'):
        source['approval'][action] = dict(tourgo.approved_range(source,'collection'),approved=True, scope='general_travel_monthly',
            evidence_ref='isolated-preview-only-not-production-approval',valid_from=now.date().isoformat())
    for i in config['indicators']:
        if i['source_id'] == tourgo.SOURCE:i['enabled'] = True
    output.mkdir(parents=True, mode=0o700)
    site, state = output/'site', output/'private'
    shutil.copytree(ROOT/'site', site, ignore=shutil.ignore_patterns('data'))
    shutil.copytree(baseline_root/'site/data', site/'data')
    state.mkdir(mode=0o700)
    shutil.copyfile(archive, state/'macro_archive.json')
    # A persistent label accompanies all preview pages, including direct hashes.
    index = site/'index.html'
    index.write_text(index.read_text().replace('<body>', '<body><div role="status" style="padding:12px;background:#fff2b3;color:#663900;text-align:center;font-weight:700">격리 미리보기 · 운영 게시 아님 · TOURGO 수동 파일 통합 검증</div>', 1))
    result = collect(config,site/'data',state,now=now,force=True,tourgo_ledger=ledger,only_sources={tourgo.SOURCE})
    if result['status'] not in ('ok','partial') or not result['successful_sources']:
        raise ValueError('tourgo_preview_integration_failed')
    manifest = dict(mode='isolated_offline_preview_not_for_deployment',data_origin='official_export',
                    latest_period=ledger['latest_period'],months=len(ledger['series']['receipts']),
                    production_approvals_changed=False,network_calls=False,status=result['status'])
    write_atomic(output/'preview.json',manifest)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True, help='New private directory outside repository')
    p.add_argument('--baseline-root', type=Path, default=ROOT, help='Read-only local snapshot containing site/data and collector_state')
    p.add_argument('--period-from');p.add_argument('--period-through')
    p.add_argument('--ledger', type=Path)
    p.add_argument('--ledger-sha256', help='Independently reviewed private ledger file hash')
    for kind in KINDS:p.add_argument('--'+kind,type=Path)
    p.add_argument('--hash-manifest', type=Path, help='Reviewed JSON mapping receipts/expenditure/balance to original SHA-256')
    args = p.parse_args()
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    try:
        declared=None if args.period_from is None and args.period_through is None else dict(period_from=args.period_from,period_through=args.period_through)
        if args.ledger:
            if args.hash_manifest or any(getattr(args,k) for k in KINDS):
                p.error('choose a private ledger OR three original XLS files')
            ledger = tourgo.from_private_ledger(args.ledger,args.ledger_sha256,now,requested_range=declared)
        else:
            if not args.hash_manifest or not all(getattr(args,k) for k in KINDS) or args.ledger_sha256:
                p.error('three original XLS files and reviewed hash-manifest are required')
            ledger = tourgo.from_files({k:getattr(args,k) for k in KINDS},json.loads(args.hash_manifest.read_text()),now,requested_range=declared)
        manifest = preview(ledger,args.output,args.baseline_root,now)
        print(json.dumps(manifest,ensure_ascii=False))
        return 0
    except ImportError:
        print('tourgo_xlrd_dependency_required; install xlrd==2.0.2; no production changes')
        return 1
    except Exception:
        # Parser exceptions may contain excerpts from a private original file.
        # Fail explicitly without reflecting file contents or caller paths.
        print('tourgo_preview_validation_failed; no production data or approvals changed')
        return 1


if __name__ == '__main__':raise SystemExit(main())
