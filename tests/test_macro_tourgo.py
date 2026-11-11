"""All amounts/files/proofs here are SYNTHETIC. No official values are fixtures.

Official-shaped records test the publication boundary; synthetic_test records
must never cross it. No fixture is written to production JSON.
"""
import copy
import datetime as dt
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from unittest.mock import patch, Mock
from src.macro import balance, tourgo, tourgo_preview
from src.macro.engine import collect, public_view

ROOT=Path(__file__).resolve().parents[1]
NOW=dt.datetime(2026,11,9,12,tzinfo=dt.timezone(dt.timedelta(hours=9)))


def bundle():
    return dict(receipts={'2025-08':100,'2026-07':120,'2026-08':150},
                expenditure={'2025-08':110,'2026-07':130,'2026-08':140},
                balance={'2025-08':-10,'2026-07':-10,'2026-08':10})


def proof():
    return dict(data_origin='official_export',unit=balance.UNIT,source_url=tourgo.URL,
                collection_method=tourgo.COLLECTION,sha256_by_kind={k:str(n)*64 for n,k in enumerate(balance.KINDS,1)})


def ledger(values=None, previous=None, provenance=None):
    return balance.merge_ledger(previous,values or bundle(),provenance or proof(),NOW)


def config():
    cfg=tourgo.select_source(json.loads((ROOT/'macro_sources.json').read_text()))
    cfg['sources']=[s for s in cfg['sources'] if s['id']==tourgo.SOURCE]
    cfg['indicators']=[i for i in cfg['indicators'] if i['source_id']==tourgo.SOURCE]
    s=cfg['sources'][0];s['enabled']=True
    for action in ('collection','publication'):
        s['approval'][action].update(approved=True,scope='general_travel_monthly',evidence_ref='SYNTHETIC-TEST-ONLY',valid_from='2026-11-01')
    for i in cfg['indicators']:i['enabled']=True
    return cfg


