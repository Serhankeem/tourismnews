"""Deterministic, metadata-only relevance rules. No article-body retrieval or AI.

Indirect stories are held until a title-bound editorial approval supplies an
original-source URL and an impact explanation. Keyword presence alone is not an
approval. Evidence contains rule identifiers/terms, never copied RSS paragraphs.
"""
import hashlib
import re
import unicodedata

RULE_VERSION = '0.2'
CATEGORIES = ('관광정책', '인바운드', '여행산업', '항공·숙박', '문화·트렌드', '경제·시장')
LEGACY_CATEGORIES = {'정책': '관광정책', '수요': '인바운드', '산업': '여행산업',
                     '리서치': '경제·시장', '지역': '문화·트렌드', 'MICE': '여행산업'}
# A subject is an industry concept, not the generic word 관광/여행/항공/문화.
SUBJECTS = {
    '관광정책': ('관광정책', '관광산업', '관광진흥', '관광예산', '관광기금', '관광비자', '관광세', '무비자', 'tourism policy', 'tourism strategy'),
    '인바운드': ('외래관광객', '외국인관광객', '방한객', '방한관광객', '방한수요', '인바운드', '관광객수', '입국관광객', 'inbound tourism', 'visitor arrivals'),
    '여행산업': ('여행업', '여행사', '관광기업', '관광스타트업', '관광플랫폼', '여행플랫폼', '국제회의', '컨벤션산업', '마이스산업', 'travel agency', 'convention industry'),
    '항공·숙박': ('호텔업', '호텔시장', '관광숙박', '숙박업', '호텔객실', '객실점유율', '객실공급', '숙박요금', '항공노선', '국제선', '항공운임', '항공사', '여객수요', 'airline routes', 'hospitality'),
    '문화·트렌드': ('지역관광', '관광특구', '관광도시', '관광개발', '관광콘텐츠', '관광활성화', '관광재단', '웰니스관광', '웰니스트래블', 'regional tourism'),
    '경제·시장': ('국내여행수요', '관광통계', '관광수입', '관광지출', '관광소비', '관광데이터', '관광연구', '관광산업동향', 'tourism statistics', 'tourism receipts'),
}
ACTIONS = ('발표', '지원', '개최', '운영', '증가', '감소', '확대', '축소', '공급', '취항', '운항', '결항', '예약', '투자', '실적', '매출', '정책', '개편', '수요', '개발', '지원', '증편', '감편', '파산', '신설', '폐지')
SECTORS = {
    '경제·시장': ('환율', '원화약세', '원화강세', '원달러', '금리', '유가', '물가', '소비심리', '경기침체'),
    '문화·트렌드': ('앨범', '도서전', '미술', '콘서트', '공연', '한류', '영화', '스포츠', '축제', '전시'),
    '항공·숙박': ('폭우', '태풍', '지진', '파업', '공항폐쇄'),
    '여행산업': ('철도', '고속철', '교통망', '주52시간', '휴일', '휴가제도'),
}
IMPACTS = {
    '관광수요': ('관광수요', '국내여행수요', '방한수요', '방한객', '외래관광객', '외국인관광객', '해외여행수요', '입국관광객', '관광객수', '해외팬입국'),
    '관광소비': ('관광소비', '관광지출', '관광수입', '여행경비', '숙박예약', '객실예약', '호텔객실', '객실점유율'),
    '관광기업': ('여행사', '호텔업', '숙박업', '항공사', '국제선', '관광기업'),
    '관광정책': ('관광정책', '관광예산', '관광기금', '관광비자'),
}
LINKS = ('영향', '증가', '감소', '확대', '축소', '부담', '견인', '때문', '따라', '급증', '취소', '결항', '감편', '증편')
UNCERTAIN = ('가능성', '예상', '추정', '전망', '수있', '수도있', '확인되지', '근거없')
NEGATIVE = ('무관', '관련없', '영향없', '관계없', '영향을주지않', '영향이없')
PERSONAL = ('연예인여행', '연예여행', '여행예능', '여행블로그', '여행후기', '산책후기', '맛집소개', '가볼만한곳', '영화줄거리')


