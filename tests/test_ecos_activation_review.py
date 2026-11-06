"""Synthetic-only readiness tests; no official values, keys or network."""
import copy
import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.macro import ecos, ecos_activation_review as review
from src.macro.ecos_preflight import Inspector, diagnostic

NOW = dt.datetime(2026, 11, 6, 15, tzinfo=review.KST)
SECRET = 'SYNTHETIC_NEVER_REAL_KEY'

class Fixture:
    def __init__(self):
        self.calls = []
        self.response_hashes = ['0'*64]
        self.table = [dict(STAT_CODE='301Y013', STAT_NAME='2.2.1. 국제수지',
                           P_STAT_CODE='*', SRCH_YN='Y', CYCLE='A,M')]
        self.items = []
        seen = set()
        for path in review.EXPECTED.values():
            parent_code = parent_name = None
            for code, name in path:
                if code not in seen:
                    self.items.append(dict(STAT_CODE='301Y013', STAT_NAME=self.table[0]['STAT_NAME'],
                        GRP_CODE='Group1', ITEM_CODE=code, ITEM_NAME=name, P_ITEM_CODE=parent_code,
                        P_ITEM_NAME=parent_name, CYCLE='M', UNIT_NAME='백만달러',
                        START_TIME='198001', END_TIME='202609'))
                    seen.add(code)
                parent_code,parent_name=code,name
    def rows(self,service,*args):
        self.calls.append((service,args))
        if service=='StatisticTableList':return copy.deepcopy(self.table)
        if service=='StatisticItemList':return copy.deepcopy(self.items)
        raise AssertionError('Only metadata endpoints are permitted')

class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.client=Fixture()
        self.inspector=Inspector(SECRET)
    def verify(self):
        return review.inspect_mapping(self.client,self.inspector,NOW)
    def test_mapping_contract_and_no_amount_query(self):
        r=self.verify()
        self.assertEqual(r['metadata_contract'],'passed')
        self.assertEqual(r['stat_code'],'301Y013')
        self.assertEqual(r['operational_approval'],'not_granted')
        self.assertEqual(r['coverage']['kto_tourism_receipts'],['1980-01','2026-09'])
        self.assertEqual([name for name,args in self.client.calls],
                         ['StatisticTableList','StatisticItemList'])
    def test_wrong_table_properties_fail(self):
        for field, value in [('STAT_CODE','301Y014'),('STAT_NAME','서비스무역세분류통계'),
                             ('SRCH_YN','N'),('CYCLE','A')]:
            with self.subTest(field=field):
                self.client=Fixture();self.client.table[0][field]=value
                with self.assertRaises((ecos.EcosError, ValueError)):self.verify()
    def test_wrong_item_parent_unit_and_period_fail(self):
        for field,value in [('P_ITEM_CODE','2C0000'),('ITEM_NAME','유학연수수입'),
                            ('UNIT_NAME','달러'),('END_TIME','202501')]:
            with self.subTest(field=field):
                self.client=Fixture()
                leaf=next(i for i in self.client.items if i['ITEM_CODE']=='2C1Y00')
                leaf[field]=value
                if field=='END_TIME':leaf['START_TIME']='202601'
                with self.assertRaises((ecos.EcosError, ValueError)):self.verify()
    def test_additional_dimension_rejected(self):
        self.client.items.append(dict(self.client.items[-1], GRP_CODE='Group2',
                                      ITEM_CODE='EXTRA', ITEM_NAME='기타 차원'))
        with self.assertRaises((ecos.EcosError, ValueError)):self.verify()
    def test_untrusted_name_not_leaked(self):
        self.client.table[0]['STAT_NAME']='<script>alert(1)</script>'
        with self.assertRaises(ValueError) as caught:self.verify()
        output=review.render(error=review.safe_reason(caught.exception),
                             details=diagnostic(caught.exception))
        self.assertNotIn('<script>',output)
        self.assertNotIn(SECRET,output)
    def test_approval_remains_pending(self):
        source=json.loads((review.ROOT/'macro_sources.json').read_text())
        s=next(x for x in source['sources'] if x['id']=='ecos_general_travel')
        self.assertFalse(s['enabled'])
        self.assertFalse(ecos.publishable(s))
        self.assertNotEqual(s['rights_review']['status'],'verified')
        self.assertNotEqual(s['crosscheck']['status'],'verified')
        self.assertTrue(all(not i['enabled'] for i in source['indicators'] if i['source_id']==s['id']))
    def test_workflow_readonly_main_only(self):
        content=(review.ROOT/'.github/workflows/ecos-activation-readiness.yml').read_text()
        self.assertIn('workflow_dispatch:',content)
        self.assertIn("github.ref == 'refs/heads/main'",content)
        self.assertIn('contents: read',content)
        self.assertIn('persist-credentials: false',content)
        self.assertEqual(content.count('secrets.ECOS_API_KEY'),1)
        for bad in ('schedule:','pull_request:','push:','contents: write','pages: write',
                    'upload-artifact','git push','src.macro.engine'):
            self.assertNotIn(bad,content)
    def test_missing_secret_no_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'summary.md'
            with patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(path)},clear=True):
                self.assertEqual(review.main(),1)
            self.assertIn('ecos_readiness_auth_missing',path.read_text())
    def test_synthetic_success_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'summary.md'
            env={'GITHUB_STEP_SUMMARY':str(path),'ECOS_API_KEY':SECRET}
            with patch.dict(os.environ,env,clear=True),patch.object(review.ecos,'Client',return_value=Fixture()):
                self.assertEqual(review.main(),0)
            summary=path.read_text()
            self.assertIn('매핑 계약: passed',summary)
            self.assertIn('게시 승인: not_granted',summary)
            self.assertNotIn(SECRET,summary)
            self.assertNotIn('2.2.1. 국제수지',summary)

if __name__=='__main__':
    unittest.main()