class TourgoValidationTests(unittest.TestCase):
    def test_exact_units_and_negative_balance(self):
        self.assertEqual(tourgo.usd(2460800),2460800000)
        self.assertEqual(balance.million_usd(2460800),Decimal('2460.8'))
        for v in [True,1.5,-1,10**13]:
            with self.subTest(v=v),self.assertRaises(ValueError):tourgo.usd(v)
        s=tourgo.fetch(config()['sources'][0],config()['indicators'],ledger(),NOW)
        self.assertEqual(s['records'][tourgo.IDS[0]]['2025-08']['official_balance_value'],-10000)
        self.assertEqual(s['records'][tourgo.IDS[0]]['2026-08']['source_value'],150)
        for sign in (1,-1):
            pair={key:{'observations':{f'2025-{m:02}':dict(value=(10**15 if (n==0)==(sign==1) else 0),official_balance_finality='not_stated') for m in range(1,13)}} for n,key in enumerate(tourgo.IDS)}
            self.assertIsNone(tourgo.balance_view(pair)['latest']['comparisons']['ytd_value'])

    def test_bad_period_sets_identity_unit_provenance_and_origin_fail(self):
        cases=[]
        for mode in ['period','identity','unit','negative_receipts','origin','mixed','hash','source','future']:
            d=ledger()
            if mode=='period':del d['series']['balance']['2026-07']
            if mode=='identity':d['series']['balance']['2026-08']['value']+=1
            if mode=='unit':d['unit']='US$'
            if mode=='negative_receipts':d['series']['receipts']['2026-08']['value']=-1
            if mode=='origin':d['data_origin']='synthetic_test'
            if mode=='mixed':d['series']['receipts']['2026-08']['provenance']['data_origin']='synthetic_test'
            if mode=='hash':d['series']['receipts']['2026-08']['provenance']['sha256_by_kind']['balance']='bad'
            if mode=='source':d['series']['receipts']['2026-08']['provenance']['source_url']='https://ecos.bok.or.kr/api/'
            if mode=='future':d['latest_period']='2026-11'
            cases.append((mode,d))
        for mode,d in cases:
            with self.subTest(mode=mode),self.assertRaises(ValueError):tourgo.validate_ledger(d,NOW)

    def test_original_hash_checked_before_parser_and_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            files={k:Path(tmp)/(k+'.xls') for k in balance.KINDS}
            for k,p in files.items():p.write_bytes(('SYNTHETIC-'+k).encode())
            hashes={k:tourgo.digest(p.read_bytes()) for k,p in files.items()}
            with patch.object(balance,'read_xls',side_effect=lambda p,k,now:bundle()[k]) as read:
                result=tourgo.from_files(files,hashes,NOW,requested_range=tourgo.INITIAL_PERIOD_RANGE)
                self.assertEqual(len(result['series']['balance']),3);self.assertEqual(read.call_count,3)
            hashes['receipts']='0'*64
            with patch.object(balance,'read_xls') as read,self.assertRaisesRegex(ValueError,'hash_mismatch'):
                tourgo.from_files(files,hashes,NOW,requested_range=tourgo.INITIAL_PERIOD_RANGE)
            read.assert_not_called()

    def test_private_ledger_hash_and_duplicate_month_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'private.json';path.write_text(json.dumps(ledger()))
            self.assertEqual(tourgo.from_private_ledger(path,tourgo.digest(path.read_bytes()),NOW,requested_range=tourgo.INITIAL_PERIOD_RANGE),ledger())
            with self.assertRaises(ValueError):tourgo.from_private_ledger(path,'0'*64,NOW,requested_range=tourgo.INITIAL_PERIOD_RANGE)
            raw=path.read_text().replace('"receipts": {','"receipts": {"2026-08": {},',1);path.write_text(raw)
            with self.assertRaisesRegex(ValueError,'duplicate_json_key'):tourgo.from_private_ledger(path,tourgo.digest(path.read_bytes()),NOW,requested_range=tourgo.INITIAL_PERIOD_RANGE)

    def test_missing_months_preserved_without_zero_and_revisions(self):
        original=ledger();values=bundle()
        values['receipts']['2026-08']+=5;values['balance']['2026-08']+=5
        revised=ledger(values,original)
        self.assertEqual(len(revised['revisions']),2)
        self.assertEqual(original['series']['receipts']['2026-08']['value'],150)
        self.assertEqual(revised['series']['receipts']['2026-08']['first_collected_at'],original['series']['receipts']['2026-08']['first_collected_at'])
        for k in balance.KINDS:del values[k]['2026-07']
        retained=ledger(values,revised)
        self.assertIn('2026-07',retained['series']['receipts'])
        tourgo.validate_ledger(retained,NOW)

    def test_synthetic_preview_rejected_before_any_output(self):
        d=ledger();d['data_origin']='synthetic_test'
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'must-not-exist'
            with self.assertRaisesRegex(ValueError,'synthetic'):tourgo_preview.preview(d,output,ROOT,NOW)
            self.assertFalse(output.exists())

    def test_original_changes_during_parse_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            files={k:Path(tmp)/(k+'.xls') for k in balance.KINDS}
            for k,p in files.items():p.write_bytes(k.encode())
            hashes={k:tourgo.digest(p.read_bytes()) for k,p in files.items()}
            def changed(path,kind,now):
                if kind=='balance':path.write_bytes(b'CHANGED-SYNTHETIC')
                return bundle()[kind]
            with patch.object(balance,'read_xls',side_effect=changed),self.assertRaisesRegex(ValueError,'hash_mismatch'):
                tourgo.from_files(files,hashes,NOW,requested_range=tourgo.INITIAL_PERIOD_RANGE)

    def test_cli_error_does_not_reflect_private_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'private.json';path.write_text('{"unit":"PRIVATE-CONTENT-MUST-NOT-LEAK"}')
            output=Path(tmp)/'new-preview';stdout=io.StringIO()
            args=['tourgo_preview','--ledger',str(path),'--ledger-sha256',tourgo.digest(path.read_bytes()),'--output',str(output)]
            with patch('sys.argv',args),redirect_stdout(stdout):self.assertEqual(tourgo_preview.main(),1)
            self.assertNotIn('PRIVATE-CONTENT',stdout.getvalue());self.assertFalse(output.exists())


