"""Synthetic API responses only; no Actions, credentials, live DB or network."""
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.macro import ecos
from src.macro import ecos_market_preflight as p
from src.macro.engine import collect
from src.macro.model import months
from tools.validate_market_weather_foundation import Replay

NOW=dt.datetime(2026,11,12,tzinfo=dt.timezone.utc)
FAKE='SYNTHETIC_ECOS_SECRET_NEVER_REAL_918273645'
CONFIG=json.loads((p.ROOT/'macro_sources.json').read_text())


def fixture():
    rows={};baseline=copy.deepcopy(p.load_baseline())
    for key,(table,codes,unit,base,end) in p.SPECS.items():
        item=next(i for i in CONFIG['indicators'] if i['id']==key)
        values=[]
        periods=months(p.month_before(p.month_before(end)),end)
        for n,period in enumerate(periods):
            row=dict(STAT_CODE=table,UNIT_NAME=unit,TIME=period.replace('-',''),DATA_VALUE='123.45678912345678'+str(n))
            for g in range(1,5):
                row[f'ITEM_CODE{g}']=codes[g-1] if g<=len(codes) else None
                row[f'ITEM_NAME{g}']=item['item_names'][g-1] if g<=len(codes) else None
            values.append(row)
            baseline['series'][key]['fingerprints'][period]=p.fingerprint(key,period,row['DATA_VALUE'])
        rows[key]=values
    class Client(Replay):
        def __init__(self):super().__init__(dict(indicators=[i for i in CONFIG['indicators'] if i['id'] in p.SPECS]),rows);self.calls=[]
        def rows(self,service,table,*args):
            self.calls.append((service,table,args))
            return super().rows(service,table,*args)
    return Client(),baseline


def run(client=None,baseline=None,scope='all'):
    c,b=fixture()
    return p.probe(CONFIG,baseline or b,scope,client or c,NOW)


class BaselineTests(unittest.TestCase):
    def test_real_baseline_has_exact_628_identities_and_no_values(self):
        baseline=p.load_baseline()
        self.assertEqual(sum(len(v['fingerprints']) for v in baseline['series'].values()),628)
        self.assertEqual(baseline['provenance']['original_response_count'],63)
        raw=p.BASELINE.read_text();self.assertNotIn('DATA_VALUE',raw);self.assertNotIn('source_value',raw)

    def test_identity_omission_duplicate_period_scope_or_hash_change_fails(self):
        for mutation in ('identity','period','hash','scope','base'):
            doc=copy.deepcopy(p.load_baseline());s=doc['series']['market_cpilodging']
            if mutation=='identity':s['item_codes']=['other']
            if mutation=='period':del s['fingerprints']['2021-01']
            if mutation=='hash':s['fingerprints']['2021-01']='bad'
            if mutation=='scope':doc['series'].pop('market_leisure')
            if mutation=='base':s['base_year']=2025
            with self.subTest(mutation=mutation),self.assertRaises(p.ProbeError):p.validate_baseline(doc)

    def test_file_hash_is_pinned_before_parse(self):
        with patch.object(Path,'read_bytes',return_value=b'{}'),self.assertRaises(p.ProbeError):p.load_baseline()


