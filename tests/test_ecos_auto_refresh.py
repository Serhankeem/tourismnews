"""ECOS 24-month refresh and approval-gated publication regression tests.
All statistics in this file are synthetic fixtures, never official data.
"""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.macro import ecos
from src.macro.engine import collect, public_view
from test_macro_ecos import FixtureClient, source, indicators

KST=dt.timezone(dt.timedelta(hours=9))
FIRST=dt.datetime(2026,11,5,12,tzinfo=KST)
LATER=dt.datetime(2027,12,5,12,tzinfo=KST)

class RangeClient(FixtureClient):
    def rows(self, service, *args):
        if service=='StatisticSearch':
            self.calls.append((service,args))
            code=args[-1]
            ident=next(key for key in ecos.IDS if source()['mapping']['series'][key]['selectors'][0]['path'][-1]['code']==code)
            return copy.deepcopy([r for r in self.data[ident] if args[2]<=r['TIME']<=args[3]])
        return super().rows(service,*args)

class AutomaticCollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config=dict(sources=[source()],indicators=indicators())
        self.client=RangeClient()
    def run_collect(self,now=FIRST):
        return collect(self.config,self.root/'data',self.root/'state',now=now,force=True,ecos_client=self.client)
    def state(self):
        return json.loads((self.root/'state/macro_archive.json').read_text())
    def test_first_backfill_then_rolling_range_retains_older_month(self):
        first=self.run_collect()
        self.assertEqual(first['new_observations'],26)
        self.assertEqual(first['sources'][0]['collection_state'],'new_data')
        self.assertEqual(first['sources'][0]['reference_period'],'2026-09')
        first_search=[args for name,args in self.client.calls if name=='StatisticSearch']
        self.assertTrue(all(q[2]=='202509' for q in first_search))
        initial=self.state()['indicators'][ecos.IDS[0]]['observations']['2025-09']
        self.client.calls=[]
        second=self.run_collect(LATER)
        second_search=[args for name,args in self.client.calls if name=='StatisticSearch']
        self.assertEqual(len(second_search),2)
        self.assertTrue(all(q[2]=='202512' and q[3]=='202609' for q in second_search))
        self.assertEqual(second['new_observations'],0)
        self.assertEqual(second['sources'][0]['status'],'ok')
        saved=self.state()['indicators'][ecos.IDS[0]]
        self.assertEqual(saved['observations']['2025-09'],initial)
        self.assertEqual(saved['latest_checked_range'],['2025-12','2026-09'])
        self.assertEqual(saved['latest_snapshot_missing_periods'],[])
    def test_rolling_revision_detected_and_old_data_not_classed_missing(self):
        self.run_collect()
        self.client.data[ecos.IDS[0]][-2]['DATA_VALUE']='999.123456'
        second=self.run_collect(LATER)
        self.assertEqual(second['value_corrections'],1)
        self.assertEqual(self.state()['indicators'][ecos.IDS[0]]['observations']['2025-09']['value'],1123456)
        self.assertEqual(self.state()['indicators'][ecos.IDS[0]]['revisions'][-1]['period'],'2026-08')
    def test_public_view_fails_closed_if_source_or_indicator_disabled(self):
        self.run_collect()
        archive=self.state()
        self.assertTrue(public_view(self.config,archive,FIRST)['indicators'][0]['connected'])
        self.config['sources'][0]['enabled']=False
        self.assertTrue(all(not i['connected'] for i in public_view(self.config,archive,FIRST)['indicators']))
        self.config['sources'][0]['enabled']=True
        self.config['indicators'][0]['enabled']=False
        self.assertFalse(public_view(self.config,archive,FIRST)['indicators'][0]['connected'])
    def test_unapproved_source_never_fetches_or_publishes(self):
        self.config['sources'][0]['crosscheck']['status']='pending'
        with patch.object(ecos,'fetch') as fetch:
            r=self.run_collect()
            fetch.assert_not_called()
        self.assertEqual(r['sources'][0]['status'],'error')
        self.assertFalse((self.root/'data/macro.json').exists())
    def test_official_production_config_remains_disabled(self):
        from src.macro.engine import ROOT
        c=json.loads((ROOT/'macro_sources.json').read_text())
        s=next(x for x in c['sources'] if x['id']=='ecos_general_travel')
        self.assertFalse(s['enabled'])
        self.assertNotEqual(s['mapping']['status'],'verified')
        self.assertNotEqual(s['rights_review']['status'],'verified')
        self.assertNotEqual(s['crosscheck']['status'],'verified')
        self.assertFalse(ecos.publishable(s))
        self.assertTrue(all(not x['enabled'] for x in c['indicators'] if x['id'] in ecos.IDS))
if __name__=='__main__':
    unittest.main()
