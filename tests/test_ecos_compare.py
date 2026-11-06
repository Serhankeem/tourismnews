"""Synthetic responses for the user-confirmed candidate IDs; zero real values.
Tests do not use the Repository Secret or network or write operational data.
"""
import copy
import datetime as dt
from decimal import Decimal
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from src.macro import ecos_compare as c, ecos
from src.macro.ecos_preflight import Inspector
from src.macro.model import months

NOW=dt.datetime(2026,11,6,12,tzinfo=c.KST)
FAKE='SYNTHETIC_CANDIDATE_TEST_KEY'

class Fixture:
    def __init__(self):
        self.calls=[];self.response_hashes=['0'*64];self.tables={};self.items={};self.data={}
        for code,config in c.CANDIDATES.items():
            name='2.2.1. '+config['title']
            self.tables[code]=dict(STAT_CODE=code,STAT_NAME=name,P_STAT_CODE='*',CYCLE='A,M',SRCH_YN='Y')
            rows=[]
            for item,namepart,parent in [('B','서비스수지',None),('R','여행수입','B'),('P','여행지급','B')]:
                rows.append(self.item(code,name,item,namepart,parent))
            for kind,item in config['codes'].items():
                rows.append(self.item(code,name,item,'일반여행','R' if kind=='receipts' else 'P'))
                self.data[(code,item)]=[dict(STAT_CODE=code,STAT_NAME=name,ITEM_CODE1=item,ITEM_NAME1='일반여행',UNIT_NAME='백만달러',TIME=p.replace('-',''),DATA_VALUE=('123.4567891' if kind=='receipts' else '234.9876543')) for p in months('2025-01','2026-09')]
            self.items[code]=rows
    @staticmethod
    def item(code,name,item,label,parent):
        return dict(STAT_CODE=code,STAT_NAME=name,GRP_CODE='Group1',ITEM_CODE=item,ITEM_NAME=label,P_ITEM_CODE=parent,CYCLE='M',UNIT_NAME='백만달러',START_TIME='202501',END_TIME='202609')
    def rows(self,service,*args):
        self.calls.append((service,args));code=args[0]
        if service=='StatisticTableList':return [copy.deepcopy(self.tables[code])]
        if service=='StatisticItemList':return copy.deepcopy(self.items[code])
        if service=='StatisticSearch':
            return copy.deepcopy([r for r in self.data[(code,args[-1])] if args[2]<=r['TIME']<=args[3]])
        raise AssertionError('Unapproved service')


def reference():
    return dict(data_origin='official_kto_export',definition='general_travel',reference_review='official_file_verified',unit='천 US$',source_url='https://datalab.visitkorea.or.kr/site/portal/ex/bbs/View.do?bcIdx=1&cbIdx=1127',source_sha256='0'*64,published_at='2026-10-01T12:00:00+09:00',verified_at='2026-10-02T12:00:00+09:00',finality='provisional',observations=[dict(period='2026-03',receipts='123456.7891',expenditure='234987.6543')])


