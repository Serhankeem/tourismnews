"""Actions-only, metadata-only inspection. No collectors, raw files or activation.

The sole public output is a bounded, allowlisted and escaped Actions Summary.
The existing ECOS metadata client keeps HTTPS/robots/retry and key safeguards.
"""
import base64
import html
import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote
from .ecos import Client, EcosError, FACTORS, metadata

ROOT = Path(__file__).resolve().parents[2]
TABLE_CODE = re.compile(r'\d{3}[A-Z]\d{3}')
TOPICS = ('국제수지', '일반여행', '여행수지', '관광수지')
SAFE_ERRORS = frozenset({
    'ecos_auth_required', 'ecos_auth_invalid', 'ecos_auth_or_access_denied',
    'ecos_rate_limited', 'ecos_query_timeout', 'ecos_period_format_invalid',
    'ecos_api_error', 'ecos_robots_invalid', 'ecos_robots_unavailable',
    'ecos_robots_disallowed', 'ecos_deferred_fetch_required', 'ecos_response_too_large',
    'ecos_redirect_blocked', 'ecos_network_or_tls_failure', 'ecos_json_invalid',
    'ecos_response_invalid', 'ecos_total_or_pagination_invalid', 'ecos_pagination_incomplete',
    'ecos_row_limit', 'ecos_unexpected_credential_in_response', 'ecos_request_not_allowlisted',
    'preflight_unsafe_metadata', 'preflight_catalogue_invalid', 'preflight_empty_catalogue',
    'preflight_no_candidates', 'preflight_table_mismatch', 'preflight_items_invalid',
    'preflight_duplicate_item', 'preflight_missing_parent', 'preflight_parent_cycle',
    'preflight_parent_name_mismatch', 'preflight_report_limit', 'preflight_failed',
})


SAFE_FIELDS = frozenset({'unknown','record','catalogue','items','STAT_CODE','P_STAT_CODE',
    'STAT_NAME','CYCLE','GRP_CODE','ITEM_CODE','ITEM_NAME','P_ITEM_CODE','P_ITEM_NAME',
    'UNIT_NAME','START_TIME','END_TIME'})
SAFE_CLASSIFICATIONS = frozenset({'validation_failed','invalid_type','invalid_length',
    'empty_value','unsafe_content','invalid_code','missing_field','invalid_format',
    'duplicate_code','invalid_collection','invalid_group','table_mismatch','period_order'})


class MetadataValidationError(EcosError):
    """No raw value in args/attributes. Public diagnostics are fixed enums only."""
    def __init__(self, field, classification, code='preflight_unsafe_metadata'):
        super().__init__(code)
        self.field = field
        self.classification = classification


def diagnostic(exc):
    if not isinstance(exc, MetadataValidationError):return None
    field,kind=getattr(exc,'field',None),getattr(exc,'classification',None)
    if type(field) is str and field in SAFE_FIELDS and type(kind) is str and kind in SAFE_CLASSIFICATIONS:
        return {'field':field,'classification':kind}
    return {'field':'unknown','classification':'validation_failed'}


def required(row, field):
    if not isinstance(row,dict):raise MetadataValidationError('record','invalid_type')
    if field not in row:raise MetadataValidationError(field,'missing_field')
    return row[field]


def safe_error(exc):
    # Even unexpected EcosError objects must not echo arbitrary text/URLs.
    return str(exc) if isinstance(exc, EcosError) and str(exc) in SAFE_ERRORS else 'preflight_failed'


