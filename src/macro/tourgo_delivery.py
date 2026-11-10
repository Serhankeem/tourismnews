"""Protected manual delivery from a pinned PRIVATE GitHub repository.

Bounded HTTPS GitHub API requests only. No user URLs, redirects, shell, archive
extraction, public artifacts, operating settings edits or standalone Git pushes.
All error reporting is fixed enums; private payloads/URLs/hashes are never logged.
"""
import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import urllib.request
from . import tourgo
from .tourgo_release import ROOT, INITIAL_HASHES, ReleaseRequest, operating_configuration
from ..pipeline.layout import read, DataError

LIMIT=8*1024*1024
NAMES=('ledger.json','receipt.json','receipts.xls','expenditure.xls','balance.xls')


class DeliveryError(ValueError):pass


def fail(code):raise DeliveryError(code)

def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:fail('duplicate_json_key')
        result[key]=value
    return result


def decode_json(raw):
    try:return json.loads(raw,object_pairs_hook=unique)
    except DeliveryError:raise
    except Exception:fail('invalid_json')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class GitHub:
    def __init__(self,token):
        if not token or any(c.isspace() for c in token):fail('private_input_credential_missing')
        self.token=token
        self.open=urllib.request.build_opener(NoRedirect()).open

    def get(self,path):
        # All paths are constructed from validated repo IDs, SHA and fixed enums.
        request=urllib.request.Request('https://api.github.com/'+path,headers={
            'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json',
            'X-GitHub-Api-Version':'2022-11-28','User-Agent':'currentourism-protected-tourgo'})
        try:
            with self.open(request,timeout=45) as response:
                raw=response.read(LIMIT+1)
            if len(raw)>LIMIT:fail('private_input_size_limit')
            return decode_json(raw)
        except DeliveryError:raise
        except Exception:fail('private_input_api_unavailable')


def protected_context(api, env, workflow='TOURGO initial publication (manual)'):
    if (env.get('GITHUB_ACTIONS')!='true' or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch'
            or env.get('GITHUB_REF')!='refs/heads/main'
            or env.get('GITHUB_REPOSITORY')!='Serhankeem/tourismnews'
            or env.get('GITHUB_WORKFLOW')!=workflow):
        fail('protected_manual_main_required')
    actors=env.get('TOURGO_ALLOWED_ACTOR_IDS','').split(',')
    if len(actors)!=1 or any(not re.fullmatch('[1-9][0-9]*',a) for a in actors) or env.get('GITHUB_ACTOR_ID') not in actors:
        fail('authorized_admin_actor_required')
    policy=api.get('repos/Serhankeem/tourismnews/environments/tourgo-production')
    rules=policy.get('protection_rules',[])
    # Solo-owner mode: the protected environment must impose a real cooling-off
    # period instead of a non-existent second reviewer. The configured wait
    # timer is enforced using GitHub's live environment API, not input secrets.
    if not isinstance(rules,list):
        fail('protected_environment_not_ready')
    wait_rules=[r for r in rules if isinstance(r,dict) and r.get('type')=='wait_timer']
    reviewer_rules=[r for r in rules if isinstance(r,dict) and r.get('type')=='required_reviewers']
    branch=policy.get('deployment_branch_policy') or {}
    if (len(wait_rules)!=1 or type(wait_rules[0].get('wait_timer')) is not int
            or wait_rules[0]['wait_timer']<10 or reviewer_rules
            or policy.get('can_admins_bypass') is not False
            or branch.get('custom_branch_policies') is not True):
        fail('protected_solo_environment_not_ready')
    branches=api.get('repos/Serhankeem/tourismnews/environments/tourgo-production/deployment-branch-policies')
    if branches.get('total_count')!=1 or [(r.get('name'),r.get('type')) for r in branches.get('branch_policies',[])]!=[('main','branch')]:
        fail('protected_environment_main_only_required')


