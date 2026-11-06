"""ECOS general-travel mapping readiness: authenticated, read-only metadata review.

Builds an ephemeral mapping from verified ECOS metadata, then checks that it
satisfies the production adapter's exact matching contract. Never persists it,
fetches monetary amounts, grants rights, or changes public operational files.
"""
import datetime as dt
import os
import re
from pathlib import Path

from . import ecos
from .ecos_preflight import Inspector, diagnostic, diagnostic_line, safe_error

ROOT = Path(__file__).resolve().parents[2]
KST = dt.timezone(dt.timedelta(hours=9))
TABLE = '301Y013'
UNIT = '백만달러'
# Official paths from successful ECOS Preflight 42165343790.
# All nodes are checked against the authenticated live ItemList before use.
EXPECTED = {
    'kto_tourism_receipts': (
        ('000000', '경상수지'),
        ('200000', '서비스수지'),
        ('2C0000', '여행수지'),
        ('2C1000', '여행수입'),
        ('2C1Y00', '일반여행수입'),
    ),
    'kto_tourism_expenditure': (
        ('000000', '경상수지'),
        ('200000', '서비스수지'),
        ('2C0000', '여행수지'),
        ('2C2000', '여행지급'),
        ('2C2Y00', '일반여행지급'),
    ),
}
FIXED_ERRORS = frozenset({
    'ecos_readiness_invalid_table', 'ecos_readiness_invalid_group',
    'ecos_readiness_invalid_hierarchy', 'ecos_readiness_invalid_unit',
    'ecos_readiness_invalid_coverage', 'ecos_readiness_incompatible_adapter',
    'ecos_readiness_auth_missing', 'ecos_readiness_failed',
})


def fail(code):
    raise ecos.EcosError(code)


def inspect_mapping(client, inspector, now):
    """Validate metadata and ephemeral adapter compatibility; no value query."""
    doc = ecos.metadata(client, TABLE)
    raw_tables, raw_items = doc['tables'], doc['items']
    catalogue = inspector.catalogue(raw_tables)
    table = catalogue.get(TABLE)
    if not table or not table['searchable'] or 'M' not in table['cycles']:
        fail('ecos_readiness_invalid_table')
    normalized_title = re.sub(r'^[0-9.]+', '', re.sub(r'\s+', '', table['name']))
    if normalized_title != '국제수지':
        fail('ecos_readiness_invalid_table')

    parsed = inspector.items(table, raw_items)
    if set(parsed['groups']) != {'Group1'}:
        fail('ecos_readiness_invalid_group')

    lookup = {}
    for raw in raw_items:
        if raw.get('CYCLE') != 'M':
            continue
        if raw.get('GRP_CODE') != 'Group1':
            fail('ecos_readiness_invalid_group')
        code = inspector.code(raw.get('ITEM_CODE'), field='ITEM_CODE')
        if code in lookup:
            fail('ecos_readiness_invalid_hierarchy')
        # The parser validates all names, parents, and forbidden metadata.
        name = inspector.text(raw.get('ITEM_NAME'), field='ITEM_NAME')
        parent = (inspector.code(raw['P_ITEM_CODE'], field='P_ITEM_CODE')
                  if raw.get('P_ITEM_CODE') else None)
        parent_name = (inspector.text(raw['P_ITEM_NAME'], field='P_ITEM_NAME')
                       if raw.get('P_ITEM_NAME') else None)
        lookup[code] = (raw, name, parent, parent_name)

    selectors = {}
    for indicator_id, expected_path in EXPECTED.items():
        chain = []
        parent_code = None
        parent_name = None
        for code, expected_name in expected_path:
            node = lookup.get(code)
            if node is None:
                fail('ecos_readiness_invalid_hierarchy')
            raw, normalized, actual_parent, actual_parent_name = node
            if normalized != expected_name or actual_parent != parent_code:
                fail('ecos_readiness_invalid_hierarchy')
            if parent_code is not None and actual_parent_name not in (None, parent_name):
                fail('ecos_readiness_invalid_hierarchy')
            if raw.get('STAT_CODE') != TABLE:
                fail('ecos_readiness_invalid_hierarchy')
            if inspector.text(raw.get('STAT_NAME'), field='STAT_NAME') != table['name']:
                fail('ecos_readiness_invalid_table')
            chain.append({'code': code, 'name': raw['ITEM_NAME']})
            parent_code, parent_name = code, normalized

        leaf = lookup[expected_path[-1][0]][0]
        if inspector.text(leaf.get('UNIT_NAME'), field='UNIT_NAME') != UNIT:
            fail('ecos_readiness_invalid_unit')
        start, end = ecos.period(leaf.get('START_TIME')), ecos.period(leaf.get('END_TIME'))
        if start > end or start >= now.strftime('%Y-%m'):
            fail('ecos_readiness_invalid_coverage')
        selectors[indicator_id] = {'selectors': [{'group': 'Group1', 'path': chain}]}

    matched = {i['code']: i for i in parsed['items']}
    for indicator_id, expected_path in EXPECTED.items():
        last = expected_path[-1][0]
        row = matched.get(last)
        direction = ('receipts_candidate' if indicator_id == 'kto_tourism_receipts'
                     else 'expenditure_candidate')
        if (not row or row['direction'] != direction
                or row['unit'] != UNIT or not row['metadata_complete']):
            fail('ecos_readiness_invalid_hierarchy')

    # The actual raw table/ItemList spelling is retained only in memory.
    # The verified marker is ephemeral for local schema validation only:
    # operational mapping/rights/crosscheck remain untouched and pending.
    mapping = dict(status='verified', evidence_url=ecos.BASE,
                   verified_at=now.date().isoformat(),
                   stat_code=TABLE, stat_name=table['raw_name'],
                   frequency='M', unit_name=UNIT, series=selectors)
    try:
        source = {'mapping': mapping}
        ecos.mapping(source)
        coverage = ecos.validate_metadata(mapping, raw_tables, raw_items)
    except (ValueError, KeyError, TypeError):
        fail('ecos_readiness_incompatible_adapter')
    if set(coverage) != set(EXPECTED):
        fail('ecos_readiness_invalid_coverage')
    if any(start > end or end >= now.strftime('%Y-%m') for start, end in coverage.values()):
        fail('ecos_readiness_invalid_coverage')

    return dict(
        metadata_contract='passed',
        stat_code=TABLE, unit=UNIT, frequency='M',
        coverage={k: list(v) for k, v in coverage.items()},
        rights_review='pending_official_scope',
        kto_provenance='pending_original_export',
        operational_approval='not_granted',
    )


