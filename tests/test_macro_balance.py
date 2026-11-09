"""All values in this file are artificial; no TOURGO source values/exports."""
import copy
import datetime as dt
import unittest
from unittest.mock import Mock, patch
import tempfile
from pathlib import Path
from src.macro.engine import collect
from src.macro.balance import *
from src.macro.engine import public_view

NOW = dt.datetime(2026, 10, 30, tzinfo=dt.timezone.utc)

def bundle():
    return dict(receipts={'2025-08': 100, '2026-07': 120, '2026-08': 150},
                expenditure={'2025-08': 110, '2026-07': 130, '2026-08': 140},
                balance={'2025-08': -10, '2026-07': -10, '2026-08': 10})

def proof():
    return dict(data_origin='synthetic_test', unit=UNIT, sha256_by_kind={k:'0'*64 for k in KINDS})

def source():
    return dict(approval={a:dict(approved=True,scope='general_travel_monthly',evidence_ref='synthetic-test-only',valid_from='2026-01-01') for a in ('collection','publication')})

class BalanceTests(unittest.TestCase):
    def test_verify_only_never_creates_private_or_public_files(self):
        import sys
        from src.macro import balance_prepare
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/'private'
            argv=['balance_prepare', '--receipts', str(Path(root)/'in.xls'),
                  '--expenditure',str(Path(root)/'out.xls'),
                  '--balance',str(Path(root)/'net.xls'),
                  '--private-dir',str(target), '--verify-only']
            with (patch.object(sys,'argv',argv),
                  patch.object(balance_prepare,'read_xls',side_effect=lambda path,kind,now:bundle()[kind]),
                  patch.object(balance_prepare,'write_atomic') as write):
                balance_prepare.main()
                write.assert_not_called()
                self.assertFalse(target.exists())

    def test_exact_display_conversion(self):
        self.assertEqual(million_usd(123456), Decimal('123.456'))
        self.assertEqual(million_usd(-123456), Decimal('-123.456'))
    def test_missing_historical_month_retained(self):
        old=merge_ledger(None,bundle(),proof(),NOW);b=bundle()
        for k in KINDS: del b[k]['2025-08']
        new=merge_ledger(old,b,proof(),NOW)
        self.assertIn('2025-08',new['series']['receipts'])
    def test_default_and_string_truth_are_denied(self):
        self.assertFalse(permitted({},'collection'))
        s=source();s['approval']['collection']['approved']='true'
        self.assertFalse(permitted(s,'collection'))
    def test_expiry_scope_evidence(self):
        for field,value in [('valid_until','2026-01-01'),('scope','all'),('evidence_ref',None),('valid_from','bad')]:
            s=source();s['approval']['collection'][field]=value
            self.assertFalse(permitted(s,'collection',NOW.date()))
    def test_no_callback_without_collection_approval(self):
        f=Mock();s=source();s['approval']['collection']['approved']=False
        with self.assertRaises(ValueError):approved_download(s,f,NOW.date())
        f.assert_not_called()
        approved_download(source(),f,NOW.date());f.assert_called_once()
    def test_separate_publication_permission(self):
        s=source();s['approval']['publication']['approved']=False
        with self.assertRaises(ValueError):publication_view(s,{'data_origin':'official_export'},NOW.date())
    def test_synthetic_never_publish(self):
        with self.assertRaises(ValueError):publication_view(source(),{'data_origin':'synthetic_test'},NOW.date())
    def test_parse_units_totals_and_missing(self):
        header=['연도','계']+[f'{m}월' for m in range(1,13)]
        row=['2026년(1,000 US$)',30,10,20]+['']*10
        self.assertEqual(parse_rows([header,row],'receipts',NOW),{'2026-01':10,'2026-02':20})
        for bad in [row[:1]+[31]+row[2:],['2026년(US$)']+row[1:]]:
            with self.assertRaises(ValueError):parse_rows([header,bad],'receipts',NOW)
    def test_official_xls_trailing_format_column(self):
        header=['연도','계']+[f'{m}월' for m in range(1,13)]
        row=['2026년(1,000 US$)',30,10,20]+['']*10
        self.assertEqual(parse_rows([header+[''],row+['']],'receipts',NOW),
                         {'2026-01':10,'2026-02':20})
        self.assertEqual(parse_rows([header+['',None],row+['',None]],'receipts',NOW),
                         {'2026-01':10,'2026-02':20})
        for bad in (
            [header+['기타'], row+['']],
            [header+[''], row+[1]],
            [header+[''], row+['0']],
            [header+[''], row+[' ']],
            [header[:-1], row+['']],
            [header+[''], row[:-1]],
        ):
            with self.subTest(bad=bad[0][-1] if bad[0] else ''):
                with self.assertRaises(ValueError):
                    parse_rows(bad,'receipts',NOW)

    def test_official_xls_trailing_format_balance_negative(self):
        header=['연도','계']+[f'{m}월' for m in range(1,13)]
        row=['2026년(1,000 US$)',-5,-10,5]+['']*10
        self.assertEqual(parse_rows([header+[''],row+['']],'balance',NOW),
                         {'2026-01':-10,'2026-02':5})

    def test_invalid_amounts(self):
        for v in [-1,'NaN','Infinity',1.2,True]:
            with self.assertRaises(ValueError):amount(v)
        self.assertEqual(amount(-10,True),-10)
    def test_identity_and_matching_months(self):
        self.assertEqual(validate_bundle(bundle()),'2026-08')
        for k in KINDS:
            b=bundle();b[k]['2026-08']+=1
            with self.assertRaises(ValueError):validate_bundle(b)
        b=bundle();del b['balance']['2026-07']
        with self.assertRaises(ValueError):validate_bundle(b)
    def test_comparisons_signed_and_missing(self):
        b=bundle();r=monthly_comparisons(b['receipts'],'2026-08','receipts')
        self.assertEqual(r['mom_pct'],25);self.assertEqual(r['yoy_pct'],50)
        self.assertIsNone(r['ytd_value'])
        r=monthly_comparisons(b['balance'],'2026-08','balance')
        self.assertIsNone(r['mom_pct']);self.assertEqual(r['mom_change'],20)
    def test_corrections_atomic_and_origin_isolation(self):
        old=merge_ledger(None,bundle(),proof(),NOW);before=copy.deepcopy(old)
        b=bundle();b['receipts']['2026-08']+=5;b['balance']['2026-08']+=5
        new=merge_ledger(old,b,proof(),NOW)
        self.assertEqual(old,before);self.assertEqual(len(new['revisions']),2)
        self.assertEqual(new['series']['receipts']['2026-08']['first_collected_at'],old['series']['receipts']['2026-08']['first_collected_at'])
        p=proof();p['data_origin']='official_export'
        with self.assertRaises(ValueError):merge_ledger(old,b,p,NOW)
        b['balance']['2026-08']+=1
        with self.assertRaises(ValueError):merge_ledger(old,b,proof(),NOW)
        self.assertEqual(old,before)
    def test_status_revision(self):
        old=merge_ledger(None,bundle(),proof(),NOW);p=proof();p['finality']='provisional'
        new=merge_ledger(old,bundle(),p,NOW)
        self.assertEqual(len(new['revisions']),9)
    def test_enabling_source_cannot_bypass_collection_gate(self):
        config=dict(sources=[dict(id='blocked',name='blocked',enabled=True,requires_approval=True)],indicators=[])
        with tempfile.TemporaryDirectory() as tmp, patch('src.macro.engine.kto.fetch') as fetch:
            health=collect(config,Path(tmp)/'public',Path(tmp)/'state',now=NOW)
            fetch.assert_not_called()
            self.assertEqual(health['sources'][0]['reason'],'collection_approval_required')
            self.assertFalse((Path(tmp)/'public'/'macro.json').exists())
    def test_public_engine_hides_unapproved_even_if_archived(self):
        item=dict(id='money',source_id='blocked',priority=1)
        config=dict(sources=[dict(id='blocked',requires_approval=True)],indicators=[item])
        archive=dict(indicators={'money':{'observations':{'2026-08':{'value':999}}}})
        row=public_view(config,archive,NOW)['indicators'][0]
        self.assertFalse(row['connected']);self.assertEqual(row['observations'],[])
