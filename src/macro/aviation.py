"""Offline official airport XLSX adapter. No downloader or public projection.

Airport statistics (920005) are distinct from MOLIT transport statistics. Files
and the reviewed acquisition manifest are supplied explicitly; never scrape an
internal API or infer seats from operations/passengers.
"""
import copy
import datetime as dt
import hashlib
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from .model import months, valid_period
from .xlsx import workbook

SOURCE = 'kac_airport_monthly'
METHOD = 'official_airport_xlsx_private'
KIND = 'airport_activity_count'
PUBLISHER = '한국공항공사·인천국제공항공사'
CATALOG = 'https://www.airport.co.kr/www/cms/frCon/index.do?MENU_ID=1250'
TIME_URL = 'https://www.airport.co.kr/cms/frFlightStatsCon/timeSeriesStatExcelDown.do'
AIRPORT_URL = 'https://www.airport.co.kr/cms/frFlightStatsCon/airportStatExcelDown.do'
AIRPORTS = ('김포','김해','제주','청주','대구','무안','양양','광주','울산','여수','포항경주','사천','군산','원주','인천')
CODES = ('GMP','PUS','CJU','CJJ','TAE','MWX','YNY','KWJ','USN','RSU','KPO','HIN','KUV','WJU','ICN')
IDS = {'operations': 'market_airport_international_operations',
       'passengers': 'market_airport_international_passengers'}
UNITS = {'operations': '편', 'passengers': '명'}
SCOPE = dict(statistical_approval='920005', basis='airport_statistics_not_molit_transport',
    geography='KR_nationwide_15_airports_including_ICN', airports=list(CODES),
    route='international', direction='arrivals_plus_departures',
    operations='scheduled_and_nonscheduled', aircraft='passenger_and_cargo',
    passengers='revenue_nonrevenue_transfer_excluding_direct_transit')
REVIEWS = ('collection_review','rights_review','automation_review','vintage_review','crosscheck')
MAX_INTEGER = 2**53-1


def definition(item):
    metric = item.get('metric')
    if (metric not in IDS or item.get('id') != IDS[metric] or item.get('source_id') != SOURCE
            or item.get('value_kind') != KIND or item.get('storage') != 'integer'
            or item.get('frequency') != 'M' or item.get('unit') != UNITS[metric]
            or item.get('publisher') != PUBLISHER or item.get('scope') != SCOPE
            or not item.get('definition')):
        raise ValueError('aviation_definition_mismatch')


def reviewed(source, now):
    """Separate dated collection permission; publication never follows from it."""
    grant = source.get('approval', {}).get('collection', {})
    try:
        day = now.date()
        return (source.get('id') == SOURCE and source.get('method') == METHOD
            and source.get('scope') == SCOPE and source.get('enabled') is True
            and grant.get('approved') is True and grant.get('scope') == SOURCE
            and bool(grant.get('evidence_ref'))
            and dt.date.fromisoformat(grant['valid_from']) <= day <= dt.date.fromisoformat(grant['valid_until'])
            and valid_period(grant['period_from']) <= valid_period(source['start_period'])
            <= valid_period(source['end_period']) <= valid_period(grant['period_through'])
            and all(source.get(k, {}).get('status') == 'verified'
                and source[k].get('evidence_url', '').startswith('https://')
                and dt.date.fromisoformat(source[k]['verified_at']) <= day for k in REVIEWS))
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def integer(raw):
    # Counts are exact integers. No decimal/exponent, negative, blank or bool.
    if not isinstance(raw, str) or not re.fullmatch(r'(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)', raw):
        raise ValueError('aviation_integer_invalid')
    value = int(raw.replace(',', ''))
    if value > MAX_INTEGER:
        raise ValueError('aviation_integer_invalid')
    return value


def timestamp(text):
    if not isinstance(text, str):
        raise ValueError('aviation_timestamp_invalid')
    value = dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('aviation_timestamp_invalid')
    return value


