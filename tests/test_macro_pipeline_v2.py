"""SYNTHETIC JSON stand-ins parsed through the real table validator.

No official XLS bytes/credentials are available here. Hashing/packaging, all
normalization rules, private Git transport fixtures and local bare Git CAS run.
"""
import copy
import datetime as dt
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from src.macro import balance,tourgo,tourgo_staging as staging,tourgo_update as update,tourgo_release as release,tourgo_activation as activation,tourgo_delivery as delivery
from src.pipeline.layout import ROOT,read,copy_data,CONTROL
from src.pipeline.store import Store,git
from src.pipeline.runner import transact
from src.pipeline.report import render
from test_pipeline import PipelineHarness
from test_tourgo_activation import approval,environment,FakeAPI
from test_tourgo_readiness import synthetic69,NOW,kto_snapshot


def table(values,unit='1,000 US$'):
    rows=[['연도','계']+[f'{m}월' for m in range(1,13)]]
    for year in sorted({p[:4] for p in values}):
        cells=[values.get(f'{year}-{m:02}','') for m in range(1,13)]
        rows.append([f'{year}년({unit})',sum(v for v in cells if v!='')]+cells)
    return rows


def values70():
    ledger=synthetic69();v=tourgo.validate_ledger(ledger,NOW)
    for k,n in [('receipts',10100),('expenditure',13140),('balance',-3040)]:v[k]['2026-10']=n
    return v


def originals(root,values):
    root.mkdir(parents=True)
    paths={k:root/(k+'.xls') for k in balance.KINDS}
    for k,p in paths.items():p.write_text(json.dumps(table(values[k]),ensure_ascii=False))
    return paths


def parse_fake(path,kind,now):return balance.parse_rows(json.loads(Path(path).read_text()),kind,now)


def delivered(root,paths,source):
    with patch.object(balance,'read_xls',side_effect=parse_fake):
        staging.source_package(paths,root,True,source=source,requested_range=tourgo.approved_range(source,'collection'))
    (root/'delivery.json').write_text(json.dumps({'schema_version':2,'manifest_sha256':release.digest_file(root/'manifest.json')}))
    return update.RecurringRequest(root)


