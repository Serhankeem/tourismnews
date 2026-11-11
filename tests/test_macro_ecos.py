"""SYNTHETIC ECOS fixtures. 999Y999 and every amount here are NOT real data.

API field names follow the inspected official developer specification. No fixture
or derived result is added to operational JSON, data/live or the site bundle.
"""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from urllib.error import HTTPError, URLError
from src.macro import ecos
from src.macro.engine import collect, public_view
from src.macro.model import comparisons, months
from test_macro import CONFIG, CORE, snapshot as kto_snapshot

NOW = dt.datetime(2026, 11, 5, 12, tzinfo=dt.timezone(dt.timedelta(hours=9)))


def source():
    paths = {
        ecos.IDS[0]: [('B', '국제수지'), ('C', '경상수지'), ('S', '서비스수지'), ('TR', '여행수입'), ('GR', '일반여행')],
        ecos.IDS[1]: [('B', '국제수지'), ('C', '경상수지'), ('S', '서비스수지'), ('TP', '여행지급'), ('GP', '일반여행')],
    }
    proof = dict(status='verified', evidence_url='https://ecos.bok.or.kr/api/#/DevGuide/DevSpeciflcation', verified_at='2026-11-05')
    m = dict(**proof, stat_code='999Y999', stat_name='SYNTHETIC 일반여행 (실제 통계표 아님)', unit_name='백만달러', frequency='M', series={})
    for key, path in paths.items():
        m['series'][key] = dict(selectors=[dict(group='Group1', path=[dict(code=c, name=n) for c, n in path])])
    return dict(id='ecos_general_travel', name='SYNTHETIC ECOS TEST ONLY', enabled=True,
                method='official_ecos_api', auth_env='ECOS_API_KEY', start_period='2025-09',
                mapping=m, rights_review=copy.deepcopy(proof), crosscheck=copy.deepcopy(proof))


def indicators():
    return [dict(id=key, name=kind, source_id='ecos_general_travel', enabled=True, unit='US$',
                 value_kind='money_nonnegative', priority=1, frequency='M', publisher='한국은행 ECOS',
                 definition='SYNTHETIC GENERAL TRAVEL ' + kind, source_url=ecos.BASE)
            for key, kind in zip(ecos.IDS, ('일반여행수입', '일반여행지급'))]


class FixtureClient:
    """Deterministic fixture transport, no network and no real statistics."""
    def __init__(self):
        s = source(); m = s['mapping']; self.calls = []; self.response_hashes = ['0'*64]
        self.table = [dict(STAT_CODE=m['stat_code'], STAT_NAME=m['stat_name'], CYCLE='M', SRCH_YN='Y')]
        self.items = []; seen = set()
        self.data = {}
        for key in ecos.IDS:
            selector = m['series'][key]['selectors'][0]; parent = None
            for node in selector['path']:
                if node['code'] not in seen:
                    self.items.append(dict(STAT_CODE=m['stat_code'], STAT_NAME=m['stat_name'], GRP_CODE='Group1', ITEM_CODE=node['code'], ITEM_NAME=node['name'], P_ITEM_CODE=parent, CYCLE='M', START_TIME='202509', END_TIME='202609', UNIT_NAME='백만달러'))
                    seen.add(node['code'])
                parent = node['code']
            self.data[key] = [dict(STAT_CODE=m['stat_code'], STAT_NAME=m['stat_name'],
                ITEM_CODE1=selector['path'][-1]['code'], ITEM_NAME1=selector['path'][-1]['name'],
                TIME=p.replace('-', ''), UNIT_NAME='백만달러', DATA_VALUE=f'{n+1}.123456')
                for n, p in enumerate(months('2025-09', '2026-09'))]
    def rows(self, service, *args):
        self.calls.append((service, args))
        if service == 'StatisticTableList':return copy.deepcopy(self.table)
        if service == 'StatisticItemList':return copy.deepcopy(self.items)
        key = next(k for k in ecos.IDS if source()['mapping']['series'][k]['selectors'][0]['path'][-1]['code'] == args[-1])
        return copy.deepcopy(self.data[key])


