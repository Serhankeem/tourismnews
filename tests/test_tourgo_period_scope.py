"""Approved-month boundaries. All non-pinned data are SYNTHETIC in temp files.

No October source is fetched. Spies prove blocked inputs are never requested,
opened, parsed or stored. Owner-signature/Environment gates remain in use.
"""
import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from src.macro import tourgo,balance,tourgo_release as release,tourgo_staging as staging,tourgo_delivery as delivery,tourgo_update as update
from src.macro.engine import collect,public_view
from src.pipeline.layout import ROOT,read
from test_tourgo_readiness import synthetic69
from test_macro_tourgo import config as small_config
from test_tourgo_activation import environment,FakeAPI

NOW=dt.datetime(2026,11,11,12,tzinfo=dt.timezone(dt.timedelta(hours=9)))


def source():return next(s for s in read(ROOT/'macro_sources.json')['sources'] if s['id']==tourgo.SOURCE)


class ApprovedMonthTests(unittest.TestCase):
    def test_config_separates_month_bounds_from_expiry_and_preserves_flags(self):
        s=source()
        for action in ('collection','publication'):
            self.assertEqual(tourgo.approved_range(s,action),tourgo.INITIAL_PERIOD_RANGE)
            self.assertEqual(s['approval'][action]['valid_until'],'2027-02-08')
            self.assertTrue(s['approval'][action]['approved'])
            self.assertTrue(tourgo.permitted(s,action,NOW.date()))
        self.assertTrue(s['enabled'])
        self.assertFalse(any(s['enabled'] for s in read(ROOT/'macro_sources.json')['sources'] if s['id'].startswith('ecos_')))

    def test_september_passes_october_and_missing_or_invalid_ranges_fail(self):
        for action in ('collection','publication'):
            tourgo.require_periods(source(),action,['2021-01','2026-09'])
            with self.assertRaisesRegex(ValueError,'scope_exceeded'):tourgo.require_periods(source(),action,['2026-10'])
            for bad in (None,{},dict(period_from='2026-09',period_through='2021-01'),dict(period_from='2021-01',period_through='2026-13')):
                with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'scope_unverified'):tourgo.require_range(source(),action,bad)
        for ledger in ({},{'series':{}},{'series':{'receipts':{}}}):
            with self.assertRaisesRegex(ValueError,'scope_unverified'):tourgo.require_ledger_scope(source(),'collection',ledger)
        s=source();del s['approval']['collection']['period_through']
        self.assertFalse(tourgo.permitted(s,'collection',NOW.date()))

    def test_unknown_or_excessive_input_never_opens_or_parses_originals(self):
        paths={k:Path('/tmp/MUST-NOT-OPEN-'+k+'.xls') for k in balance.KINDS}
        for declared in (None,dict(period_from='2021-01',period_through='2026-10')):
            with patch.object(Path,'read_bytes',side_effect=AssertionError('must not open originals')),patch.object(balance,'read_xls',side_effect=AssertionError('must not parse')):
                with self.assertRaisesRegex(ValueError,'period_scope_'):
                    staging.OfficialFiles(paths,source=source(),requested_range=declared).load({'indicators':{}},'update',NOW)
                with tempfile.TemporaryDirectory() as tmp:
                    out=Path(tmp)/'input'
                    with self.assertRaisesRegex(ValueError,'period_scope_'):staging.source_package(paths,out,True,requested_range=declared)
                    self.assertFalse(out.exists())

    def test_unknown_or_excessive_private_ledger_is_not_read(self):
        for declared in (None,dict(period_from='2021-01',period_through='2026-10')):
            with patch.object(Path,'read_bytes',side_effect=AssertionError('must not read ledger')),self.assertRaises(ValueError):
                tourgo.from_private_ledger('/tmp/MUST-NOT-OPEN.json','a'*64,NOW,requested_range=declared)

    def test_existing_initial_hashes_prove_legacy_range_but_new_hashes_do_not(self):
        self.assertEqual(tourgo.input_range(release.INITIAL_HASHES),tourgo.INITIAL_PERIOD_RANGE)
        with self.assertRaisesRegex(ValueError,'scope_unverified'):tourgo.input_range(dict(receipts='a'*64,expenditure='b'*64,balance='c'*64))

    def test_outside_ledger_is_rejected_before_values_or_stage_storage(self):
        d=synthetic69()
        for rows in d['series'].values():rows['2026-10']={'NO_VALUES_MAY_BE_READ':True}
        with patch.object(tourgo,'validate_ledger',side_effect=AssertionError('scope first')):
            with self.assertRaisesRegex(ValueError,'scope_exceeded'):tourgo.fetch(source(),[],d,NOW)
            with tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp)/'staging'
                with self.assertRaisesRegex(ValueError,'scope_exceeded'):release.stage(d,ROOT,out,release.INITIAL_HASHES,'initial',NOW)
                self.assertFalse(out.exists())

    def test_legacy_download_callback_requires_verified_range_before_call(self):
        for requested in (None,dict(period_from='2021-01',period_through='2026-10')):
            callback=Mock()
            with self.assertRaises(ValueError):balance.approved_download(source(),callback,NOW.date(),requested_range=requested)
            callback.assert_not_called()
        callback=Mock()
        balance.approved_download(source(),callback,NOW.date(),requested_range=tourgo.INITIAL_PERIOD_RANGE)
        callback.assert_called_once()

    def test_legacy_prepare_rejects_october_before_parser_or_storage(self):
        from src.macro import balance_prepare
        args=['balance_prepare','--receipts','r.xls','--expenditure','e.xls','--balance','b.xls',
              '--private-dir','/tmp/MUST-NOT-CREATE','--period-from','2021-01','--period-through','2026-10']
        with patch('sys.argv',args),patch.object(balance_prepare,'read_xls') as parser,patch.object(balance_prepare,'write_atomic') as writer,self.assertRaises(ValueError):balance_prepare.main()
        parser.assert_not_called();writer.assert_not_called()

    def test_69_months_correction_and_failed_import_preserve_ledger_history(self):
        cfg=small_config()
        with tempfile.TemporaryDirectory() as tmp:
            data,state=Path(tmp)/'data',Path(tmp)/'state';d=synthetic69()
            collect(cfg,data,state,now=NOW,tourgo_ledger=d)
            before=read(state/'macro_archive.json')
            d['series']['receipts']['2026-09']['value']+=1;d['series']['balance']['2026-09']['value']+=1
            collect(cfg,data,state,now=NOW,tourgo_ledger=d)
            corrected=read(state/'macro_archive.json')
            self.assertEqual(sum(len(i['observations']) for i in corrected['indicators'].values()),138)
            self.assertTrue(corrected['indicators'][tourgo.IDS[0]]['revisions'])
            self.assertEqual(corrected['indicators'][tourgo.IDS[0]]['observations']['2026-09']['first_collected_at'],before['indicators'][tourgo.IDS[0]]['observations']['2026-09']['first_collected_at'])
            raw=(state/'macro_archive.json').read_bytes()
            for rows in d['series'].values():rows['2026-10']={'NO_VALUES':True}
            h=collect(cfg,data,state,now=NOW,tourgo_ledger=d)
            self.assertEqual(h['sources'][0]['status'],'error');self.assertEqual((state/'macro_archive.json').read_bytes(),raw)

    def test_publication_holds_outside_month_without_accessing_values_or_deleting_archive(self):
        class NoAccess(dict):
            def get(self,*a):raise AssertionError('outside values must not be accessed')
        with tempfile.TemporaryDirectory() as tmp:
            data,state=Path(tmp)/'data',Path(tmp)/'state';cfg=small_config()
            collect(cfg,data,state,now=NOW,tourgo_ledger=synthetic69())
            archive=read(state/'macro_archive.json')
            for k in tourgo.IDS:archive['indicators'][k]['observations']['2026-10']=NoAccess()
            view=public_view(cfg,archive,NOW)
            for i in view['indicators']:
                self.assertEqual(len(i['observations']),69);self.assertEqual(i['latest_period'],'2026-09')
            self.assertEqual(len(view['tourism_balance']['observations']),69)
            for k in tourgo.IDS:self.assertIn('2026-10',archive['indicators'][k]['observations'])

    def test_collection_and_publication_ranges_remain_independent(self):
        for narrower in ('collection','publication'):
            with self.subTest(narrower=narrower):
                s=source()
                s['approval'][narrower].update(period_from='2022-01',period_through='2026-08',approved=False)
                config={**read(ROOT/'macro_sources.json'),'sources':[s]};before=copy.deepcopy(config)
                planned=release.activation_candidate(config,NOW);preview=planned['sources'][0]
                self.assertEqual(config,before)
                for action in ('collection','publication'):
                    self.assertEqual(tourgo.approved_range(preview,action),tourgo.approved_range(s,action))
                    self.assertTrue(preview['approval'][action]['approved'])
                    self.assertEqual(preview['approval'][action]['evidence_ref'],'staging-only-not-operating-approval')
                with self.assertRaisesRegex(ValueError,'scope_exceeded'):
                    tourgo.require_periods(preview,narrower,['2026-09'])
                tourgo.require_periods(preview,'publication' if narrower=='collection' else 'collection',['2026-09'])
                # Ephemeral grants cannot authorize the real operating transaction.
                with self.assertRaisesRegex(ValueError,'dated_operating_approval_required'):
                    release.operating_configuration(planned,read(ROOT/'operating_policy.json'),NOW)
        s=source();del s['approval']['publication']['period_through']
        with self.assertRaisesRegex(ValueError,'scope_unverified'):
            release.activation_candidate({**read(ROOT/'macro_sources.json'),'sources':[s]},NOW)

    def test_expiry_revocation_and_missing_bounds_block_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=small_config();data,state=Path(tmp)/'data',Path(tmp)/'state'
            collect(cfg,data,state,now=NOW,tourgo_ledger=synthetic69());archive=read(state/'macro_archive.json')
            for mode in ('expired','revoked','missing'):
                altered=copy.deepcopy(cfg);s=altered['sources'][0]
                if mode=='expired':s['approval']['publication']['valid_until']='2026-11-10'
                if mode=='revoked':s['approval']['publication']['approved']=False
                if mode=='missing':del s['approval']['publication']['period_through']
                self.assertTrue(all(not i['connected'] for i in public_view(altered,archive,NOW)['indicators']))

    def test_receipt_scope_checked_before_private_ledger_or_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'stage';release.stage(synthetic69(),ROOT,out,release.INITIAL_HASHES,'initial',NOW)
            doc=read(out/'readiness.json');doc['latest_period']='2026-10';(out/'readiness.json').write_text(json.dumps(doc))
            request=release.ReleaseRequest(out/'validated-input.json',release.digest_file(out/'validated-input.json'),out/'readiness.json',release.digest_file(out/'readiness.json'))
            with patch.object(tourgo,'from_private_ledger',side_effect=AssertionError('must not read ledger')),self.assertRaisesRegex(ValueError,'approval_invalid'):
                request.validate(ROOT,ROOT,NOW)