class AdapterQualityTests(unittest.TestCase):
    def test_initial_pins_69_months_and_exact_units_and_automatic_release_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);v=tourgo.validate_ledger(synthetic69(),NOW);paths=originals(root/'originals',v)
            pins={k:release.digest_file(p) for k,p in paths.items()}
            archive=read(ROOT/'collector_state/macro_archive.json')
            with patch.object(staging,'INITIAL_HASHES',pins),patch.object(release,'INITIAL_HASHES',pins),patch.object(balance,'read_xls',side_effect=parse_fake):
                ledger,_=staging.OfficialFiles(paths).load(archive,'initial',NOW)
                quality=staging.assess(ledger,archive,'initial',NOW)
                self.assertEqual(quality['official_identity_months'],69)
                self.assertFalse(quality['publication_allowed'])
                self.assertEqual(tourgo.usd(ledger['series']['receipts']['2026-09']['value']),10068000)
                m=staging.release_package(paths,ROOT,root/'handoff','initial',NOW,True)
            self.assertEqual(m['schema_version'],1);self.assertEqual(len(m['files']),5)
            self.assertEqual({p.name for p in (root/'handoff/input').iterdir()},{'manifest.json',*delivery.NAMES})
            self.assertEqual(read(root/'handoff/staging/readiness.json')['projected_total_observations'],621)
            with self.assertRaises(ValueError):staging.OfficialFiles(paths).load(archive,'initial',NOW)

    def test_source_review_is_required_and_no_ledger_receipt_or_manual_hash_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths=originals(root/'source',tourgo.validate_ledger(synthetic69(),NOW))
            with self.assertRaises(ValueError):staging.source_package(paths,root/'bad',False)
            with patch.object(balance,'read_xls',side_effect=parse_fake):
                m=staging.source_package(paths,root/'package',True,requested_range=tourgo.INITIAL_PERIOD_RANGE)
            self.assertEqual(m['profile'],'update');self.assertEqual(m['schema_version'],2)
            self.assertEqual(set(m['files']),set(staging.SOURCE_FILES))
            self.assertFalse((root/'package/ledger.json').exists());self.assertFalse((root/'package/receipt.json').exists())
            self.assertEqual(read(root/'package/source.json'),staging.SOURCE)

    def test_missing_future_duplicate_month_wrong_unit_and_identity_are_rejected(self):
        for mode in ('gap','future','duplicate','unit','identity'):
            v=tourgo.validate_ledger(synthetic69(),NOW)
            if mode=='gap':
                for kind in v:del v[kind]['2024-03']
            if mode=='future':
                for kind in v:v[kind]['2026-11']=1 if kind!='balance' else 0
            if mode=='identity':v['balance']['2026-09']+=1
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);paths=originals(root/'files',v)
                if mode=='duplicate':
                    rows=json.loads(paths['receipts'].read_text());rows.append(rows[-1]);paths['receipts'].write_text(json.dumps(rows))
                if mode=='unit':paths['receipts'].write_text(json.dumps(table(v['receipts'],'US$')))
                with patch.object(balance,'read_xls',side_effect=parse_fake),self.assertRaises(ValueError):
                    # Use an empty baseline with update deliberately rejected at
                    # the bootstrap boundary; parse independently to exercise errors.
                    parsed=tourgo.from_files(paths,{k:release.digest_file(p) for k,p in paths.items()},NOW,requested_range=tourgo.INITIAL_PERIOD_RANGE)
                    staging.assess(parsed,read(ROOT/'collector_state/macro_archive.json'),'initial',NOW)

    def test_gate_never_promotes_collection_to_publication_or_changes_config(self):
        cfg=activation.plan(read(ROOT/'macro_sources.json'),read(ROOT/'operating_policy.json'),approval(),NOW)
        source=next(s for s in cfg['sources'] if s['id']==tourgo.SOURCE);source['enabled']=False
        source['approval']['publication']['approved']=False;before=copy.deepcopy(cfg)
        rights=staging.gates(cfg,read(ROOT/'operating_policy.json'),NOW)
        self.assertTrue(rights['collection_allowed']);self.assertFalse(rights['publication_allowed']);self.assertEqual(cfg,before)
        source['approval']['collection']['valid_until']='2026-11-09'
        self.assertFalse(staging.gates(cfg,read(ROOT/'operating_policy.json'),NOW)['collection_allowed'])
        policy=read(ROOT/'operating_policy.json');policy['ads_enabled']=True
        self.assertFalse(staging.gates(cfg,policy,NOW)['terms_verified'])
        source['rights_evidence']['status']='review'
        self.assertFalse(staging.gates(cfg,read(ROOT/'operating_policy.json'),NOW)['collection_allowed'])


class UpdateAPI(FakeAPI):
    def __init__(self,package):
        super().__init__();self.raw={p.name:p.read_bytes() for p in package.iterdir()}
        self.tree=[dict(path=name,mode='100644',type='blob',sha=f'{i+1:040x}') for i,name in enumerate(self.raw)]
        self.verified=True;self.author=123
    def get(self,path):
        if path.endswith('/git/ref/heads/updates'):return dict(object=dict(type='commit',sha='a'*40))
        if '/git/' not in path and path.endswith('/commits/'+'a'*40):return dict(sha='a'*40,author={'id':self.author},commit=dict(verification=dict(verified=self.verified,reason='valid')))
        return super().get(path)


