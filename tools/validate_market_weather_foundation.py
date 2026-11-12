"""Offline Step 3 replay. Never downloads or activates operational configuration.

Use: python -m tools.validate_market_weather_foundation --evidence-dir ... --work ...
Real API response bodies remain outside git; metadata transport is simulated.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
from src.macro import decimal_series, ecos_decimal
from src.macro.engine import collect
from src.macro.model import decimal_comparisons, decimal_value

ROOT = Path(__file__).resolve().parents[1]
NOW = dt.datetime(2026, 11, 12, 12, tzinfo=dt.timezone.utc)


def private_config():
    config = json.loads((ROOT/'macro_sources.json').read_text())
    return dict(sources=[s for s in config['sources'] if s.get('method')==ecos_decimal.METHOD],
                indicators=[i for i in config['indicators'] if i.get('value_kind') in decimal_series.KINDS])


def replay_config(config):
    """In-memory test activation only; no rights/publication approvals changed."""
    config = copy.deepcopy(config)
    for source in config['sources']:
        source['enabled'] = True
        source['collection_review'] = dict(status='verified', evidence_url='https://example.org/offline-test-only', verified_at='2026-11-12')
    for item in config['indicators']:
        item['enabled'] = True
    return config


class Replay:
    """Offline metadata simulation + provided rows, explicitly unverified auth."""
    def __init__(self, config, rows, hashes=None):
        self.config, self.data = config, rows
        self.response_hashes = hashes or ['0'*64]

    def rows(self, service, table, *args):
        items = [i for i in self.config['indicators'] if i['stat_code']==table]
        if service == 'StatisticTableList':
            return [dict(STAT_CODE=table, SRCH_YN='Y', CYCLE='M')]
        if service == 'StatisticItemList':
            records = {}
            for item in items:
                data = self.data[item['id']]
                for n, (code, name) in enumerate(zip(item['item_codes'], item['item_names']), 1):
                    records[(n, code)] = dict(STAT_CODE=table, GRP_CODE=f'Group{n}', ITEM_CODE=code,
                        ITEM_NAME=name, UNIT_NAME=item['unit'] if n==1 else None, CYCLE='M', START_TIME='202101',
                        END_TIME=max(r['TIME'] for r in data))
            return list(records.values())
        if service == 'StatisticSearch':
            item = next(i for i in items if i['item_codes']==list(args[3:]))
            return copy.deepcopy(self.data[item['id']])
        raise AssertionError('unexpected offline service')


def load_evidence(folder, config):
    folder = Path(folder)
    manifest = json.loads((folder/'manifest.json').read_text())
    data, response_hashes = {}, []
    for item in config['indicators']:
        key = item['evidence_key']; rows = []
        for path in sorted((folder/'responses').glob(key+'-[0-9][0-9][0-9].json')):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            meta = json.loads(path.with_suffix('.meta.json').read_text())
            relative = str(path.relative_to(folder))
            if digest != meta['sha256'] or digest != manifest['files'][relative] or meta['http']!=200:
                raise ValueError('original_response_hash_mismatch')
            rows.extend(json.loads(path.read_text())['StatisticSearch']['row'])
            response_hashes.append(digest)
        aggregate = folder/(key+'.json')
        if hashlib.sha256(aggregate.read_bytes()).hexdigest()!=manifest['files'][key+'.json']:
            raise ValueError('aggregate_hash_mismatch')
        if rows != json.loads(aggregate.read_text()):
            raise ValueError('aggregate_response_mismatch')
        data[item['id']] = rows
    if len(response_hashes)!=63 or sum(map(len,data.values()))!=628:
        raise ValueError('step3_evidence_count_mismatch')
    return data, response_hashes


def run(evidence, work):
    work = Path(work).resolve()
    # No state/data directory inside checkout; never overwrite an earlier run.
    if work == ROOT or ROOT in work.parents or work.exists():
        raise ValueError('fresh_external_isolation_directory_required')
    config = replay_config(private_config())
    rows, hashes = load_evidence(evidence, config)
    client = Replay(config, rows, hashes)
    health = collect(config, work/'data', work/'state', ecos_client=client, now=NOW, force=True)
    if health['successful_sources']!=3 or health['new_observations']!=628:
        raise AssertionError(health)
    archive_path = work/'state/macro_archive.json'
    archive = json.loads(archive_path.read_text())
    results = []; total_yoy = 0
    for item in config['indicators']:
        obs = archive['decimal_indicators'][item['id']]['observations']
        assert all(obs[r['TIME'][:4]+'-'+r['TIME'][4:]]['value']==decimal_value(r['DATA_VALUE']) for r in rows[item['id']])
        changes = [dict(period=p,**decimal_comparisons(obs,p)) for p in sorted(obs)]
        count = sum(c['yoy_pct'] is not None for c in changes); total_yoy+=count
        # Independent Step 3 research rates, rounded only at comparison boundary.
        from decimal import Decimal, ROUND_HALF_UP
        reference_path = Path(evidence)/(item['evidence_key']+'-yoy.json')
        manifest = json.loads((Path(evidence)/'manifest.json').read_text())
        if hashlib.sha256(reference_path.read_bytes()).hexdigest()!=manifest['files'][reference_path.name]:
            raise ValueError('research_yoy_hash_mismatch')
        reference = json.loads(reference_path.read_text())
        # The research file format is checked below before accepting rates.
        expected = {r['month'][:4]+'-'+r['month'][4:]:r for r in reference}
        for change in changes:
            if change['yoy_pct'] is not None:
                value = expected[change['period']]['yoy_pct']
                assert change['yoy_pct']==format(Decimal(str(value)).quantize(Decimal('0.000001'),rounding=ROUND_HALF_UP),'f')
        results.append(dict(id=item['id'],observations=len(obs),yoy_observations=count,
            first_period=min(obs),latest_period=max(obs),unit=item['unit'],base_year=item['base_year']))
    assert total_yoy==520
    again = collect(config,work/'data',work/'state',ecos_client=client,now=NOW+dt.timedelta(days=1),force=True)
    assert again['new_observations']==0 and again['unchanged_observations']==628
    repeated = json.loads(archive_path.read_text())
    assert all(not s['revisions'] for s in repeated['decimal_indicators'].values())
    first = config['indicators'][0]; row = client.data[first['id']][0]
    row['DATA_VALUE'] = str(Decimal(row['DATA_VALUE'])+Decimal('0.1'))
    corrected = collect(config,work/'data',work/'state',ecos_client=client,now=NOW+dt.timedelta(days=2),force=True)
    assert corrected['value_corrections']==1
    changed = json.loads(archive_path.read_text())
    revision = changed['decimal_indicators'][first['id']]['revisions'][0]
    assert revision['before']==repeated['decimal_indicators'][first['id']]['observations']['2021-01']
    before = {p:p.read_bytes() for p in (archive_path,work/'data/macro.json')}
    class Broken:
        def rows(self,*args):raise ValueError('SYNTHETICKEYDONOTLOG')
    failed = collect(config,work/'data',work/'state',ecos_client=Broken(),now=NOW+dt.timedelta(days=3),force=True)
    assert failed['successful_sources']==0 and all(p.read_bytes()==v for p,v in before.items())
    assert 'SYNTHETICKEYDONOTLOG' not in json.dumps(failed)
    assert json.loads((work/'data/macro.json').read_text())['indicators']==[]
    report = dict(series=results,observations=628,yoy_observations=520,response_files=63,
        response_sha256=hashes,exact_decimal_reproduction=True,idempotence=True,correction_vintage_retained=True,
        failure_preserves_archive_and_public=True,public_indicators=0,
        authenticated_production_collection_verified=False,metadata_transport='simulated; observation responses are original Step 3 bodies',
        full_primary_crossvalidation_complete=False,rights_review_complete=False)
    (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir',required=True,type=Path)
    parser.add_argument('--work',required=True,type=Path)
    args=parser.parse_args()
    result=run(args.evidence_dir,args.work)
    print(json.dumps({k:v for k,v in result.items() if k not in ('series','response_sha256')},ensure_ascii=False))
