"""Synthetic observations only. No production key, network, data/live, or UI."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.macro import decimal_series, ecos, ecos_decimal
from src.macro.engine import collect, public_view
from src.macro.model import decimal_value, decimal_comparisons
from tools.validate_market_weather_foundation import private_config, replay_config, Replay, NOW


def fixture():
    config = replay_config(private_config())
    rows = {}
    for item in config['indicators']:
        rows[item['id']] = []
        for month, value in [('202101','100.0100'),('202102','102.123456789123456789')]:
            row = dict(STAT_CODE=item['stat_code'],TIME=month,DATA_VALUE=value,UNIT_NAME=item['unit'])
            for n in range(1,5):
                row[f'ITEM_CODE{n}'] = item['item_codes'][n-1] if n<=len(item['item_codes']) else None
                row[f'ITEM_NAME{n}'] = item['item_names'][n-1] if n<=len(item['item_names']) else None
            rows[item['id']].append(row)
    return config,Replay(config,rows)


class DecimalFoundationTests(unittest.TestCase):
    def setUp(self):
        self.config,self.client=fixture()
        self.source=self.config['sources'][0]
        self.items=[i for i in self.config['indicators'] if i['source_id']==self.source['id']]

    def snapshot(self):return ecos_decimal.fetch(self.source,self.items,self.client,NOW)
    def archive(self):return dict(schema_version=1,indicators={},sources={})

    def test_exact_canonical_values_without_float(self):
        self.assertEqual(decimal_value('1337.6600'),'1337.66')
        self.assertEqual(decimal_value('102.123456789123456789'),'102.123456789123456789')
        self.assertEqual(decimal_value('0.000000000000000001'),'0.000000000000000001')
        for value in [1,True,1.1,'1e2','NaN','Infinity','-1','01','1.0000000000000000001']:
            with self.subTest(value=value),self.assertRaises(ValueError):decimal_value(value)

    def test_yoy_explicit_precision_missing_zero_and_no_sum(self):
        obs={'2021-01':{'value':'100.01'},'2022-01':{'value':'110.011'}}
        result=decimal_comparisons(obs,'2022-01')
        self.assertEqual(result['yoy_pct'],'10.000000')
        self.assertIsNone(result['mom_pct'])
        self.assertNotIn('ytd_value',result)
        obs['2021-01']['value']='0'
        self.assertIsNone(decimal_comparisons(obs,'2022-01')['yoy_pct'])

    def test_default_disabled_and_existing_config_unchanged(self):
        config=private_config()
        self.assertEqual(len(config['sources']),3);self.assertEqual(len(config['indicators']),9)
        self.assertTrue(all(not s['enabled'] and s['rights_review']['status']=='review' for s in config['sources']))
        with tempfile.TemporaryDirectory() as d,patch('src.macro.ecos.Client',side_effect=AssertionError('no network')):
            h=collect(config,Path(d)/'data',Path(d)/'state',now=NOW,force=True)
            self.assertEqual(h['attempted_sources'],0)
            self.assertFalse((Path(d)/'state/macro_archive.json').exists())

    def test_collection_review_gate_precedes_client(self):
        self.source['collection_review']['status']='review'
        with self.assertRaisesRegex(ValueError,'not_approved'):self.snapshot()

    def test_missing_and_sample_key_rejected(self):
        for env in [{},{'ECOS_API_KEY':'sample'}]:
            with patch.dict('os.environ',env,clear=True),self.assertRaises(ValueError):ecos.Client()

    def test_replay_is_never_authenticated_or_published(self):
        snap=self.snapshot()
        self.assertFalse(snap['authentication_verified'])
        for observations in snap['records'].values():
            for record in observations.values():
                self.assertEqual(record['publication_status'],'blocked')
                self.assertIsNone(record['release_published_at'])
                self.assertIsNone(record['original_publication_at'])
                self.assertEqual(record['finality'],'not_stated')
        archive,_=decimal_series.merge(self.archive(),self.source,self.items,snap,NOW)
        self.assertEqual(public_view(self.config,archive,NOW)['indicators'],[])

    def test_selectors_units_duplicates_missing_months_reject(self):
        for mutate in [lambda r:r[0].update(ITEM_CODE2='0000200'),
                       lambda r:r[0].update(UNIT_NAME='2025=100'),
                       lambda r:r.append(copy.deepcopy(r[0])),
                       lambda r:r.pop(0),lambda r:r[0].update(DATA_VALUE=1.1),
                       lambda r:r[0].update(TIME='202611')]:
            with self.subTest(mutate=mutate):
                config,client=fixture();items=[i for i in config['indicators'] if i['source_id']==self.source['id']]
                mutate(client.data[items[0]['id']])
                with self.assertRaises((ValueError,TypeError)):ecos_decimal.fetch(config['sources'][0],items,client,NOW)

    def test_metadata_drift_and_future_latest_reject(self):
        original=self.client.rows
        for field,value in [('UNIT_NAME','2025=100'),('ITEM_NAME','changed'),('END_TIME','202611')]:
            def changed(service,*args,field=field,value=value):
                rows=original(service,*args)
                if service=='StatisticItemList':rows[0][field]=value
                return rows
            self.client.rows=changed
            with self.assertRaises(ValueError):self.snapshot()
        self.client.rows=original

    def test_value_and_finality_vintages_and_idempotence(self):
        archive,counts=decimal_series.merge(self.archive(),self.source,self.items,self.snapshot(),NOW)
        self.assertEqual(counts['new_observations'],4)
        repeated,counts=decimal_series.merge(archive,self.source,self.items,self.snapshot(),NOW+dt.timedelta(days=1))
        self.assertEqual(counts['unchanged_observations'],4)
        self.assertTrue(all(not i['revisions'] for i in repeated['decimal_indicators'].values()))
        key=self.items[0]['id'];period='2021-01';previous=copy.deepcopy(repeated['decimal_indicators'][key]['observations'][period])
        snap=self.snapshot();snap['records'][key][period].update(value='103.1',source_value='103.100')
        corrected,counts=decimal_series.merge(repeated,self.source,self.items,snap,NOW+dt.timedelta(days=2))
        series=corrected['decimal_indicators'][key]
        self.assertEqual(counts['value_corrections'],1)
        self.assertEqual(series['revisions'][0]['before'],previous)
        self.assertEqual(series['observations'][period]['first_collected_at'],previous['first_collected_at'])
        snap['records'][key][period]['finality']='provisional'
        final,counts=decimal_series.merge(corrected,self.source,self.items,snap,NOW+dt.timedelta(days=3))
        self.assertEqual(counts['status_changes'],1)
        self.assertEqual(len(final['decimal_indicators'][key]['revisions']),2)
        decimal_series.validate_archive(final,corrected)

    def test_identity_change_rejected_without_mutating_old_archive(self):
        archive,_=decimal_series.merge(self.archive(),self.source,self.items,self.snapshot(),NOW)
        before=copy.deepcopy(archive)
        for field,value in [('base_year',2025),('unit','2025=100'),('item_codes',['new']),('definition','new')]:
            items=copy.deepcopy(self.items);items[0][field]=value
            with self.assertRaises(ValueError):decimal_series.merge(archive,self.source,items,self.snapshot(),NOW)
        self.assertEqual(archive,before)

    def test_durable_history_checks(self):
        archive,_=decimal_series.merge(self.archive(),self.source,self.items,self.snapshot(),NOW)
        for change in ('delete_period','delete_series','change_value','first_collected_at'):
            broken=copy.deepcopy(archive);s=broken['decimal_indicators'][self.items[0]['id']]
            if change=='delete_period':del s['observations']['2021-01']
            elif change=='delete_series':del broken['decimal_indicators'][self.items[0]['id']]
            elif change=='change_value':s['observations']['2021-01'].update(value='5',source_value='5')
            else:s['observations']['2021-01']['first_collected_at']='changed'
            with self.subTest(change=change),self.assertRaises(ValueError):decimal_series.validate_archive(broken,archive)

    def test_engine_retains_legacy_ledger_and_failure_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            data,state=Path(d)/'data',Path(d)/'state';state.mkdir()
            legacy=self.archive();legacy['sources']['legacy']={'last_successful_check':'2026-01-01'}
            legacy['indicators']['legacy']={'unit':'명','observations':{'2021-01':{'value':12,'unit':'명','first_collected_at':'2021-02-01'}},'revisions':[]}
            ledger=state/'macro_archive.json';ledger.write_text(json.dumps(legacy))
            h=collect(self.config,data,state,now=NOW,force=True,ecos_client=self.client)
            self.assertEqual(h['new_observations'],18)
            archive=json.loads(ledger.read_text());self.assertEqual(archive['indicators'],legacy['indicators'])
            self.assertEqual(archive['sources'],legacy['sources'])
            before={p:p.read_bytes() for p in (ledger,data/'macro.json')}
            class Broken:
                def rows(self,*args):raise ValueError('SYNTHETICKEYDONOTLOG')
            h=collect(self.config,data,state,now=NOW,force=True,ecos_client=Broken())
            self.assertEqual(h['successful_sources'],0)
            self.assertNotIn('SYNTHETICKEYDONOTLOG',json.dumps(h))
            self.assertTrue(all(p.read_bytes()==value for p,value in before.items()))

    def test_failed_source_is_atomic_while_other_sources_can_succeed(self):
        # Second production series malformed: neither production series is committed.
        self.client.data[self.items[1]['id']][0]['UNIT_NAME']='wrong'
        with tempfile.TemporaryDirectory() as d:
            h=collect(self.config,Path(d)/'data',Path(d)/'state',now=NOW,force=True,ecos_client=self.client)
            self.assertEqual(h['successful_sources'],2)
            archive=json.loads((Path(d)/'state/macro_archive.json').read_text())
            self.assertFalse(any(i['id'] in archive['decimal_indicators'] for i in self.items))
            self.assertEqual(len(archive['decimal_indicators']),7)


if __name__=='__main__':unittest.main()