class CandidateTests(unittest.TestCase):
    def setUp(self):self.f=Fixture();self.i=Inspector(FAKE)
    def run_compare(self,start='2026-01',end='2026-03',ref=None):return c.compare(self.f,self.i,NOW,start,end,ref)
    def test_metadata_and_search_for_only_two_fixed_candidates(self):
        r=self.run_compare();self.assertEqual(r['status'],'comparison_completed');self.assertEqual(r['kto_status'],'reference_missing')
        calls=[a for s,a in self.f.calls if s=='StatisticSearch']
        self.assertEqual(calls,[('301Y013','M','202601','202603','2C1Y00'),('301Y013','M','202601','202603','2C2Y00'),('301Y014','M','202601','202603','SDA200'),('301Y014','M','202601','202603','SDB200')])
        self.assertTrue(all(v=='equal_at_current_query' for row in r['rows'] for v in row['candidate'].values()))
        self.assertEqual(r['operational_approval'],'not_granted')
    def test_default_latest_common_twelve_and_different_coverage(self):
        r=c.compare(self.f,self.i,NOW);self.assertEqual((r['start'],r['end']),('2025-10','2026-09'))
        self.f.items['301Y014'][-1]['END_TIME']='202608'
        r=c.compare(self.f,self.i,NOW);self.assertEqual(r['end'],'2026-08')
    def test_actual_name_change_or_frequency_and_query_permission_fail(self):
        for field,value in [('STAT_NAME','국제수지 전망'),('CYCLE','A'),('SRCH_YN','N')]:
            self.f=Fixture();self.f.tables['301Y013'][field]=value
            with self.assertRaises(ecos.EcosError):self.run_compare()
    def test_metadata_direction_unit_group_and_hierarchy_fail(self):
        for field,value in [('ITEM_NAME','유학연수'),('UNIT_NAME','명'),('GRP_CODE','Group2'),('P_ITEM_CODE','P')]:
            self.f=Fixture();self.f.items['301Y013'][-2][field]=value
            with self.assertRaises(ecos.EcosError):self.run_compare()
    def test_additional_dimensions_not_guessed(self):
        row=self.f.items['301Y013'][0].copy();row.update(GRP_CODE='Group2',ITEM_CODE='X')
        self.f.items['301Y013'].append(row)
        with self.assertRaises(ecos.EcosError):self.run_compare()
    def test_search_metadata_identity_direction_and_extra_dimension_checked(self):
        for field,value in [('STAT_CODE','301Y014'),('STAT_NAME','wrong'),('ITEM_CODE1','2C2Y00'),('ITEM_NAME1','전체 여행수입'),('UNIT_NAME','천달러'),('ITEM_CODE2','X'),('ITEM_CODE2',False)]:
            self.f=Fixture();self.f.data[('301Y013','2C1Y00')][12][field]=value
            with self.assertRaises(ecos.EcosError):self.run_compare()
    def test_missing_months_are_partial_never_zero(self):
        self.f.data[('301Y013','2C1Y00')][12]['DATA_VALUE']=''
        r=self.run_compare();self.assertEqual(r['status'],'partial_missing');self.assertEqual(r['rows'][0]['candidate']['receipts'],'missing')
    def test_duplicate_month_is_not_silently_deduplicated(self):
        self.f.data[('301Y013','2C1Y00')].append(self.f.data[('301Y013','2C1Y00')][12].copy())
        with self.assertRaises(ecos.EcosError):self.run_compare()
    def test_bad_periods_future_outside_coverage_and_large_range_fail(self):
        for start,end in [('2026-11','2026-11'),('2024-12','2025-01'),('2026-04','2026-01'),('bad','2026-03')]:
            with self.subTest(start=start),self.assertRaises(ValueError):self.run_compare(start,end)
        meta={code:c.candidate_metadata(self.f,self.i,code) for code in c.CANDIDATES}
        for m in meta.values():
            for i in m['series'].values():i['start']='2020-01'
        with self.assertRaises(ecos.EcosError):c.period_range(meta,'2021-01','2026-09',NOW)
    def test_fine_decimal_precision_no_float_or_dollar_rounding(self):
        self.assertEqual(c.monetary('123.4567891','백만달러'),Decimal('123.4567891'))
        self.assertEqual(c.monetary('123456.7891','천 US$'),Decimal('123.4567891'))
        self.f.data[('301Y014','SDA200')][12]['DATA_VALUE']='123.4567892'
        self.assertIn('difference',self.run_compare()['rows'][0]['candidate']['receipts'])
        for value in ['NaN','inf','-1','1e2',True,1.2,'1,000']:
            with self.assertRaises(ecos.EcosError):c.monetary(value,'백만달러')
    def test_kto_reference_exact_conversion_and_vintage_not_assumed(self):
        r=self.run_compare(ref=reference());self.assertEqual(r['kto_status'],'partial_reference_coverage');self.assertEqual(r['rows'][-1]['kto']['receipts'],'value_equal_vintage_not_equivalent')
        self.assertEqual(r['rows'][0]['kto']['receipts'],'reference_missing')
        ref=reference();ref['observations'][0]['receipts']='123456.7892'
        self.assertIn('vintage_review',self.run_compare(ref=ref)['rows'][-1]['kto']['receipts'])
    def test_reference_without_evidence_wrong_source_units_dates_or_origin_denied(self):
        for field,value in [('data_origin','synthetic_test'),('definition','total_travel'),('reference_review','pending'),('unit','원'),('source_url','http://datalab.visitkorea.or.kr/'),('source_url','https://private.example/file'),('source_sha256',None),('published_at','2026-10-01'),('finality','assumed_final')]:
            ref=reference();ref[field]=value
            with self.subTest(field=field),self.assertRaises(ecos.EcosError):c.references(ref,NOW)
    def test_duplicate_reference_future_and_float_invalid(self):
        for what in ['duplicate','future','float']:
            ref=reference()
            if what=='duplicate':ref['observations'].append(ref['observations'][0].copy())
            if what=='future':ref['observations'][0]['period']='2026-11'
            if what=='float':ref['observations'][0]['receipts']=1.23
            with self.assertRaises(ecos.EcosError):c.references(ref,NOW)
    def test_summary_is_minimal_outcomes_not_response_or_monetary_values(self):
        r=self.run_compare(ref=reference());body=c.summary(r)
        for forbidden in [FAKE,'123.4567891','123456.7891','DATA_VALUE','2.2.1. 국제수지','source_sha256','P_ITEM_CODE']:
            self.assertNotIn(forbidden,body)
        for allowed in ['301Y013','301Y014','백만달러','2026-03','reference']:
            self.assertIn(allowed,body)
    def test_whitespace_names_are_consistent_across_all_services(self):
        original=self.f.rows
        def rows(service,*args):
            result=original(service,*args)
            for r in result:r['STAT_NAME']=r['STAT_NAME'].replace(' ','\n' if service=='StatisticTableList' else '\t')
            return result
        self.f.rows=rows;self.assertEqual(self.run_compare()['status'],'comparison_completed')
    def test_false_kto_reference_status_is_not_crosscheck_success(self):
        r=self.run_compare();self.assertTrue(all(row['kto']['receipts']=='reference_missing' for row in r['rows']))
        self.assertIn('교차검증 미완료',c.summary(r))


