"""Manual Actions-only decimal preflight. No collector, ledger or public export.

Only fixed enums, registered identities, validated periods and bounded counts may
leave memory. Injected transports are simulations, never authenticated evidence.
"""
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from . import ecos, ecos_decimal
from .model import decimal_value, months, month_before, valid_period

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT/'fixtures/macro_market_step3_baseline.json'
BASELINE_SHA256 = 'd9d5e2df5197be687d2b0f7a423961b9f9fd95dbd9b202c2a374b9af84ee6f84'
# Freeze reviewed identities independently of any provider text/configuration.
SPECS = {
    'market_fxavg': ('731Y004', ['0000001','0000100'], '원', None, '2026-10'),
    'market_lodging': ('901Y038', ['I51ADA','2'], '2020=100', 2020, '2026-09'),
    'market_leisure': ('901Y038', ['I51AL','2'], '2020=100', 2020, '2026-09'),
    'market_cpilodging': ('901Y009', ['K02'], '2020=100', 2020, '2026-10'),
    'market_cpihotel': ('901Y009', ['K02101'], '2020=100', 2020, '2026-10'),
    'market_cpiinn': ('901Y009', ['K02102'], '2020=100', 2020, '2026-10'),
    'market_cpicondo': ('901Y009', ['K02103'], '2020=100', 2020, '2026-10'),
    'market_cpidomestic': ('901Y009', ['I06101'], '2020=100', 2020, '2026-10'),
    'market_cpiforeign': ('901Y009', ['I06102'], '2020=100', 2020, '2026-10'),
}
ERRORS = {
    'ecos_auth_required':'credential_missing', 'ecos_auth_invalid':'authentication_rejected',
    'ecos_auth_or_access_denied':'auth_or_access_denied',
    'ecos_rate_limited':'rate_limited', 'ecos_query_timeout':'query_timeout',
    'ecos_network_or_tls_failure':'network_or_tls_failure',
    'ecos_robots_unavailable':'robots_unavailable', 'ecos_robots_invalid':'robots_invalid',
    'ecos_robots_disallowed':'access_restricted', 'ecos_deferred_fetch_required':'access_restricted',
    'ecos_redirect_blocked':'redirect_blocked',
    'ecos_unexpected_credential_in_response':'unsafe_response',
}
ERROR_CODES = set(ERRORS.values()) | {'unexpected_failure','configuration_invalid','baseline_invalid',
    'metadata_invalid','metadata_regressed','baseline_change','invalid_period','series_invalid','no_observations',
    'missing_months','duplicate_months','probe_aborted'}


class ProbeError(ValueError):
    pass


class Discard:
    def write(self, value):return len(value)
    def flush(self):pass