def _file(entry, now):
    payload, meta = entry['payload'], entry['metadata']
    kind = meta.get('kind')
    url = TIME_URL if kind == 'national_time_series_original' else AIRPORT_URL
    if (kind not in ('national_time_series_original','national_airport_breakdown_original')
            or not isinstance(payload, bytes) or len(payload) > 2*1024*1024
            or meta.get('bytes') != len(payload) or meta.get('download_url') != url
            or hashlib.sha256(payload).hexdigest() != meta.get('sha256')
            or not meta.get('path') or timestamp(meta.get('retrieved_at')) > now
            or meta.get('original_publication_at') is not None or meta.get('finality') != 'not_stated'):
        raise ValueError('aviation_file_provenance_invalid')
    sheets = workbook(payload)
    if set(sheets) != {'MENU'}:
        raise ValueError('aviation_sheet_mismatch')
    # The shared values reader never executes formulas. This adapter also rejects
    # cached formulas/duplicate cell addresses rather than treating them as data.
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('aviation_duplicate_zip_entry')
        for name in z.namelist():
            if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                xml = ET.fromstring(z.read(name))
                cells = list(xml.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'))
                if (len({c.get('r') for c in cells}) != len(cells)
                        or any(c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}f') is not None for c in cells)):
                    raise ValueError('aviation_formula_or_duplicate_cell')
    return sheets['MENU'], copy.deepcopy(meta)


def _headers(cells, meta):
    time_series = meta['kind'] == 'national_time_series_original'
    title = '시계열 통계' if time_series else '공항별 통계'
    expected = dict(D1=title,A3='검색 기간',A4='공항 구분',A5='노선 구분',B5='국제선',
        C5='운항 구분',D5='전체',E5='여객기/화물기 구분',F5='전체',G5='여객 구분',H5='전체',
        I5='화물 구분',J5='전체',A7='공항명')
    expected.update(dict(B7='연도',C7='월',D7='운항(편)',G7='여객(명)',J7='화물(톤)',
        K5='연도/월 구분',L5='월별') if time_series else dict(B7='운항(편)',E7='여객(명)',H7='화물(톤)'))
    for base in ('DEF','GHI') if time_series else ('BCD','EFG'):
        expected.update({col+'8': label for col, label in zip(base, ('도착','출발','계'))})
    airports = cells.get('B4','').split(',')
    if (any(cells.get(k) != v for k,v in expected.items())
            or len(airports) != len(AIRPORTS) or set(airports) != set(AIRPORTS)):
        raise ValueError('aviation_header_or_scope_mismatch')
    pairs = meta.get('filters')
    if not isinstance(pairs, list) or any(not isinstance(p, (list,tuple)) or len(p) != 2 for p in pairs):
        raise ValueError('aviation_filters_invalid')
    f = {}
    for key,value in pairs:
        f.setdefault(key, []).append(value)
    if (len(f.get('AIRPORT_CHK', [])) != 15 or set(f['AIRPORT_CHK']) != set(CODES)
            or any(f.get(k) != [v] for k,v in dict(LINE_TYPE='1',RAGUL_TYPE='',USE_TYPE='',PASS_TYPE='',CAGO_TYPE='').items())
            or (f.get('YM_TYPE') != ['MMMM'] if time_series else f.get('INOUT_TYPE') != ['0'])):
        raise ValueError('aviation_filters_invalid')
    try:
        start = valid_period(f['ST_YY'][0]+'-'+f['ST_MM'][0])
        end = valid_period(f['EN_YY'][0]+'-'+f['EN_MM'][0])
        if any(len(f[k]) != 1 for k in ('ST_YY','ST_MM','EN_YY','EN_MM')) or start > end or start[5:] > end[5:]:
            raise ValueError()
    except (ValueError,TypeError,KeyError,IndexError):
        raise ValueError('aviation_query_period_invalid') from None
    if cells.get('B3') != start.replace('-','.')+'~'+end.replace('-','.'):
        raise ValueError('aviation_query_header_mismatch')
    # Official time exports apply the month interval to EACH selected year.
    selected = {f'{y:04}-{m:02}' for y in range(int(start[:4]),int(end[:4])+1)
                for m in range(int(start[5:]),int(end[5:])+1)}
    if not time_series and (start != end or len(selected) != 1):
        raise ValueError('aviation_breakdown_requires_one_month')
    return selected


def _triples(cells, row, time_series):
    values = {}
    for metric, cols in zip(IDS, ('DEF','GHI') if time_series else ('BCD','EFG')):
        triple = [integer(cells.get(c+str(row))) for c in cols]
        if triple[0]+triple[1] != triple[2]:
            raise ValueError('aviation_direction_total_mismatch')
        values[metric] = triple
    return values


def parse_file(entry, now):
    cells, meta = _file(entry, now)
    selected = _headers(cells, meta)
    time_series = meta['kind'] == 'national_time_series_original'
    rows = sorted({int(re.fullmatch(r'[A-Z]+([1-9]\d*)', c)[1]) for c in cells})
    data, subtotals, total = {}, {}, None
    for row in (r for r in rows if r >= 9):
        label = cells.get('A'+str(row))
        if label == '합계':
            if total is not None:
                raise ValueError('aviation_duplicate_total')
            total = _triples(cells,row,time_series)
        elif time_series and label is None and re.fullmatch(r'\d{2}월 소계',cells.get('B'+str(row),'')):
            month = cells['B'+str(row)][:2]
            if month in subtotals:
                raise ValueError('aviation_duplicate_subtotal')
            subtotals[month] = _triples(cells,row,True)
        else:
            if time_series:
                if label != '선택 공항':
                    raise ValueError('aviation_unrecognized_data_row')
                key = valid_period(cells.get('B'+str(row),'')+'-'+cells.get('C'+str(row),''))
            else:
                key = label
                if key not in AIRPORTS:
                    raise ValueError('aviation_airport_row_invalid')
            if key in data:
                raise ValueError('aviation_duplicate_month_or_airport')
            data[key] = dict(values=_triples(cells,row,time_series),excel_row=row)
    if not data or total is None:
        raise ValueError('aviation_missing_data_or_total')
    def summed(keys, metric):
        return [sum(data[k]['values'][metric][n] for k in keys) for n in range(3)]
    if any(summed(data,m) != total[m] for m in IDS):
        raise ValueError('aviation_grand_total_mismatch')
    if time_series:
        if set(data) != selected or set(subtotals) != {p[5:] for p in selected}:
            raise ValueError('aviation_query_months_missing_or_changed')
        if any(summed([p for p in data if p[5:]==month],m) != values[m]
               for month,values in subtotals.items() for m in IDS):
            raise ValueError('aviation_subtotal_mismatch')
    elif '인천' not in data:
        raise ValueError('aviation_incheon_missing')
    return dict(data=data,totals=total,selected=selected,metadata=meta)


def snapshot(source, items, bundle, now):
    """Technical parsing only, usable offline without pretending rights approval."""
    if (source.get('id') != SOURCE or source.get('method') != METHOD or source.get('scope') != SCOPE
            or {i.get('id') for i in items} != set(IDS.values()) or len(items) != 2):
        raise ValueError('aviation_source_or_pair_mismatch')
    for item in items:
        definition(item)
    start,end = valid_period(source['start_period']),valid_period(source['end_period'])
    if start > end or end >= now.strftime('%Y-%m') or not bundle:
        raise ValueError('aviation_period_range_invalid')
    data, checks, files, hashes = {}, {}, [], set()
    for entry in bundle:
        parsed = parse_file(entry,now);meta=parsed['metadata']
        if meta['sha256'] in hashes:
            raise ValueError('aviation_duplicate_file')
        hashes.add(meta['sha256']);files.append(meta)
        if meta['kind'] == 'national_time_series_original':
            for p,row in parsed['data'].items():
                if p in data:
                    raise ValueError('aviation_overlapping_months')
                data[p] = dict(**row,metadata=meta)
        else:
            period = next(iter(parsed['selected']))
            if period in checks:
                raise ValueError('aviation_duplicate_breakdown')
            checks[period] = parsed['totals']
    if set(data) != set(months(start,end)):
        raise ValueError('aviation_months_missing_or_range_changed')
    if any(p not in data or any(data[p]['values'][m] != v[m] for m in IDS) for p,v in checks.items()):
        raise ValueError('aviation_breakdown_crosscheck_mismatch')
    records = {i['id']: {} for i in items}
    for p,row in sorted(data.items()):
        meta=row['metadata']
        for item in items:
            a,d,v = row['values'][item['metric']]
            records[item['id']][p] = dict(value=v,arrivals=a,departures=d,unit=item['unit'],frequency='M',
                scope=copy.deepcopy(SCOPE),publisher=PUBLISHER,source_url=CATALOG,
                collection_method=METHOD,collection_mode='offline_official_file_validation',
                source_file=meta['path'],file_url=meta['download_url'],file_sha256=meta['sha256'],
                retrieved_at=meta['retrieved_at'],sheet='MENU',excel_row=row['excel_row'],
                release_published_at=None,original_publication_at=None,finality='not_stated',
                publication_status='blocked')
    return dict(records=records,reference_period=end,start_period=start,files=files,
        checked_breakdown_periods=sorted(checks),independent_crosscheck_complete=False,
        collection_mode='offline_official_file_validation',automatic_download=False,publication_status='blocked')


def fetch(source, items, bundle=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if not reviewed(source,now) or any(i.get('enabled') is not True for i in items):
        raise ValueError('aviation_collection_not_approved')
    if bundle is None:
        raise ValueError('aviation_manual_files_required')
    return snapshot(source,items,bundle,now)
