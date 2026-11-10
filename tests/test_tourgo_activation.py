"""Synthetic private delivery fixtures; no real credentials, original XLS or refs."""
import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.macro import tourgo, tourgo_activation as activation, tourgo_delivery as delivery
from src.macro import tourgo_release as release
from src.pipeline.layout import read
from src.pipeline.store import Store
from test_tourgo_readiness import ROOT,NOW,synthetic69


def approval():
    return dict(collection=dict(evidence_ref='owner-collection-review',valid_from='2026-11-10',valid_until='2027-11-09'),
        publication=dict(evidence_ref='owner-publication-review',valid_from='2026-11-10',valid_until='2027-11-09'),
        terms_evidence_ref='institution-terms-20261109',conditions=dict(noncommercial=True,free_access=True,no_ads=True,attribution=True))


def environment():
    return dict(GITHUB_ACTIONS='true',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF='refs/heads/main',
        GITHUB_REPOSITORY='Serhankeem/tourismnews',GITHUB_WORKFLOW='TOURGO initial publication (manual)',GITHUB_ACTOR_ID='123',TOURGO_ALLOWED_ACTOR_IDS='123,456')


class FakeAPI:
    def __init__(self):
        self.calls=[]
        self.rules=dict(can_admins_bypass=False,protection_rules=[dict(type='required_reviewers',prevent_self_review=True,reviewers=[{'type':'User','reviewer':{'id':456}}])],deployment_branch_policy=dict(custom_branch_policies=True))
        self.branches=dict(total_count=1,branch_policies=[dict(name='main',type='branch')])
        self.raw={name:b'SYNTHETIC PRIVATE INPUT '+name.encode() for name in delivery.NAMES}
        self.raw['receipt.json']=json.dumps(dict(profile='initial')).encode()
        self.pins={k:tourgo.digest(self.raw[k+'.xls']) for k in release.INITIAL_HASHES}
        self.raw['manifest.json']=json.dumps(dict(schema_version=1,profile='initial',files={k:tourgo.digest(v) for k,v in self.raw.items()})).encode()
        self.manifest_hash=tourgo.digest(self.raw['manifest.json'])
        self.tree=[dict(path=name,mode='100644',type='blob',sha=f'{i+1:040x}') for i,name in enumerate(self.raw)]
        self.private=True

    def get(self,path):
        self.calls.append(path)
        if path.endswith('/deployment-branch-policies'):return self.branches
        if path.endswith('/environments/tourgo-production'):return self.rules
        if '/git/commits/' in path:return dict(sha='a'*40,tree=dict(sha='b'*40))
        if '/git/trees/' in path:return dict(sha='b'*40,tree=self.tree,truncated=False)
        if '/git/blobs/' in path:
            name=next(r['path'] for r in self.tree if r['sha']==path.rsplit('/',1)[-1]);raw=self.raw[name]
            return dict(encoding='base64',content=base64.b64encode(raw).decode(),size=len(raw))
        return dict(private=self.private,full_name='trusted/private-tourgo')