class Inspector:
    def __init__(self, secret):
        self.tokens = [secret] if secret else []
        if secret:
            encoded=[base64.b64encode(secret.encode()).decode(),base64.urlsafe_b64encode(secret.encode()).decode()]
            self.tokens += encoded+[value.rstrip('=') for value in encoded]+[secret.encode().hex(),secret.encode().hex().upper()]

    def text(self, raw, limit=200, empty=False, field='unknown'):
        if not isinstance(raw,str):raise MetadataValidationError(field,'invalid_type')
        if len(raw)>limit:raise MetadataValidationError(field,'invalid_length')
        if not raw.strip() and not empty:raise MetadataValidationError(field,'empty_value')
        decoded = raw
        for _ in range(3):
            decoded = unicodedata.normalize('NFKC', html.unescape(unquote(decoded)))
        if ('\\' in raw or re.search(r'%[0-9a-fA-F]{2}|&(?:#[a-zA-Z0-9]+|[a-zA-Z]+);',raw)
                or any(t in decoded for t in self.tokens)
                or any(unicodedata.category(c).startswith('C') for c in decoded)
                or re.search(r'(?i)://|https?\s*:|www\.|/api/|<[^>]*>', decoded)):
            raise MetadataValidationError(field,'unsafe_content')
        return raw.strip()

    def code(self, raw, field='unknown'):
        value = self.text(raw, 20, field=field)
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,20}', value):
            raise MetadataValidationError(field,'invalid_code')
        return value

    def catalogue_parent(self, raw):
        """Only TableList's literal root parent marker; never a real code."""
        if raw is None or raw=='':return None
        self.text(raw,20,field='P_STAT_CODE')  # Run all content/Secret guards first.
        if raw=='*':return None
        return self.code(raw,field='P_STAT_CODE')

    def catalogue(self, rows):
        if not isinstance(rows, list) or len(rows)>5000:
            raise MetadataValidationError('catalogue','invalid_collection','preflight_catalogue_invalid')
        result = {}
        for raw in rows:
            code = self.code(required(raw,'STAT_CODE'),field='STAT_CODE')
            if code in result:
                raise MetadataValidationError('STAT_CODE','duplicate_code','preflight_catalogue_invalid')
            cycle = self.text(raw.get('CYCLE') or '', 30, empty=True,field='CYCLE')
            if not re.fullmatch(r'[A-Z,\s]*', cycle):
                raise MetadataValidationError('CYCLE','invalid_format','preflight_catalogue_invalid')
            result[code] = dict(code=code, name=self.text(required(raw,'STAT_NAME'),field='STAT_NAME'),
                parent=self.catalogue_parent(raw.get('P_STAT_CODE')),
                cycles=[c.strip() for c in cycle.split(',') if c.strip()], searchable=raw.get('SRCH_YN')=='Y')
        return result

    def candidates(self, catalogue):
        selected = {code for code, row in catalogue.items() if any(t in re.sub(r'\s+', '', row['name']) for t in TOPICS)}
        while True:
            extra = {code for code,row in catalogue.items() if row['parent'] in selected}-selected
            if not extra:break
            selected |= extra
        candidates = [r for code,r in catalogue.items() if code in selected and TABLE_CODE.fullmatch(code) and r['searchable'] and 'M' in r['cycles']]
        return sorted(candidates, key=lambda r:('일반여행' not in r['name'],r['code']))

    def items(self, table, rows):
        if not isinstance(rows,list) or len(rows)>5000:
            raise MetadataValidationError('items','invalid_collection','preflight_items_invalid')
        lookup = {}
        groups = {}
        for raw in rows:
            for field in ('STAT_CODE','STAT_NAME'):
                if required(raw,field)!=table['code' if field=='STAT_CODE' else 'name']:
                    raise MetadataValidationError(field,'table_mismatch','preflight_table_mismatch')
            if raw.get('CYCLE')!='M':continue
            group=self.code(required(raw,'GRP_CODE'),field='GRP_CODE')
            if group not in ('Group1','Group2','Group3','Group4'):
                raise MetadataValidationError('GRP_CODE','invalid_group','preflight_items_invalid')
            code=self.code(required(raw,'ITEM_CODE'),field='ITEM_CODE');key=(group,code)
            if key in lookup:raise MetadataValidationError('ITEM_CODE','duplicate_code','preflight_duplicate_item')
            row=dict(group=group,code=code,name=self.text(required(raw,'ITEM_NAME'),field='ITEM_NAME'),
                parent=self.code(raw['P_ITEM_CODE'],field='P_ITEM_CODE') if raw.get('P_ITEM_CODE') else None,
                parent_name=self.text(raw['P_ITEM_NAME'],field='P_ITEM_NAME') if raw.get('P_ITEM_NAME') else None,
                unit=self.text(raw.get('UNIT_NAME') or '',80,empty=True,field='UNIT_NAME'),
                start=self.text(raw.get('START_TIME') or '',6,empty=True,field='START_TIME'),
                end=self.text(raw.get('END_TIME') or '',6,empty=True,field='END_TIME'))
            for field,period_key in (('START_TIME','start'),('END_TIME','end')):
                value=row[period_key]
                if value and not re.fullmatch(r'\d{4}(?:0[1-9]|1[0-2])',value):raise MetadataValidationError(field,'invalid_format','preflight_items_invalid')
            if row['start'] and row['end'] and row['start']>row['end']:raise MetadataValidationError('END_TIME','period_order','preflight_items_invalid')
            lookup[key]=row;groups[group]=groups.get(group,0)+1
        found=[]
        for row in lookup.values():
            if '일반여행' not in re.sub(r'\s+', '',row['name']):continue
            path=[];current=row;seen=set()
            while current:
                key=(current['group'],current['code'])
                if key in seen:raise EcosError('preflight_parent_cycle')
                seen.add(key);path.append(current)
                parent=lookup.get((current['group'],current['parent'])) if current['parent'] else None
                if current['parent'] and not parent:raise EcosError('preflight_missing_parent')
                if parent and current['parent_name'] and current['parent_name']!=parent['name']:raise EcosError('preflight_parent_name_mismatch')
                current=parent
            path.reverse();names=[p['name'] for p in path];direction='direction_unverified'
            if not any('유학' in name for name in names):
                signs={(('수입' in name),('지급' in name)) for name in names}
                exclusive=signs & {(True,False),(False,True)}
                if exclusive=={(True,False)}:direction='receipts_candidate'
                elif exclusive=={(False,True)}:direction='expenditure_candidate'
            found.append(dict(group=row['group'],code=row['code'],name=row['name'],parent=row['parent'],unit=row['unit'],start=row['start'],end=row['end'],
                path=' → '.join(p['code']+': '+p['name'] for p in path),direction=direction,
                metadata_complete=bool(row['unit'] and row['start'] and row['end'])))
        if len(found)>60 or any(len(r['path'])>4000 for r in found):raise EcosError('preflight_report_limit')
        return dict(groups=groups,items=found)


