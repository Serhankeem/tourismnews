"""Offline, hash-checked TOURGO adapter. No network transport or activation.

The original ledger stays in thousand USD; Macro records use exact integer USD.
An operator must supply reviewed original hashes, or the hash of a private ledger.
"""
import copy
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from . import balance

SOURCE = balance.SOURCE
URL = 'https://know.tour.go.kr/stat/koreaTourIncomeDis19Re.do'
PUBLISHER = '한국문화관광연구원 관광지식정보시스템(TOURGO)'
METHOD = 'official_tourgo_xls'
COLLECTION = 'operator_supplied_official_excel_export'
VERIFICATION = 'official_tourgo_file_validated'
IDS = ('kto_tourism_receipts', 'kto_tourism_expenditure')
MAX_INTEGER = 2**53-1


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hashes_valid(hashes):
    return (isinstance(hashes, dict) and set(hashes) == set(balance.KINDS)
            and all(isinstance(v, str) and re.fullmatch('[a-f0-9]{64}', v) for v in hashes.values())
            and len(set(hashes.values())) == 3)


def usd(value, signed=False):
    raw = balance.amount(value, signed)
    if not isinstance(value, int) or isinstance(value, bool) or abs(raw*1000) > MAX_INTEGER:
        raise ValueError('tourgo_unsafe_integer')
    return raw*1000


def validate_ledger(ledger, now):
    if not isinstance(ledger, dict):
        raise ValueError('tourgo_ledger_schema_invalid')
    if ledger.get('data_origin') != 'official_export':
        raise ValueError('synthetic_data_publication_forbidden')
    if ledger.get('unit') != balance.UNIT or not isinstance(ledger.get('revisions'), list):
        raise ValueError('tourgo_ledger_schema_invalid')

    def record(o, kind, period):
        balance.valid_period(period)
        if not isinstance(o, dict) or not isinstance(o.get('provenance'), dict):
            raise ValueError('tourgo_record_provenance_invalid')
        p = o.get('provenance', {})
        if (o.get('period') != period or o.get('unit') != balance.UNIT
                or o.get('finality') not in ('not_stated', 'provisional', 'final')
                or p.get('finality', 'not_stated') != o.get('finality')
                or p.get('data_origin') != 'official_export' or p.get('unit') != balance.UNIT
                or p.get('source_url') != URL or p.get('collection_method') != COLLECTION
                or not hashes_valid(p.get('sha256_by_kind'))):
            raise ValueError('tourgo_record_provenance_invalid')
        if period >= now.strftime('%Y-%m'):
            raise ValueError('balance_future_period')
        for key in ('first_collected_at', 'last_collected_at'):
            if not isinstance(o.get(key), str) or dt.datetime.fromisoformat(o[key]).tzinfo is None:
                raise ValueError('tourgo_record_timestamp_invalid')
        usd(o['value'], kind == 'balance')
        return o['value']

    series = ledger.get('series', {})
    if not isinstance(series,dict) or set(series) != set(balance.KINDS) or any(not isinstance(v,dict) for v in series.values()):
        raise ValueError('balance_bundle_incomplete')
    values = {k: {p: record(o, k, p) for p, o in series[k].items()} for k in balance.KINDS}
    latest = balance.validate_bundle(values)
    if ledger.get('latest_period') != latest:
        raise ValueError('tourgo_latest_period_mismatch')
    for period in values['receipts']:
        proofs = [series[k][period]['provenance']['sha256_by_kind'] for k in balance.KINDS]
        if any(p != proofs[0] for p in proofs):
            raise ValueError('tourgo_cross_vintage_mix_forbidden')
    for revision in ledger['revisions']:
        if not isinstance(revision,dict) or revision.get('kind') not in balance.KINDS:
            raise ValueError('tourgo_revision_invalid')
        for key in ('before', 'after'):
            record(revision[key], revision['kind'], revision['period'])
    return values


