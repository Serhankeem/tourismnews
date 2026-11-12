"""Explicit offline import to a private directory OUTSIDE this repository.

No downloader, schedule, public exporter, credentials or synthetic-data promotion.
Requires optional xlrd==2.0.2 for operator-supplied official XLS files.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from .balance import KINDS, UNIT, read_xls, merge_ledger, validate_bundle
from . import tourgo
from ..collector import write_atomic

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for kind in KINDS:
        parser.add_argument('--'+kind, type=Path, required=True)
    parser.add_argument('--private-dir', type=Path, required=True,
                        help='Absolute or relative path outside this repository; output only for imports')
    parser.add_argument('--verify-only', action='store_true',
                        help='Read and validate official XLS files without writing any ledger')
    parser.add_argument('--period-from');parser.add_argument('--period-through')
    args = parser.parse_args()
    source=tourgo.configured_source()
    requested=tourgo.require_range(source,'collection',dict(period_from=args.period_from,period_through=args.period_through))
    directory = args.private_dir.resolve()
    if directory == ROOT or ROOT in directory.parents:
        parser.error('private-dir must be outside the repository (never site/data or collector_state)')
    now = dt.datetime.now(dt.timezone.utc)
    files = {k:getattr(args,k) for k in KINDS}
    if len({p.resolve() for p in files.values()}) != len(KINDS):
        parser.error('three distinct official export files are required')
    values = {k:read_xls(p,k,now) for k,p in files.items()}
    for rows in values.values():tourgo.require_periods(source,'collection',rows,requested)
    latest = validate_bundle(values)
    if args.verify_only:
        print(f'Validation PASS: {len(values["receipts"])} matching months, latest {latest}, identity OK. No files written.')
        return
    provenance = dict(data_origin='official_export',unit=UNIT,finality='not_stated',
                      source_url='https://know.tour.go.kr/stat/koreaTourIncomeDis19Re.do',
                      collection_method='operator_supplied_official_excel_export',
                      sha256_by_kind={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in files.items()})
    path = directory/'tourgo_balance_private.json'
    previous = json.loads(path.read_text()) if path.exists() else None
    if previous:tourgo.require_ledger_scope(source,'collection',previous)
    ledger = merge_ledger(previous,values,provenance,now)
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    write_atomic(path,ledger);path.chmod(0o600)
    print('Private validation complete. Nothing exported to the website.')

if __name__ == '__main__':
    main()
