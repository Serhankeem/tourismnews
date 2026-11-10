"""Follow the official site's public release and XLSX download controls only."""
import datetime as dt
import hashlib
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlsplit, parse_qs, urlencode
from ..reports.html import DOM
from .xlsx import workbook

BASE='https://datalab.visitkorea.or.kr'
TITLE=re.compile(r'(?:\[(?:정정|수정|재공표)\]\s*)?(20\d{2})년\s*(\d{1,2})월\s*한국관광통계\s*(?:공표|재공표)(?:\s*[\(\[]\s*(?:정정|수정|재공표)\s*[\)\]])?')
STATISTICS_PATH='/datalab/portal/ts/getEntcnyFrgnCust2Form.do'
CATALOG_PATH='/site/portal/ex/bbs/List.do'

class ReleaseNotAdvertised(ValueError):
    pass

def public_url(href,base=BASE):
    # Extract, never execute, the documented public menu goUrl link.
    if not isinstance(href,str) or not href:raise ValueError('unapproved_release_link')
    match=re.fullmatch(r"javascript:goUrl\('([^']+)'(?:,'\d+'){0,2}\);?",href)
    url=urljoin(base,match[1] if match else href)
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname!='datalab.visitkorea.or.kr' or p.username or p.password or p.port not in (None,443) or p.fragment:
        raise ValueError('unapproved_release_link')
    return url,p,parse_qs(p.query,keep_blank_values=True)

def release_url(href):
    url,p,q=public_url(href)
    legacy=q.get('cbIdx')==['1127'] and 'cbIdx2' not in q
    # The public statistics board wraps the same 1127 posts in umbrella 1603.
    wrapped=(q.get('cbIdx')==['1603'] and q.get('cbIdx2')==['1127']
             and q.get('tgtTypeCd')==['CATE_CONT'] and q.get('searchKey2')==['spt01'])
    if (p.path!='/site/portal/ex/bbs/View.do' or q.get('cateCont')!=['spt01']
            or not (legacy or wrapped) or len(q.get('bcIdx',[]))!=1 or not re.fullmatch(r'[1-9]\d*',q['bcIdx'][0])
            or any(len(v)!=1 for v in q.values())):
        raise ValueError('unapproved_release_link')
    return url

def compact(value):return re.sub(r'\s+','',value or '')
def count(value):
    try:d=Decimal(str(value).replace(',',''))
    except InvalidOperation:raise ValueError('invalid_statistical_value') from None
    if not d.is_finite() or d<0 or d!=d.to_integral_value() or d>1_000_000_000:raise ValueError('invalid_person_count')
    return int(d)

def latest_release(payload,now):
    doc=DOM(payload);rows=[]
    for a in doc.root.all('a'):
        match=TITLE.fullmatch(a.text().strip())
        if not match:continue
        year,month=map(int,match.groups());period=f'{year:04}-{month:02}'
        if not 1<=month<=12 or period>=now.strftime('%Y-%m'):raise ValueError('unreleased_or_future_reference_period')
        rows.append((period,release_url(a.attrs.get('href',''))))
    if not rows:raise ReleaseNotAdvertised('monthly_release_not_advertised_in_public_catalog')
    return max(rows)

def discover_release(source,loader,now):
    home=loader(source['catalog_url'])
    try:
        return (*latest_release(home,now),source['catalog_url'])
    except ReleaseNotAdvertised:
        # The homepage's rolling highlights are not a complete release catalogue.
        # Follow only controls actually advertised by both public HTML pages.
        stats=[]
        for a in DOM(home).root.all('a'):
            if a.text() not in ('방한 외래관광객','한국관광 통계 바로가기','방한 관광객 통계'):continue
            url,p,q=public_url(a.attrs.get('href',''))
            if p.path==STATISTICS_PATH and not q:stats.append(url)
        if not stats:raise ValueError('public_statistics_navigation_unverified')
        stats_url=stats[0];page=DOM(loader(stats_url))
        buttons=[a for a in page.root.all('a') if a.attrs.get('id')=='bbsBtn' and a.text()=='통계게시판']
        if len(buttons)!=1:raise ValueError('public_statistics_catalog_control_unverified')
        board,p,q=public_url(buttons[0].attrs.get('href',''),stats_url)
        if p.path!=CATALOG_PATH or q!={'cbIdx':['1603'],'tgtTypeCd':['CATE_CONT'],'searchKey2':['spt01']}:
            raise ValueError('unapproved_public_statistics_catalog')
        return (*latest_release(loader(board),now),board)

