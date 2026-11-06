"""Manual, read-only candidate comparison. Never approves/collects production data.

The key and all responses stay within the Actions process. Only fixed-schema
comparison outcomes reach Summary; no monetary values, names or raw API payloads.
"""
import datetime as dt
import json
import os
import re
from decimal import Decimal, localcontext
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from . import ecos
from .model import valid_period, months, month_before
from .ecos_preflight import Inspector, MetadataValidationError, diagnostic, diagnostic_line, safe_error, cell

ROOT=Path(__file__).resolve().parents[2]
KST=dt.timezone(dt.timedelta(hours=9))
CANDIDATES={
    '301Y013':{'title':'국제수지','codes':{'receipts':'2C1Y00','expenditure':'2C2Y00'}},
    '301Y014':{'title':'서비스무역세분류통계','codes':{'receipts':'SDA200','expenditure':'SDB200'}},
}
REFERENCE=ROOT/'docs/ecos-candidate-validation/kto-reference.json'
ERRORS=frozenset({'candidate_table_invalid','candidate_selection_invalid','candidate_period_invalid',
    'candidate_period_unavailable','candidate_period_limit','candidate_series_invalid',
    'candidate_duplicate_or_future_period','candidate_empty_series','kto_reference_invalid',
    'ecos_unit_or_amount_invalid','ecos_amount_invalid','ecos_amount_precision_or_range_invalid',
    'invalid_period','ecos_month_invalid','candidate_verification_failed','candidate_amount_invalid'})


def fail(code):raise ecos.EcosError(code)


def safe_code(exc):
    if isinstance(exc,ecos.EcosError) and str(exc) in ERRORS:return str(exc)
    result=safe_error(exc)
    return result if result!='preflight_failed' else 'candidate_verification_failed'


def candidate_metadata(client,inspector,code):
    config=CANDIDATES[code];doc=ecos.metadata(client,code)
    catalog=inspector.catalogue(doc['tables']);table=catalog.get(code)
    if (not table or not table['searchable'] or 'M' not in table['cycles']
            or re.sub(r'^[0-9.]+','',re.sub(r'\s+','',table['name']))!=config['title']):fail('candidate_table_invalid')
    parsed=inspector.items(table,doc['items'])
    if set(parsed['groups'])!={'Group1'}:fail('candidate_selection_invalid')
    selected={}
    for kind,item_code in config['codes'].items():
        found=[i for i in parsed['items'] if i['group']=='Group1' and i['code']==item_code]
        if len(found)!=1:fail('candidate_selection_invalid')
        item=found[0]
        expected='receipts_candidate' if kind=='receipts' else 'expenditure_candidate'
        if item['direction']!=expected or item['unit']!='백만달러' or not item['metadata_complete']:fail('candidate_selection_invalid')
        start,end=ecos.period(item['start']),ecos.period(item['end'])
        if start>end:fail('candidate_selection_invalid')
        selected[kind]=dict(code=item_code,name=item['name'],start=start,end=end)
    return dict(code=code,name=table['name'],series=selected)


def period_range(meta,start,end,now):
    earliest=max(i['start'] for m in meta.values() for i in m['series'].values())
    latest=min(i['end'] for m in meta.values() for i in m['series'].values())
    latest=min(latest,month_before(now.strftime('%Y-%m')))
    end=valid_period(end) if end else latest
    if start:start=valid_period(start)
    else:
        start=end
        for _ in range(11):start=month_before(start)
        start=max(start,earliest,'2021-01')
    if start>end or end>=now.strftime('%Y-%m'):fail('candidate_period_invalid')
    if start<earliest or end>latest:fail('candidate_period_unavailable')
    if len(months(start,end))>24:fail('candidate_period_limit')
    return start,end


def monetary(raw, unit):
    # Verification is Decimal in millions, independent of the integer ledger.
    if unit not in ('백만달러','천 US$') or not isinstance(raw,str) or len(raw)>64 or not re.fullmatch(r'\d+(?:\.\d+)?',raw):
        fail('candidate_amount_invalid')
    with localcontext() as ctx:
        ctx.prec=80
        value=Decimal(raw)
        return value if unit=='백만달러' else value/Decimal(1000)