class StagingTests(unittest.TestCase):
    def test_fx_default_never_requests_other_tables_and_is_not_auth_evidence(self):
        c,b=fixture();r=p.probe(CONFIG,b,client=c,now=NOW)
        self.assertEqual([s['id'] for s in r['series']],['market_fxavg'])
        self.assertTrue(all(table=='731Y004' for service,table,args in c.calls))
        self.assertEqual(r['status'],'simulation_only');self.assertEqual(r['authentication'],'not_verified')
        self.assertEqual(r['series'][0]['matched_count'],3)
        self.assertEqual(c.calls[-1][2],('M','202608','202610','0000001','0000100'))

    def test_fx_success_all_expands_in_order_and_reuses_metadata(self):
        c,b=fixture();r=p.probe(CONFIG,b,'all',c,NOW)
        self.assertEqual([s['id'] for s in r['series']],list(p.SPECS))
        self.assertEqual(sum(s['response_count'] for s in r['series']),27)
        self.assertEqual(len([call for call in c.calls if call[0]=='StatisticTableList']),3)
        self.assertEqual(len([call for call in c.calls if call[0]=='StatisticItemList']),3)
        self.assertEqual(sum(s['matched_count'] for s in r['series']),27)
        self.assertEqual(r['expansion'],'fx_gate_passed')
        self.assertTrue(all(call[2][-1]=='0000100' for call in c.calls if call[0]=='StatisticSearch' and call[1]=='731Y004'))

    def test_any_fx_validation_failure_blocks_eight(self):
        for mutate,error in [(lambda rows:rows.pop(0),'missing_months'),
                (lambda rows:rows.append(copy.deepcopy(rows[0])),'duplicate_months'),
                (lambda rows:rows[0].update(ITEM_CODE2='0000200'),'series_invalid'),
                (lambda rows:rows[0].update(DATA_VALUE='NaN'),'series_invalid')]:
            c,b=fixture();mutate(c.data['market_fxavg']);r=p.probe(CONFIG,b,'all',c,NOW)
            self.assertEqual(r['status'],'failed');self.assertEqual(r['error'],error)
            self.assertEqual(r['series'],[]);self.assertEqual(r['expansion'],'blocked_by_fx')
            self.assertTrue(all(table=='731Y004' for service,table,args in c.calls))

    def test_rejected_denied_rate_network_unknown_error_are_distinct_and_safe(self):
        for message,code in [('ecos_auth_invalid','authentication_rejected'),('ecos_auth_or_access_denied','auth_or_access_denied'),
                ('ecos_rate_limited','rate_limited'),('ecos_network_or_tls_failure','network_or_tls_failure'),
                ('ecos_robots_disallowed','access_restricted'),(FAKE,'unexpected_failure'),('ecos_'+FAKE,'unexpected_failure')]:
            c,b=fixture()
            def fail(*args,message=message):raise ecos.EcosError(message)
            c.rows=fail;r=p.probe(CONFIG,b,'all',c,NOW)
            self.assertEqual(r['error'],code);self.assertEqual(r['status'],'failed')
            self.assertNotIn(FAKE,p.render(r));self.assertFalse(r['series'])

    def test_baseline_failure_prevents_all_network(self):
        c,b=fixture();b['series'].pop('market_fxavg')
        r=p.probe(CONFIG,b,'all',c,NOW);self.assertEqual(r['error'],'baseline_invalid');self.assertEqual(c.calls,[])

    def test_later_auth_failure_stops_and_retains_only_diagnostics(self):
        c,b=fixture();old=c.rows
        def fail(service,table,*args):
            if table=='901Y038':raise ecos.EcosError('ecos_auth_or_access_denied')
            return old(service,table,*args)
        c.rows=fail;r=p.probe(CONFIG,b,'all',c,NOW)
        self.assertEqual(r['status'],'failed');self.assertEqual(len(r['series']),1)
        self.assertEqual(r['authentication'],'auth_or_access_denied')
        self.assertEqual(r['expansion'],'stopped_on_failure')
        self.assertFalse(any(table=='901Y009' for service,table,args in c.calls))

    def test_corrections_normalized_precision_and_no_actual_values_in_summary(self):
        c,b=fixture();before=copy.deepcopy(b)
        c.data['market_fxavg'][0]['DATA_VALUE']='100.000000000000000001'
        r=p.probe(CONFIG,b,'fx',c,NOW)
        self.assertEqual(r['series'][0]['correction_candidate_count'],1)
        self.assertEqual(r['series'][0]['matched_count'],2)
        self.assertEqual(b,before)
        text=p.render(r);self.assertNotIn('100.000000000000000001',text);self.assertNotIn('123.456789',text)
        self.assertEqual(p.fingerprint('market_fxavg','2026-10','100.0100'),p.fingerprint('market_fxavg','2026-10','100.01'))
        self.assertNotEqual(p.fingerprint('market_fxavg','2026-10','100.000000000000000001'),p.fingerprint('market_fxavg','2026-10','100'))

    def test_new_month_is_new_not_unchanged_or_revision(self):
        c,b=fixture();item=next(i for i in CONFIG['indicators'] if i['id']=='market_fxavg')
        last=copy.deepcopy(c.data[item['id']][-1]);last['TIME']='202611'
        c.data[item['id']]=c.data[item['id']][1:]+[last]
        r=p.probe(CONFIG,b,'fx',c,NOW.replace(month=12));row=r['series'][0]
        self.assertEqual(row['new_period_count'],1);self.assertEqual(row['overlap_count'],2)
        self.assertEqual(row['baseline_unqueried_count'],68)

    def test_cpi_2025_base_in_metadata_or_observations_is_not_a_revision(self):
        for where in ('metadata','observations'):
            c,b=fixture();before=copy.deepcopy(b);original=c.rows
            def changed(service,table,*args):
                rows=original(service,table,*args)
                if table=='901Y009' and service==('StatisticItemList' if where=='metadata' else 'StatisticSearch'):
                    rows[0]['UNIT_NAME']='2025=100'
                return rows
            c.rows=changed;r=p.probe(CONFIG,b,'all',c,NOW)
            self.assertEqual(r['error'],'baseline_change');self.assertEqual(r['failed_indicator'],'market_cpilodging')
            self.assertEqual(len(r['series']),3);self.assertEqual(b,before)
            self.assertEqual(sum(s['correction_candidate_count'] for s in r['series']),0)

    def test_future_metadata_and_wrong_metadata_codes_reject(self):
        for field,value in [('END_TIME','202611'),('ITEM_NAME',FAKE),('STAT_CODE','999Y999')]:
            c,b=fixture();old=c.rows
            def changed(service,*args):
                rows=old(service,*args)
                if service=='StatisticItemList':rows[0][field]=value
                return rows
            c.rows=changed;r=p.probe(CONFIG,b,'all',c,NOW)
            self.assertEqual(r['status'],'failed');self.assertNotIn(FAKE,p.render(r))

    def test_activation_flags_not_mutated_and_config_drift_rejected(self):
        c,b=fixture();before=copy.deepcopy(CONFIG);p.probe(CONFIG,b,'all',c,NOW);self.assertEqual(CONFIG,before)
        altered=copy.deepcopy(CONFIG);next(i for i in altered['indicators'] if i['id']=='market_fxavg')['enabled']=True
        c.calls=[];r=p.probe(altered,b,'all',c,NOW)
        self.assertEqual(r['error'],'configuration_invalid');self.assertEqual(c.calls,[])

    def test_no_observations_blocks_expansion(self):
        c,b=fixture();old=c.rows
        def empty(service,*args):return [] if service=='StatisticSearch' else old(service,*args)
        c.rows=empty;r=p.probe(CONFIG,b,'all',c,NOW)
        self.assertEqual(r['error'],'no_observations');self.assertEqual(r['expansion'],'blocked_by_fx')

    def test_metadata_cannot_regress_before_known_step3_latest(self):
        c,b=fixture();old=c.rows
        def stale(service,*args):
            rows=old(service,*args)
            if service=='StatisticItemList':
                for row in rows:row['END_TIME']='202103'
            return rows
        c.rows=stale;r=p.probe(CONFIG,b,'all',c,NOW)
        self.assertEqual(r['error'],'metadata_regressed');self.assertFalse(r['series'])
        self.assertFalse(any(s=='StatisticSearch' for s,t,a in c.calls))

    def test_error_handler_never_reraises_malformed_exception_payload(self):
        for raw in [[],{},None,FAKE]:self.assertEqual(p.error_code(p.ProbeError(raw)),'unexpected_failure')

    def test_cpi_rebase_collector_regression_keeps_2020_vintage_and_tourgo(self):
        # Existing engine is tested only in temporary directories, not preflight.
        c,b=fixture();cfg=copy.deepcopy(CONFIG)
        source=next(s for s in cfg['sources'] if s['id']=='ecos_market_cpi')
        source.update(enabled=True,start_period='2026-08',collection_review=dict(status='verified',evidence_url='https://example.org/synthetic',verified_at='2026-11-12'))
        for item in cfg['indicators']:
            if item['source_id']==source['id']:item['enabled']=True
        with tempfile.TemporaryDirectory() as d:
            state=Path(d)/'state';data=Path(d)/'data';state.mkdir()
            ledger=state/'macro_archive.json'
            old=(p.ROOT/'collector_state/macro_archive.json').read_bytes();ledger.write_bytes(old)
            h=collect(cfg,data,state,ecos_client=c,now=NOW,force=True,only_sources={source['id']})
            self.assertEqual(h['new_observations'],18)
            before={f:f.read_bytes() for f in (ledger,data/'macro.json')}
            previous=json.loads(old);staged=json.loads(ledger.read_text())
            self.assertEqual(previous['indicators'],staged['indicators'])
            self.assertEqual(previous['sources'],staged['sources'])
            for item in cfg['indicators']:
                if item['source_id']==source['id']:
                    for row in c.data[item['id']]:row['UNIT_NAME']='2025=100'
            h=collect(cfg,data,state,ecos_client=c,now=NOW,force=True,only_sources={source['id']})
            self.assertEqual(h['successful_sources'],0)
            self.assertTrue(all(f.read_bytes()==v for f,v in before.items()))