def from_files(files, expected_hashes, now, previous=None):
    if set(files) != set(balance.KINDS) or not hashes_valid(expected_hashes):
        raise ValueError('tourgo_expected_hashes_required')
    paths = {k: Path(v) for k, v in files.items()}
    if len({p.resolve() for p in paths.values()}) != 3:
        raise ValueError('tourgo_distinct_originals_required')
    if any(digest(p.read_bytes()) != expected_hashes[k] for k, p in paths.items()):
        raise ValueError('tourgo_original_hash_mismatch')
    if previous:
        validate_ledger(previous, now)
    values = {k: balance.read_xls(p, k, now) for k, p in paths.items()}
    # Detect a file changed during parsing instead of trusting its old digest.
    if any(digest(p.read_bytes()) != expected_hashes[k] for k, p in paths.items()):
        raise ValueError('tourgo_original_hash_mismatch')
    proof = dict(data_origin='official_export', unit=balance.UNIT, finality='not_stated',
                 source_url=URL, collection_method=COLLECTION, sha256_by_kind=expected_hashes)
    ledger = balance.merge_ledger(previous, values, proof, now)
    validate_ledger(ledger, now)
    return ledger


def from_private_ledger(path, expected_hash, now):
    raw = Path(path).read_bytes()
    if not isinstance(expected_hash, str) or not re.fullmatch('[a-f0-9]{64}', expected_hash) or digest(raw) != expected_hash:
        raise ValueError('tourgo_private_ledger_hash_mismatch')
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError('tourgo_duplicate_json_key')
            out[k] = v
        return out
    ledger = json.loads(raw, object_pairs_hook=unique)
    validate_ledger(ledger, now)
    return ledger


def permitted(source, action, today):
    # Not conditional on requires_approval: toggling that flag cannot bypass this.
    return (source.get('id') == SOURCE and source.get('method') == METHOD
            and source.get('requires_approval') is True
            and balance.permitted(source, action, today))


def select_source(config):
    """Explicit alternative mapping, still disabled; does NOT grant permissions."""
    result = copy.deepcopy(config)
    for source in result['sources']:
        if source['id']=='ecos_general_travel':source['enabled']=False
    for i, kind in zip((next(i for i in result['indicators'] if i['id'] == key) for key in IDS), balance.KINDS):
        i.update(source_id=SOURCE, enabled=False, unit='US$', value_kind='money_nonnegative',
                 frequency='M', publisher=PUBLISHER, source_url=URL, definition_url=URL,
                 definition='TOURGO 관광수입(일반여행수입)' if kind == 'receipts' else 'TOURGO 관광지출(일반여행지급)',
                 reason='수동 공식 XLS 통합 준비; 운영 수집·게시 승인 전 미연동')
        i['definition'] += '; 유학연수를 포함한 전체 여행수지와 구분. 원본 천 US$, Macro 원장 US$.'
    return result


def fetch(source, active, ledger, now):
    if not all(permitted(source, a, now.date()) for a in ('collection', 'publication')):
        raise ValueError('tourgo_collection_or_publication_not_approved')
    if ledger is None:
        raise ValueError('tourgo_manual_input_required')
    values = validate_ledger(ledger, now)
    if {i['id'] for i in active} != set(IDS) or len(active) != 2 or any(
            i.get('source_id') != SOURCE or i.get('unit') != 'US$'
            or i.get('value_kind') != 'money_nonnegative' or i.get('frequency') != 'M' for i in active):
        raise ValueError('tourgo_indicator_mapping_invalid')
    records = {}
    for key, kind in zip(IDS, balance.KINDS):
        records[key] = {}
        for period, o in ledger['series'][kind].items():
            proof = o['provenance']
            records[key][period] = dict(value=usd(o['value']), source_value=o['value'], source_unit=balance.UNIT,
                unit='US$', frequency='M', source_id=SOURCE, data_origin='official_export', kind=kind,
                publisher=PUBLISHER, source_url=URL, verification_status=VERIFICATION, collection_method=COLLECTION,
                file_sha256=proof['sha256_by_kind'][kind], bundle_sha256_by_kind=copy.deepcopy(proof['sha256_by_kind']),
                official_balance_value=usd(values['balance'][period], True), finality=o['finality'],
                official_balance_finality=ledger['series']['balance'][period]['finality'],
                release_published_at=None, original_publication_at=None,
                first_collected_at=o['first_collected_at'], last_collected_at=o['last_collected_at'])
    return dict(values={key:{p:o['value'] for p,o in rows.items()} for key,rows in records.items()},
                records=records, reference_period=ledger['latest_period'], source_url=URL,
                unit='US$', frequency='M', method=COLLECTION, release_published_at=None,
                rights='비상업적 이용·TOURGO 출처표시; 운영 승인은 별도',
                import_revisions=copy.deepcopy(ledger['revisions']))


