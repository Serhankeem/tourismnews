"""Private monthly indices/FX adapter using the existing authenticated ECOS client.

Injected responses are replay evidence, never proof of production authentication.
No sample-key fallback, public records, automatic approvals, or raw error logging.
"""
import datetime as dt
import re
from . import ecos
from .model import months, valid_period, decimal_value

METHOD = 'official_ecos_decimal_api'


def reviewed(source):
    review = source.get('collection_review', {})
    return review.get('status') == 'verified' and ecos._evidence(review)


def definition(item):
    if (item.get('frequency') != 'M' or item.get('value_kind') not in ('decimal_index', 'decimal_exchange_rate')
            or item.get('storage') != 'decimal_string' or not re.fullmatch(r'\d{3}[A-Z]\d{3}', item.get('stat_code', ''))
            or not 1 <= len(item.get('item_codes', [])) <= 4
            or len(item.get('item_names', [])) != len(item['item_codes'])
            or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,20}', code) for code in item['item_codes'])):
        raise ValueError('ecos_decimal_definition_invalid')
    if item['value_kind'] == 'decimal_index':
        if item.get('unit') != '2020=100' or item.get('base_year') != 2020:
            raise ValueError('ecos_decimal_base_year_invalid')
    elif item.get('unit') != '원' or item.get('base_year') is not None:
        raise ValueError('ecos_decimal_unit_invalid')


def parse(rows, item, start, end, now, hashes, mode):
    definition(item)
    records = {}
    for row in rows:
        period = ecos.period(row.get('TIME'))
        if (period in records or not start <= period <= end or period >= now.strftime('%Y-%m')
                or row.get('STAT_CODE') != item['stat_code'] or row.get('UNIT_NAME') != item['unit']):
            raise ValueError('ecos_decimal_series_mismatch')
        for n in range(1, 5):
            code = item['item_codes'][n-1] if n <= len(item['item_codes']) else None
            name = item['item_names'][n-1] if n <= len(item['item_names']) else None
            if row.get(f'ITEM_CODE{n}') != code or row.get(f'ITEM_NAME{n}') != name:
                raise ValueError('ecos_decimal_selector_mismatch')
        value = decimal_value(row.get('DATA_VALUE'))
        records[period] = dict(value=value, source_value=row['DATA_VALUE'],
            raw_record={k: row.get(k) for k in ('STAT_CODE','ITEM_CODE1','ITEM_CODE2','ITEM_CODE3','ITEM_CODE4','UNIT_NAME','TIME','DATA_VALUE')},
            unit=item['unit'], frequency='M', base_year=item['base_year'], stat_code=item['stat_code'],
            item_codes=list(item['item_codes']), publisher=item['publisher'], provider='한국은행 ECOS',
            source_url=ecos.BASE, collection_method=METHOD, collection_mode=mode,
            authentication_verified=mode == 'authenticated_api',
            release_published_at=None, original_publication_at=None, finality='not_stated',
            finality_basis='API does not supply observation finality; no inferred confirmation',
            crosscheck_status=item['crosscheck']['status'], publication_status='blocked', response_sha256=list(hashes))
    if not records or set(records) != set(months(start, end)):
        raise ValueError('ecos_decimal_missing_months')
    return records


def fetch(source, items, client=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if not source.get('enabled') or not reviewed(source):
        raise ValueError('ecos_decimal_collection_not_approved')
    if not items or any(not i.get('enabled') or i.get('source_id') != source['id'] for i in items):
        raise ValueError('ecos_decimal_indicators_disabled')
    client = client if client is not None else ecos.Client()
    mode = 'authenticated_api' if isinstance(client, ecos.Client) else 'injected_replay_unverified_auth'
    start = valid_period(source['start_period'])
    latest = now.strftime('%Y-%m')
    tables = client.rows('StatisticTableList', source['stat_code'])
    if (len(tables) != 1 or tables[0].get('STAT_CODE') != source['stat_code']
            or tables[0].get('SRCH_YN') != 'Y' or 'M' not in tables[0].get('CYCLE', '').split(',')):
        raise ValueError('ecos_decimal_table_mismatch')
    metadata = client.rows('StatisticItemList', source['stat_code'])
    lookup = {}
    for row in metadata:
        if row.get('CYCLE') == 'M':
            key = row.get('GRP_CODE'), row.get('ITEM_CODE')
            if key in lookup:
                raise ValueError('ecos_decimal_duplicate_metadata')
            lookup[key] = row
    result = {}
    for item in items:
        definition(item)
        if item['stat_code'] != source['stat_code']:
            raise ValueError('ecos_decimal_table_mismatch')
        ends = []
        for n, code in enumerate(item['item_codes'], 1):
            m = lookup.get((f'Group{n}', code), {})
            if (m.get('STAT_CODE') != source['stat_code'] or m.get('ITEM_NAME') != item['item_names'][n-1]
                    or (m.get('UNIT_NAME') != item['unit'] if n == 1 else m.get('UNIT_NAME') not in (None, item['unit']))
                    or ecos.period(m.get('START_TIME')) > start):
                raise ValueError('ecos_decimal_metadata_mismatch')
            endpoint = ecos.period(m.get('END_TIME'))
            if endpoint >= latest:
                raise ValueError('ecos_decimal_latest_month_invalid')
            ends.append(endpoint)
        end = min(ends)
        if end < start or end >= latest:
            raise ValueError('ecos_decimal_latest_month_invalid')
        rows = client.rows('StatisticSearch', source['stat_code'], 'M', start.replace('-',''), end.replace('-',''), *item['item_codes'])
        hashes = list(client.response_hashes)
        result[item['id']] = parse(rows, item, start, end, now, hashes, mode)
    return dict(records=result, reference_period=max(max(x) for x in result.values()),
                collection_mode=mode, authentication_verified=mode=='authenticated_api',
                response_sha256=list(client.response_hashes))
