"""Six-field link curation. No excerpt, generated prose, image or internal evidence."""
import re

if __package__:
    from .relevance import matches, SUBJECTS
else:
    from relevance import matches, SUBJECTS

PUBLIC_FIELDS = ('title', 'source', 'published_at', 'url', 'category', 'keywords')
TERMS = tuple(dict.fromkeys(term for terms in SUBJECTS.values() for term in terms)) + (
    '방한관광객', '대한항공', '아시아나항공', '제주항공', '진에어', '티웨이', '이스타항공',
    '하나투어', '모두투어', '야놀자', '여기어때', '아고다', '에어비앤비', 'OTA', 'GDS',
    '세이버', '호텔', '크루즈', '인바운드', '취항', '증편', '감편', '발권', '인수', '매출',
    '영업이익', '관광재단', '관광공사', '관광청', 'Korean Air', 'Booking', 'Expedia', 'Trip.com',
    'MICE', '가업상속공제', '의료친화 숙박시설', '탑승률')


# Literal industry phrases and identified tourism businesses only. No inferred
# locations, translated topics, generic financial verbs, product names or AI tags.
ENGLISH_TERMS = (
    'Air Passenger Demand', 'Air Passengers', 'Airline Routes', 'Business Travel',
    'Travel Technology', 'Hospitality Operations', 'Hotel Industry', 'Hotel Market',
    'Hotel Technology', 'Hospitality', 'Hotels', 'Hotel',
    'Booking Holdings', 'Expedia Group', 'Trip.com Group', 'Korean Air', 'Asiana Airlines',
    'Grand Hyatt', 'Hyatt', 'IHG', 'Kimpton', 'Accor', 'Corinthia Group', 'Hilton', 'Marriott',
)

# Retain the existing English industry vocabulary with proper matching. The
# standalone word 'Booking' is ambiguous; require the identified company name.
ENGLISH_TERMS = tuple(dict.fromkeys(
    [term for term in TERMS if re.fullmatch(r'[A-Za-z][A-Za-z .-]*', term) and term != 'Booking']
    + list(ENGLISH_TERMS)))


def keywords(title):
    """Preserve legacy Korean terms; add literal MICE and coverage vocabulary.

    Longest overlapping phrase wins. Preserve the headline's spelling/case and
    never derive a keyword from source, category, description or editorial tier.
    """
    if re.search(r'[가-힣]', title):
        # The legacy matcher expects folded input; changing it globally would
        # alter existing OTA/GDS tags. Match this new acronym literally instead.
        terms = matches(title, TERMS) + re.findall(r'(?<!\w)MICE(?!\w)', title)
        return sorted(set(terms), key=lambda s: (-len(s), s))[:8]
    candidates = []
    for term in ENGLISH_TERMS:
        pattern = r'(?<!\w)' + r'\s+'.join(re.escape(w) for w in term.split()) + r'(?!\w)'
        candidates.extend(re.finditer(pattern, title, re.I))
    selected = []
    for match in sorted(candidates, key=lambda m: (-(m.end()-m.start()), m.start())):
        if not any(match.start() < old.end() and old.start() < match.end() for old in selected):
            selected.append(match)
    unique = {}
    for match in selected:
        value = match.group()
        unique.setdefault(value.casefold(), value)
    return sorted(unique.values(), key=lambda s: (-len(s), s))[:8]


def public_record(record):
    """Allowlist, never copy arbitrary source fields (including old desc/insight)."""
    return {**{key: record[key] for key in PUBLIC_FIELDS if key != 'keywords'},
            'keywords': keywords(record['title'])}
