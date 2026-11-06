"""One-time KTO user CSV display-precision check against live ECOS.

Read-only. A match does NOT establish KTO provenance, statistical-definition
equivalence, publication rights, release vintage, or operational approval.
Only fixed status labels, not amounts, enter GitHub Actions Summary.
"""
import datetime as dt
import hashlib
import json
import os
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from . import ecos
from .ecos_compare import candidate_metadata, values, KST
from .ecos_preflight import Inspector, diagnostic, diagnostic_line, safe_error

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'docs/ecos-candidate-validation/kto-provisional-digests.json'
TABLE = '301Y013'
KINDS = ('receipts', 'expenditure')
MONTH = re.compile(r'20\d{2}-(?:0[1-9]|1[0-2])\Z')
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
SAFE_ERRORS = frozenset({'kto_provisional_manifest_invalid', 'kto_provisional_period_invalid',
                         'kto_provisional_metadata_invalid', 'kto_provisional_comparison_failed'})

def fail(reason):
    raise ecos.EcosError(reason)

def digest(period, kind, amount):
    """Canonical digest of a displayed 1-decimal amount; not secret protection."""
    formatted = f'{amount.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP):.1f}'
    return hashlib.sha256(f'kto-csv-v1|{period}|{kind}|{formatted}'.encode('ascii')).hexdigest()

def validate_manifest(doc, now):
    if not isinstance(doc, dict) or doc.get('schema') != 'kto_provisional_csv_digest_v1':
        fail('kto_provisional_manifest_invalid')
    if doc.get('source_kind') != 'user_uploaded_csv_unverified' or doc.get('source_origin_review') != 'pending':
        fail('kto_provisional_manifest_invalid')
    if doc.get('unit') != '백만달러' or doc.get('display_decimals') != 1:
        fail('kto_provisional_manifest_invalid')
    if not isinstance(doc.get('source_sha256'), str) or not SHA256.fullmatch(doc['source_sha256']):
        fail('kto_provisional_manifest_invalid')
    entries = doc.get('values_sha256')
    if not isinstance(entries, dict) or len(entries) != 12:
        fail('kto_provisional_manifest_invalid')
    periods = sorted(entries)
    if any(not isinstance(p, str) or not MONTH.fullmatch(p) or p >= now.strftime('%Y-%m') for p in periods):
        fail('kto_provisional_period_invalid')
    from .model import months
    if periods != months(periods[0], periods[-1]):
        fail('kto_provisional_period_invalid')
    for row in entries.values():
        if not isinstance(row, dict) or set(row) != set(KINDS) or any(
                not isinstance(row[k], str) or not SHA256.fullmatch(row[k]) for k in KINDS):
            fail('kto_provisional_manifest_invalid')
    return periods, entries

def compare_provisional(client, inspector, manifest, now):
    periods, expected = validate_manifest(manifest, now)
    meta = candidate_metadata(client, inspector, TABLE)
    for kind in KINDS:
        item = meta['series'][kind]
        if periods[0] < item['start'] or periods[-1] > item['end']:
            fail('kto_provisional_metadata_invalid')
    observed = {kind: values(client, inspector, meta, kind, periods[0], periods[-1], now)
                for kind in KINDS}
    result = []
    for period in periods:
        row = {}
        for kind in KINDS:
            value = observed[kind].get(period)
            row[kind] = ('missing' if value is None else
                         'matches_at_one_decimal' if digest(period, kind, value) == expected[period][kind]
                         else 'different_at_one_decimal')
        result.append(dict(period=period, **row))
    return result

def safe_failure(exc):
    code = str(exc) if isinstance(exc, ecos.EcosError) else ''
    if code in SAFE_ERRORS:
        return code
    fixed = safe_error(exc)
    return fixed if fixed != 'preflight_failed' else 'kto_provisional_comparison_failed'

def render(result, error=None, details=None):
    out = ['# ECOS × KTO CSV provisional check', '',
           '- 원천: 한국은행 ECOS 301Y013 / 일반여행수입·지급',
           '- 비교 자료: 사용자가 제출한 KTO 관광수지 CSV (출처 증빙 미완료)',
           '- 정밀도: 백만달러, 소수점 첫째 자리 반올림 후 비교',
           '- KTO 공식 증빙: pending / 운영 승인: not_granted',
           '- 판단 범위: CSV 표시값과 이번 ECOS 조회값의 일치 여부만 확인', '']
    if error:
        out.append('- 상태: validation_failed')
        out.append('- 오류: '+(error if error in SAFE_ERRORS else 'kto_provisional_comparison_failed'))
        if details:
            out.append(diagnostic_line(details))
    else:
        matched = sum(row[k]=='matches_at_one_decimal' for row in result for k in KINDS)
        out.extend(['- 상태: comparison_completed', f'- 표시 정밀도 일치: {matched}/{2*len(result)}', '',
                    '| 기간 | 관광수입 | 관광지출 |', '| --- | --- | --- |'])
        for row in result:
            out.append('| '+row['period']+' | '+row['receipts']+' | '+row['expenditure']+' |')
    out += ['', '- 이 검증은 KTO 원본 파일의 공식성, 공표시점, 정정 이력, 이용허락을 증명하지 않습니다.',
            '- 값이 일치해도 기존 ECOS Preflight review_required와 운영 설정은 변경하지 않습니다.',
            '- KTO CSV 소수점 첫째 자리 비교이므로 ECOS 원본 소수점 이하 정밀도 일치는 확인하지 않습니다.']
    return '\n'.join(out)+'\n'

def main():
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY', '')
    if not summary_path:
        return 1
    path = Path(summary_path).resolve()
    if path == ROOT or ROOT in path.parents:
        return 1
    path.write_text('# ECOS × KTO CSV provisional check\n\n검증 미완료\n')
    secret = os.environ.get('ECOS_API_KEY', '')
    try:
        if not MANIFEST.is_file() or MANIFEST.is_symlink() or MANIFEST.stat().st_size > 20000:
            fail('kto_provisional_manifest_invalid')
        doc = json.loads(MANIFEST.read_text(encoding='utf-8'))
        if not secret:
            fail('kto_provisional_comparison_failed')
        result = compare_provisional(ecos.Client(), Inspector(secret), doc, dt.datetime.now(KST))
        body = render(result)
    except Exception as exc:
        body = render(None, safe_failure(exc), diagnostic(exc))
        result = None
    if secret and any(token in body for token in Inspector(secret).tokens):
        path.write_text('# ECOS × KTO CSV provisional check\n\n결과 공개 보류\n')
        return 1
    path.write_text(body)
    print('Provisional KTO CSV comparison finished; see safe Actions Summary.')
    return 0 if result is not None and all(row[k]=='matches_at_one_decimal' for row in result for k in KINDS) else 1

if __name__ == '__main__':
    raise SystemExit(main())