class MappingAndParserTests(unittest.TestCase):
    def test_checked_in_config_has_no_invented_codes_units_or_activation(self):
        s = next(s for s in CONFIG['sources'] if s['id'] == 'ecos_general_travel')
        self.assertFalse(s['enabled']); self.assertIsNone(s['mapping']['stat_code'])
        self.assertIsNone(s['mapping']['unit_name']); self.assertFalse(ecos.publishable(s))
        for i in CONFIG['indicators']:
            if i['source_id']=='ecos_general_travel':
                self.assertFalse(i['enabled'])
                self.assertIsNone(i['unit'])
            elif i['id'] in ecos.IDS:
                self.assertEqual(i['source_id'],'tourgo_tourism_balance')
                self.assertTrue(i['enabled'])
    def test_pending_mapping_never_calls_transport(self):
        s=source();s['mapping']['status']='pending_verification';client=Mock()
        with self.assertRaisesRegex(ecos.EcosError,'mapping_pending'):ecos.fetch(s,indicators(),client,NOW)
        client.rows.assert_not_called()

    def test_zero_is_observed_and_blank_duplicate_is_rejected(self):
        c=FixtureClient();c.data[ecos.IDS[0]][0]['DATA_VALUE']='0'
        self.assertEqual(ecos.fetch(source(),indicators(),c,NOW)['values'][ecos.IDS[0]]['2025-09'],0)
        c.data[ecos.IDS[0]][0]['DATA_VALUE']='';c.data[ecos.IDS[0]].append(c.data[ecos.IDS[0]][0].copy())
        with self.assertRaisesRegex(ecos.EcosError,'duplicate'):ecos.fetch(source(),indicators(),c,NOW)

    def test_validated_fixture_full_hierarchy_and_separate_directions(self):
        c=FixtureClient();s=source();r=ecos.fetch(s,indicators(),c,NOW)
        self.assertEqual(sum(len(v) for v in r['values'].values()),26)
        self.assertEqual(r['values'][ecos.IDS[0]]['2025-09'],1123456)
        self.assertIsNone(r['release_published_at']);self.assertEqual(r['records'][ecos.IDS[0]]['2025-09']['finality'],'not_stated')
        self.assertEqual(c.calls[0],('StatisticTableList',('999Y999',)))
    def test_total_travel_or_education_cannot_replace_general_travel(self):
        for title in ['여행수입 전체','유학연수수입','유학 포함 일반여행수입']:
            s=source();s['mapping']['series'][ecos.IDS[0]]['selectors'][0]['path'][-1]['name']=title
            with self.assertRaisesRegex(ecos.EcosError,'definition_mismatch'):ecos.mapping(s)
    def test_reversed_receipts_payment_mapping_fails(self):
        s=source();m=s['mapping'];m['series'][ecos.IDS[0]],m['series'][ecos.IDS[1]]=m['series'][ecos.IDS[1]],m['series'][ecos.IDS[0]]
        with self.assertRaisesRegex(ecos.EcosError,'definition_mismatch'):ecos.mapping(s)
    def test_wrong_table_item_parent_cycle_or_unit_fails(self):
        for target,field,value in [('table','STAT_CODE','999Y998'),('table','STAT_NAME','different'),('table','CYCLE','A'),('items','P_ITEM_CODE','unknown'),('items','UNIT_NAME','원')]:
            c=FixtureClient();getattr(c,target)[-1][field]=value
            with self.subTest(field=field), self.assertRaises(ecos.EcosError):ecos.fetch(source(),indicators(),c,NOW)
    def test_record_unit_direction_and_stat_name_checked_again(self):
        for field,value in [('UNIT_NAME','천명'),('ITEM_CODE1','GP'),('ITEM_NAME1','여행수입 전체'),('STAT_NAME','other')]:
            c=FixtureClient();c.data[ecos.IDS[0]][0][field]=value
            with self.subTest(field=field), self.assertRaises(ecos.EcosError):ecos.fetch(source(),indicators(),c,NOW)
    def test_exact_decimal_to_dollars_no_binary_rounding(self):
        self.assertEqual(ecos.amount('123.456789','백만달러'),123456789)
        self.assertEqual(ecos.amount('0.000001','백만달러'),1)
        self.assertEqual(ecos.amount('1.001','천달러'),1001)
        self.assertEqual(ecos.amount('9007199254.740991','백만달러'),ecos.MAX_INTEGER)
        for raw in ['1.0000001','NaN','Infinity','-1','1e2','1,000','9007199254.740992','1.'+'0'*40+'1']:
            with self.subTest(raw=raw),self.assertRaises(ecos.EcosError):ecos.amount(raw,'백만달러')
    def test_invalid_data_types_bool_and_wrong_units(self):
        for value in [True,12,1.2,None]:
            with self.assertRaises(ecos.EcosError):ecos.amount(value,'백만달러')
        with self.assertRaises(ecos.EcosError):ecos.amount('1','백만원')
    def test_future_duplicate_month_and_outside_range_fail(self):
        for mode in ['future','duplicate','outside','malformed']:
            c=FixtureClient();rows=c.data[ecos.IDS[0]]
            if mode=='duplicate':rows.append(rows[0].copy())
            else:rows[0]['TIME']={'future':'202611','outside':'202401','malformed':'2026-09'}[mode]
            with self.subTest(mode=mode),self.assertRaises(ecos.EcosError):ecos.fetch(source(),indicators(),c,NOW)
    def test_missing_cells_and_absent_months_are_never_zero(self):
        c=FixtureClient();c.data[ecos.IDS[0]][1]['DATA_VALUE']='';del c.data[ecos.IDS[0]][2]
        r=ecos.fetch(source(),indicators(),c,NOW)
        self.assertNotIn('2025-10',r['values'][ecos.IDS[0]]);self.assertEqual(r['missing_periods'][ecos.IDS[0]],['2025-10','2025-11'])
        self.assertFalse(r['missing_periods'][ecos.IDS[1]])
    def test_api_does_not_infer_finality_from_date_or_unknown_flags(self):
        c=FixtureClient();c.data[ecos.IDS[0]][0]['FINALITY']='final'
        r=ecos.fetch(source(),indicators(),c,NOW)
        self.assertEqual(r['records'][ecos.IDS[0]]['2025-09']['finality'],'not_stated')
    def test_signed_balance_separate_and_percentage_not_interpreted(self):
        self.assertEqual(ecos.balance(100,200),dict(value=-100,unit='US$',percentage_policy='absolute_changes_only'))
        for value in [-1,True,1.5]:
            with self.assertRaises(ecos.EcosError):ecos.balance(value,100)
    def test_exact_comparisons_and_missing_months(self):
        r=comparisons({'2025-09':{'value':3},'2026-08':{'value':7},'2026-09':{'value':10}},'2026-09',exact=True)
        self.assertEqual(r['mom_pct'],42.86);self.assertEqual(r['yoy_pct'],233.33);self.assertIsNone(r['ytd_value'])
    def test_exact_ytd_never_exports_an_unsafe_integer(self):
        r=comparisons({'2026-01':{'value':ecos.MAX_INTEGER},'2026-02':{'value':1}},'2026-02',exact=True)
        self.assertIsNone(r['ytd_value']);self.assertIsNone(r['ytd_yoy_pct'])

    def test_crosscheck_same_period_units_and_vintage_difference(self):
        values={k:{'2026-09':1123456} for k in ecos.IDS}
        official=dict(period='2026-09',receipts='1.123456',expenditure='1.123455',unit_name='백만달러',source_url='https://datalab.visitkorea.or.kr/site/portal/ex/bbs/View.do',release_published_at='2026-10-28T00:00:00+09:00')
        r=ecos.crosscheck(values,official);self.assertEqual(r['series'][ecos.IDS[0]]['status'],'match')
        self.assertIn('requires_review',r['series'][ecos.IDS[1]]['status'])
        official['period']='2026-08';self.assertEqual(ecos.crosscheck(values,official)['series'][ecos.IDS[0]]['status'],'missing')