def release_files(payload,url,period,now):
    doc=DOM(payload)
    title=next((n.text() for n in doc.root.all('p') if n.has('table-title')),'')
    m=TITLE.fullmatch(title)
    if not m or f'{int(m[1]):04}-{int(m[2]):02}'!=period:raise ValueError('release_reference_mismatch')
    nuris=[n for n in doc.root.all('div') if n.has('nuri')]
    if not nuris or not any('/kogl/img_opentype00.png' in n.attrs.get('src','') for n in nuris[0].all('img')):raise ValueError('release_rights_changed_or_unverified')
    table=next((n for n in doc.root.all('table') if n.has('table-type2')),None)
    dates=re.findall(r'(20\d{2})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})',table.text() if table else '')
    if len(dates)!=1:raise ValueError('release_date_unverified')
    y,mo,d,h,mi=map(int,dates[0]);published=dt.datetime(y,mo,d,h,mi,tzinfo=dt.timezone(dt.timedelta(hours=9)))
    if published>now+dt.timedelta(minutes=10):raise ValueError('future_release_date')
    files={};q=parse_qs(urlsplit(url).query);ym=period.replace('-','')
    for a in doc.root.all('a'):
        if a.text() not in (f'전체국가통계_{ym}.xlsx',f'통계월보_{ym}.xlsx'):continue
        match=re.fullmatch(r"funDownload\('(\d+)',\s*'(\d+)',\s*'([a-f0-9-]+\.xlsx)'\)",a.attrs.get('onclick',''))
        if not match or match[1]!=q.get('bcIdx',[''])[0] or match[2]!='1127':raise ValueError('download_control_mismatch')
        key='series' if a.text().startswith('전체국가') else 'crosscheck'
        files[key]=BASE+'/common/board/Download.do?'+urlencode(dict(bcIdx=match[1],cbIdx=match[2],streFileNm=match[3]))
    if set(files)!={'series','crosscheck'}:raise ValueError('required_official_files_missing')
    return files,published.isoformat()

def parse_series(payload,reference,indicators,start_period):
    book=workbook(payload);records={};locations={}
    for indicator in indicators:
        sheet=indicator['sheet'];cells=book.get(sheet)
        if not cells or compact(cells.get('A1',''))!=('［입국］' if sheet=='입국' else '［출국］'):
            raise ValueError('official_sheet_title_changed')
        if cells.get('A4')!='G.TOTAL' or cells.get('A3')!=('Country' if sheet=='입국' else 'Destination'):raise ValueError('official_total_row_or_header_changed')
        if indicator.get('country'):
            rows=[int(k[1:]) for k,v in cells.items() if re.fullmatch(r'B\d+',k) and v==indicator['country']]
            if len(rows)!=1:raise ValueError('country_row_unverified')
            row=rows[0]
        else:row=4
        values={};coords={}
        for cell,heading in cells.items():
            if not re.fullmatch(r'[A-Z]+3',cell):continue
            match=re.fullmatch(r'(20\d{2})(?:\.|년)\s*(\d{1,2})월',heading.strip())
            if not match:continue
            year,month=map(int,match.groups())
            if not 1<=month<=12:raise ValueError('invalid_reference_month')
            period=f'{year:04}-{month:02}'
            if period<start_period:continue
            coordinate=cell[:-1]+str(row);value=cells.get(coordinate)
            if value is None:continue # Blank is missing, never a zero.
            if period>reference:raise ValueError('data_after_release_reference')
            if period in values:raise ValueError('duplicate_reference_month')
            values[period]=count(value);coords[period]=coordinate
        if reference not in values:raise ValueError('latest_reference_value_missing')
        records[indicator['id']]=values;locations[indicator['id']]=dict(sheet=sheet,cells=coords)
    return records,locations