def values(client,inspector,meta,kind,start,end,now):
    selector=meta['series'][kind]
    rows=client.rows('StatisticSearch',meta['code'],'M',start.replace('-',''),end.replace('-',''),selector['code'])
    out={};seen=set()
    for row in rows:
        for field,actual,expected in (
            ('STAT_CODE',row.get('STAT_CODE'),meta['code']),
            ('STAT_NAME',inspector.text(row.get('STAT_NAME'),field='STAT_NAME'),meta['name']),
            ('UNIT_NAME',row.get('UNIT_NAME'),'백만달러'),
            ('ITEM_CODE',row.get('ITEM_CODE1'),selector['code']),
            ('ITEM_NAME',inspector.text(row.get('ITEM_NAME1'),field='ITEM_NAME'),selector['name'])):
            if actual!=expected:raise MetadataValidationError(field,'table_mismatch','candidate_series_invalid')
        if any(row.get(k+str(n)) not in (None,'') for n in (2,3,4) for k in ('ITEM_CODE','ITEM_NAME')):
            raise MetadataValidationError('GRP_CODE','invalid_group','candidate_series_invalid')
        p=ecos.period(row.get('TIME'))
        if p in seen or not start<=p<=end or p>=now.strftime('%Y-%m'):fail('candidate_duplicate_or_future_period')
        seen.add(p)
        if row.get('DATA_VALUE') in (None,''):continue
        out[p]=monetary(row['DATA_VALUE'],'백만달러')
    if not out:fail('candidate_empty_series')
    return out


def references(doc,now):
    """Only a code-reviewed official KTO export reference, never TOURGO/fixtures.

    No runtime downloader or arbitrary URL/path input. The file is absent until
    a separate evidence review supplies it; absence means crosscheck pending.
    """
    if doc is None:return {}
    try:
        if doc['data_origin']!='official_kto_export' or doc['definition']!='general_travel' or doc['reference_review']!='official_file_verified':fail('kto_reference_invalid')
        if doc['unit'] not in ('백만달러','천 US$'):fail('kto_reference_invalid')
        u=urlsplit(doc['source_url']);q=parse_qs(u.query)
        if (u.scheme!='https' or u.hostname!='datalab.visitkorea.or.kr' or u.username or u.password or u.port not in (None,443)
            or u.path not in ('/site/portal/ex/bbs/View.do','/common/board/Download.do')
            or not set(q)<= {'bcIdx','cbIdx','streFileNm','pageIndex','cateCont'}
            or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}',v) for vs in q.values() for v in vs)):fail('kto_reference_invalid')
        if not re.fullmatch(r'[a-f0-9]{64}',doc['source_sha256']):fail('kto_reference_invalid')
        published=dt.datetime.fromisoformat(doc['published_at']);checked=dt.datetime.fromisoformat(doc['verified_at'])
        if not published.tzinfo or not checked.tzinfo or published>checked or checked>now:fail('kto_reference_invalid')
        if doc['finality'] not in ('provisional','final','not_stated'):fail('kto_reference_invalid')
        if not isinstance(doc['observations'],list) or not 1<=len(doc['observations'])<=120:fail('kto_reference_invalid')
        result={}
        for row in doc['observations']:
            p=valid_period(row['period'])
            if p in result or p>=now.strftime('%Y-%m'):fail('kto_reference_invalid')
            result[p]={kind:monetary(row[kind],doc['unit']) for kind in ('receipts','expenditure')}
        return result
    except Exception:raise ecos.EcosError('kto_reference_invalid') from None


def compare(client,inspector,now,start='',end='',kto=None):
    ref=references(kto,now)
    meta={code:candidate_metadata(client,inspector,code) for code in CANDIDATES}
    start,end=period_range(meta,start,end,now)
    series={code:{kind:values(client,inspector,m,kind,start,end,now) for kind in ('receipts','expenditure')} for code,m in meta.items()}
    result=dict(status='comparison_completed',start=start,end=end,unit='백만달러',operational_approval='not_granted',
        kto_status='reference_missing' if not ref else 'reviewed_reference_compared',
        metadata={code:{kind:[i['start'],i['end']] for kind,i in m['series'].items()} for code,m in meta.items()},rows=[])
    for p in months(start,end):
        row=dict(period=p,candidate={},kto={})
        for kind in ('receipts','expenditure'):
            a,b=(series[c][kind].get(p) for c in CANDIDATES)
            row['candidate'][kind]='missing' if a is None or b is None else 'equal_at_current_query' if a==b else 'difference_requires_definition_or_vintage_review'
            k=ref.get(p,{}).get(kind)
            row['kto'][kind]='reference_missing' if k is None else 'ecos_missing' if a is None else 'value_equal_vintage_not_equivalent' if a==k else 'value_difference_vintage_review_required'
        result['rows'].append(row)
    if any('missing'==v for r in result['rows'] for v in r['candidate'].values()):result['status']='partial_missing'
    if kto is not None:
        result['kto_publication_date']=dt.datetime.fromisoformat(kto['published_at']).date().isoformat()
        result['kto_finality']=kto['finality']
        covered=sum(r['period'] in ref for r in result['rows'])
        result['kto_status']='reference_periods_unavailable' if not covered else 'partial_reference_coverage' if covered<len(result['rows']) else 'reviewed_reference_compared'
    return result