class EntrypointTests(unittest.TestCase):
    def test_only_summary_file_and_no_secret_or_raw_logs(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'summary.md';out=io.StringIO()
            env={'GITHUB_STEP_SUMMARY':str(target),'ECOS_API_KEY':FAKE,'ECOS_COMPARE_START':'2026-01','ECOS_COMPARE_END':'2026-03'}
            with patch.dict(os.environ,env,clear=True),patch.object(c.ecos,'Client',return_value=Fixture()),patch('sys.stdout',out),patch.object(c,'REFERENCE',Path(d)/'absent-reference.json'):
                self.assertEqual(c.main(),0)
            self.assertEqual([p.name for p in Path(d).iterdir()],['summary.md']);self.assertNotIn(FAKE,target.read_text()+out.getvalue());self.assertNotIn('123.4567891',target.read_text()+out.getvalue())
    def test_missing_invalid_key_and_unexpected_errors_are_fixed(self):
        for error in [ecos.EcosError('ecos_auth_required'),ecos.EcosError('ecos_auth_invalid'),RuntimeError('https://private.example/'+FAKE)]:
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':d+'/summary'},clear=True),patch.object(c.ecos,'Client',side_effect=error),patch('sys.stdout',io.StringIO()):
                self.assertEqual(c.main(),1);body=Path(d+'/summary').read_text();self.assertNotIn(FAKE,body);self.assertNotIn('private.example',body)
    def test_repository_output_is_blocked_before_network(self):
        with patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(c.ROOT/'macro_sources.json')},clear=True),patch.object(c.ecos,'Client') as client:
            self.assertEqual(c.main(),1);client.assert_not_called()
    def test_new_workflow_is_manual_main_only_and_readonly(self):
        text=(c.ROOT/'.github/workflows/ecos-compare.yml').read_text()
        self.assertIn('workflow_dispatch:',text);self.assertIn("github.ref == 'refs/heads/main'",text)
        self.assertIn('contents: read',text);self.assertIn('persist-credentials: false',text);self.assertIn('ref: ${{ github.sha }}',text)
        self.assertEqual(text.count('${{ secrets.ECOS_API_KEY }}'),1)
        for forbidden in ['schedule:','pull_request:','push:','workflow_call:','contents: write','pages:','id-token:','upload-artifact','src.macro.engine','src.pipeline','git push','environment:']:
            self.assertNotIn(forbidden,text)
    def test_original_metadata_review_guard_is_unchanged(self):
        from src.macro.ecos_preflight import assessment
        self.assertEqual(assessment(dict(status='inspection_complete',tables=[dict(items=[])])),'not_found')
        pair=[dict(direction='receipts_candidate',metadata_complete=True,unit='백만달러'),dict(direction='expenditure_candidate',metadata_complete=True,unit='백만달러')]
        self.assertEqual(assessment(dict(status='inspection_complete',tables=[dict(items=pair,groups={'Group1':2}),dict(items=pair,groups={'Group1':2})])),'review_required')
        self.assertNotIn('assessment',Path(c.__file__).read_text())

if __name__=='__main__':unittest.main()