def public_pair(source, archive, today):
    """Revalidate archived provenance AND the official balance before publication."""
    if not permitted(source, 'publication', today):
        return {}
    try:
        saved = {key:archive['indicators'][key] for key in IDS}
        if any(s.get('unit')!='US$' for s in saved.values()):return {}
        periods = set(saved[IDS[0]]['observations'])
        if not periods or set(saved[IDS[1]]['observations']) != periods:
            return {}
        for period in periods:
            balance.valid_period(period)
            if period>=today.strftime('%Y-%m'):return {}
            pair = [saved[key]['observations'][period] for key in IDS]
            for kind, o in zip(balance.KINDS, pair):
                if (o.get('source_id') != SOURCE or o.get('data_origin') != 'official_export'
                        or not isinstance(o.get('value'),int) or isinstance(o.get('value'),bool) or not 0<=o['value']<=MAX_INTEGER
                        or not isinstance(o.get('official_balance_value'),int) or isinstance(o.get('official_balance_value'),bool)
                        or o.get('kind') != kind or o.get('unit') != 'US$' or o.get('frequency') != 'M'
                        or o.get('verification_status') != VERIFICATION or o.get('collection_method') != COLLECTION
                        or o.get('source_url') != URL or o.get('publisher') != PUBLISHER
                        or o.get('source_unit') != balance.UNIT or usd(o.get('source_value')) != o.get('value')
                        or not hashes_valid(o.get('bundle_sha256_by_kind'))
                        or o.get('file_sha256') != o['bundle_sha256_by_kind'][kind]
                        or o.get('finality') not in ('not_stated','provisional','final')):
                    return {}
            r, e = pair
            if (r['bundle_sha256_by_kind'] != e['bundle_sha256_by_kind']
                    or r.get('official_balance_value') != r['value']-e['value']
                    or e.get('official_balance_value') != r['value']-e['value']
                    or r.get('official_balance_finality') not in ('not_stated','provisional','final')
                    or r.get('official_balance_finality') != e.get('official_balance_finality')):
                return {}
        fields={'value','source_value','source_unit','unit','frequency','source_id','data_origin','kind',
                'publisher','source_url','verification_status','collection_method','file_sha256',
                'bundle_sha256_by_kind','official_balance_value','official_balance_finality','finality',
                'release_published_at','original_publication_at','first_collected_at','last_collected_at','revision_status'}
        return {key:{**s,'observations':{p:{k:v for k,v in o.items() if k in fields} for p,o in s['observations'].items()}} for key,s in saved.items()}
    except (ValueError, TypeError, KeyError):
        return {}


def balance_view(pair):
    if not pair:
        return None
    values = {p:o['value']-pair[IDS[1]]['observations'][p]['value'] for p,o in pair[IDS[0]]['observations'].items()}
    def safe_comparisons(period):
        result=balance.monthly_comparisons(values,period,'balance')
        for key in ('mom_change','yoy_change','ytd_value'):
            if result[key] is not None and abs(result[key])>MAX_INTEGER:result[key]=None
        return result
    ordered = [dict(period=p, value=v, unit='US$', finality=pair[IDS[0]]['observations'][p]['official_balance_finality'],
                    comparisons=safe_comparisons(p)) for p,v in sorted(values.items())]
    return dict(source_id=SOURCE, publisher=PUBLISHER, source_url=URL, unit='US$', display_unit='백만 US$',
                verification_status=VERIFICATION, percentage_policy='signed_balance_absolute_changes_only',
                observations=ordered, latest=ordered[-1], official_identity_verified=True)