class ClientSecurityTests(unittest.TestCase):
    def test_missing_key_and_sample_cannot_be_promoted(self):
        for key,code in [('', 'auth_required'),('sample','auth_invalid'),('a/b','auth_invalid')]:
            with self.assertRaisesRegex(ecos.EcosError,code):ecos.Client(key=key)
    def client(self,doc):
        client=ecos.Client(key='SYNTHETIC_NOT_A_REAL_KEY')
        client._read=Mock(return_value=json.dumps(doc).encode());return client
    def test_invalid_key_rate_and_query_errors_never_copy_message(self):
        for code,kind in [('INFO-100','auth_invalid'),('ERROR-602','rate_limited'),('ERROR-400','query_timeout')]:
            c=self.client({'RESULT':{'CODE':code,'MESSAGE':'SECRET URL /SYNTHETIC_NOT_A_REAL_KEY/'}})
            with self.assertRaisesRegex(ecos.EcosError,kind) as error:c.rows('StatisticItemList','999Y999')
            self.assertNotIn('SECRET',str(error.exception));self.assertNotIn('SYNTHETIC_',str(error.exception))
    def test_no_data_not_confused_with_successful_values(self):
        self.assertEqual(self.client({'RESULT':{'CODE':'INFO-200'}}).rows('StatisticSearch','999Y999'),[])
    def test_malformed_and_truncated_page_fail_closed(self):
        for doc in [[],{}, {'StatisticItemList':{'list_total_count':2,'row':[{}]}}, {'StatisticItemList':{'list_total_count':True,'row':[]}}]:
            with self.assertRaises(ecos.EcosError):self.client(doc).rows('StatisticItemList','999Y999')
    def test_complete_pagination_and_key_echo_rejection(self):
        c=ecos.Client(key='SYNTHETIC_NOT_A_REAL_KEY');c._read=Mock(side_effect=[json.dumps({'StatisticTableList':{'list_total_count':1001,'row':[{}]*1000}}).encode(),json.dumps({'StatisticTableList':{'list_total_count':1001,'row':[{}]}}).encode()])
        self.assertEqual(len(c.rows('StatisticTableList')),1001);self.assertEqual(c._read.call_count,2)
        c=self.client({'StatisticTableList':{'list_total_count':1,'row':[{'STAT_NAME':'SYNTHETIC_NOT_A_REAL_KEY'}]}})
        with self.assertRaisesRegex(ecos.EcosError,'unexpected_credential'):c.rows('StatisticTableList')

    def test_allowlisted_services_and_parameters_only(self):
        c=self.client({})
        for svc,arg in [('internalService','x'),('StatisticSearch','../secret'),('StatisticSearch','a?key=b')]:
            with self.assertRaises(ecos.EcosError):c.rows(svc,arg)
        c._read.assert_not_called()
    def test_https_only_no_redirect_and_error_url_redaction(self):
        c=ecos.Client(key='SYNTHETIC_NOT_A_REAL_KEY');rules=Mock();rules.can_fetch.return_value=True;rules.crawl_delay.return_value=None;rules.request_rate.return_value=None;c.rules=rules
        for code,kind in [(302,'redirect_blocked'),(403,'auth_or_access_denied'),(429,'rate_limited')]:
            c.opener=Mock();c.opener.open.side_effect=HTTPError('https://ecos.bok.or.kr/api/SYNTHETIC_NOT_A_REAL_KEY',code,'SECRET',{},None)
            with patch('src.macro.ecos.time.sleep'),self.assertRaisesRegex(ecos.EcosError,kind) as error:c.rows('StatisticTableList','999Y999')
            self.assertNotIn('SYNTHETIC_',str(error.exception));self.assertEqual(c.opener.open.call_count,1)
    def test_retry_bounded_network_and_robots_failures_sanitized(self):
        c=ecos.Client(key='SYNTHETIC_NOT_A_REAL_KEY');c.opener=Mock();c.opener.open.side_effect=URLError('SECRET')
        with self.assertRaisesRegex(ecos.EcosError,'robots_unavailable'):c.rows('StatisticTableList','999Y999')
        rules=Mock();rules.can_fetch.return_value=True;rules.crawl_delay.return_value=None;rules.request_rate.return_value=None;c.rules=rules
        c.opener.open.side_effect=HTTPError('SECRET',503,'SECRET',{},None);c.opener.open.reset_mock()
        with patch('src.macro.ecos.time.sleep'),self.assertRaisesRegex(ecos.EcosError,'http_503'):c.rows('StatisticTableList','999Y999')
        self.assertEqual(c.opener.open.call_count,2)


class FinancialEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.config=dict(sources=[source()],indicators=indicators());self.c=FixtureClient()
    def run_collect(self,now=NOW):
        return collect(self.config,self.root/'data',self.root/'state',now=now,force=True,ecos_client=self.c)
    def archive(self):return json.loads((self.root/'state/macro_archive.json').read_text())
    def test_new_and_repeat_exact_persistence_no_duplicates(self):
        self.assertEqual(self.run_collect()['new_observations'],26)
        a=self.archive();r=self.run_collect(NOW+dt.timedelta(hours=1))
        self.assertEqual(r['new_observations'],0);self.assertEqual(r['unchanged_observations'],26)
        self.assertEqual(r['sources'][0]['collection_state'],'no_new_data')
        b=self.archive();self.assertEqual(len(b['indicators'][ecos.IDS[0]]['observations']),13)
        self.assertEqual(a['indicators'][ecos.IDS[0]]['observations']['2025-09']['first_collected_at'],b['indicators'][ecos.IDS[0]]['observations']['2025-09']['first_collected_at'])
        public=json.loads((self.root/'data/macro.json').read_text());i=public['indicators'][0]
        self.assertEqual(i['display_divisor'],1000000);self.assertEqual(i['latest']['unit'],'US$')
        self.assertNotIn('SYNTHETIC_NOT_A_REAL_KEY',json.dumps(b))
    def test_revision_records_before_after_and_no_inferred_publication(self):
        self.run_collect();self.c.data[ecos.IDS[0]][0]['DATA_VALUE']='2.123456';r=self.run_collect(NOW+dt.timedelta(days=1));a=self.archive()['indicators'][ecos.IDS[0]]
        self.assertEqual(r['value_corrections'],1);self.assertEqual(a['revisions'][0]['before']['value'],1123456)
        self.assertEqual(a['revisions'][0]['after']['value'],2123456)
        self.assertIsNone(a['observations']['2025-09']['release_published_at'])
        self.assertEqual(a['observations']['2025-09']['source_value'],'2.123456')
    def test_missing_past_month_retains_its_complete_original_record(self):
        self.run_collect();old=self.archive()['indicators'][ecos.IDS[0]]['observations']['2025-10']
        self.c.data[ecos.IDS[0]][1]['DATA_VALUE']='';r=self.run_collect()
        self.assertEqual(r['status'],'partial');self.assertEqual(old,self.archive()['indicators'][ecos.IDS[0]]['observations']['2025-10'])
    def test_invalid_auth_preserves_last_verified_files(self):
        self.run_collect();paths=[self.root/'data/macro.json',self.root/'state/macro_archive.json'];before=[p.read_bytes() for p in paths]
        self.c.rows=Mock(side_effect=ecos.EcosError('ecos_auth_invalid'));r=self.run_collect()
        self.assertEqual(r['sources'][0]['collection_state'],'authentication_required');self.assertEqual(before,[p.read_bytes() for p in paths])
    def test_publication_review_hides_existing_records_and_can_restore(self):
        self.run_collect();archive=self.archive();self.config['sources'][0]['rights_review']['status']='review'
        self.assertFalse(public_view(self.config,archive,NOW)['indicators'][0]['connected'])
        self.config['sources'][0]['rights_review']['status']='verified'
        self.assertTrue(public_view(self.config,archive,NOW)['indicators'][0]['connected'])
        self.config['sources'][0]['crosscheck']['status']='pending'
        self.assertFalse(public_view(self.config,archive,NOW)['indicators'][0]['connected'])
        self.assertEqual(len(archive['indicators'][ecos.IDS[0]]['observations']),13)
    def test_stored_wrong_provenance_hidden_without_deleting_history(self):
        self.run_collect();a=self.archive();before=copy.deepcopy(a);record=a['indicators'][ecos.IDS[0]]['observations']['2025-09'];record['item_codes']=['TOTAL_TRAVEL']
        self.assertFalse(public_view(self.config,a,NOW)['indicators'][0]['connected'])
        self.assertEqual(len(a['indicators'][ecos.IDS[0]]['observations']),13)
        a=before;a['indicators'][ecos.IDS[0]]['observations']['2025-09']['source_value']='9'
        self.assertFalse(public_view(self.config,a,NOW)['indicators'][0]['connected'])

    def test_real_existing_seven_series_and_revisions_byte_equivalent(self):
        original=json.loads((Path(__file__).resolve().parents[1]/'collector_state/macro_archive.json').read_text())
        self.assertEqual(len(original['indicators']),7)
        state=self.root/'state';state.mkdir();(state/'macro_archive.json').write_text(json.dumps(original))
        self.config['sources'].insert(0,copy.deepcopy(CONFIG['sources'][0]))
        self.config['indicators'] += [copy.deepcopy(i) for i in CONFIG['indicators'] if i.get('country') or i['id'] in ('kto_inbound','kto_outbound')]
        with patch('src.macro.kto.fetch',side_effect=OSError('synthetic provider failure')):result=self.run_collect()
        updated=self.archive();self.assertEqual(result['status'],'partial')
        for key,old in original['indicators'].items():self.assertEqual(updated['indicators'][key],old)

    def test_one_failed_source_does_not_fail_successful_kto(self):
        self.config['sources'].insert(0,copy.deepcopy(CONFIG['sources'][0]));self.config['indicators']+=copy.deepcopy(CORE)
        self.c.rows=Mock(side_effect=ecos.EcosError('ecos_auth_invalid'))
        with patch('src.macro.kto.fetch',return_value=kto_snapshot()):r=self.run_collect()
        self.assertEqual(r['status'],'partial');self.assertEqual(r['successful_sources'],1)
        self.assertEqual(r['connected_primary_indicators'],2)
        self.assertEqual(self.archive()['indicators']['kto_inbound']['observations']['2026-09']['value'],200)
    def test_corrupt_ledger_refuses_reset_and_operator_restoration_works(self):
        self.run_collect();p=self.root/'state/macro_archive.json';backup=p.read_bytes();public=(self.root/'data/macro.json').read_bytes()
        for bad in [b'broken',b'{}']:
            p.write_bytes(bad);r=self.run_collect();self.assertEqual(r['status'],'failed');self.assertEqual((self.root/'data/macro.json').read_bytes(),public)
        p.write_bytes(backup);self.assertEqual(self.run_collect()['new_observations'],0)
    def test_disabled_config_key_absence_is_not_success_and_no_fetch(self):
        config=copy.deepcopy(CONFIG)
        with patch.dict(os.environ,{},clear=True),patch('src.macro.kto.fetch',return_value=kto_snapshot()) as fetch:
            # Match only the KTO fixture's two test indicators.
            config['indicators']=[i for i in config['indicators'] if i.get('priority')==1]
            r=collect(config,self.root/'data',self.root/'state',now=NOW,force=True)
        api=next(s for s in r['sources'] if s['id']=='ecos_general_travel')
        self.assertEqual(api['status'],'not_connected');self.assertEqual(api['collection_state'],'authentication_required');self.assertEqual(r['connected_primary_indicators'],2)

class PrivatePreflightTests(unittest.TestCase):
    def test_private_output_is_required_and_repository_output_refused(self):
        root=Path(__file__).resolve().parents[1]
        for path in [root,root/'site/data',root/'collector_state']:
            with patch('sys.argv',['ecos','metadata','--private-dir',str(path)]),patch('sys.stderr'),self.assertRaises(SystemExit) as error:ecos.main()
            self.assertEqual(error.exception.code,2)
    def test_missing_key_writes_no_file_or_public_output(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{},clear=True),patch('sys.argv',['ecos','metadata','--private-dir',d]),patch('sys.stdout') as out:
            self.assertEqual(ecos.main(),1);self.assertFalse(list(Path(d).iterdir()));out.write.assert_any_call('ecos_auth_required')

if __name__ == '__main__':unittest.main()