def summary(result):
    out=['# ECOS Candidate Comparison','',
        '- 출처: 한국은행 ECOS (https://ecos.bok.or.kr/)',
        '- 우선 검증 대상: 301Y013 / 비교 대상: 301Y014 (운영 매핑 승인 아님)',
        '- 상태: '+cell(result['status']),'- 301Y013 원천 적합성: review_required (KTO·빈티지 근거 검토 필요)', '- 운영 승인: not_granted']
    if 'error' in result:
        out.append('- 오류: '+cell(result['error']))
        if result.get('error_diagnostic'):out.append(diagnostic_line(result['error_diagnostic']))
    else:
        out+=['- 비교 기간: '+result['start']+'~'+result['end'],'- 단위: 백만달러 (Decimal 정확 대조, 천 US$는 1,000으로 나눔)',
            '- 각 표의 공식 명칭·월간 계층·Group1 수입/지급·원 단위 검증 통과',
            '- KTO: '+cell(result['kto_status']),
            '- KTO 공식 정의: https://datalab.visitkorea.or.kr/datalab/portal/ts/getKorTursmBalcForm.do',
            '- ECOS 개별 잠정/확정 및 공식 공표일: API 미표기. 조회시각을 공표일로 대체하지 않음.']
        if 'kto_publication_date' in result:out.append('- KTO 참고 자료 공표일: '+result['kto_publication_date']+' / '+result['kto_finality'])
        for code,kinds in result['metadata'].items():
            for kind,span in kinds.items():out.append('- '+code+' / '+kind+' 수록기간: '+'~'.join(span))
        out+=['','| 기간 | 두 표 수입 비교 | 두 표 지급 비교 | 301Y013-KTO 수입 | 301Y013-KTO 지급 |', '| --- | --- | --- | --- | --- |']
        for r in result['rows']:out.append('| '+' | '.join(cell(x) for x in [r['period'],r['candidate']['receipts'],r['candidate']['expenditure'],r['kto']['receipts'],r['kto']['expenditure']])+' |')
    out+=['','- equal은 이번 조회 값의 동일성만 뜻합니다. 다른 공표시점·정정·정의의 동등성을 증명하지 않습니다.',
        '- 두 표의 차이를 정정 때문이라고 단정하지 않습니다. 정의·계상 범위·공표 빈티지를 별도로 검토해야 합니다.',
        '- KTO 근거가 없으면 교차검증 미완료. 301Y013 적합성 확정·수집 성공·운영 연동 완료가 아닙니다.',
        '- 기존 Preflight review_required, source 설정·승인·원장·data/live·Pages는 변경하지 않았습니다.']
    return '\n'.join(out)+'\n'


def main():
    path=Path(os.environ.get('GITHUB_STEP_SUMMARY','')).resolve()
    if not os.environ.get('GITHUB_STEP_SUMMARY') or path==ROOT or ROOT in path.parents:return 1
    path.write_text('# ECOS Candidate Comparison\n\n검증 미완료. 중단 시 workflow 상태를 확인하세요.\n')
    key=os.environ.get('ECOS_API_KEY','')
    try:
        doc=None
        if REFERENCE.exists():
            if REFERENCE.is_symlink() or REFERENCE.stat().st_size>200000:fail('kto_reference_invalid')
            doc=json.loads(REFERENCE.read_text())
        result=compare(ecos.Client(),Inspector(key),dt.datetime.now(KST),os.environ.get('ECOS_COMPARE_START',''),os.environ.get('ECOS_COMPARE_END',''),doc)
    except Exception as exc:
        result=dict(status='validation_failed',error=safe_code(exc))
        if diagnostic(exc):result['error_diagnostic']=diagnostic(exc)
    body=summary(result)
    if key and any(t in body for t in Inspector(key).tokens):
        path.write_text('# ECOS Candidate Comparison\n\n결과 안전성 검증 실패. 공개 보류.\n');return 1
    path.write_text(body)
    print('Candidate comparison finished. See the safe Actions Summary.')
    return 0 if result['status']=='comparison_completed' else 1


if __name__=='__main__':raise SystemExit(main())