class RequestPreflightTests(unittest.TestCase):
    def test_recurring_unknown_or_october_range_never_requests_data_blobs(self):
        env=environment();env.update(GITHUB_WORKFLOW=update.WORKFLOW,TOURGO_INPUT_TOKEN='SYNTHETIC',TOURGO_INPUT_REPOSITORY='trusted/private-tourgo')
        class API(FakeAPI):
            def get(self,path):
                if path.endswith('/git/ref/heads/updates'):return {'object':{'type':'commit','sha':'a'*40}}
                if '/git/' not in path and '/commits/' in path:return {'sha':'a'*40,'author':{'id':123},'commit':{'verification':{'verified':True,'reason':'valid'}}}
                return super().get(path)
        for declared in (None,dict(period_from='2021-01',period_through='2026-10')):
            m=dict(schema_version=2,profile='update',files={name:('a' if name=='source.json' else 'b')*64 for name in staging.SOURCE_FILES})
            if declared:m['period_range']=declared
            calls=[]
            def blob(name):
                calls.append(name)
                if name!='manifest.json':raise AssertionError('data must not be requested')
                return json.dumps(m).encode()
            with tempfile.TemporaryDirectory() as tmp,patch.object(delivery,'GitHub',return_value=API()),patch.object(delivery,'private_blobs',return_value=blob),self.assertRaisesRegex(ValueError,'period_scope_'):
                update.deliver(Path(tmp)/'input',env,NOW)
            self.assertEqual(calls,['manifest.json'])

    def test_legacy_receipt_with_october_is_blocked_before_data_blobs(self):
        api=FakeAPI();receipt=json.loads(api.raw['receipt.json']);receipt.update(first_period='2021-01',latest_period='2026-10')
        api.raw['receipt.json']=json.dumps(receipt).encode();m=json.loads(api.raw['manifest.json']);m['files']['receipt.json']=tourgo.digest(api.raw['receipt.json']);api.raw['manifest.json']=json.dumps(m).encode()
        with tempfile.TemporaryDirectory() as tmp,patch.object(delivery,'INITIAL_HASHES',api.pins),self.assertRaisesRegex(ValueError,'scope_exceeded'):
            delivery.fetch_inputs(api,'trusted/private-tourgo','a'*40,tourgo.digest(api.raw['manifest.json']),Path(tmp)/'input')
        requested={p.rsplit('/',1)[-1] for p in api.calls if '/git/blobs/' in p}
        prohibited={r['sha'] for r in api.tree if r['path'] in ('ledger.json',*staging.ORIGINALS)}
        self.assertFalse(requested & prohibited)