class RecurringTransportTests(unittest.TestCase):
    def test_only_signed_owner_private_commit_and_real_protection_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths=originals(root/'files',tourgo.validate_ledger(synthetic69(),NOW))
            with patch.object(balance,'read_xls',side_effect=parse_fake):
                staging.source_package(paths,root/'package',True,requested_range=tourgo.INITIAL_PERIOD_RANGE)
            cfg=activation.plan(read(ROOT/'macro_sources.json'),read(ROOT/'operating_policy.json'),approval(),NOW)
            def settings(p):return cfg if Path(p).name=='macro_sources.json' else read(ROOT/'operating_policy.json')
            env=environment();env.update(GITHUB_WORKFLOW=update.WORKFLOW,TOURGO_INPUT_TOKEN='SYNTHETIC',TOURGO_INPUT_REPOSITORY='trusted/private-tourgo')
            for mode in ('normal','unsigned','other_owner','bad_timer','public','bad_origin','foreign_attestation'):
                api=UpdateAPI(root/'package')
                if mode=='unsigned':api.verified=False
                if mode=='other_owner':api.author=456
                if mode=='bad_timer':api.rules['protection_rules'][0]['wait_timer']=0
                if mode=='public':api.private=False
                if mode=='bad_origin':api.raw['source.json']=b'FOREIGN SOURCE'
                if mode=='foreign_attestation':
                    foreign=copy.deepcopy(staging.SOURCE);foreign['source_url']='https://foreign.invalid'
                    api.raw['source.json']=json.dumps(foreign).encode()
                    m=json.loads(api.raw['manifest.json']);m['files']['source.json']=tourgo.digest(api.raw['source.json']);api.raw['manifest.json']=json.dumps(m).encode()
                with patch.object(delivery,'GitHub',return_value=api),patch.object(update,'read',side_effect=settings):
                    if mode=='normal':
                        update.deliver(root/mode,env,NOW)
                        self.assertEqual(read(root/mode/'source.json'),staging.SOURCE)
                        self.assertTrue((root/mode/'delivery.json').exists())
                    else:
                        with self.subTest(mode=mode),self.assertRaises(ValueError):update.deliver(root/mode,env,NOW)
                        self.assertFalse((root/mode).exists())

    def test_revoked_collection_flag_blocks_before_private_api_use(self):
        config=read(ROOT/'macro_sources.json')
        source=next(s for s in config['sources'] if s['id']==tourgo.SOURCE)
        self.assertTrue(source['approval']['collection']['approved'])
        source['approval']['collection']['approved']=False
        def denied_settings(path):
            return config if Path(path).name=='macro_sources.json' else read(ROOT/'operating_policy.json')
        with patch.object(update,'read',side_effect=denied_settings),patch.object(delivery,'GitHub',side_effect=AssertionError('no credential use')),self.assertRaises(ValueError):
            update.deliver('/tmp/no-update-input',environment(),NOW)


