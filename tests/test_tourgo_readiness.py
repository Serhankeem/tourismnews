"""SYNTHETIC 69-month scenarios, never proof of the real XLS byte contents.

Known original hash labels exercise the trusted-admin ledger contract only.
All inputs, approval changes, Git remotes and staging outputs are temporary.
"""
import copy
import contextlib
import io
import datetime as dt
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from src.macro import balance,tourgo
from src.macro import tourgo_release as release
from src.macro.engine import collect
from src.macro.engine import public_view
from src.macro.model import months
from src.pipeline.layout import configuration,copy_data,read,CONTROL
from src.pipeline.runner import transact
from src.pipeline.store import Store,git
from src.pipeline.policy import verify_public
from test_pipeline import PipelineHarness
from test_macro_tourgo import config as small_config,ledger as small_ledger

ROOT=Path(__file__).resolve().parents[1]
NOW=dt.datetime(2026,11,10,12,tzinfo=dt.timezone(dt.timedelta(hours=9)))


def synthetic69():
    periods=months('2021-01','2026-09')
    values=dict(receipts={p:10000+n for n,p in enumerate(periods)},
                expenditure={p:13000+2*n for n,p in enumerate(periods)})
    values['balance']={p:values['receipts'][p]-values['expenditure'][p] for p in periods}
    proof=dict(data_origin='official_export',unit=balance.UNIT,source_url=tourgo.URL,
        collection_method=tourgo.COLLECTION,sha256_by_kind=release.INITIAL_HASHES)
    return balance.merge_ledger(None,values,proof,NOW)


def kto_snapshot(archive):
    result=copy.deepcopy(archive['sources']['kto_monthly_statistics'])
    series={k:i for k,i in archive['indicators'].items() if k not in tourgo.IDS}
    result['values']={k:{p:o['value'] for p,o in i['observations'].items()} for k,i in series.items()}
    result['locations']={k:dict(sheet=next(iter(i['observations'].values()))['sheet'],
        cells={p:o['cell'] for p,o in i['observations'].items()}) for k,i in series.items()}
    return result


class ManualScheduleTests(unittest.TestCase):
    def test_no_input_waits_without_success_time_or_data_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data,state=Path(tmp)/'data',Path(tmp)/'state';cfg=small_config()
            collect(cfg,data,state,now=NOW,force=True,tourgo_ledger=small_ledger())
            old=[p.read_bytes() for p in (data/'macro.json',state/'macro_archive.json')]
            h=collect(cfg,data,state,now=NOW+dt.timedelta(days=1))
            self.assertEqual(h['status'],'not_due');self.assertEqual(h['successful_sources'],0)
            self.assertEqual(h['sources'][0]['status'],'manual_update_pending')
            self.assertEqual(h['sources'][0]['last_successful_check'],NOW.isoformat())
            self.assertEqual(old,[p.read_bytes() for p in (data/'macro.json',state/'macro_archive.json')])

    def test_explicit_bad_input_same_day_is_a_failure_not_not_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            data,state=Path(tmp)/'data',Path(tmp)/'state';cfg=small_config()
            collect(cfg,data,state,now=NOW,tourgo_ledger=small_ledger())
            h=collect(cfg,data,state,now=NOW,tourgo_ledger={})
            self.assertEqual(h['status'],'failed');self.assertEqual(h['sources'][0]['status'],'error')

    def test_noncommercial_condition_is_rechecked_for_existing_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            data,state=Path(tmp)/'data',Path(tmp)/'state';cfg=small_config()
            collect(cfg,data,state,now=NOW,tourgo_ledger=small_ledger())
            archive=read(state/'macro_archive.json');bad={'mode':'noncommercial','ads_enabled':True,'paid_access':False}
            self.assertTrue(all(not i['connected'] for i in public_view(cfg,archive,NOW,bad)['indicators']))
            h=collect(cfg,data,state,now=NOW,tourgo_ledger=small_ledger(),operating_policy=bad)
            self.assertEqual(h['sources'][0]['error_kind'],'tourgo_noncommercial_policy_required')

    def test_waiting_tourgo_does_not_fail_or_refresh_on_normal_kto_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=release.activation_candidate(read(ROOT/'macro_sources.json'),NOW)
            data,state=Path(tmp)/'site/data',Path(tmp)/'collector_state'
            copy_data(ROOT,Path(tmp),configuration());base=read(state/'macro_archive.json')
            collect(cfg,data,state,now=NOW,force=True,tourgo_ledger=synthetic69(),only_sources={tourgo.SOURCE})
            before=read(state/'macro_archive.json')
            with patch('src.macro.kto.fetch',return_value=kto_snapshot(base)):
                h=collect(cfg,data,state,now=NOW+dt.timedelta(days=1))
            self.assertEqual(h['status'],'ok');self.assertEqual(h['successful_sources'],1)
            waiting=next(s for s in h['sources'] if s['id']==tourgo.SOURCE)
            self.assertEqual(waiting['status'],'manual_update_pending');self.assertEqual(waiting['last_successful_check'],NOW.isoformat())
            after=read(state/'macro_archive.json')
            for k in tourgo.IDS:self.assertEqual(before['indicators'][k],after['indicators'][k])


