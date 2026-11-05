"""Official ECOS adapter. Disabled until a reviewed, evidence-bound mapping exists.

No inferred codes, sample-key fallback, internal web APIs, redirects or raw error
messages. The API key is used only in a server-side HTTPS request and never kept
in provenance. Tests inject synthetic responses; these are not official statistics.
"""
import datetime as dt
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from decimal import Decimal, InvalidOperation, localcontext
from .model import months, valid_period
from ..discovery import NoRedirect

BASE = 'https://ecos.bok.or.kr/api/'
AGENT = 'currentourism-macro/0.6 (+https://github.com/Serhankeem/tourismnews; official Open API)'
IDS = ('kto_tourism_receipts', 'kto_tourism_expenditure')
FACTORS = {'달러': 1, 'US달러': 1, '천달러': 1000, '백만달러': 1000000}
MAX_INTEGER = 2**53 - 1  # Exact integer transport through the existing JSON/JS ledger.
SERVICES = {'StatisticTableList', 'StatisticItemList', 'StatisticSearch'}


class EcosError(ValueError):
    """Only fixed, credential-free error identifiers may cross the API boundary."""


def _evidence(row):
    try:
        p = urllib.parse.urlsplit(row['evidence_url'])
        dt.date.fromisoformat(row['verified_at'])
        return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password
    except (KeyError, ValueError, TypeError):
        return False


def mapping(source):
    m = source.get('mapping', {})
    if m.get('status') != 'verified' or not _evidence(m):
        raise EcosError('ecos_mapping_pending')
    if (not re.fullmatch(r'\d{3}[A-Z]\d{3}', str(m.get('stat_code', '')))
            or not m.get('stat_name') or m.get('frequency') != 'M'
            or m.get('unit_name') not in FACTORS or set(m.get('series', {})) != set(IDS)):
        raise EcosError('ecos_mapping_invalid')
    for index, key in enumerate(IDS):
        selectors = m['series'][key].get('selectors', [])
        if not 1 <= len(selectors) <= 4:
            raise EcosError('ecos_selectors_invalid')
        for slot, selector in enumerate(selectors, 1):
            path = selector.get('path', [])
            if (selector.get('group') != f'Group{slot}' or not path
                    or not all(isinstance(n, dict) and re.fullmatch(r'[A-Za-z0-9_.-]{1,20}', str(n.get('code', ''))) and n.get('name') for n in path)
                    or len({n['code'] for n in path}) != len(path)):
                raise EcosError('ecos_selectors_invalid')
        names = '/'.join(n['name'] for n in selectors[0]['path'])
        if '일반여행' not in names or ('수입' if index == 0 else '지급') not in names or '유학' in names:
            raise EcosError('ecos_general_travel_definition_mismatch')
    a, b = (m['series'][key]['selectors'] for key in IDS)
    if [s['path'][-1]['code'] for s in a] == [s['path'][-1]['code'] for s in b]:
        raise EcosError('ecos_receipts_expenditure_same_item')
    return m


def publishable(source):
    """Existing stored records also need current mapping/rights/crosscheck review."""
    try:
        mapping(source)
        return all(source.get(k, {}).get('status') == 'verified' and _evidence(source[k])
                   for k in ('rights_review', 'crosscheck'))
    except (ValueError, TypeError, KeyError):
        return False


def public_records(source, item, saved):
    """Fail closed on stale/wrong-series stored provenance; keep the private ledger."""
    if not publishable(source) or item.get('value_kind') != 'money_nonnegative' or item.get('unit') != 'US$':
        return {}
    try:
        m = mapping(source)
        codes = [s['path'][-1]['code'] for s in m['series'][item['id']]['selectors']]
        if saved.get('unit') != 'US$' or saved.get('definition') != item['definition']:
            return {}
        for p, o in saved.get('observations', {}).items():
            valid_period(p)
            if (not isinstance(o.get('value'),int) or isinstance(o.get('value'),bool) or o.get('unit') != 'US$' or o.get('frequency') != 'M'
                    or o.get('verification_status') != 'official_api_validated'
                    or o.get('collection_method') != 'official_ecos_api'
                    or o.get('source_url') != BASE or o.get('stat_code') != m['stat_code']
                    or o.get('item_codes') != codes or o.get('source_unit') != m['unit_name']
                    or amount(o.get('source_value'), o.get('source_unit')) != o.get('value')
                    or o.get('finality') != 'not_stated'
                    or not o.get('response_sha256')
                    or any(not re.fullmatch(r'[a-f0-9]{64}', str(h)) for h in o['response_sha256'])):
                return {}
        return saved
    except (ValueError, TypeError, KeyError):
        return {}