class ActivationPlanTests(unittest.TestCase):
    def test_plan_is_external_review_only_and_preserves_other_configuration(self):
        config=read(ROOT/'macro_sources.json');before=copy.deepcopy(config)
        planned=activation.plan(config,read(ROOT/'operating_policy.json'),approval(),NOW)
        self.assertEqual(config,before)
        for s in config['sources']:
            if s['id']!=tourgo.SOURCE:self.assertEqual(s,next(row for row in planned['sources'] if row['id']==s['id']))
        for i in config['indicators']:
            if i['id'] not in tourgo.IDS:self.assertEqual(i,next(row for row in planned['indicators'] if row['id']==i['id']))
        source=next(s for s in planned['sources'] if s['id']==tourgo.SOURCE)
        self.assertTrue(source['enabled']);self.assertTrue(source['approval']['publication']['approved'])
        self.assertFalse(next(s for s in config['sources'] if s['id']==tourgo.SOURCE)['enabled'])
        self.assertFalse(any(s['enabled'] for s in planned['sources'] if s['id'].startswith('ecos_')))

    def test_missing_expired_indefinite_or_staging_approval_is_rejected(self):
        for mode in ('missing','expired','future','unbounded','staging','same_ref','ads'):
            grant=approval()
            if mode=='missing':del grant['publication']['valid_until']
            if mode=='expired':grant['publication']['valid_until']='2026-11-09'
            if mode=='future':grant['publication']['valid_from']='2026-11-11'
            if mode=='unbounded':grant['publication']['valid_until']='9999-12-31'
            if mode=='staging':grant['publication']['evidence_ref']='staging-only'
            if mode=='same_ref':grant['collection']['evidence_ref']=grant['terms_evidence_ref']
            if mode=='ads':grant['conditions']['no_ads']=False
            with self.subTest(mode=mode),self.assertRaises(ValueError):activation.plan(read(ROOT/'macro_sources.json'),read(ROOT/'operating_policy.json'),grant,NOW)