class RecurringTransactionTests(PipelineHarness):
    def setUp(self):
        super().setUp();self.at=NOW
        for name in release.IMPLEMENTATION:
            target=self.code/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        self.config=activation.plan(read(self.code/'macro_sources.json'),read(self.code/'operating_policy.json'),approval(),NOW)
        # Separate synthetic future approval only in the local bare-Git fixture.
        for grant in next(s for s in self.config['sources'] if s['id']==tourgo.SOURCE)['approval'].values():grant['period_through']='2026-10'
        (self.code/'macro_sources.json').write_text(json.dumps(self.config))
        self.kto=kto_snapshot(read(self.code/'collector_state/macro_archive.json'))
        from src.macro.engine import collect
        collect(self.config,self.code/'site/data',self.code/'collector_state',now=NOW,force=True,tourgo_ledger=synthetic69(),only_sources={tourgo.SOURCE})
        git(self.code,'add','.');git(self.code,'commit','-m','Synthetic activated baseline');git(self.code,'push','origin','main')
        self.main=git(self.code,'rev-parse','HEAD').stdout.strip();self.run_pipeline();self.counter=0

    def input(self,values=None):
        self.counter+=1;paths=originals(self.root/('originals-'+str(self.counter)),values or values70())
        return delivered(self.root/('input-'+str(self.counter)),paths,next(s for s in self.config['sources'] if s['id']==tourgo.SOURCE))

    def run_update(self,request):
        work=self.root/('update-'+str(len(list(self.root.glob('update-*')))))
        with patch.object(balance,'read_xls',side_effect=parse_fake),patch('src.macro.kto.fetch',return_value=self.kto):
            return transact(self.code,str(self.remote),work,self.root/'pages',requested='macro',collector=lambda *args:True,at=NOW,tourgo_request=request)

    def test_valid_new_month_then_identical_replay_skips_commit_collect_and_pages(self):
        r=self.run_update(self.input());self.assertTrue(r['ready']);self.assertEqual(r['new_records']['macro_observations'],2)
        self.assertEqual(r['tourgo_verification']['status'],'VALID');before=self.reader();tip=before.tip()
        raw=(before.path/'collector_state/macro_archive.json').read_bytes()
        with patch('src.macro.engine.collect',side_effect=AssertionError('unchanged must not collect')),patch('src.pipeline.runner.compose',side_effect=AssertionError('unchanged must not assemble')):
            r=self.run_update(self.input())
        self.assertFalse(r['ready']);self.assertTrue(r['collection_ok']);self.assertFalse(r['data_committed'])
        self.assertEqual(r['tourgo_verification']['status'],'UNCHANGED');self.assertEqual(self.reader().tip(),tip)
        self.assertEqual((self.reader().path/'collector_state/macro_archive.json').read_bytes(),raw)
        self.assertEqual(r['counts']['macro_observations'],623)

    def test_historical_correction_and_outlier_require_review_without_remote_writes(self):
        before=self.reader().tip()
        for kind in ('revision','outlier'):
            v=values70()
            if kind=='revision':v['receipts']['2024-03']+=7;v['balance']['2024-03']+=7
            else:v['receipts']['2026-10']*=5;v['balance']['2026-10']=v['receipts']['2026-10']-v['expenditure']['2026-10']
            r=self.run_update(self.input(v));self.assertFalse(r['ready']);self.assertFalse(r['collection_ok']);self.assertEqual(r['tourgo_verification']['status'],'REVIEW_REQUIRED')
            self.assertFalse(r['tourgo_verification']['publication_allowed']);self.assertEqual(self.reader().tip(),before)

    def test_collection_only_stages_privately_but_never_publishes(self):
        s=next(s for s in self.config['sources'] if s['id']==tourgo.SOURCE);s['approval']['publication']['approved']=False;s['enabled']=False
        (self.code/'macro_sources.json').write_text(json.dumps(self.config));git(self.code,'add','.');git(self.code,'commit','-m','Synthetic publication withheld');git(self.code,'push','origin','main')
        before=self.reader().tip();r=self.run_update(self.input());self.assertFalse(r['ready'])
        self.assertIn('publication_approval_required',r['tourgo_verification']['reasons']);self.assertEqual(self.reader().tip(),before)
        self.assertTrue(any(self.root.glob('input-*/verified-*/readiness.json')))
        # Ordinary policy deployment removes prior public amounts after approval
        # withdrawal. The private archive itself and all 621 records remain.
        self.main=git(self.code,'rev-parse','HEAD').stdout.strip();r=self.run_pipeline()
        self.assertEqual(r['counts']['macro_observations'],621)
        self.assertIsNone(read(self.root/'pages/data/macro.json').get('tourism_balance'))

    def test_bad_original_hash_or_expired_approval_preserves_latest_snapshot(self):
        for mode in ('bad_hash','expired'):
            request=self.input();before=self.reader().tip()
            if mode=='bad_hash':(request.directory/'receipts.xls').write_bytes(b'CORRUPTED')
            else:
                s=next(s for s in self.config['sources'] if s['id']==tourgo.SOURCE);s['approval']['publication']['valid_until']='2026-11-09'
                (self.code/'macro_sources.json').write_text(json.dumps(self.config));git(self.code,'add','.');git(self.code,'commit','-m','Synthetic expiry');git(self.code,'push','origin','main')
            r=self.run_update(request);self.assertFalse(r['ready']);self.assertEqual(self.reader().tip(),before)
            self.assertEqual(r['tourgo_verification']['status'],'REJECTED' if mode=='bad_hash' else 'REVIEW_REQUIRED')

    def test_conflict_preserves_concurrent_news_and_rebuilds_staging(self):
        request=self.input();original=Store.commit;injected=[]
        def conflict(store,stage,code_commit,before):
            if not injected:
                injected.append(True);other=self.reader();cp=self.root/'concurrent-news';copy_data(other.path,cp,self.cfg);shutil.copyfile(other.path/CONTROL,cp/CONTROL)
                doc=read(cp/'site/data/health.json');doc['v2_news_marker']='preserved';(cp/'site/data/health.json').write_text(json.dumps(doc));original(other,cp,self.main,other.path)
            return original(store,stage,code_commit,before)
        with patch.object(Store,'commit',conflict):r=self.run_update(request)
        self.assertEqual(r['attempt'],2);self.assertTrue(r['ready']);self.assertEqual(read(self.reader().path/'site/data/health.json')['v2_news_marker'],'preserved')

    def test_concurrent_macro_changes_are_reassessed_not_overwritten(self):
        request=self.input();other_values=values70();other_values['receipts']['2026-10']+=1;other_values['balance']['2026-10']+=1
        other_request=self.input(other_values);original=Store.commit;injected=[]
        def conflict(store,stage,code_commit,before):
            if not injected:
                injected.append(True);self.run_update(other_request)
            return original(store,stage,code_commit,before)
        with patch.object(Store,'commit',conflict):r=self.run_update(request)
        self.assertFalse(r['ready']);self.assertEqual(r['tourgo_verification']['status'],'REVIEW_REQUIRED')
        self.assertEqual(r['attempt'],2);self.assertEqual(r['engines'],{})
        saved=read(self.reader().path/'collector_state/macro_archive.json')
        self.assertEqual(saved['indicators'][tourgo.IDS[0]]['observations']['2026-10']['value'],10101000)

    def test_explicitly_reviewed_revision_reuses_legacy_receipt_and_approvals(self):
        v=tourgo.validate_ledger(synthetic69(),NOW);v['receipts']['2024-03']+=4;v['balance']['2024-03']+=4
        paths=originals(self.root/'reviewed-originals',v);baseline=self.reader()
        with patch.object(balance,'read_xls',side_effect=parse_fake):
            staging.release_package(paths,baseline.path,self.root/'reviewed-release','update',NOW,True,code=self.code,requested_range=tourgo.INITIAL_PERIOD_RANGE)
        p=self.root/'reviewed-release/input';request=delivery.request(p,release.digest_file(p/'manifest.json'))
        r=self.run_update(request);self.assertTrue(r['ready'])
        saved=read(self.reader().path/'collector_state/macro_archive.json');self.assertTrue(saved['indicators'][tourgo.IDS[0]]['revisions'])
        self.assertEqual(read(self.code/'macro_sources.json'),self.config)

    def test_terms_withdrawal_hides_existing_public_amounts_without_deleting_records(self):
        s=next(s for s in self.config['sources'] if s['id']==tourgo.SOURCE)
        s['rights_evidence']['status']='review'
        (self.code/'macro_sources.json').write_text(json.dumps(self.config));git(self.code,'add','.');git(self.code,'commit','-m','Synthetic institutional terms withdrawal');git(self.code,'push','origin','main')
        self.main=git(self.code,'rev-parse','HEAD').stdout.strip();r=self.run_pipeline()
        self.assertEqual(r['counts']['macro_observations'],621)
        self.assertIsNone(read(self.root/'pages/data/macro.json').get('tourism_balance'))
        self.assertFalse(any(i['connected'] for i in read(self.root/'pages/data/macro.json')['indicators'] if i['source_id']==tourgo.SOURCE))

    def test_summary_discloses_only_whitelisted_verification_fields(self):
        result={'tourgo_verification':dict(status='REVIEW_REQUIRED',new_months=1,revised_observations=2,
            reasons=['historical_revision_requires_review','https://PRIVATE-TOKEN.invalid'],secret='PRIVATE-METADATA')}
        text=render(result,'skipped');self.assertIn('REVIEW_REQUIRED',text);self.assertNotIn('PRIVATE',text)