class OutputAndCliTests(unittest.TestCase):
    def env(self,folder):
        summary=Path(folder)/'summary.md';summary.write_text('prior step content\n')
        return dict(GITHUB_ACTIONS='true',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF='refs/heads/main',
            GITHUB_STEP_SUMMARY=str(summary),RUNNER_TEMP=folder,ECOS_API_KEY=FAKE,ECOS_PREFLIGHT_SCOPE='fx'),summary

    def test_manual_main_runtime_guard_prevents_client_construction(self):
        for changes in [{},{'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'pull_request','GITHUB_REF':'refs/heads/main'},
                {'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':'refs/heads/feature'}]:
            with patch.dict(os.environ,changes,clear=True),patch.object(ecos,'Client',side_effect=AssertionError('no client')),contextlib_output():
                self.assertEqual(p.main(),1)

    def test_missing_secret_and_sample_are_failure_not_authenticated(self):
        with tempfile.TemporaryDirectory() as d:
            env,file=self.env(d)
            for key in ('','sample'):
                env['ECOS_API_KEY']=key
                with patch.dict(os.environ,env,clear=True):self.assertEqual(p.main(),1)
                body=file.read_text();self.assertNotIn('Status: passed',body)
            self.assertIn('credential_missing',body);self.assertIn('authentication_rejected',body)

    def test_cli_success_uses_constructed_client_and_appends_sanitized_summary_only(self):
        c,b=fixture()
        # Synthetic fake constructor is scoped only to this unit test. Not evidence
        # of a real authenticated request; CLI production constructs ecos.Client.
        with tempfile.TemporaryDirectory() as d:
            env,file=self.env(d)
            with patch.dict(os.environ,env,clear=True),patch.object(p,'load_baseline',return_value=b),patch.object(ecos,'Client',return_value=c),contextlib_output() as streams:
                self.assertEqual(p.main(),0)
            body=file.read_text();self.assertTrue(body.startswith('prior step content'))
            self.assertIn('verified_fx_observations',body);self.assertNotIn(FAKE,body)
            self.assertEqual(streams[0].getvalue()+streams[1].getvalue(),'')

    def test_raw_exception_and_even_printing_transport_cannot_leak(self):
        c,b=fixture()
        def fail(*args):
            print('https://ecos.bok.or.kr/api/'+FAKE);print(FAKE,file=__import__('sys').stderr)
            raise RuntimeError('Authorization: '+FAKE)
        c.rows=fail
        with tempfile.TemporaryDirectory() as d:
            env,file=self.env(d)
            with patch.dict(os.environ,env,clear=True),patch.object(p,'load_baseline',return_value=b),patch.object(ecos,'Client',return_value=c),contextlib_output() as streams:
                self.assertEqual(p.main(),1)
            body=file.read_text()+streams[0].getvalue()+streams[1].getvalue()
            self.assertNotIn(FAKE,body);self.assertNotIn('Authorization',body);self.assertNotIn('https://',body)
            self.assertIn('unexpected_failure',body)


    def test_existing_real_client_parses_envelopes_without_network_and_no_raw_export(self):
        c,b=fixture()
        def transport(client,url):
            # Only fabricated wire responses; URL is intentionally never printed.
            parts=url[len(ecos.BASE):].split('/')
            service,table=parts[0],parts[6]
            rows=c.rows(service,table,*parts[7:])
            return json.dumps({service:dict(list_total_count=len(rows),row=rows)}).encode()
        with tempfile.TemporaryDirectory() as d:
            env,file=self.env(d)
            with patch.dict(os.environ,env,clear=True),patch.object(p,'load_baseline',return_value=b),patch.object(ecos.Client,'_read',transport):
                self.assertEqual(p.main(),0)
            body=file.read_text();self.assertIn('Status: passed',body)
            self.assertIn('verified_fx_observations',body)
            for forbidden in [FAKE,'https://','DATA_VALUE','123.456789','Authorization']:
                self.assertNotIn(forbidden,body)

    def test_real_client_rejects_error_envelopes_and_credential_reflection(self):
        c,b=fixture()
        for code,expected in [('INFO-100','authentication_rejected'),('ERROR-602','rate_limited'),('REFLECT','unsafe_response')]:
            raw=json.dumps(dict(RESULT=dict(CODE=code,MESSAGE=FAKE))).encode() if code!='REFLECT' else json.dumps(dict(StatisticTableList=dict(list_total_count=1,row=[dict(leaked=FAKE)]))).encode()
            with tempfile.TemporaryDirectory() as d:
                env,file=self.env(d);env['ECOS_PREFLIGHT_SCOPE']='all'
                with patch.dict(os.environ,env,clear=True),patch.object(p,'load_baseline',return_value=b),patch.object(ecos.Client,'_read',return_value=raw):
                    self.assertEqual(p.main(),1)
                body=file.read_text();self.assertIn('Error: '+expected,body)
                self.assertIn('blocked_by_fx',body);self.assertNotIn(FAKE,body)

    def test_symlink_repo_or_nonrunner_summary_path_never_writes(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as external:
            env,file=self.env(d);dest=Path(external)/'data';dest.write_text('retain')
            link=Path(d)/'link';link.symlink_to(dest);env['GITHUB_STEP_SUMMARY']=str(link)
            with patch.dict(os.environ,env,clear=True),patch.object(ecos,'Client',side_effect=AssertionError('no client')):self.assertEqual(p.main(),1)
            self.assertEqual(dest.read_text(),'retain')
            env['GITHUB_STEP_SUMMARY']=str(p.ROOT/'macro_sources.json');env['RUNNER_TEMP']=str(p.ROOT)
            before=(p.ROOT/'macro_sources.json').read_bytes()
            with patch.dict(os.environ,env,clear=True):self.assertEqual(p.main(),1)
            self.assertEqual((p.ROOT/'macro_sources.json').read_bytes(),before)

    def test_renderer_cannot_echo_injected_metadata_or_counts(self):
        result=run(scope='fx')
        for path,value in [('unit',FAKE),('latest_period',FAKE),('response_count',FAKE),('stat_code',FAKE),('item_codes',[FAKE])]:
            r=copy.deepcopy(result);r['series'][0][path]=value
            with self.subTest(path=path),self.assertRaises(ValueError):p.render(r)
        r=copy.deepcopy(result);r['error']=FAKE
        with self.assertRaises(p.ProbeError):p.render(r)

    def test_secret_collision_in_allowlisted_result_leaves_summary_untouched(self):
        c,b=fixture()
        with tempfile.TemporaryDirectory() as d:
            env,file=self.env(d);env['ECOS_API_KEY']='market_fxavg'
            before=file.read_bytes()
            with patch.dict(os.environ,env,clear=True),patch.object(p,'load_baseline',return_value=b),patch.object(ecos,'Client',return_value=c):
                self.assertEqual(p.main(),1)
            self.assertEqual(file.read_bytes(),before)

    def test_preflight_and_rebase_failure_preserve_all_operational_datasets(self):
        files=[f for folder in ('site/data','collector_state') for f in (p.ROOT/folder).rglob('*') if f.is_file()]
        snapshots={f:f.read_bytes() for f in files}
        c,b=fixture();r=p.probe(CONFIG,b,'all',c,NOW);self.assertEqual(r['status'],'simulation_only')
        c.data['market_cpilodging'][0]['UNIT_NAME']='2025=100'
        self.assertEqual(p.probe(CONFIG,b,'all',c,NOW)['error'],'baseline_change')
        self.assertTrue(all(f.read_bytes()==raw for f,raw in snapshots.items()))


# Named helper avoids accidental use of real stderr in secret-reflection tests.
from contextlib import contextmanager,redirect_stdout,redirect_stderr
@contextmanager
def contextlib_output():
    out,err=io.StringIO(),io.StringIO()
    with redirect_stdout(out),redirect_stderr(err):yield out,err


class WorkflowTests(unittest.TestCase):
    def test_dispatch_main_only_readonly_secret_step_no_upload_or_deploy(self):
        import re
        path=p.ROOT/'.github/workflows/ecos-market-preflight.yml';raw=path.read_text()
        events=raw.split('\non:\n',1)[1].split('\npermissions:',1)[0]
        self.assertEqual(re.findall(r'^  (\w+):$',events,re.M),['workflow_dispatch'])
        self.assertIn('permissions:\n  contents: read\n',raw)
        self.assertIn("github.ref == 'refs/heads/main'",raw)
        self.assertIn('ref: ${{ github.sha }}',raw)
        self.assertIn('persist-credentials: false',raw)
        self.assertEqual(raw.count('secrets.ECOS_API_KEY'),1)
        pretests=raw.split('      - name: Verify official monthly series',1)[0]
        self.assertNotIn('ECOS_API_KEY',pretests)
        for text in ['upload-artifact','src.pipeline','src.macro.engine','data/live','pages: write','schedule:','push:','pull_request:']:
            self.assertNotIn(text,raw)


if __name__=='__main__':unittest.main()
