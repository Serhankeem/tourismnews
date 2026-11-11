"""Preparation-only general-travel ledger. No network calls or public writes.

Rows are read from an operator-supplied official export; synthetic fixtures must
never be promoted. Permission to download and permission to publish are separate.
"""
import copy
import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from .model import valid_period, month_before, comparisons

UNIT = '천 US$'
KINDS = ('receipts', 'expenditure', 'balance')
SOURCE = 'tourgo_tourism_balance'

def permitted(source, action, today=None):
    approval = source.get('approval', {})
    grant = approval.get(action, {})
    today = today or dt.date.today()
    try:
        since = dt.date.fromisoformat(grant['valid_from'])
        until = dt.date.fromisoformat(grant['valid_until']) if grant.get('valid_until') else dt.date.max
    except (KeyError, ValueError, TypeError):
        return False
    return (grant.get('approved') is True and bool(grant.get('evidence_ref'))
            and grant.get('scope') == 'general_travel_monthly'
            and since <= today <= until)

def amount(value, signed=False):
    try:
        n = Decimal(str(value).replace(',', ''))
    except InvalidOperation:
        raise ValueError('invalid_balance_amount') from None
    if not n.is_finite() or n != n.to_integral_value() or abs(n) > 10**12 or (n < 0 and not signed):
        raise ValueError('invalid_balance_amount')
    return int(n)

def million_usd(value):
    """Exact conversion only; raw ledger remains in thousand US dollars."""
    return Decimal(amount(value, signed=True)) / Decimal(1000)

def parse_rows(rows, kind, now):
    """Strict TOURGO year/month XLS layout; blank cells remain missing."""
    if kind not in KINDS or not rows:
        raise ValueError('balance_export_header_mismatch')

    def canonical(raw):
        # TOURGO's 2026-11 XLS export declares an additional formatting-only
        # column in BIFF. Discard it ONLY when all trailing cells are empty.
        if len(raw) < 14:
            raise ValueError('balance_export_shape_mismatch')
        if any(cell not in ('', None) for cell in raw[14:]):
            raise ValueError('balance_export_unexpected_trailing_data')
        return raw[:14]

    if canonical(rows[0]) != ['연도', '계'] + [f'{m}월' for m in range(1, 13)]:
        raise ValueError('balance_export_header_mismatch')
    values = {}
    for original in rows[1:]:
        row = canonical(original)
        match = re.fullmatch(r'(20\d{2})년\(1,000 US\$\)', str(row[0]))
        if not match:
            raise ValueError('balance_export_unit_or_year_mismatch')
        year = int(match[1]); subtotal = 0; observed = 0
        for month, raw in enumerate(row[2:], 1):
            if raw == '' or raw is None:
                continue
            period = valid_period(f'{year:04}-{month:02}')
            if period >= now.strftime('%Y-%m') or period in values:
                raise ValueError('balance_future_or_duplicate_period')
            value = amount(raw, kind == 'balance')
            values[period] = value; subtotal += value; observed += 1
        if observed and amount(row[1], kind == 'balance') != subtotal:
            raise ValueError('balance_annual_total_mismatch')
    if not values:
        raise ValueError('balance_empty_export')
    return values

def read_xls(path, kind, now):
    # Optional dependency is not required by the existing daily collector/tests.
    import xlrd
    book = xlrd.open_workbook(path)
    if book.nsheets != 1:
        raise ValueError('balance_sheet_count_mismatch')
    sheet = book.sheet_by_index(0)
    return parse_rows([sheet.row_values(r) for r in range(sheet.nrows)], kind, now)

def validate_bundle(bundle):
    if set(bundle) != set(KINDS) or not bundle['receipts']:
        raise ValueError('balance_bundle_incomplete')
    periods = set(bundle['receipts'])
    if any(set(bundle[k]) != periods for k in KINDS):
        raise ValueError('balance_periods_mismatch')
    for period in periods:
        valid_period(period)
        for k in KINDS:
            amount(bundle[k][period], k == 'balance')
        if bundle['receipts'][period] - bundle['expenditure'][period] != bundle['balance'][period]:
            raise ValueError('balance_identity_mismatch')
    return max(periods)

def monthly_comparisons(values, period, kind):
    if kind not in KINDS:
        raise ValueError('unknown_balance_kind')
    result = comparisons({p: {'value': v} for p, v in values.items()}, period)
    year, month = map(int, period.split('-'))
    for name, base in [('mom', month_before(period)), ('yoy', f'{year-1:04}-{month:02}')]:
        result[name + '_change'] = values[period] - values[base] if base in values else None
    if kind == 'balance':
        # Deficit/surplus sign changes make percentage comparisons misleading.
        for key in ('mom_pct', 'yoy_pct', 'ytd_yoy_pct'):
            result[key] = None
        result['percentage_policy'] = 'signed_balance_absolute_changes_only'
    return result

def merge_ledger(previous, bundle, provenance, now):
    """Return a private ledger copy; source failure leaves the input untouched."""
    latest = validate_bundle(bundle)
    if provenance.get('data_origin') not in ('official_export', 'synthetic_test') or not provenance.get('sha256_by_kind') or provenance.get('unit') != UNIT:
        raise ValueError('balance_provenance_missing')
    hashes = provenance['sha256_by_kind']
    if set(hashes) != set(KINDS) or any(not isinstance(v, str) or not re.fullmatch(r'[a-f0-9]{64}', v) for v in hashes.values()):
        raise ValueError('balance_file_hashes_invalid')
    origin = provenance['data_origin']
    if previous and previous.get('data_origin') != origin:
        raise ValueError('synthetic_official_mix_forbidden')
    ledger = copy.deepcopy(previous or {'data_origin': origin, 'unit': UNIT, 'series': {}, 'revisions': []})
    if latest < ledger.get('latest_period', ''):
        raise ValueError('balance_older_snapshot_rejected')
    finality = provenance.get('finality', 'not_stated')
    if finality not in ('not_stated', 'provisional', 'final'):
        raise ValueError('balance_finality_invalid')
    for kind in KINDS:
        records = ledger['series'].setdefault(kind, {})
        for period, value in sorted(bundle[kind].items()):
            if period >= now.strftime('%Y-%m'):
                raise ValueError('balance_future_period')
            old = records.get(period)
            record = dict(value=value, unit=UNIT, period=period, finality=finality,
                          first_collected_at=old['first_collected_at'] if old else now.isoformat(),
                          last_collected_at=now.isoformat(), provenance=copy.deepcopy(provenance))
            if old and (old['value'] != value or old['finality'] != finality):
                ledger['revisions'].append(dict(kind=kind, period=period, detected_at=now.isoformat(), before=old, after=copy.deepcopy(record)))
            records[period] = record
    ledger['latest_period'] = max(ledger.get('latest_period', latest), latest)
    return ledger

def approved_download(source, downloader, today=None, *, requested_range=None):
    """A future transport callback is never called before explicit permission."""
    if not permitted(source, 'collection', today):
        raise ValueError('balance_collection_not_approved')
    from . import tourgo
    tourgo.require_range(source,'collection',requested_range)
    return downloader()

def publication_view(source, ledger, today=None):
    if not permitted(source, 'publication', today):
        raise ValueError('balance_publication_not_approved')
    if ledger.get('data_origin') != 'official_export':
        raise ValueError('synthetic_data_publication_forbidden')
    from . import tourgo
    tourgo.require_ledger_scope(source,'publication',ledger)
    return copy.deepcopy(ledger)