class ProtectedDeliveryTests(unittest.TestCase):
    def test_only_explicit_authorized_main_dispatch_and_reviewed_environment(self):
        api=FakeAPI();delivery.protected_context(api,environment())
        for key,bad in [('GITHUB_EVENT_NAME','push'),('GITHUB_REF','refs/heads/feature'),('GITHUB_ACTOR_ID','999'),('GITHUB_WORKFLOW','Other workflow')]:
            env=environment();env[key]=bad
            with self.subTest(key=key),self.assertRaises(delivery.DeliveryError):delivery.protected_context(api,env)
        for mode in ('no_review','self_review','bypass','branch','tag'):
            api=FakeAPI()
            if mode=='no_review':api.rules['protection_rules']=[]
            if mode=='self_review':api.rules['protection_rules'][0]['prevent_self_review']=False
            if mode=='bypass':api.rules['can_admins_bypass']=True
            if mode=='branch':api.branches['total_count']=2
            if mode=='tag':api.branches['branch_policies'][0]['type']='tag'
            with self.subTest(mode=mode),self.assertRaises(delivery.DeliveryError):delivery.protected_context(api,environment())

    def fetch(self,api,target,expected=None):
        with patch.object(delivery,'INITIAL_HASHES',api.pins):
            return delivery.fetch_inputs(api,'trusted/private-tourgo','a'*40,expected or api.manifest_hash,target)

    def test_private_pinned_inputs_have_limits_and_private_permissions(self):
        api=FakeAPI()
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'input';self.fetch(api,target)
            self.assertEqual(target.stat().st_mode&0o777,0o700)
            self.assertEqual({p.name for p in target.iterdir()},{'manifest.json',*delivery.NAMES})
            self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in target.iterdir()))
            request=delivery.request(target,api.manifest_hash)
            self.assertEqual(set(request.originals),set(release.INITIAL_HASHES))
            self.assertTrue(all(p.parent==target for p in request.originals.values()))
            self.assertTrue(any('/git/commits/' in p for p in api.calls))
            self.assertFalse(any('contents/' in p or 'raw.githubusercontent' in p for p in api.calls))

    def test_public_repo_hash_mutation_symlink_and_path_traversal_fail_closed(self):
        for mode in ('public','manifest','corruption','symlink','traversal','extra_file','wrong_originals'):
            api=FakeAPI()
            if mode=='public':api.private=False
            if mode=='corruption':api.raw['ledger.json']+=b'CORRUPT'
            if mode=='symlink':api.tree[0]['mode']='120000'
            if mode=='traversal':api.tree[0]['path']='../ledger.json'
            if mode=='extra_file':api.tree.append(dict(path='other',mode='100644',type='blob',sha='c'*40))
            if mode=='wrong_originals':api.pins['receipts']='0'*64
            with tempfile.TemporaryDirectory() as tmp:
                target=Path(tmp)/'input'
                with self.subTest(mode=mode),self.assertRaises(delivery.DeliveryError):self.fetch(api,target,'0'*64 if mode=='manifest' else None)
                self.assertFalse(target.exists())

    def test_no_redirect_or_raw_errors_and_size_limit(self):
        self.assertIsNone(delivery.NoRedirect().redirect_request(None,None,None,None,None,None))
        api=delivery.GitHub('SYNTHETIC-NONSECRET-TOKEN')
        with patch.object(api,'open',side_effect=RuntimeError('PRIVATE RESPONSE https://private.invalid SECRET')):
            with self.assertRaisesRegex(delivery.DeliveryError,'^private_input_api_unavailable$'):api.get('repos/trusted/private')
        response=unittest.mock.MagicMock();response.__enter__.return_value.read.return_value=b'x'*(delivery.LIMIT+1)
        with patch.object(api,'open',return_value=response),self.assertRaisesRegex(delivery.DeliveryError,'size_limit'):api.get('repos/trusted/private')
        with self.assertRaisesRegex(delivery.DeliveryError,'duplicate_json_key'):delivery.decode_json(b'{"x":1,"x":2}')

    def test_default_inactive_configuration_never_contacts_private_repository(self):
        with patch.object(delivery,'GitHub',side_effect=AssertionError('no credential use')):
            with self.assertRaises(ValueError):delivery.prepare('/tmp/no-input-created',environment(),NOW)

    def test_approved_prepare_uses_environment_bound_private_token_and_keeps_config_unchanged(self):
        config=activation.plan(read(ROOT/'macro_sources.json'),read(ROOT/'operating_policy.json'),approval(),NOW)
        original=copy.deepcopy(config);api=FakeAPI();env=environment()
        env.update(TOURGO_INPUT_TOKEN='SYNTHETIC-INPUT-TOKEN',TOURGO_INPUT_REPOSITORY='trusted/private-tourgo',TOURGO_INPUT_COMMIT='a'*40,TOURGO_MANIFEST_SHA256=api.manifest_hash)
        def config_read(path):return config if Path(path).name=='macro_sources.json' else read(ROOT/'operating_policy.json')
        with tempfile.TemporaryDirectory() as tmp,patch.object(delivery,'GitHub',return_value=api) as client,patch.object(delivery,'read',side_effect=config_read),patch.object(delivery,'INITIAL_HASHES',api.pins):
            delivery.prepare(Path(tmp)/'input',env,NOW)
            client.assert_called_once_with('SYNTHETIC-INPUT-TOKEN')
        self.assertEqual(config,original)

    def test_workflow_is_manual_protected_shared_transaction_without_private_artifacts(self):
        manual=(ROOT/'.github/workflows/tourgo-publish.yml').read_text()
        pipeline=(ROOT/'.github/workflows/pipeline.yml').read_text()
        self.assertIn('workflow_dispatch:',manual);self.assertNotIn('schedule:',manual)
        self.assertIn("github.event_name == 'workflow_dispatch'",manual)
        self.assertIn('uses: ./.github/workflows/pipeline.yml',manual)
        self.assertEqual(pipeline.count('group: tourism-pulse-publish'),1)
        self.assertIn("'tourgo-production' || 'github-pages'",pipeline)
        self.assertIn('rm -rf -- "$RUNNER_TEMP/tourgo-private-input"',pipeline)
        for key in ('TOURGO_INPUT_REPOSITORY','TOURGO_INPUT_COMMIT','TOURGO_MANIFEST_SHA256','TOURGO_ALLOWED_ACTOR_IDS'):
            self.assertIn('${{ secrets.'+key+' }}',pipeline)
            self.assertNotIn('${{ vars.'+key+' }}',pipeline)
        artifacts=pipeline[pipeline.index('name: pipeline-diagnostics-'):]
        self.assertNotIn('receipt.json',artifacts);self.assertNotIn('ledger.json',artifacts)
        self.assertNotIn('git push',pipeline);self.assertNotIn('git push',manual)