def private_blobs(api,repository,commit,names):
    if (not isinstance(repository,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',repository)
            or repository.lower()=='serhankeem/tourismnews' or not re.fullmatch('[a-f0-9]{40}',commit or '')):
        fail('private_input_location_invalid')
    prefix='repos/'+repository
    meta=api.get(prefix)
    if meta.get('private') is not True or str(meta.get('full_name','')).lower()!=repository.lower():fail('private_repository_required')
    committed=api.get(prefix+'/git/commits/'+commit)
    tree_sha=committed.get('tree',{}).get('sha','')
    if committed.get('sha')!=commit or not re.fullmatch('[a-f0-9]{40}',tree_sha):fail('private_input_commit_invalid')
    tree=api.get(prefix+'/git/trees/'+tree_sha)
    if tree.get('truncated') or tree.get('sha') is None:fail('private_input_tree_invalid')
    rows=tree.get('tree',[])
    if len(rows)!=len(names) or {r.get('path') for r in rows}!=set(names) or any(r.get('type')!='blob' or r.get('mode')!='100644' for r in rows):
        fail('private_input_tree_invalid')
    entries={r['path']:r for r in rows}
    def blob(name):
        sha=entries[name].get('sha','')
        if not re.fullmatch('[a-f0-9]{40}',sha):fail('private_input_blob_invalid')
        doc=api.get(prefix+'/git/blobs/'+sha)
        try:
            if doc.get('encoding')!='base64':fail('private_input_encoding_invalid')
            raw=base64.b64decode(''.join(doc['content'].split()),validate=True)
            if len(raw)>LIMIT//2 or doc.get('size')!=len(raw):fail('private_input_size_limit')
            return raw
        except DeliveryError:raise
        except Exception:fail('private_input_blob_invalid')
    return blob


def fetch_inputs(api, repository, commit, manifest_hash, output, profile='initial'):
    if (not isinstance(repository,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',repository)
            or repository.lower()=='serhankeem/tourismnews'
            or not re.fullmatch('[a-f0-9]{40}',commit or '')
            or not re.fullmatch('[a-f0-9]{64}',manifest_hash or '')):
        fail('private_input_location_invalid')
    blob=private_blobs(api,repository,commit,('manifest.json',*NAMES))
    manifest_raw=blob('manifest.json')
    if tourgo.digest(manifest_raw)!=manifest_hash:fail('private_input_manifest_hash_mismatch')
    manifest=decode_json(manifest_raw)
    if not isinstance(manifest,dict) or set(manifest)!={'schema_version','profile','files'} or manifest.get('schema_version')!=1 or profile not in ('initial','update') or manifest.get('profile')!=profile:
        fail('private_input_manifest_invalid')
    expected=manifest['files']
    if not isinstance(expected,dict) or set(expected)!=set(NAMES) or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in expected.values()):
        fail('private_input_manifest_invalid')
    if profile=='initial' and any(expected[k+'.xls']!=v for k,v in INITIAL_HASHES.items()):fail('initial_original_hashes_required')
    output=Path(output).resolve()
    if output.exists() or output==ROOT or ROOT in output.parents:fail('new_private_temp_directory_required')
    output.mkdir(mode=0o700,parents=True)
    try:
        for name in NAMES:
            raw=blob(name)
            if tourgo.digest(raw)!=expected[name]:fail('private_input_file_hash_mismatch')
            target=output/name;target.write_bytes(raw);target.chmod(0o600)
        # The receipt is never re-signed or regenerated during delivery.
        receipt=decode_json((output/'receipt.json').read_bytes())
        if receipt.get('profile')!=profile:fail('reviewed_receipt_profile_required')
        (output/'manifest.json').write_bytes(manifest_raw);(output/'manifest.json').chmod(0o600)
        return manifest
    except Exception:
        shutil.rmtree(output)
        raise


def request(directory, manifest_hash):
    directory=Path(directory)
    raw=(directory/'manifest.json').read_bytes()
    if tourgo.digest(raw)!=manifest_hash:fail('private_input_manifest_hash_mismatch')
    manifest=decode_json(raw)
    return ReleaseRequest(directory/'ledger.json',manifest['files']['ledger.json'],
        directory/'receipt.json',manifest['files']['receipt.json'],
        originals={k:directory/(k+'.xls') for k in INITIAL_HASHES})


def prepare(output,env=None,now=None,profile='initial'):
    env=os.environ if env is None else env
    now=now or dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    # Do not consume private repository data before checking actual activation.
    config,policy=read(ROOT/'macro_sources.json'),read(ROOT/'operating_policy.json')
    operating_configuration(config,policy,now)
    from .tourgo_activation import plan
    source=next(s for s in config['sources'] if s['id']==tourgo.SOURCE)
    approval={a:{k:source['approval'][a][k] for k in ('evidence_ref','valid_from','valid_until')} for a in ('collection','publication')}
    approval.update(terms_evidence_ref=source.get('activation_terms_evidence_ref'),conditions=source.get('activation_conditions'))
    if plan(config,policy,approval,now)!=config:fail('activation_configuration_requires_review')
    api=GitHub(env.get('TOURGO_INPUT_TOKEN'))
    protected_context(api,env)
    return fetch_inputs(api,env.get('TOURGO_INPUT_REPOSITORY'),env.get('TOURGO_INPUT_COMMIT'),env.get('TOURGO_MANIFEST_SHA256'),output,profile=profile)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--profile',choices=['initial','update'],default='initial');args=p.parse_args()
    try:
        prepare(args.output,profile=args.profile)
        print('tourgo_private_input_verified; publication_not_executed')
        return 0
    except Exception as exc:
        code=str(exc) if isinstance(exc,DeliveryError) else 'activation_or_private_input_invalid'
        print('tourgo_delivery_blocked: '+code)
        # Only fixed classification; no API exceptions, file paths or payloads.
        summary=os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary,'a') as f:f.write('## TOURGO manual publication\n\nBlocked: `'+code+'`. No publication executed.\n')
        return 1


if __name__=='__main__':raise SystemExit(main())