def inspect(client, inspector, max_tables=12):
    if max_tables not in (6,12,24):raise EcosError('preflight_failed')
    result=dict(authentication='not_verified',status='incomplete',catalogue_count=0,candidate_count=0,tables=[],errors=[])
    try:
        catalogue=inspector.catalogue(metadata(client)['tables'])
        if not catalogue:raise EcosError('preflight_empty_catalogue')
        result.update(authentication='verified_catalogue',catalogue_count=len(catalogue))
        candidates=inspector.candidates(catalogue)
        result['candidate_count']=len(candidates)
        if not candidates:raise EcosError('preflight_no_candidates')
        if len(candidates)>100:raise EcosError('preflight_report_limit')
        for table in candidates[:max_tables]:
            report={k:table[k] for k in ('code','name','cycles')}
            try:
                detail=metadata(client,table['code'])
                check=inspector.catalogue(detail['tables']).get(table['code'])
                if not check or any(check[k]!=table[k] for k in ('name','cycles','searchable')):raise EcosError('preflight_table_mismatch')
                report.update(inspector.items(table,detail['items']),status='inspected')
            except Exception as exc:
                report.update(status='failed',error=safe_error(exc))
                if diagnostic(exc):report['error_diagnostic']=diagnostic(exc)
            result['tables'].append(report)
            if report.get('error')=='ecos_auth_invalid':result['authentication']='rejected_after_catalogue'
            elif report.get('error')=='ecos_auth_or_access_denied':result['authentication']='access_denied_after_catalogue'
            if report.get('error') in ('ecos_auth_invalid','ecos_auth_or_access_denied','ecos_rate_limited','ecos_robots_disallowed'):break
        result['status']='inspection_complete' if len(result['tables'])==len(candidates) and all(t['status']=='inspected' for t in result['tables']) else 'partial'
    except Exception as exc:
        result['errors'].append(safe_error(exc));result['status']='failed'
        if diagnostic(exc):result['error_diagnostic']=diagnostic(exc)
        if isinstance(exc,EcosError) and str(exc)=='ecos_auth_invalid':result['authentication']='rejected'
        elif isinstance(exc,EcosError) and str(exc)=='ecos_auth_or_access_denied':result['authentication']='access_denied'
    return result