class TourgoIntegrationTests(unittest.TestCase):
    def run_import(self,tmp,cfg=None,data=None):
        return collect(cfg or config(),Path(tmp)/'site/data',Path(tmp)/'state',now=NOW,force=True,tourgo_ledger=data or ledger())

    def test_mapping_helper_never_activates_or_mutates(self):
        raw=json.loads((ROOT/'macro_sources.json').read_text());before=copy.deepcopy(raw)
        selected=tourgo.select_source(raw);self.assertEqual(raw,before)
        self.assertTrue(all(not i['enabled'] for i in selected['indicators'] if i['source_id']==tourgo.SOURCE))
        s=next(s for s in raw['sources'] if s['id']==tourgo.SOURCE)
        self.assertTrue(s['enabled']);self.assertFalse(balance.permitted(s,'publication',NOW.date()))  # test clock predates publication grant

    def test_full_import_public_view_exact_comparisons_and_signed_balance(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=self.run_import(tmp);self.assertEqual(h['status'],'ok');self.assertEqual(h['new_observations'],6)
            public=json.loads((Path(tmp)/'site/data/macro.json').read_text())
            r=public['indicators'][0];self.assertEqual(r['latest']['value'],150000)
            self.assertEqual(r['latest']['comparisons']['mom_pct'],25)
            self.assertEqual(r['latest']['comparisons']['yoy_pct'],50)
            self.assertIsNone(r['latest']['comparisons']['ytd_value'])
            b=public['tourism_balance'];self.assertEqual(b['latest']['value'],10000)
            self.assertEqual(b['latest']['comparisons']['yoy_change'],20000)
            self.assertIsNone(b['latest']['comparisons']['yoy_pct'])
            self.assertEqual(h['sources'][0]['collection_state'],'manual_import_validated')

    def test_approval_flags_and_enabled_alone_never_bypass(self):
        for action in ('collection','publication'):
            for bypass in (False,True):
                c=config();c['sources'][0]['approval'][action]['approved']=False
                if bypass:c['sources'][0]['requires_approval']=False
                with tempfile.TemporaryDirectory() as tmp,patch.object(tourgo,'fetch',wraps=tourgo.fetch) as fetch:
                    h=self.run_import(tmp,c)
                    self.assertFalse((Path(tmp)/'site/data/macro.json').exists())
                    if action=='collection':fetch.assert_not_called()
                    self.assertNotEqual(h['sources'][0]['status'],'ok')

    def test_revocation_and_archived_record_tampering_hide_without_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_import(tmp);state=json.loads((Path(tmp)/'state/macro_archive.json').read_text());before=copy.deepcopy(state)
            for mode in ['revoked','synthetic','ecos','identity','unit','hash','float']:
                c=config();a=copy.deepcopy(state);r=a['indicators'][tourgo.IDS[0]]['observations']['2026-08']
                if mode=='revoked':c['sources'][0]['approval']['publication']['approved']=False
                if mode=='synthetic':r['data_origin']='synthetic_test'
                if mode=='ecos':r['collection_method']='official_ecos_api'
                if mode=='identity':r['official_balance_value']+=1
                if mode=='unit':r['source_unit']='백만 US$'
                if mode=='hash':r['file_sha256']='0'*64
                if mode=='float':r['value']=float(r['value'])
                v=public_view(c,a,NOW);self.assertTrue(all(not i['connected'] for i in v['indicators']),mode)
                self.assertNotIn('tourism_balance',v)
            self.assertEqual(state,before)

    def test_failure_and_source_change_preserve_existing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_import(tmp);p=Path(tmp)/'site/data/macro.json';a=Path(tmp)/'state/macro_archive.json'
            before=(p.read_bytes(),a.read_bytes());d=ledger();d['series']['balance']['2026-08']['value']+=1
            h=self.run_import(tmp,data=d);self.assertEqual(h['sources'][0]['status'],'error')
            self.assertEqual((p.read_bytes(),a.read_bytes()),before)
            raw=json.loads(a.read_text());raw['indicators'][tourgo.IDS[0]]['observations']['2026-08']['collection_method']='official_ecos_api';a.write_text(json.dumps(raw));old=a.read_bytes()
            h=self.run_import(tmp);self.assertEqual(h['sources'][0]['error_kind'],'financial_source_change_requires_review');self.assertEqual(a.read_bytes(),old)

    def test_repeat_correction_and_missing_snapshot_retain_other_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_import(tmp);h=self.run_import(tmp);self.assertEqual(h['new_observations'],0);self.assertEqual(h['unchanged_observations'],6)
            values=bundle();values['receipts']['2026-08']+=5;values['balance']['2026-08']+=5
            h=self.run_import(tmp,data=ledger(values));self.assertEqual(h['value_corrections'],1)
            a=json.loads((Path(tmp)/'state/macro_archive.json').read_text());self.assertEqual(a['indicators'][tourgo.IDS[0]]['revisions'][0]['before']['value'],150000)
            for k in balance.KINDS:del values[k]['2026-07']
            h=self.run_import(tmp,data=ledger(values));self.assertEqual(h['sources'][0]['status'],'partial')
            a=json.loads((Path(tmp)/'state/macro_archive.json').read_text());self.assertIn('2026-07',a['indicators'][tourgo.IDS[0]]['observations'])

    def test_no_network_or_other_source_collection_in_preview_and_production_gates_unchanged(self):
        production=(ROOT/'macro_sources.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp,patch('src.macro.engine.kto.fetch') as kto,patch('src.macro.engine.ecos.fetch') as ecos:
            result=tourgo_preview.preview(ledger(),Path(tmp)/'preview',ROOT,NOW)
            self.assertEqual(result['months'],3);kto.assert_not_called();ecos.assert_not_called()
            self.assertIn('격리 미리보기',(Path(tmp)/'preview/site/index.html').read_text())
            self.assertEqual((ROOT/'macro_sources.json').read_bytes(),production)
            public=json.loads((Path(tmp)/'preview/site/data/macro.json').read_text())
            self.assertEqual(len([i for i in public['indicators'] if i['connected'] and i['unit']=='명']),7)
        with self.assertRaises(ValueError):tourgo_preview.preview(ledger(),ROOT/'site',ROOT,NOW)

    def test_official_balance_finality_is_not_inferred_from_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=ledger()
            for o in d['series']['balance'].values():o['finality']='provisional';o['provenance']['finality']='provisional'
            self.run_import(tmp,data=d)
            v=json.loads((Path(tmp)/'site/data/macro.json').read_text())
            self.assertEqual(v['tourism_balance']['latest']['finality'],'provisional')
            self.assertEqual(v['indicators'][0]['latest']['finality'],'not_stated')

    def test_public_projection_allowlist_keeps_private_notes_in_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_import(tmp);a=json.loads((Path(tmp)/'state/macro_archive.json').read_text())
            a['indicators'][tourgo.IDS[0]]['observations']['2026-08']['private_note']='PRIVATE-TEST-NOTE'
            self.assertNotIn('PRIVATE-TEST-NOTE',json.dumps(public_view(config(),a,NOW)))
            self.assertIn('private_note',a['indicators'][tourgo.IDS[0]]['observations']['2026-08'])

    def test_changing_back_to_ecos_cannot_mix_existing_tourgo(self):
        from test_macro_ecos import source as ecos_source,indicators as ecos_indicators
        with tempfile.TemporaryDirectory() as tmp:
            self.run_import(tmp);path=Path(tmp)/'state/macro_archive.json';before=path.read_bytes();client=Mock()
            h=collect(dict(sources=[ecos_source()],indicators=ecos_indicators()),Path(tmp)/'site/data',Path(tmp)/'state',now=NOW,force=True,ecos_client=client)
            self.assertEqual(h['sources'][0]['error_kind'],'financial_source_change_requires_review');client.rows.assert_not_called();self.assertEqual(path.read_bytes(),before)