def fingerprint(key, period, value):
    table, codes, unit, base, _ = SPECS[key]
    doc = [key, table, codes, unit, base, 'M', valid_period(period), decimal_value(value)]
    return hashlib.sha256(json.dumps(doc,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def validate_baseline(doc):
    if not isinstance(doc,dict) or doc.get('schema_version')!=1 or set(doc.get('series',{}))!=set(SPECS):
        raise ProbeError('baseline_invalid')
    total = 0
    for key,(table,codes,unit,base,end) in SPECS.items():
        row=doc['series'][key]
        if (row.get('stat_code'),row.get('item_codes'),row.get('unit'),row.get('base_year'))!=(table,codes,unit,base):
            raise ProbeError('baseline_invalid')
        values=row.get('fingerprints',{})
        if set(values)!=set(months('2021-01',end)) or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in values.values()):
            raise ProbeError('baseline_invalid')
        total+=len(values)
    if total!=628:raise ProbeError('baseline_invalid')
    return doc


def load_baseline():
    raw=BASELINE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASELINE_SHA256:raise ProbeError('baseline_invalid')
    return validate_baseline(json.loads(raw))


def registry(config):
    items={}
    for key,(table,codes,unit,base,_) in SPECS.items():
        selected=[i for i in config['indicators'] if i['id']==key]
        if len(selected)!=1:raise ProbeError('configuration_invalid')
        item=selected[0];ecos_decimal.definition(item)
        sources=[s for s in config['sources'] if s['id']==item['source_id']]
        if (len(sources)!=1 or sources[0].get('method')!=ecos_decimal.METHOD
                or sources[0].get('stat_code')!=table or sources[0].get('start_period')!='2021-01'
                or sources[0].get('enabled') is not False or item.get('enabled') is not False
                or item.get('publication_status')!='blocked'
                or (item['stat_code'],item['item_codes'],item['unit'],item['base_year'])!=(table,codes,unit,base)):
            raise ProbeError('configuration_invalid')
        items[key]=item
    return items


def error_code(exc):
    # No prefix matching, exception repr, request URL, or arbitrary provider text.
    if isinstance(exc,ProbeError) and exc.args and isinstance(exc.args[0],str) and exc.args[0] in ERROR_CODES:return exc.args[0]
    if isinstance(exc,ecos.EcosError) and exc.args and isinstance(exc.args[0],str):
        return ERRORS.get(exc.args[0],'unexpected_failure')
    if isinstance(exc,(KeyboardInterrupt,SystemExit)):return 'probe_aborted'
    return 'unexpected_failure'


def inspect(item, client, now, cache):
    table=item['stat_code']
    if table not in cache:
        tables=client.rows('StatisticTableList',table)
        if (len(tables)!=1 or tables[0].get('STAT_CODE')!=table or tables[0].get('SRCH_YN')!='Y'
                or 'M' not in tables[0].get('CYCLE','').split(',')):
            raise ProbeError('metadata_invalid')
        metadata=client.rows('StatisticItemList',table);lookup={}
        for row in metadata:
            if row.get('CYCLE')!='M':continue
            pair=row.get('GRP_CODE'),row.get('ITEM_CODE')
            if pair in lookup:raise ProbeError('metadata_invalid')
            lookup[pair]=row
        cache[table]=lookup
    ranges=[]
    for n,(code,name) in enumerate(zip(item['item_codes'],item['item_names']),1):
        row=cache[table].get((f'Group{n}',code),{})
        if not row or row.get('STAT_CODE')!=table or row.get('ITEM_NAME')!=name:
            raise ProbeError('metadata_invalid')
        # Base-year changes are never treated as ordinary value corrections.
        if row.get('UNIT_NAME') not in (item['unit'],None) or (n==1 and row.get('UNIT_NAME')!=item['unit']):
            raise ProbeError('baseline_change')
        start,end=ecos.period(row.get('START_TIME')),ecos.period(row.get('END_TIME'))
        if start>end or end>=now.strftime('%Y-%m'):raise ProbeError('invalid_period')
        ranges.append((start,end))
    end=min(e for s,e in ranges)
    if end<SPECS[item['id']][4]:raise ProbeError('metadata_regressed')
    start=month_before(month_before(end))
    if start<'2021-01' or any(s>start for s,e in ranges):raise ProbeError('metadata_invalid')
    rows=client.rows('StatisticSearch',table,'M',start.replace('-',''),end.replace('-',''),*item['item_codes'])
    if not rows:raise ProbeError('no_observations')
    periods=[ecos.period(r.get('TIME')) for r in rows]
    if len(set(periods))!=len(periods):raise ProbeError('duplicate_months')
    if any(r.get('UNIT_NAME')!=item['unit'] for r in rows):raise ProbeError('baseline_change')
    if set(periods)!=set(months(start,end)):raise ProbeError('missing_months')
    try:
        records=ecos_decimal.parse(rows,item,start,end,now,client.response_hashes,'preflight_memory_only')
    except (ValueError,TypeError,KeyError):
        raise ProbeError('series_invalid') from None
    return start,end,records


def probe(config, baseline, scope='fx', client=None, now=None):
    result=dict(status='failed',authentication='not_verified',scope=scope,expansion='not_requested',series=[])
    current=None;simulated=client is not None
    try:
        if scope not in ('fx','all'):raise ProbeError('configuration_invalid')
        validate_baseline(baseline);items=registry(config)
        # Only the non-injected CLI constructs the normal authenticated client.
        client=ecos.Client() if client is None else client
        now=now or dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
        cache={}
        for key in SPECS if scope=='all' else ('market_fxavg',):
            current=key
            start,end,records=inspect(items[key],client,now,cache)
            stored=baseline['series'][key]['fingerprints']
            overlap=set(records)&set(stored)
            changed=sum(fingerprint(key,p,records[p]['value'])!=stored[p] for p in overlap)
            result['series'].append(dict(id=key,status='validated',stat_code=SPECS[key][0],item_codes=SPECS[key][1],
                unit=SPECS[key][2],base_year=SPECS[key][3],first_period=start,latest_period=end,response_count=len(records),
                missing_count=0,duplicate_count=0,overlap_count=len(overlap),matched_count=len(overlap)-changed,
                correction_candidate_count=changed,new_period_count=len(set(records)-set(stored)),
                baseline_unqueried_count=len(set(stored)-set(records))))
            if key=='market_fxavg':
                result['authentication']='not_verified' if simulated else 'verified_fx_observations'
                if scope=='all':result['expansion']='fx_gate_passed'
        result['status']='simulation_only' if simulated else 'passed'
    except BaseException as exc:
        code=error_code(exc)
        result['error']=code
        if current:result['failed_indicator']=current
        if code in ('credential_missing','authentication_rejected','auth_or_access_denied'):
            result['authentication']=code
        if scope=='all':result['expansion']='blocked_by_fx' if not result['series'] else 'stopped_on_failure'
    return result


def render(result):
    """Strict output schema: no passthrough values from exceptions/providers."""
    if (result.get('status') not in ('failed','passed','simulation_only')
            or result.get('authentication') not in ('not_verified','verified_fx_observations','credential_missing','authentication_rejected','auth_or_access_denied')
            or result.get('scope') not in ('fx','all')
            or result.get('expansion') not in ('not_requested','fx_gate_passed','blocked_by_fx','stopped_on_failure')
            or result.get('error') not in ERROR_CODES|{None}
            or result.get('failed_indicator') not in set(SPECS)|{None}):
        raise ProbeError('configuration_invalid')
    lines=['## Market Weather ECOS Preflight', '',
        '- Status: '+result['status'], '- Authentication: '+result['authentication'],
        '- Scope: '+result['scope'], '- Expansion: '+result['expansion'],
        '- Read-only diagnostic; no collection/publication approval or production writes.']
    if result.get('error'):lines+=['- Error: '+result['error']]
    if result.get('failed_indicator'):lines+=['- Failed indicator: '+result['failed_indicator']]
    fields=('response_count','missing_count','duplicate_count','overlap_count','matched_count',
        'correction_candidate_count','new_period_count','baseline_unqueried_count')
    if len(result['series'])>9:raise ProbeError('configuration_invalid')
    for row in result['series']:
        key=row.get('id')
        if key not in SPECS:raise ProbeError('configuration_invalid')
        table,codes,unit,base,_=SPECS[key]
        if (row.get('stat_code'),row.get('item_codes'),row.get('unit'),row.get('base_year'))!=(table,codes,unit,base):
            raise ProbeError('configuration_invalid')
        if row.get('status')!='validated' or any(type(row.get(k)) is not int or not 0<=row[k]<=5000 for k in fields):
            raise ProbeError('configuration_invalid')
        valid_period(row['first_period']);valid_period(row['latest_period'])
        lines+=['', '### '+key, '- Table/items: '+table+' / '+' / '.join(codes),
            '- Unit/base year: '+unit+' / '+str(base),
            '- Validated monthly window: '+row['first_period']+'..'+row['latest_period']]
        lines+=['- '+k+': '+str(row[k]) for k in fields]
    return '\n'.join(lines)+'\n'


def summary_fd(env):
    # Actions owns an existing regular file in RUNNER_TEMP, never a repo path.
    path=Path(env['GITHUB_STEP_SUMMARY']);temp=Path(env['RUNNER_TEMP']).resolve()
    resolved=path.resolve(strict=True)
    if (not path.is_absolute() or temp not in resolved.parents or resolved==ROOT or ROOT in resolved.parents):
        raise ProbeError('configuration_invalid')
    fd=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)
    if not stat.S_ISREG(os.fstat(fd).st_mode):os.close(fd);raise ProbeError('configuration_invalid')
    return fd