def compact(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text).casefold()).strip()


def title_digest(title):
    return hashlib.sha256(unicodedata.normalize('NFKC', title).strip().encode()).hexdigest()


def matches(text, terms):
    found = []
    for term in terms:
        letters = re.sub(r'\s+', '', compact(term))
        pattern = r'\s*'.join(re.escape(char) for char in letters)
        if term in ('여행사', '항공사'):
            # Do not turn 참'여 행사', 여행사진 or 여행사랑 into a company.
            pattern = r'(?<![가-힣A-Za-z])' + pattern + r'(?=\s|[은는이가를의와도에로]|[^가-힣A-Za-z]|$)'
        if re.search(pattern, text):
            found.append(term)
    return found


def english_industry(title):
    """Require an industry subject plus an operational/financial change."""
    text = unicodedata.normalize('NFKC', title).casefold()
    if re.search(r'\b(exchange rates?|oil prices?|interest rates?)\b', text) and re.search(r'\b(travel demand|tourism spending|hotel bookings)\b', text):
        return {'label': 'Indirect', 'decision': 'hold', 'category': '경제·시장', 'score': 4,
                'rules': ['english_cross_sector_impact'], 'signals': [{'field': 'title', 'terms': ['macro_change', 'tourism_impact']}],
                'impact_targets': ['관광수요'], 'evidence_status': 'explicit_feed_claim' if re.search(r'increas|decreas|affect|reduc', text) else 'insufficient',
                'reason': '인접 산업 변화가 관광수요에 미치는 원문 근거를 편집 검토해야 합니다.'}
    if re.search(r'aviation careers|student competition|museum exhibit|photography contest|employee party|birthday|discount coupons?|hotel deals|best hotels|travel tips|bucket list', text):
        return None
    action = re.search(r'financial filing|financial results|introduc|digital solution|earnings|revenue|profit|capacity|new route|new flight|launch|expand|opens?\b|opening|demand|fares?|refund|passenger rights|strategy|funding|investment|tourism tax|visitor levy|tourist tax|safeguards|extra charges', text)
    if not action:
        return None
    groups = (
        ('항공·숙박', r'\b(airline|airlines|air travel|flights?|air passengers?|passengers.*flying|runway|aviation|airport hotel|hotel|hotels|hospitality|marriott|hilton|hyatt|accor)\b|delta air lines|united airlines|jetblue|korean air|asiana airlines'),
        ('여행산업', r'booking holdings|expedia group|trip\.com group|makemytrip|travel agenc|tour operator|travel technolog|amadeus|sabre'),
        ('관광정책', r'tourism strategy|tourism funding|tourist tax|tourism tax|visitor levy'),
        ('경제·시장', r'tourism spending|tourism revenue|visitor economy|tourism investment'),
        ('인바운드', r'inbound tourism|visitor arrivals'),
    )
    for category, pattern in groups:
        match = re.search(pattern, text)
        if match:
            return {'label': 'Direct', 'decision': 'publish', 'category': category, 'score': 8,
                    'rules': ['english_industry_change'], 'signals': [{'field': 'title', 'terms': [match.group(), action.group()]}],
                    'impact_targets': [], 'evidence_status': 'industry_subject_in_feed',
                    'reason': '공식 제목에 관광기업·항공·숙박 등 산업 대상과 운영 또는 재무 변화가 함께 명시되어 있습니다.'}
    return None


