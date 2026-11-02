"""Report taxonomy and date precision; no inferred day from year/month/period."""
import calendar
import datetime as dt
import re
import unicodedata

FIELDS=('title','publisher','published_at','report_type','category','keywords','url','access_type')
TYPES=('종합 연구보고서','정기 시장동향','정책연구','산업·경제 분석','통계보고서','산업 브리프 / 인사이트')
CATEGORIES=('국제관광·인바운드','국내관광·관광소비','숙박·호텔산업','항공·교통산업','OTA·여행기술','관광정책·산업경제','MICE·비즈니스 이벤트','관광시장 전망·트렌드')
ACCESS=('무료 공개','회원 접근','유료','미확인')
TOPICS={
 'MICE·비즈니스 이벤트':('MICE','business events','business event','international meetings','international congress','international congresses','convention industry','convention market','convention bureau','congress market','exhibition industry','국제회의','컨벤션','전시산업','비즈니스 이벤트'),
 'OTA·여행기술':('OTA','online travel','travel technology','distribution','booking','AI','인공지능','여행기술','플랫폼','특허'),
 '숙박·호텔산업':('lodging','hotel','hotels','accommodation','accommodations','short-term rental','short-term rentals','short term rental','short term rentals','guesthouse','guesthouses','hotel industry','객실','야영장','숙박','호텔'),
 '항공·교통산업':('aviation','airline','airlines','air transport','air travel','airport','airports','rail','railway','railways','passenger aviation','air passenger','항공','공항','교통','여객시장'),
 '국제관광·인바운드':('international tourism','inbound','long-haul','인바운드','국제관광','방한'),
 '국내관광·관광소비':('consumer','spending','domestic travel','consumption','관광소비','국내관광','내국인'),
 '관광정책·산업경제':('economic impact','economics','employment','GDP','policy','policies','governance','regulation','정책','경제효과','관광산업','고용'),
 '관광시장 전망·트렌드':('outlook','forecast','trends','sentiment','market','tourism','travel','전망','동향','관광','여행'),
}

def normalize(text):return re.sub(r'[^\w가-힣]+','',unicodedata.normalize('NFKC',text).casefold())

def terms(title, values):
    text=unicodedata.normalize('NFKC',title).casefold();found=[]
    for term in values:
        pattern=r'\s*'.join(re.escape(v) for v in re.sub(r'\s+','',term.casefold()))
        if term.isascii():pattern=r'(?<![A-Za-z0-9_])'+pattern+r'(?![A-Za-z0-9_])'
        if re.search(pattern,text):found.append(term)
    return found

def classify(title, source, candidate):
    if re.search(r'채용|입찰공고|행사\s*안내|보도자료|staff appointment|webinar registration|annual activity report|press release',title,re.I):
        return None
    category=next((cat for cat,words in TOPICS.items() if terms(title,words)),CATEGORIES[-1])
    keywords=list(dict.fromkeys(term for words in TOPICS.values() for term in terms(title,words)))[:10]
    series=candidate.get('series','')
    if series in ('insight','brief') or '/Research-Updates/' in candidate['url']:kind=TYPES[-1]
    elif series=='trend' or re.search(r'barometer|monitoring sentiment|trends.*prospects|market analysis',title,re.I):kind=TYPES[1]
    elif source['id']=='kcti' or re.search(r'policy|정책',title,re.I):kind=TYPES[2]
    elif re.search(r'economic impact|economics|경제효과',title,re.I):kind=TYPES[3]
    elif re.search(r'statistic|통계',title,re.I):kind=TYPES[4]
    else:kind=TYPES[0]
    return {'report_type':kind,'category':category,'keywords':keywords}

def parse_date(value, today):
    if not isinstance(value,str):raise ValueError('missing_official_publication_date')
    raw=value.strip().replace('.','-').rstrip('-')
    match=re.fullmatch(r'(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?(?:T.+)?',raw)
    if not match:raise ValueError('invalid_official_publication_date')
    year=int(match[1]);month=int(match[2] or 1);day=int(match[3] or 1)
    start=dt.date(year,month,day)
    if match[3]:end=start;precision='day';normalized=start.isoformat()
    elif match[2]:end=dt.date(year,month,calendar.monthrange(year,month)[1]);precision='month';normalized=f'{year:04}-{month:02}'
    else:end=dt.date(year,12,31);precision='year';normalized=str(year)
    if start>today:raise ValueError('future_publication_date')
    return normalized,precision,start,min(end,today)

def cutoff_months(today,months):
    total=today.year*12+today.month-1-months;year,month=divmod(total,12);month+=1
    return dt.date(year,month,min(today.day,calendar.monthrange(year,month)[1]))

def public(record):return {key:record[key] for key in FIELDS}