def amount(raw, unit):
    if unit not in FACTORS or not isinstance(raw, str) or len(raw)>64 or not re.fullmatch(r'\d+(?:\.\d+)?', raw):
        raise EcosError('ecos_unit_or_amount_invalid')
    try:
        with localcontext() as ctx:
            ctx.prec = max(28, len(raw)+8)
            value = Decimal(raw) * FACTORS[unit]
    except InvalidOperation:
        raise EcosError('ecos_amount_invalid') from None
    if not value.is_finite() or value != value.to_integral_value() or not 0 <= value <= MAX_INTEGER:
        raise EcosError('ecos_amount_precision_or_range_invalid')
    return int(value)


def period(raw):
    if not isinstance(raw, str) or not re.fullmatch(r'\d{6}', raw):
        raise EcosError('ecos_month_invalid')
    return valid_period(raw[:4] + '-' + raw[4:])


class Client:
    def __init__(self, key=None, timeout=25):
        self._key = os.environ.get('ECOS_API_KEY', '') if key is None else key
        if not self._key:
            raise EcosError('ecos_auth_required')
        if self._key.lower() == 'sample' or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', self._key):
            raise EcosError('ecos_auth_invalid')
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect)
        self.rules = None
        self.last_request = 0
        self.response_hashes = []

    def _read(self, url):
        if self.rules is None:
            try:
                with self.opener.open(urllib.request.Request('https://ecos.bok.or.kr/robots.txt', headers={'User-Agent': AGENT}), timeout=self.timeout) as r:
                    raw = r.read(200001)
                if len(raw) > 200000 or b'<html' in raw[:1000].lower():
                    raise EcosError('ecos_robots_invalid')
                self.rules = urllib.robotparser.RobotFileParser()
                self.rules.parse(raw.decode('utf-8').splitlines())
            except EcosError:
                raise
            except Exception:
                raise EcosError('ecos_robots_unavailable') from None
        if not self.rules.can_fetch(AGENT, url):
            raise EcosError('ecos_robots_disallowed')
        delay = max(1, self.rules.crawl_delay(AGENT) or self.rules.crawl_delay('*') or 0)
        rate = self.rules.request_rate(AGENT) or self.rules.request_rate('*')
        if rate and rate.requests:
            delay = max(delay, rate.seconds / rate.requests)
        if delay > 10:
            raise EcosError('ecos_deferred_fetch_required')
        for attempt in range(2):
            time.sleep(max(0, delay - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                with self.opener.open(urllib.request.Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/json'}), timeout=self.timeout) as r:
                    raw = r.read(4000001)
                if len(raw) > 4000000:
                    raise EcosError('ecos_response_too_large')
                return raw
            except urllib.error.HTTPError as exc:
                # No redirects (in particular no key-bearing HTTP downgrade),
                # auth retries, raw provider messages or exception URL logging.
                code = exc.code
                if code in (502, 503, 504) and attempt == 0:
                    time.sleep(1)
                    continue
                if code in (401, 403):
                    raise EcosError('ecos_auth_or_access_denied') from None
                if code == 429:
                    raise EcosError('ecos_rate_limited') from None
                if 300 <= code < 400:
                    raise EcosError('ecos_redirect_blocked') from None
                raise EcosError('ecos_http_' + str(code)) from None
            except EcosError:
                raise
            except Exception:
                raise EcosError('ecos_network_or_tls_failure') from None

    def rows(self, service, *parameters):
        if service not in SERVICES or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,40}', str(p)) for p in parameters):
            raise EcosError('ecos_request_not_allowlisted')
        rows = []
        total = None
        # A single table/item catalogue or 2021+ monthly series fits well below
        # this limit. Never silently accept a truncated response as a full series.
        for start in range(1, 5001, 1000):
            url = BASE + '/'.join([service, self._key, 'json', 'kr', str(start), str(start+999), *map(str, parameters)])
            raw = self._read(url)
            try:
                doc = json.loads(raw)
            except (ValueError, UnicodeError):
                raise EcosError('ecos_json_invalid') from None
            if not isinstance(doc, dict):
                raise EcosError('ecos_response_invalid')
            result = doc.get('RESULT', {})
            if isinstance(result, dict) and result.get('CODE'):
                code = result['CODE']
                if code == 'INFO-200':
                    if rows:
                        raise EcosError('ecos_pagination_incomplete')
                    return []
                errors = {'INFO-100': 'ecos_auth_invalid', 'ERROR-602': 'ecos_rate_limited',
                          'ERROR-400': 'ecos_query_timeout', 'ERROR-101': 'ecos_period_format_invalid'}
                raise EcosError(errors.get(code, 'ecos_api_error'))
            if self._key.encode() in raw:
                raise EcosError('ecos_unexpected_credential_in_response')
            data = doc.get(service)
            if not isinstance(data, dict) or not isinstance(data.get('row'), list):
                raise EcosError('ecos_response_invalid')
            n = data.get('list_total_count')
            if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 5000 or (total is not None and total != n):
                raise EcosError('ecos_total_or_pagination_invalid')
            total = n
            page = data['row']
            if len(page) != min(1000, max(0, total - start + 1)) or any(not isinstance(r, dict) for r in page):
                raise EcosError('ecos_pagination_incomplete')
            self.response_hashes.append(hashlib.sha256(raw).hexdigest())
            rows.extend(page)
            if len(rows) == total:
                return rows
        raise EcosError('ecos_row_limit')


def validate_metadata(m, tables, items):
    selected = [r for r in tables if r.get('STAT_CODE') == m['stat_code']]
    if (len(selected) != 1 or selected[0].get('STAT_NAME') != m['stat_name']
            or selected[0].get('SRCH_YN') != 'Y' or 'M' not in selected[0].get('CYCLE', '').split(',')):
        raise EcosError('ecos_table_mismatch')
    lookup = {}
    for row in items:
        if row.get('CYCLE') != 'M':
            continue
        key = (row.get('GRP_CODE'), row.get('ITEM_CODE'))
        if key in lookup:
            raise EcosError('ecos_duplicate_item_metadata')
        lookup[key] = row
    availability = {}
    for key in IDS:
        for selector in m['series'][key]['selectors']:
            parent = None
            for node in selector['path']:
                row = lookup.get((selector['group'], node['code']))
                if (not row or row.get('STAT_CODE') != m['stat_code'] or row.get('STAT_NAME') != m['stat_name']
                        or row.get('ITEM_NAME') != node['name'] or (row.get('P_ITEM_CODE') or None) != parent):
                    raise EcosError('ecos_item_hierarchy_mismatch')
                parent = node['code']
            if row.get('UNIT_NAME') != m['unit_name']:
                raise EcosError('ecos_unit_mismatch')
            start, end = period(row.get('START_TIME')), period(row.get('END_TIME'))
            if start > end:
                raise EcosError('ecos_coverage_invalid')
            availability.setdefault(key, []).append((start, end))
    return {k: (max(s for s, e in ranges), min(e for s, e in ranges)) for k, ranges in availability.items()}


def parse_series(rows, m, key, start, end, now):
    selectors = m['series'][key]['selectors']
    values = {}
    records = {}
    missing = []
    for row in rows:
        if row.get('STAT_CODE') != m['stat_code'] or row.get('STAT_NAME') != m['stat_name'] or row.get('UNIT_NAME') != m['unit_name']:
            raise EcosError('ecos_stat_or_unit_mismatch')
        for slot in range(1, 5):
            expected = selectors[slot-1]['path'][-1] if slot <= len(selectors) else {'code': None, 'name': None}
            if (row.get('ITEM_CODE'+str(slot)) or None) != expected['code'] or (row.get('ITEM_NAME'+str(slot)) or None) != expected['name']:
                raise EcosError('ecos_series_or_direction_mismatch')
        p = period(row.get('TIME'))
        if p < start or p > end or p >= now.strftime('%Y-%m') or p in records or p in missing:
            raise EcosError('ecos_future_duplicate_or_outside_period')
        raw = row.get('DATA_VALUE')
        if raw is None or raw == '':
            missing.append(p)
            continue
        value = amount(raw, m['unit_name'])
        values[p] = value
        records[p] = dict(value=value, source_value=raw, source_unit=m['unit_name'],
                          stat_code=m['stat_code'], stat_name=m['stat_name'],
                          item_codes=[s['path'][-1]['code'] for s in selectors],
                          item_names=[s['path'][-1]['name'] for s in selectors],
                          verification_status='official_api_validated', finality='not_stated')
    absent = sorted(set(months(start, end)) - set(values))
    return values, records, absent


def fetch(source, indicators, client, now):
    m = mapping(source)
    if (source.get('id')!='ecos_general_travel' or len(indicators)!=2 or set(i['id'] for i in indicators) != set(IDS) or any(i.get('unit') != 'US$' or i.get('frequency') != 'M' or i.get('value_kind') != 'money_nonnegative' for i in indicators)):
        raise EcosError('ecos_indicator_definition_invalid')
    client = client or Client()
    tables = client.rows('StatisticTableList', m['stat_code'])
    items = client.rows('StatisticItemList', m['stat_code'])
    availability = validate_metadata(m, tables, items)
    last_month = (now.replace(day=1) - dt.timedelta(days=1)).strftime('%Y-%m')
    values, records, missing = {}, {}, {}
    for key in IDS:
        first, last = availability[key]
        start, end = max(first, valid_period(source['start_period'])), min(last, last_month)
        if start > end:
            raise EcosError('ecos_no_released_months')
        codes = [s['path'][-1]['code'] for s in m['series'][key]['selectors']]
        rows = client.rows('StatisticSearch', m['stat_code'], 'M', start.replace('-', ''), end.replace('-', ''), *codes)
        values[key], records[key], missing[key] = parse_series(rows, m, key, start, end, now)
        if not values[key]:
            raise EcosError('ecos_no_data')
    # Each series keeps its own latest period; never force-fill the shorter one.
    return dict(reference_period=max(max(v) for v in values.values()), values=values, records=records,
                source_url=BASE, release_published_at=None, original_publication_at=None,
                unit='US$', frequency='M', method='official_ecos_api', finality='not_stated',
                rights=source.get('rights_review', {}), missing_periods=missing,
                metadata_coverage={k: list(v) for k, v in availability.items()},
                response_sha256=list(client.response_hashes), stat_code=m['stat_code'])


def balance(receipts, expenditure):
    """Internal identity in exact US dollars; never a nonnegative observation."""
    if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= MAX_INTEGER for v in (receipts, expenditure)):
        raise EcosError('ecos_balance_inputs_invalid')
    return {'value': receipts-expenditure, 'unit': 'US$', 'percentage_policy': 'absolute_changes_only'}


def crosscheck(values, official, tolerance='0'):
    """Compare operator-verified KTO evidence; do not conflate different vintages.

    `official`: period, receipts/expenditure raw strings, unit_name,
    source_url, release_published_at. No network or publication side effects.
    """
    p = valid_period(official['period'])
    if not official.get('source_url', '').startswith('https://datalab.visitkorea.or.kr/') or not official.get('release_published_at'):
        raise EcosError('ecos_crosscheck_evidence_missing')
    limit = Decimal(tolerance)
    if not limit.is_finite() or limit < 0:
        raise EcosError('ecos_crosscheck_tolerance_invalid')
    result = {'period': p, 'unit': 'US$', 'source_url': official['source_url'],
              'release_published_at': official['release_published_at'], 'tolerance_usd': str(limit), 'series': {}}
    for key, kind in zip(IDS, ('receipts', 'expenditure')):
        other = amount(official[kind], official['unit_name'])
        current = values.get(key, {}).get(p)
        result['series'][key] = dict(ecos_value=current, kto_value=other,
            difference=None if current is None else current-other,
            status='missing' if current is None else 'match' if abs(current-other) <= limit else 'vintage_or_value_difference_requires_review')
    return result


def main():
    """Private preflight only. Does not write/push any operational files."""
    import argparse
    from pathlib import Path
    from ..collector import write_atomic
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='ECOS private official-metadata/data preflight (key from ECOS_API_KEY only)')
    parser.add_argument('mode', choices=('metadata', 'validate'))
    parser.add_argument('--table-code', help='A code read from the official catalogue, never a guessed code')
    parser.add_argument('--private-dir', required=True, type=Path)
    args = parser.parse_args()
    target = args.private_dir.resolve()
    if target == root or root in target.parents:
        parser.error('private-dir must be outside this repository')
    if args.table_code and not re.fullmatch(r'\d{3}[A-Z]\d{3}', args.table_code):
        parser.error('invalid official table-code syntax')
    try:
        client = Client()
        if args.mode == 'metadata':
            tables = client.rows('StatisticTableList', *([args.table_code] if args.table_code else []))
            result = dict(mode='official_ecos_metadata', checked_at=dt.datetime.now(dt.timezone.utc).isoformat(), tables=tables)
            if args.table_code:
                result['items'] = client.rows('StatisticItemList', args.table_code)
            result['response_sha256'] = client.response_hashes
        else:
            config = json.loads((root/'macro_sources.json').read_text())
            selected = next(s for s in config['sources'] if s['id'] == 'ecos_general_travel')
            if args.table_code and selected.get('mapping', {}).get('stat_code') != args.table_code:
                raise EcosError('ecos_table_mismatch')
            result = fetch(selected, [i for i in config['indicators'] if i['id'] in IDS], client, dt.datetime.now(dt.timezone(dt.timedelta(hours=9))))
            result['mode'] = 'official_ecos_private_validation'
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = target/('ecos-'+args.mode+'.json')
        write_atomic(path, result)
        path.chmod(0o600)
        print('Private ECOS preflight saved. No public data, Git ref or deployment changed.')
        return 0
    except EcosError as exc:
        print(str(exc))  # Only fixed error IDs, never a URL/key/provider message.
        return 1
    except Exception:
        print('ecos_preflight_failed')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
