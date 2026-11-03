"""Editorial exposure is separate from relevance, storage and reuse permission.

A foreign industry story is not Korea-related just because it is in English,
mentions tourism, or was written by a Korean publisher. Filing records are
preserved for research but never part of the default Newsroom or briefing.
"""
import re
import datetime as dt

TIERS = {'korea_direct': (0, '한국 관광산업 직접 관련'),
         'global_major': (1, '글로벌 관광산업 주요 변화'),
         'reference': (2, '참고용 해외 산업 자료')}
KOREAN_COMPANIES = ('대한항공', '아시아나항공', '제주항공', '진에어', '티웨이', '에어부산',
                    '호텔신라', '호텔롯데', '하나투어', '모두투어', '야놀자', '여기어때', '노랑풍선')


def is_statistical(record):
    return record.get('source_id', record.get('id')) == 'kosis_recent' or record.get('record_type') == 'statistical_release'


def statistical_assessment():
    # Dataset table-of-contents terms do not establish a news topic or relevance.
    return {'rule_version': '0.3-statistics-1', 'label': 'NotApplicable',
            'decision': 'publish', 'category': '통계자료', 'score': 0,
            'rules': ['statistical_dataset_not_news'], 'signals': [], 'impact_targets': [],
            'evidence_status': 'not_assessed_as_news',
            'reason': '통계 수록·갱신 자료입니다. 표 설명의 관광·숙박 용어를 뉴스 관련성 근거로 사용하지 않습니다.'}


def exposure(article):
    if is_statistical(article):
        return {'version': '0.3-editorial-1', 'tier': 'not_news', 'rank': 3,
                'label': '통계자료', 'korea_connection': 'not_assessed', 'evidence': [],
                'reason': '통계 원자료는 뉴스 편집 순위와 분리합니다.'}
    title = article.get('title', '')
    text = re.sub(r'\s+', ' ', title.casefold())
    evidence = []
    negative = re.search(r'무관|관련\s*없|not related|unrelated|no (?:link|connection)', text)
    relevant = (article.get('relevance_label') == 'Direct' or
                (article.get('relevance_label') == 'Indirect' and
                 article.get('relevance_evidence', {}).get('review_status') == 'approved'))
    if relevant and not negative:
        korea_text = re.sub(r'\bnorth korean?\b', 'unverified foreign market', text)
        match = re.search(r'(?:서울|부산|제주|경북|경남|전남|전북|강원|인천)\s*(?:관광|여행업|호텔시장|항공노선)|방한|한국\s*(?:관광|여행|호텔|항공|시장)|국내\s*(?:관광|여행|숙박)|\bsouth korea\b|\brepublic of korea\b|\bkorean (?:tourism|travel|hotel|aviation)\b|\b(?:to|from|in) (?:seoul|incheon|busan|jeju)\b', korea_text)
        if match:
            evidence.append({'field': 'title', 'value': match.group(), 'rule': 'explicit_korean_market'})
        # These records have a known domestic business subject, not merely a
        # multinational's familiar name. The relevance rule already requires
        # operating/revenue/route change rather than brand presence alone.
        if article.get('relevance_evidence', {}).get('rules') == ['named_company_operating_change']:
            subject_title = re.sub(r'^\[[^]]+\]\s*', '', title)
            attribution_only = re.search(r'이\s*본|가\s*본|분석한|언급한|전한|보도한', subject_title)
            company = None if attribution_only else next((name for name in KOREAN_COMPANIES if re.match(re.escape(name)+r'(?:[은는이가의,:\s]|$)', subject_title)), None)
            if company:
                evidence.append({'field': 'title', 'value': company, 'rule': 'domestic_company_operating_subject'})
        if (article.get('source_id') == 'mcst_press' and
                re.search(r'외래관광객.*(?:달성|역대|성과)', title) and
                not re.search(r'영국|미국|일본|중국|북한|런던|세계|글로벌', title)):
            evidence.append({'field': 'title+source_id', 'value': 'mcst_press:외래관광객 성과',
                             'rule': 'official_korean_inbound_performance'})
        if re.search(r'대한항공(?:\s*\(KE\))?\s*발권', title):
            evidence.append({'field': 'title', 'value': '대한항공 발권 서비스',
                             'rule': 'explicit_domestic_airline_ticketing_service'})
        if ('quantified_tourism_demand_headline' in article.get('relevance_evidence', {}).get('rules', []) and '한국인' in title):
            evidence.append({'field': 'title', 'value': '한국인 관광소비 의향',
                             'rule': 'explicit_korean_consumer_demand'})
        # A named Korean research institution + tourism-development activity
        # proves a domestic subject; the publisher's country alone never does.
        agency = re.search(r'(?:한국문화관광연구원|문광연)(?:[은는이가,·\s]|$)', title)
        if agency and re.search(r'지역관광개발.*워크숍', title):
            evidence.append({'field': 'title', 'value': agency.group().strip(),
                             'rule': 'named_korean_tourism_institution_activity'})
        rules = article.get('relevance_evidence', {}).get('rules', [])
        if ('medical_tourism_lodging_designation' in rules and
                re.search(r'서울시.*의료친화\s*숙박시설', title)):
            evidence.append({'field': 'title', 'value': '서울시 의료친화 숙박시설 지정',
                             'rule': 'explicit_korean_lodging_policy'})
        route = re.search(r'(?:인천|제주|부산)\s*[-~∼–↔]\s*[가-힣]+', title)
        if 'air_route_capacity_change' in rules and route:
            evidence.append({'field': 'title', 'value': route.group(),
                             'rule': 'explicit_korean_air_route_capacity'})
        if article.get('source_id', '').startswith('seoul_'):
            place = re.search(r'서울|동대문|남산|봉은사|제주|철원|부산|인천', title)
            foreign = re.search(r'영국|미국|일본|중국|런던|tokyo|london|united kingdom|united states', text)
            if place and not foreign:
                evidence.append({'field': 'title+source_id', 'value': place.group(), 'rule': 'official_local_tourism_report'})
    if evidence:
        tier = 'korea_direct'
        reason = '제목의 한국 시장·국내 관광기업 운영·공식 지역 관광사업 근거를 확인했습니다.'
    else:
        # Major means an explicitly industry-wide, quantified global change.
        # A local UK rule/runway, famous company, or generic English term does
        # not establish worldwide scope or a link to the Korean market.
        worldwide = re.search(r'\b(?:global|worldwide) (?:tourism|air passenger|airline (?:industry|sector|market)|hotel industry|hospitality (?:sector|industry))\b|(?:전\s*세계|세계)\s*(?:관광(?:수요|객|산업)|항공\s*여객|호텔\s*산업)', text)
        industry = re.search(r'tourism|air passenger|airline|hospitality|hotel industry|관광|항공|숙박', text)
        quantified = re.search(r'\d+(?:\.\d+)?\s*(?:%|percent|million|billion)|\d+\s*(?:억|만)\s*(?:명|달러)', text)
        change = re.search(r'demand|capacity|revenue|arrivals|growth|increas|decreas|수요|증가|감소|매출', text)
        if relevant and not negative and worldwide and industry and quantified and change:
            tier = 'global_major'
            evidence = [{'field': 'title', 'value': m.group(), 'rule': 'quantified_worldwide_industry_change'} for m in (worldwide, industry, quantified, change)]
            reason = '세계 산업 전체의 범위와 정량적 변화가 제목에 명시되어 있습니다. 한국 시장 영향은 별도로 입증되지 않았습니다.'
        else:
            tier = 'reference'
            reason = '한국 관광시장과의 직접 연계 또는 세계 산업 전체의 주요 변화라는 근거가 없어 참고 자료로 관리합니다.'
    rank, label = TIERS[tier]
    return {'version': '0.3-editorial-1', 'tier': tier, 'rank': rank, 'label': label,
            'korea_connection': 'explicit' if tier == 'korea_direct' else 'not_established',
            'evidence': evidence, 'reason': reason}