def korean_company_change(title):
    text = compact(title)
    if matches(text, ('생일행사', '봉사활동', '연예인일상', '직원체육대회')):
        return None
    companies = {
        '항공·숙박': ('대한항공', '아시아나항공', '제주항공', '진에어', '티웨이', '에어부산', '호텔신라', '호텔롯데'),
        '여행산업': ('야놀자', '여기어때', '하나투어', '모두투어', '노랑풍선', '아고다', '부킹닷컴', '익스피디아', '트립닷컴', '에어비앤비', '세이버'),
    }
    changes = matches(text, ('매출', '영업이익', '실적', '인수', '합병', '취항', '증편', '감편', '국제선', '객실공급', '플랫폼출시', '발권개시', '발권서비스', '서비스출시'))
    if not changes:
        return None
    for category, names in companies.items():
        named = matches(text, names)
        if named:
            return {'label': 'Direct', 'decision': 'publish', 'category': category, 'score': 8,
                    'rules': ['named_company_operating_change'],
                    'signals': [{'field': 'title', 'terms': named + changes}],
                    'impact_targets': ['관광기업'], 'evidence_status': 'industry_subject_in_feed',
                    'reason': '관광기업의 이름과 구체적인 운영·매출·노선 변화가 제목에 함께 명시되어 있습니다.'}
    return None


def korean_industry_change(title):
    """Narrow title evidence for missed policy, capacity and B2B news.

    A Korean publisher/brand alone supplies no evidence. Each rule needs a
    concrete industry object AND change; product promotions remain excluded.
    """
    text = compact(title)
    # Preserve the existing cross-sector approval path and consumer exclusions.
    if matches(text, SECTORS['항공·숙박']) or matches(text, ('할인쿠폰', '특가', '여행상품', '기획전')):
        return None
    rules = (
        ('tourism_sector_tax_policy', '관광정책',
         ('관광업계', '관광업종'), ('가업상속공제',), ('축소', '유지', '촉구', '대응')),
        ('mice_industry_investment', '여행산업',
         ('mice', '마이스산업'), ('예산', '투자'), ('축소', '줄어', '촉구', '확대')),
        ('medical_tourism_lodging_designation', '항공·숙박',
         ('의료친화숙박시설',), ('선정', '지정'), ('개소',)),
        ('air_route_capacity_change', '항공·숙박',
         ('항공', '운항'), ('증편', '감편', '운항확대'), ('인천', '제주', '부산', '국제선', '탑승률')),
        ('ota_b2b_technology_change', '여행산업',
         ('야놀자', '놀유니버스', '아고다', '하나투어', '모두투어', '여기어때'),
         ('b2b플랫폼', 'b2b서비스', 'ai어시스턴트'), ('도입', '출시', '개시')),
    )
    for rule, category, *groups in rules:
        evidence = [matches(text, group) for group in groups]
        if all(evidence):
            return {'label': 'Direct', 'decision': 'publish', 'category': category,
                    'score': 7, 'rules': [rule],
                    'signals': [{'field': 'title', 'terms': [term for group in evidence for term in group]}],
                    'impact_targets': ['관광기업'], 'evidence_status': 'industry_subject_in_feed',
                    'reason': '제목에 관광업종의 세제·MICE 투자·숙박 지정·항공 공급 또는 OTA 운영 기술의 구체적인 변화가 함께 명시되어 있습니다.'}
    return None