def assessment(result):
    """A successful request is not a verified receipt/payment metadata pair."""
    if result['status']!='inspection_complete':return 'incomplete'
    found=[i for t in result['tables'] for i in t.get('items',[])]
    if not found:return 'not_found'
    if len(found)!=2:return 'review_required'
    for table in result['tables']:
        rows=table.get('items',[])
        if (len(rows)==2 and len(table['groups'])==1
                and all(i['metadata_complete'] for i in rows)
                and {i['direction'] for i in rows}=={'receipts_candidate','expenditure_candidate'}
                and len({i['unit'] for i in rows})==1 and rows[0]['unit'] in FACTORS):
            return 'pair_candidates_found'
    return 'review_required'


def cell(value):
    value=html.escape(str(value),quote=True)
    return re.sub(r'([\\`*_{}\[\]()#+!|])',r'\\\1',value)


def diagnostic_line(value):
    # Recheck enums at render time; never stringify arbitrary diagnostics.
    if not isinstance(value,dict):value={}
    field,kind=value.get('field'),value.get('classification')
    if type(field) is not str or field not in SAFE_FIELDS or type(kind) is not str or kind not in SAFE_CLASSIFICATIONS:
        field,kind='unknown','validation_failed'
    return '- 필드 진단: '+cell(field)+' / '+cell(kind)