def publication_order(article):
    """UTC instants, deterministic URL/id ties; never rewrite source precision.

    Date-only records use their day lower bound in KST for ordering only, and
    remain ineligible for a rolling-hour briefing. Invalid/unverified dates last.
    """
    raw = article.get('published_at', '')
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
            stamp = dt.datetime.fromisoformat(raw).replace(tzinfo=dt.timezone(dt.timedelta(hours=9)))
        elif re.search(r'T\d{2}:\d{2}', raw) and re.search(r'(Z|[+-]\d{2}:?\d{2})$', raw):
            stamp = dt.datetime.fromisoformat(raw.replace('Z', '+00:00'))
        else:
            raise ValueError('unverified_publication_date')
        value = stamp.timestamp() if article.get('publication_time_verified_for_news') is not False else float('-inf')
    except (ValueError, TypeError, OverflowError):
        value = float('-inf')
    return (-value, article.get('url', ''), article.get('id', ''))


def project(articles):
    """Annotate copies; never delete/change the canonical stored record list."""
    stored = []
    for article in articles:
        record = {**article, 'record_type': article.get('record_type', 'news'), 'editorial': exposure(article)}
        # KOSIS recent-additions RSS announces statistical datasets, not news
        # article publication. Preserve the provider timestamp but never use it
        # as evidence of a newly issued Newsroom story.
        if record.get('source_id') == 'kosis_recent' or record['record_type'] == 'statistical_release':
            if record.get('relevance_label') != 'NotApplicable':
                record.setdefault('legacy_news_classification', {key: record.get(key) for key in
                                  ('category', 'relevance', 'relevance_label', 'relevance_evidence')})
            record.update(record_type='statistical_release', category='통계자료', relevance=0,
                          relevance_label='NotApplicable', relevance_evidence=statistical_assessment())
            record['editorial'] = exposure(record)
            record['publication_time_verified_for_news'] = False
            record.setdefault('publication_date_basis', 'statistical_provider_timestamp_not_verified_as_news')
            record['timestamp_role'] = 'provider_statistical_timestamp_not_news_publication'
        stored.append(record)
    newsroom = [a for a in stored if a['record_type'] == 'news' and not a.get('archived_only', False)]
    filings = [a for a in stored if a['record_type'] == 'regulatory_filing']
    newsroom.sort(key=publication_order)
    return stored, newsroom, filings