def safe_reason(exc):
    if isinstance(exc, ecos.EcosError) and str(exc) in FIXED_ERRORS:
        return str(exc)
    result = safe_error(exc)
    return result if result != 'preflight_failed' else 'ecos_readiness_failed'


def render(result=None, error=None, details=None):
    rows = [
        '# ECOS Activation Readiness',
        '',
        '- 용도: 일반여행수입·지급 운영 매핑 사전검증 (읽기 전용)',
        '- 공식 통계표: 301Y013 / 주기: M / 단위: 백만달러',
        '- 일반여행수입: Group1 2C1Y00 / 일반여행지급: Group1 2C2Y00',
        '- 소유권·이용조건: 별도 검토 필요 (한국은행 공식 방침 참조)',
        '- KTO 파일 공식 출처·빈티지: 확인 대기',
        '- 수집 승인: not_granted / 게시 승인: not_granted',
        '- 운영 source/indicator: disabled 유지',
        '',
    ]
    if error:
        rows.extend(['- 메타데이터 검증: failed', '- 오류: '+(
            error if error in FIXED_ERRORS else 'ecos_readiness_failed')])
        if details:
            rows.append(diagnostic_line(details))
    else:
        rows.append('- 메타데이터 및 기존 ECOS 수집기 매핑 계약: passed')
        for label, key in (('관광수입', 'kto_tourism_receipts'),
                           ('관광지출', 'kto_tourism_expenditure')):
            first, last = result['coverage'][key]
            rows.append('- '+label+' 수록기간: '+first+'~'+last)
    rows.extend([
        '',
        '- 한국은행 저작권보호방침: https://www.bok.or.kr/portal/main/contents.do?menuNo=200228',
        '- KTO 관광수지 정의: https://datalab.visitkorea.or.kr/datalab/portal/ts/getKorTursmBalcForm.do',
        '- 이번 작업은 StatisticTableList·StatisticItemList만 사용하며 수치를 요청하지 않았습니다.',
        '- 인증 URL·원본 응답·원본 명칭·ECOS_API_KEY·금액을 출력하지 않습니다.',
        '- 메타데이터 계약 통과는 수집·게시 허가나 이용조건 승인과 별개입니다.',
    ])
    return '\n'.join(rows)+'\n'


def main():
    summary = os.environ.get('GITHUB_STEP_SUMMARY', '')
    if not summary:
        return 1
    path = Path(summary).resolve()
    if path == ROOT or ROOT in path.parents:
        return 1
    path.write_text('# ECOS Activation Readiness\n\n검증 미완료\n', encoding='utf-8')
    secret = os.environ.get('ECOS_API_KEY', '')
    result, error, details = None, None, None
    try:
        if not secret:
            fail('ecos_readiness_auth_missing')
        inspector = Inspector(secret)
        result = inspect_mapping(ecos.Client(), inspector, dt.datetime.now(KST))
    except Exception as exc:
        error, details = safe_reason(exc), diagnostic(exc)
    body = render(result, error, details)
    if secret and any(t in body for t in Inspector(secret).tokens):
        path.write_text('# ECOS Activation Readiness\n\n진단 비공개\n', encoding='utf-8')
        return 1
    path.write_text(body, encoding='utf-8')
    print('ECOS metadata readiness check finished; see safe Actions Summary.')
    return 0 if result is not None else 1


if __name__ == '__main__':
    raise SystemExit(main())