def summary(result):
    items=[i for t in result['tables'] for i in t.get('items',[])]
    counts={role:sum(i['direction']==role for i in items) for role in ('receipts_candidate','expenditure_candidate','direction_unverified')}
    rows=['# ECOS Preflight', '',
        '- 인증: '+cell(result['authentication']), '- 검사 상태: '+cell(result['status']),
        '- 일반여행 판정: '+cell(assessment(result)),
        f"- 통계표 목록 {result['catalogue_count']}개 / 월간 후보 {result['candidate_count']}개 / 검사 {len(result['tables'])}개",
        '- 일반여행 항목 후보 '+str(len(items))+'개 / 수입 '+str(counts['receipts_candidate'])+' / 지급 '+str(counts['expenditure_candidate'])+' / 방향 미확인 '+str(counts['direction_unverified']),
        '- 메타데이터만 조회. 수치 조회·수집·매핑 승인·운영 활성화는 수행하지 않았습니다.', '']
    for error in result['errors']:rows.append('- 오류: '+cell(error))
    if result.get('error_diagnostic'):rows.append(diagnostic_line(result['error_diagnostic']))
    for table in result['tables']:
        rows+=['', '## '+cell(table['code'])+' · '+cell(table['name']),
               '- 주기: '+cell(','.join(table['cycles']))+' / 상태: '+cell(table['status'])]
        if table.get('error'):
            rows.append('- 오류: '+cell(table['error']))
            if table.get('error_diagnostic'):rows.append(diagnostic_line(table['error_diagnostic']))
            continue
        rows.append('- 월간 항목 그룹/개수: '+cell(', '.join(f'{k}: {v}' for k,v in sorted(table['groups'].items()))))
        if not table['items']:
            rows.append('- 일반여행 항목 미발견. 전체 여행수입·지급으로 대체하지 않습니다.');continue
        rows+=['', '| 그룹 | 항목 코드 · 명칭 | 부모 코드 | 전체 계층 | 방향 | 원본 단위 | 수록 기간 | 메타데이터 |',
               '| --- | --- | --- | --- | --- | --- | --- | --- |']
        for i in table['items']:
            fields=[i['group'],i['code']+' · '+i['name'],i['parent'] or 'root',i['path'],i['direction'],i['unit'] or '미확인',(i['start'] or '?')+'~'+(i['end'] or '?'),'complete' if i['metadata_complete'] else 'review']
            rows.append('| '+' | '.join(cell(v) for v in fields)+' |')
    rows+=['', '## 해석 범위',
        '- receipts_candidate / expenditure_candidate는 공식 명칭과 전체 계층으로 확인한 후보입니다. 모호한 방향은 direction_unverified로 남깁니다.',
        '- pair_candidates_found는 단일 차원의 수입·지급 후보 1쌍에 계층·단위·기간이 있다는 뜻이며 실제 수치 검증이나 자동 매핑 승인이 아닙니다.',
        '- not_found / review_required / incomplete에서는 workflow를 실패 상태로 남겨 추가 검토가 필요함을 알립니다.',
        '- inspection_complete는 선택 범위의 메타데이터 검사를 마쳤다는 뜻이며, 일반여행 코드·선택 차원·게시 승인을 자동 확정하지 않습니다.',
        '- 후보 제한·오류·추가 차원·단위/수록기간 미확인이 남으면 추가 검토가 필요합니다. 수록 종료월은 최신 수록 메타데이터이며 실제 수치 수신·공표일 확인을 뜻하지 않습니다.',
        '- data/live·운영 JSON·기존 Macro 수집·Pages 배포 변경 없음. 원본 응답과 인증 URL은 출력·업로드하지 않습니다.']
    body='\n'.join(rows)+'\n'
    if len(body.encode())>500000:raise EcosError('preflight_report_limit')
    return body


def main():
    """No key argument, no artifact, no raw file, only this step's Summary file."""
    target=os.environ.get('GITHUB_STEP_SUMMARY','')
    if not target:return 1
    path=Path(target).resolve()
    if path==ROOT or ROOT in path.parents:return 1
    path.write_text('# ECOS Preflight\n\n검증 미완료. 실행 중단 시 workflow 결론을 확인하세요.\n')
    key=os.environ.get('ECOS_API_KEY','')
    try:
        result=inspect(Client(),Inspector(key),int(os.environ.get('ECOS_PREFLIGHT_MAX_TABLES','12')))
    except Exception as exc:
        error=safe_error(exc)
        result=dict(authentication='credential_missing' if error=='ecos_auth_required' else 'rejected' if error=='ecos_auth_invalid' else 'not_verified',status='failed',catalogue_count=0,candidate_count=0,tables=[],errors=[error])
    try:
        body=summary(result)
        # Final fail-closed scan of the complete rendered Summary, too.
        if key and (key in body or key in html.unescape(unquote(body))):raise EcosError('preflight_unsafe_metadata')
        path.write_text(body)
    except Exception:
        path.write_text('# ECOS Preflight\n\n결과 안전성 검증 실패. 메타데이터 공개를 보류했습니다.\n')
        return 1
    print('ECOS metadata preflight finished. See the safe Actions Summary.')
    return 0 if assessment(result)=='pair_candidates_found' else 1


if __name__=='__main__':raise SystemExit(main())