def assess(title, description=''):
    fields = {'title': compact(title), 'description': compact(description)}
    result = {'rule_version': RULE_VERSION, 'label': 'Irrelevant', 'decision': 'exclude',
              'category': None, 'score': 0, 'rules': [], 'signals': [],
              'impact_targets': [], 'reason': '관광산업에 대한 구체적 대상·영향 근거가 없습니다.'}
    if re.search(r'^how to\b', title.strip(), re.I):
        return {**result, 'rules': ['general_industry_howto_not_operating_news'],
                'reason': '일반적인 방법 안내 제목은 실제 산업 변화 뉴스로 간주하지 않습니다.'}
    if matches(fields['title'], PERSONAL):
        return {**result, 'rules': ['personal_or_generic_travel'], 'reason': '개인 여행·일반 여가 정보는 산업 뉴스에서 제외합니다.'}
    if matches(fields['title'], ('할인쿠폰', '최저가', '추천숙소', '호텔추천')) and not matches(fields['title'], ('시장', '실적', '매출', '정책', '공급', '수요')):
        return {**result, 'rules': ['consumer_promotion'], 'reason': '일반 예약·할인 정보는 산업 뉴스에서 제외합니다.'}
    domestic = korean_industry_change(title)
    if domestic:
        return {**result, **domestic}
    # A quantified intent/sales survey is industry demand metadata, not a
    # recommendation for an individual trip. Preserve the original headline.
    if (re.search(r'\d+(?:\.\d+)?\s*%', fields['title']) and
            matches(fields['title'], ('한국인', '국내여행객', '방한객')) and
            matches(fields['title'], ('숙박계획', '숙박수요', '여행수요')) and
            matches(fields['title'], ('호텔숙박', '국내여행', '해외여행'))):
        return {**result, 'label': 'Direct', 'decision': 'publish', 'category': '항공·숙박' if matches(fields['title'], ('호텔숙박',)) else '경제·시장',
                'score': 6, 'rules': ['quantified_tourism_demand_headline'],
                'signals': [{'field':'title','terms':matches(fields['title'], ('한국인', '국내여행객', '방한객', '호텔숙박', '숙박계획', '숙박수요', '여행수요'))}],
                'evidence_status': 'industry_subject_in_feed',
                'reason': '제목에 관광소비 집단과 정량적 숙박·여행 수요 또는 의향이 함께 명시되어 있습니다. 계획을 실제 실적으로 바꾸지 않습니다.'}
    organization = matches(fields['title'], ('관광재단', '관광공사', '관광청'))
    market_action = matches(fields['title'], ('캠페인', '설명회', '로드쇼', '홍보대사', '유치사업'))
    execution = matches(fields['title'], ('추진', '개최', '운영', '확대', '공략', '위촉', '진행', '성료'))
    if organization and market_action and execution:
        return {**result, 'label': 'Direct', 'decision': 'publish', 'category': '문화·트렌드',
                'score': 6, 'rules': ['tourism_organization_market_action'],
                'signals': [{'field':'title','terms':organization+market_action+execution}],
                'evidence_status':'industry_subject_in_feed',
                'reason':'관광 전담기관의 구체적인 시장 유치·홍보 사업과 실행이 제목에 함께 명시되어 있습니다.'}
    ota = matches(fields['title'], ('아고다', '부킹닷컴', '익스피디아', '트립닷컴', '에어비앤비'))
    policy = matches(fields['title'], ('수수료', '퇴실규정', '예약정책', '호스트정산'))
    policy_change = matches(fields['title'], ('변경', '개편', '인상', '인하', '바뀐다'))
    if ota and policy and policy_change:
        return {**result, 'label': 'Direct', 'decision': 'publish', 'category': '여행산업',
                'score': 6, 'rules': ['ota_operating_policy_change'],
                'signals': [{'field':'title','terms':ota+policy+policy_change}],
                'evidence_status':'industry_subject_in_feed',
                'reason':'OTA의 구체적인 운영·정산·예약 조건과 실제 변경이 제목에 함께 명시되어 있습니다. 한국 시장 적용 여부는 별도입니다.'}
    company = korean_company_change(title)
    if company:
        return {**result, **company}
    english = english_industry(title)
    if english:
        return {**result, **english}
    # Never combine unrelated sentences into a manufactured causal connection.
    for field, raw in (('title', title), ('description', description)):
        for sentence in re.split(r'[.!?。\n]+', raw):
            text = compact(sentence)
            if matches(text, NEGATIVE):
                continue
            for category, sectors in SECTORS.items():
                sector_hits = matches(text, sectors)
                impacts = {k: matches(text, v) for k, v in IMPACTS.items()}
                targets = [k for k, v in impacts.items() if v]
                if sector_hits and targets:
                    linked = matches(text, LINKS)
                    uncertain = matches(text, UNCERTAIN)
                    return {**result, 'label': 'Indirect', 'decision': 'hold', 'category': category,
                            'score': 6 if linked and not uncertain else 2,
                            'rules': ['cross_sector_impact' if linked else 'cross_sector_unproven'],
                            'signals': [{'field': field, 'terms': sector_hits + [t for v in impacts.values() for t in v] + linked}],
                            'impact_targets': targets,
                            'evidence_status': 'explicit_feed_claim' if linked and not uncertain else 'insufficient',
                            'reason': '다른 산업 변화와 관광산업 영향의 근거를 원문에서 검토한 뒤 승인해야 합니다.'}
    # A generic macro/culture headline cannot become Direct from incidental
    # tourism keywords in a different paragraph.
    cross_headline = (any(matches(fields['title'], terms) for terms in SECTORS.values()) or
                      bool(matches(fields['title'], ('오마카세', '족욕', '맛집', '카페탐방', '차마시'))))
    candidates = []
    for category, terms in SUBJECTS.items():
        for field, raw in (('title', title), ('description', description)):
            # Direct support must also be local to a single sentence.
            contexts = [raw] if field == 'title' else re.split(r'[.!?。\n]+', raw)
            for context in contexts:
                text = compact(context)
                hits = matches(text, terms)
                # The broad English sector name alone is not an industry change.
                # Concrete operational headlines already pass english_industry().
                if hits == ['hospitality']:
                    continue
                if not hits or matches(text, NEGATIVE):
                    continue
                actions = matches(text, ACTIONS)
                entity_only = all(h in ('여행사', '항공사', '관광재단') for h in hits)
                if field == 'title' and entity_only and not actions:
                    continue
                if field == 'title' or len(hits) >= 2 or (hits and actions):
                    candidates.append((4 * len(hits) + (2 if field == 'title' else 0), category, field, hits))
    if cross_headline:
        candidates = [candidate for candidate in candidates if candidate[2] == 'title']
        if not candidates:
            return {**result, 'rules': ['cross_sentence_unproven'],
                    'reason': '다른 산업 기사에서 관광 키워드만으로 영향 관계를 만들지 않습니다.'}
    if candidates:
        # Keep the historical demand-before-statistics priority on tied headlines.
        order = ('인바운드', '관광정책', '경제·시장', '항공·숙박', '여행산업', '문화·트렌드')
        score, category, field, hits = max(candidates, key=lambda c: (c[0], -order.index(c[1])))
        return {**result, 'label': 'Direct', 'decision': 'publish', 'category': category,
                'score': score, 'rules': ['explicit_industry_subject'],
                'signals': [{'field': field, 'terms': hits}],
                'evidence_status': 'industry_subject_in_feed',
                'reason': 'RSS 제목 또는 설명에서 구체적인 관광산업 대상·사업 신호를 확인했습니다.'}
    return result


def approve(assessment, title, url, approval, at, parse_date):
    """Reject stale, unbound, malformed or unsupported indirect approvals."""
    if assessment.get('label') != 'Indirect' or not isinstance(approval, dict):
        return assessment
    valid = (assessment.get('evidence_status') == 'explicit_feed_claim'
             and approval.get('rule_version') == RULE_VERSION
             and approval.get('title_sha256') == title_digest(title)
             and approval.get('evidence_url') == url
             and isinstance(approval.get('reason'), str)
             and len(approval['reason'].strip()) >= 15)
    reviewed_at = parse_date(approval.get('reviewed_at', ''))
    if not valid or reviewed_at is None or reviewed_at > at:
        return assessment
    return {**assessment, 'decision': 'publish', 'review_status': 'approved',
            'review': {k: approval[k] for k in ('reviewed_at', 'evidence_url', 'reason', 'title_sha256', 'rule_version')}}
