"""Recurring owner-file updates: fresh staging, no monthly ledger/hash assembly.

Only signed owner commits on the private `updates` branch are accepted. This is
NOT an official TOURGO downloader; the owner still verifies/acquires originals.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
from . import tourgo
from . import tourgo_delivery as delivery
from . import tourgo_staging as staging
from .tourgo_release import ROOT, ReleaseRequest, digest_file, stage, operating_configuration
from ..collector import write_atomic
from ..pipeline.layout import read

WORKFLOW='TOURGO recurring update (manual)'


def deliver(output,env=None,now=None):
    env=os.environ if env is None else env
    now=now or dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    rights=staging.gates(read(ROOT/'macro_sources.json'),read(ROOT/'operating_policy.json'),now)
    if not rights['collection_allowed']:delivery.fail('tourgo_collection_approval_required')
    api=delivery.GitHub(env.get('TOURGO_INPUT_TOKEN'))
    delivery.protected_context(api,env,workflow=WORKFLOW)
    repo=env.get('TOURGO_INPUT_REPOSITORY')
    # Validate location before interpolating it in a fixed GitHub API path.
    import re
    if not isinstance(repo,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',repo) or repo.lower()=='serhankeem/tourismnews':delivery.fail('private_input_location_invalid')
    ref=api.get('repos/'+repo+'/git/ref/heads/updates')
    commit=ref.get('object',{}).get('sha','')
    if ref.get('object',{}).get('type')!='commit' or not re.fullmatch('[a-f0-9]{40}',commit):delivery.fail('private_update_ref_invalid')
    identity=api.get('repos/'+repo+'/commits/'+commit)
    verified=identity.get('commit',{}).get('verification',{})
    if (identity.get('sha')!=commit or str((identity.get('author') or {}).get('id'))!=env.get('GITHUB_ACTOR_ID')
            or verified.get('verified') is not True or verified.get('reason')!='valid'):
        delivery.fail('private_update_signed_owner_commit_required')
    blob=delivery.private_blobs(api,repo,commit,('manifest.json',*staging.SOURCE_FILES))
    manifest_raw=blob('manifest.json');manifest=delivery.decode_json(manifest_raw)
    if (not isinstance(manifest,dict) or set(manifest) not in ({'schema_version','profile','files'},{'schema_version','profile','files','period_range'})
            or manifest.get('schema_version')!=2 or manifest.get('profile')!='update'
            or not isinstance(manifest.get('files'),dict) or set(manifest['files'])!=set(staging.SOURCE_FILES)
            or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in manifest['files'].values())):
        delivery.fail('private_update_manifest_invalid')
    source=next(s for s in read(ROOT/'macro_sources.json')['sources'] if s['id']==tourgo.SOURCE)
    declared=tourgo.input_range({k:manifest['files'][k+'.xls'] for k in tourgo.balance.KINDS},manifest.get('period_range'))
    tourgo.require_range(source,'collection',declared)
    target=staging.external_directory(output)
    try:
        for name,expected in manifest['files'].items():
            raw=blob(name)
            if tourgo.digest(raw)!=expected:delivery.fail('private_input_file_hash_mismatch')
            (target/name).write_bytes(raw);(target/name).chmod(0o600)
        if delivery.decode_json((target/'source.json').read_bytes())!=staging.SOURCE:delivery.fail('tourgo_source_attestation_invalid')
        (target/'manifest.json').write_bytes(manifest_raw);(target/'manifest.json').chmod(0o600)
        # Integrity captured once after trusted transport; never exposed as output.
        write_atomic(target/'delivery.json',dict(schema_version=2,manifest_sha256=tourgo.digest(manifest_raw)))
        (target/'delivery.json').chmod(0o600)
    except Exception:
        import shutil
        shutil.rmtree(target);raise


class RecurringRequest:
    def __init__(self,directory):
        self.directory=Path(directory).resolve();self.attempt=0;self.outcome=None
        self.manifest_hash=read(self.directory/'delivery.json')['manifest_sha256']

    def validate(self,baseline,code,now):
        self.attempt+=1;code=Path(code).resolve();root=self.directory
        if root==code or code in root.parents or ROOT in root.parents:raise ValueError('tourgo_private_input_must_be_external')
        rights=staging.gates(read(code/'macro_sources.json'),read(code/'operating_policy.json'),now)
        def report(status,reason):
            self.outcome=dict(status=status,data_status=status,reasons=[reason],publication_allowed=False,profile='update',new_months=0,revised_observations=0,anomaly_count=0)
        if not rights['collection_allowed']:
            report('REVIEW_REQUIRED','collection_approval_required');return None
        try:
            if digest_file(root/'manifest.json')!=self.manifest_hash:raise ValueError('private_input_manifest_hash_mismatch')
            m=delivery.decode_json((root/'manifest.json').read_bytes())
            if set(m['files'])!=set(staging.SOURCE_FILES) or m.get('schema_version')!=2 or m.get('profile')!='update':raise ValueError('private_update_manifest_invalid')
            source=next(s for s in read(code/'macro_sources.json')['sources'] if s['id']==tourgo.SOURCE)
            declared=tourgo.input_range({k:m['files'][k+'.xls'] for k in tourgo.balance.KINDS},m.get('period_range'))
            tourgo.require_range(source,'collection',declared)
            for name,expected in m['files'].items():
                if (root/name).is_symlink() or digest_file(root/name)!=expected:raise ValueError('private_input_file_hash_mismatch')
            if delivery.decode_json((root/'source.json').read_bytes())!=staging.SOURCE:raise ValueError('tourgo_source_attestation_invalid')
            archive=read(Path(baseline)/'collector_state/macro_archive.json')
            paths={k:root/(k+'.xls') for k in tourgo.balance.KINDS}
            ledger,expected=staging.OfficialFiles(paths,{k:m['files'][k+'.xls'] for k in tourgo.balance.KINDS},source=source,requested_range=declared).load(archive,'update',now)
            quality=staging.assess(ledger,archive,'update',now);quality.update(rights);self.outcome=quality
            quality['publication_allowed']=False
            if quality['data_status']!='UNCHANGED':
                output=root/('verified-'+str(self.attempt))
                stage(ledger,baseline,output,expected,'update',now,code=code)
            if not rights['publication_allowed']:
                quality['status']='REVIEW_REQUIRED';quality['reasons'].append('publication_approval_required');return None
            try:operating_configuration(read(code/'macro_sources.json'),read(code/'operating_policy.json'),now)
            except ValueError:
                quality['status']='REVIEW_REQUIRED';quality['reasons'].append('operating_mapping_not_activated');return None
            if quality['status']=='REVIEW_REQUIRED':return None
            quality['publication_allowed']=True
            if quality['data_status']=='UNCHANGED':return None
            self.release=ReleaseRequest(output/'validated-input.json',digest_file(output/'validated-input.json'),output/'readiness.json',digest_file(output/'readiness.json'),originals=paths)
            return self.release.validate(baseline,code,now)
        except Exception as exc:
            allowed={'tourgo_missing_or_out_of_scope_period','tourgo_original_lost_existing_periods','tourgo_saved_source_or_unit_invalid',
                'private_input_file_hash_mismatch','private_input_manifest_hash_mismatch','tourgo_source_attestation_invalid',
                'balance_future_or_duplicate_period','balance_export_unit_or_year_mismatch','balance_identity_mismatch','tourgo_original_hash_mismatch'}
            reason=str(exc) if str(exc) in allowed else 'tourgo_input_validation_failed'
            if str(exc) in ('tourgo_period_scope_exceeded','tourgo_period_scope_unverified'):
                report('REVIEW_REQUIRED',str(exc))
            else:report('REJECTED',reason)
            return None

    def verify_projection(self,root):return self.release.verify_projection(root)


def main():
    p=argparse.ArgumentParser(description='Protected private recurring inputs only; no download from TOURGO or publication')
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    try:
        deliver(args.output);print('tourgo_update_private_input_verified; not_published');return 0
    except Exception as exc:
        code=str(exc) if isinstance(exc,delivery.DeliveryError) or str(exc) in ('tourgo_period_scope_exceeded','tourgo_period_scope_unverified') else 'tourgo_update_delivery_blocked'
        print(code)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('## TOURGO update\n\nBlocked: `'+code+'`; no publication.\n')
        return 1


if __name__=='__main__':raise SystemExit(main())