class StagingTests(unittest.TestCase):
    def test_initial_483_plus_138_and_no_private_pages_metadata(self):
        original=(ROOT/'macro_sources.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'stage'
            with patch('src.macro.kto.fetch',side_effect=AssertionError('no network in staging')):
                receipt=release.stage(synthetic69(),ROOT,out,release.INITIAL_HASHES,'initial',NOW)
            self.assertEqual(receipt['existing_nonfinancial_observations'],483)
            self.assertEqual(receipt['financial_observations'],138);self.assertEqual(receipt['projected_total_observations'],621)
            self.assertFalse(receipt['operating_approval'])
            health=read(out/'pages/data/macro_health.json');kto_state=next(s for s in health['sources'] if s['id']=='kto_monthly_statistics')
            self.assertFalse(kto_state['checked_in_this_run'])
            self.assertEqual(kto_state['last_successful_check'],read(ROOT/'site/data/macro_health.json')['sources'][0]['last_successful_check'])
            macro=read(out/'pages/data/macro.json')
            self.assertEqual(len(macro['tourism_balance']['observations']),69)
            self.assertLess(macro['tourism_balance']['latest']['value'],0)
            for i in macro['indicators']:
                if i['source_id']==tourgo.SOURCE:
                    self.assertFalse(any(k in i['latest'] for k in ['source_value','bundle_sha256_by_kind','file_sha256','data_origin']))
            public=''.join(p.read_text() for p in (out/'pages').rglob('*.json'))
            self.assertNotIn('expected_original_hashes',public);self.assertNotIn(release.INITIAL_HASHES['receipts'],public)
            self.assertFalse((out/'pages/collector_state').exists());self.assertFalse((out/'pages/validated-input.json').exists())
            self.assertEqual(original,(ROOT/'macro_sources.json').read_bytes())
            # Actual inactive settings reject the proposed output as production.
            with self.assertRaises(ValueError):verify_public(out/'candidate',ROOT)

    def test_wrong_months_hashes_synthetic_or_existing_output_fail(self):
        for mode in ['68months','wrong_hash','synthetic']:
            ledger=synthetic69()
            if mode=='68months':
                for records in ledger['series'].values():del records['2021-01']
            if mode=='wrong_hash':
                for records in ledger['series'].values():
                    for o in records.values():o['provenance']['sha256_by_kind']={'receipts':'1'*64,'expenditure':'2'*64,'balance':'3'*64}
            if mode=='synthetic':ledger['data_origin']='synthetic_test'
            with tempfile.TemporaryDirectory() as tmp,self.assertRaises(ValueError):release.stage(ledger,ROOT,Path(tmp)/'stage',release.INITIAL_HASHES,'initial',NOW)
        with self.assertRaises(ValueError):release.stage(synthetic69(),ROOT,ROOT/'site',release.INITIAL_HASHES,'initial',NOW)

    def test_inactive_real_gates_reject_request_and_stale_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'stage';release.stage(synthetic69(),ROOT,out,release.INITIAL_HASHES,'initial',NOW)
            request=release.ReleaseRequest(out/'validated-input.json',release.digest_file(out/'validated-input.json'),out/'readiness.json',release.digest_file(out/'readiness.json'))
            with self.assertRaisesRegex(ValueError,'approval_invalid'):request.validate(ROOT,ROOT,NOW)
            request.ledger_hash='0'*64
            with self.assertRaises(ValueError):request.validate(ROOT,ROOT,NOW)


class PublicationTests(PipelineHarness):
    def setUp(self):
        super().setUp();self.at=NOW
        # Only the disposable fake main is activated for transaction tests.
        for name in release.IMPLEMENTATION:
            target=self.code/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        cfg=release.activation_candidate(read(self.code/'macro_sources.json'),NOW)
        s=next(s for s in cfg['sources'] if s['id']==tourgo.SOURCE)
        for grant in s['approval'].values():grant['evidence_ref']='SYNTHETIC-ADMIN-APPROVAL';grant['valid_until']='2026-12-31'
        (self.code/'macro_sources.json').write_text(json.dumps(cfg))
        git(self.code,'add','.');git(self.code,'commit','-m','Synthetic approved configuration')
        self.main=git(self.code,'rev-parse','HEAD').stdout.strip();git(self.code,'push','origin','main')
        self.kto=kto_snapshot(read(self.code/'collector_state/macro_archive.json'))

    def prepare(self,baseline=None,ledger=None,profile='initial',expected=None):
        out=self.root/('readiness-'+str(len(list(self.root.glob('readiness-*')))))
        release.stage(ledger or synthetic69(),baseline or self.code,out,expected or release.INITIAL_HASHES,profile,NOW,code=self.code)
        return release.ReleaseRequest(out/'validated-input.json',release.digest_file(out/'validated-input.json'),out/'readiness.json',release.digest_file(out/'readiness.json'))

    def run_manual(self,request):
        work=self.root/('manual-'+str(len(list(self.root.glob('manual-*')))))
        with patch('src.macro.kto.fetch',return_value=self.kto):
            return transact(self.code,str(self.remote),work,self.root/'pages',requested='macro',
                            collector=lambda *args:True,at=NOW,tourgo_request=request)

    def test_fresh_transaction_persists_621_without_staging_copy_or_private_exposure(self):
        request=self.prepare()
        # A damaged preview file is never an input to the publishing transaction.
        page=request.receipt_path.parent/'pages/data/macro.json';bad=read(page);bad['administrator_path']='MUST_NOT_BE_PROMOTED';page.write_text(json.dumps(bad))
        result=self.run_manual(request)
        self.assertTrue(result['ready']);self.assertTrue(result['collection_ok'])
        self.assertEqual(result['new_records']['macro_observations'],138)
        stored=self.reader();self.assertEqual(sum(len(i['observations']) for i in read(stored.path/'collector_state/macro_archive.json')['indicators'].values()),621)
        self.assertEqual(git(self.code,'rev-parse','HEAD').stdout.strip(),self.main)
        self.assertFalse((self.root/'pages/readiness.json').exists())
        self.assertNotIn('MUST_NOT_BE_PROMOTED',(self.root/'pages/data/macro.json').read_text())
        # The old proposal cannot be replayed against an already changed archive.
        with self.assertRaises(ValueError):self.run_manual(request)

    def test_reviewed_manual_correction_retains_138_periods_and_history(self):
        self.run_manual(self.prepare());baseline=self.reader();old=read(baseline.path/'collector_state/macro_archive.json')
        previous=synthetic69();values={k:{p:o['value'] for p,o in records.items()} for k,records in previous['series'].items()}
        values['receipts']['2026-09']+=7;values['balance']['2026-09']+=7
        proof=copy.deepcopy(previous['series']['receipts']['2026-09']['provenance'])
        proof['sha256_by_kind']={'receipts':'d'*64,'expenditure':'e'*64,'balance':'f'*64}
        updated=balance.merge_ledger(previous,values,proof,NOW)
        request=self.prepare(baseline.path,updated,'update',proof['sha256_by_kind'])
        result=self.run_manual(request);self.assertTrue(result['collection_ok'])
        saved=read(self.reader().path/'collector_state/macro_archive.json')
        self.assertEqual(result['new_records']['macro_observations'],0)
        for key in tourgo.IDS:
            self.assertEqual(len(saved['indicators'][key]['observations']),69)
            self.assertEqual(saved['indicators'][key]['observations']['2026-09']['first_collected_at'],old['indicators'][key]['observations']['2026-09']['first_collected_at'])
        self.assertEqual(saved['indicators'][tourgo.IDS[0]]['revisions'][-1]['kind'],'value_correction')
        self.assertEqual(saved['indicators'][tourgo.IDS[1]]['revisions'][-1]['kind'],'balance_crosscheck_change')

    def test_subsequent_daily_macro_waiting_is_a_successful_transaction(self):
        self.run_manual(self.prepare());old=read(self.reader().path/'collector_state/macro_archive.json')
        self.at=NOW+dt.timedelta(days=1)
        def scheduled(engine,stage,*_):
            if engine!='macro':return True
            h=collect(read(self.code/'macro_sources.json'),stage/'site/data',stage/'collector_state',now=self.at)
            self.assertEqual(next(s for s in h['sources'] if s['id']==tourgo.SOURCE)['status'],'manual_update_pending')
            return h['status'] not in ('failed','blocked')
        with patch('src.macro.kto.fetch',return_value=self.kto):result=self.run_pipeline(scheduled,requested='macro')
        self.assertTrue(result['collection_ok']);self.assertTrue(result['ready'])
        saved=read(self.reader().path/'collector_state/macro_archive.json')
        for key in tourgo.IDS:self.assertEqual(old['indicators'][key],saved['indicators'][key])

    def test_conflict_reloads_current_news_and_revalidates_same_manual_input(self):
        self.run_pipeline();baseline=self.reader();request=self.prepare(baseline.path)
        original=Store.commit;injected=[]
        def conflict(store,stage,code_commit,before):
            if not injected:
                injected.append(True);other=self.reader();copy=self.root/'concurrent-news';copy_data(other.path,copy,self.cfg);shutil.copyfile(other.path/CONTROL,copy/CONTROL)
                path=copy/'site/data/health.json';doc=read(path);doc['concurrent_news_marker']='preserved';path.write_text(json.dumps(doc))
                original(other,copy,self.main,other.path)
            return original(store,stage,code_commit,before)
        with patch.object(Store,'commit',conflict):result=self.run_manual(request)
        self.assertEqual(result['attempt'],2);self.assertTrue(result['collection_ok'])
        self.assertEqual(read(self.reader().path/'site/data/health.json')['concurrent_news_marker'],'preserved')

    def test_explicit_import_error_is_failed_even_with_successful_kto(self):
        request=self.prepare()
        with patch('src.macro.tourgo.fetch',side_effect=ValueError('synthetic_manual_import_invalid')):
            with self.assertRaisesRegex(ValueError,'no_data_committed'):self.run_manual(request)
        self.assertIsNone(Store(self.root/'failed-reader',str(self.remote),self.cfg).tip())

    def test_receipt_or_approval_revocation_blocks_all_remote_writes(self):
        request=self.prepare();cfg=read(self.code/'macro_sources.json');source=next(s for s in cfg['sources'] if s['id']==tourgo.SOURCE)
        until=source['approval']['publication'].pop('valid_until');(self.code/'macro_sources.json').write_text(json.dumps(cfg))
        with self.assertRaises(ValueError):request.validate(self.code,self.code,NOW)
        source['approval']['publication']['valid_until']=until;source['approval']['publication']['approved']=False
        (self.code/'macro_sources.json').write_text(json.dumps(cfg));git(self.code,'add','.');git(self.code,'commit','-m','Synthetic revocation');git(self.code,'push','origin','main');self.main=git(self.code,'rev-parse','HEAD').stdout.strip()
        with self.assertRaises(ValueError):self.run_manual(request)
        self.assertIsNone(Store(self.root/'empty-reader',str(self.remote),self.cfg).tip())

    def test_projection_different_from_review_rolls_back_macro(self):
        request=self.prepare();doc=read(request.receipt_path);doc['financial_projection_sha256']='0'*64;request.receipt_path.write_text(json.dumps(doc));request.receipt_hash=release.digest_file(request.receipt_path)
        with self.assertRaisesRegex(ValueError,'no_data_committed'):self.run_manual(request)
        self.assertIsNone(Store(self.root/'projection-reader',str(self.remote),self.cfg).tip())


    def test_original_files_are_revalidated_and_cannot_disagree_with_ledger(self):
        request=self.prepare();request.originals={k:self.root/(k+'.xls') for k in release.INITIAL_HASHES}
        for path in request.originals.values():path.write_bytes(b'SYNTHETIC NOT AN OFFICIAL XLS')
        with self.assertRaisesRegex(ValueError,'approval_invalid'):request.validate(self.code,self.code,NOW)
        original=synthetic69()
        def noisy_parser(*args,**kwargs):
            print('SYNTHETIC-PRIVATE-WORKBOOK-DIAGNOSTIC')
            return original
        captured=io.StringIO()
        with contextlib.redirect_stdout(captured),patch('src.macro.tourgo.from_files',side_effect=noisy_parser):
            request.validate(self.code,self.code,NOW)
        self.assertEqual(captured.getvalue(),'')
        unknown=copy.deepcopy(original)
        unknown['series']['receipts']['2026-09']['finality']='final'
        unknown['series']['receipts']['2026-09']['provenance']['finality']='final'
        with patch('src.macro.tourgo.from_files',return_value=unknown),self.assertRaises(ValueError):
            request.validate(self.code,self.code,NOW)
        altered=copy.deepcopy(original)
        altered['series']['receipts']['2026-09']['value']+=1
        altered['series']['balance']['2026-09']['value']+=1
        with patch('src.macro.tourgo.from_files',return_value=altered),self.assertRaises(ValueError):
            request.validate(self.code,self.code,NOW)

    def test_changed_macro_baseline_blocks_reviewed_receipt_before_remote_writes(self):
        self.run_pipeline();baseline=self.reader();request=self.prepare(baseline.path)
        state=baseline.path/'collector_state/macro_archive.json';old=read(state)
        old['updated_at']=(NOW-dt.timedelta(seconds=1)).isoformat();state.write_text(json.dumps(old))
        before=baseline.tip()
        with self.assertRaises(ValueError):request.validate(baseline.path,self.code,NOW)
        self.assertEqual(self.reader().tip(),before)

    def test_interruption_before_persist_leaves_previous_snapshot_unchanged(self):
        self.run_pipeline();baseline=self.reader();request=self.prepare(baseline.path);tip=baseline.tip()
        with patch('src.macro.tourgo.fetch',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):self.run_manual(request)
        self.assertEqual(self.reader().tip(),tip)

    def test_assembly_failure_keeps_committed_validated_data_without_pages(self):
        request=self.prepare()
        with patch('src.pipeline.runner.compose',side_effect=RuntimeError('simulated output failure')):
            with self.assertRaises(RuntimeError):self.run_manual(request)
        stored=self.reader()
        self.assertEqual(sum(len(i['observations']) for i in read(stored.path/'collector_state/macro_archive.json')['indicators'].values()),621)
        self.assertFalse((self.root/'pages').exists())
        # Git persistence and Pages deployment are distinct. Never delete a
        # validated committed vintage to disguise an independent deploy failure.