def crosscheck(payload,period,values,indicators):
    book=workbook(payload);year,month=map(int,period.split('-'))
    name=f'성별 입국({month}월)';incoming=book.get(name,{})
    if compact(incoming.get('A1',''))!=f'성별국적별입국({year}년{month}월)' or compact(incoming.get('C3',''))!='인원(명)':raise ValueError('crosscheck_period_or_unit_unverified')
    outgoing=book.get('성별 출국',{})
    if compact(outgoing.get('B3',''))!='인원(명)' or outgoing.get('A1')!='성별출국':raise ValueError('outbound_unit_unverified')
    rows=[int(k[1:]) for k,v in outgoing.items() if re.fullmatch(r'A\d+',k) and v==f'{month}월']
    if len(rows)!=1:raise ValueError('crosscheck_outbound_month_missing')
    for item in indicators:
        if item['sheet']=='출국':v=outgoing.get('B'+str(rows[0]));prior=outgoing.get('C'+str(rows[0]))
        elif item.get('country'):
            rs=[int(k[1:]) for k,v in incoming.items() if re.fullmatch(r'B\d+',k) and v==item['country']]
            if len(rs)!=1:raise ValueError('crosscheck_country_missing')
            v=incoming.get('C'+str(rs[0]));prior=incoming.get('D'+str(rs[0]))
        else:v=incoming.get('C4');prior=incoming.get('D4')
        if v is None or count(v)!=values[item['id']][period]:raise ValueError('independent_official_tables_disagree')
        prior_period=f'{year-1:04}-{month:02}'
        if prior_period in values[item['id']] and (prior is None or count(prior)!=values[item['id']][prior_period]):raise ValueError('prior_year_month_tables_disagree')
        year_keys=[f'{year:04}-{m:02}' for m in range(1,month+1)]
        if month>1 and all(p in values[item['id']] for p in year_keys):
            if item['sheet']=='출국':annual=outgoing.get('B4');prior_annual=outgoing.get('C4')
            else:
                cumulative=book.get(f'성별 입국(1~{month}월)',{})
                if compact(cumulative.get('A1',''))!=f'성별국적별입국({year}년1~{month}월)':raise ValueError('ytd_crosscheck_period_missing')
                if item.get('country'):
                    rs=[int(k[1:]) for k,v in cumulative.items() if re.fullmatch(r'B\d+',k) and v==item['country']]
                    if len(rs)!=1:raise ValueError('ytd_crosscheck_country_missing')
                    annual=cumulative.get('C'+str(rs[0]));prior_annual=cumulative.get('D'+str(rs[0]))
                else:annual=cumulative.get('C4');prior_annual=cumulative.get('D4')
            if annual is None or count(annual)!=sum(values[item['id']][p] for p in year_keys):raise ValueError('year_to_date_tables_disagree')
            previous_keys=[f'{year-1:04}-{m:02}' for m in range(1,month+1)]
            if all(p in values[item['id']] for p in previous_keys) and (prior_annual is None or count(prior_annual)!=sum(values[item['id']][p] for p in previous_keys)):raise ValueError('prior_year_to_date_tables_disagree')

def fetch(source,indicators,loader,now):
    reference,url,catalog=discover_release(source,loader,now)
    files,published=release_files(loader(url),url,reference,now)
    primary=loader(files['series']);check=loader(files['crosscheck'])
    values,locations=parse_series(primary,reference,indicators,source['start_period'])
    crosscheck(check,reference,values,indicators)
    return dict(reference_period=reference,source_url=url,release_published_at=published,values=values,locations=locations,
                file_url=files['series'],file_sha256=hashlib.sha256(primary).hexdigest(),crosscheck_url=files['crosscheck'],crosscheck_sha256=hashlib.sha256(check).hexdigest(),rights='KOGL-0',unit='명',frequency='M',method='official_public_xlsx',discovery_catalog_url=catalog)