def main():
    # Do not even construct a client outside a reviewed main manual run.
    if not (os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
            and os.environ.get('GITHUB_REF')=='refs/heads/main'):
        print('Market Weather preflight requires a manual main Actions run.');return 1
    fd=None
    try:
        with contextlib.redirect_stdout(Discard()),contextlib.redirect_stderr(Discard()):
            fd=summary_fd(os.environ)
            scope=os.environ.get('ECOS_PREFLIGHT_SCOPE','fx')
            try:
                baseline=load_baseline()
            except BaseException:
                result=dict(status='failed',authentication='not_verified',scope='fx',expansion='not_requested',series=[],error='baseline_invalid')
            else:
                try:
                    config=json.loads((ROOT/'macro_sources.json').read_text())
                    result=probe(config,baseline,scope)
                except BaseException:
                    result=dict(status='failed',authentication='not_verified',scope='fx',expansion='not_requested',series=[],error='configuration_invalid')
            body=render(result)
            key=os.environ.get('ECOS_API_KEY','')
            # Even coincidental collisions fail closed with no output.
            if key and key in body:return 1
            with os.fdopen(fd,'a') as stream:
                fd=None;stream.write(body)
        return 0 if result['status']=='passed' else 1
    except BaseException:
        # No traceback or arbitrary exception payload on failure to write Summary.
        return 1
    finally:
        if fd is not None:os.close(fd)


if __name__=='__main__':raise SystemExit(main())
