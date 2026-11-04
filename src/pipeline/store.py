"""Normal fast-forward Git transactions. Never writes application refs."""
import json
import os
import base64
import shutil
import subprocess
from pathlib import Path
from .layout import MANIFEST, CONTROL, files, hashes, copy_data, read
from .validation import validate
from ..collector import write_atomic, now_kst, iso


class StoreError(RuntimeError):
    pass


class Conflict(StoreError):
    pass


def git(directory, *args, ok=(0,)):
    # Error output can contain remote credentials. Return a stable category only.
    env=os.environ.copy()
    token=env.get('PIPELINE_GITHUB_TOKEN')
    if token:
        index=int(env.get('GIT_CONFIG_COUNT','0'))
        env['GIT_CONFIG_COUNT']=str(index+1)
        env['GIT_CONFIG_KEY_'+str(index)]='http.https://github.com/.extraheader'
        env['GIT_CONFIG_VALUE_'+str(index)]='AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+token).encode()).decode()
    r = subprocess.run(['git',*args],cwd=directory,capture_output=True,text=True,env=env)
    if r.returncode not in ok:
        raise StoreError('git_operation_failed:'+args[0])
    return r


class Store:
    def __init__(self, path, remote, cfg):
        self.path, self.remote, self.cfg = Path(path), remote, cfg
        if cfg['branch'] != 'data/live':
            raise StoreError('ref_not_allowed')
        self.path.mkdir(parents=True,exist_ok=True)
        git(self.path,'init','-b','snapshot')
        git(self.path,'config','user.name','github-actions[bot]')
        git(self.path,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        git(self.path,'remote','add','origin',remote)
        self.base = None

    def tip(self, branch='data/live'):
        r=git(self.path,'ls-remote','--exit-code','origin','refs/heads/'+branch,ok=(0,2))
        return r.stdout.split()[0] if r.returncode==0 else None

    def load(self, seed, code_commit):
        self.base=self.tip()
        if self.base:
            git(self.path,'fetch','--no-tags','origin','refs/heads/data/live')
            git(self.path,'checkout','-B','snapshot','FETCH_HEAD')
            self.base=git(self.path,'rev-parse','HEAD').stdout.strip()
            allowed=set(files(self.cfg)+[MANIFEST,CONTROL])
            for line in git(self.path,'ls-tree','-r','HEAD').stdout.splitlines():
                mode,kind,tail=line.split(' ',2);_,name=tail.split('\t',1)
                if mode!='100644' or kind!='blob' or name not in allowed:
                    raise StoreError('unexpected_snapshot_tree_entry')
            manifest=read(self.path/MANIFEST)
            if manifest.get('schema_version')!=1 or manifest.get('files')!=hashes(self.path,files(self.cfg)+[CONTROL]):
                raise StoreError('snapshot_checksum_mismatch')
            validate(self.path,self.cfg)
            return False
        # Only an explicitly absent ref bootstraps. Network/auth errors abort.
        counts=validate(seed,self.cfg)
        copy_data(seed,self.path,self.cfg)
        write_atomic(self.path/CONTROL,{'schema_version':1,'initialized_from_main':code_commit,
                     'initialized_at':iso(now_kst()),'initial_counts':counts,
                     'initial_file_sha256':hashes(seed,files(self.cfg)),'completed_slots':{}})
        return True

    def commit(self, stage, code_commit, before):
        validate(stage,self.cfg,before=before)
        if self.tip()!=self.base:
            raise Conflict('remote_data_changed_retry_collection')
        for name in files(self.cfg)+[CONTROL]:
            src,dst=Path(stage)/name,self.path/name
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,dst)
        checksum=hashes(self.path,files(self.cfg)+[CONTROL])
        prior=read(self.path/MANIFEST) if (self.path/MANIFEST).exists() else {}
        if prior.get('files')==checksum and prior.get('policy_code_commit')==code_commit:
            return self.base,False
        write_atomic(self.path/MANIFEST,{'schema_version':1,'policy_code_commit':code_commit,'files':checksum})
        git(self.path,'add','--',*files(self.cfg),CONTROL,MANIFEST)
        git(self.path,'commit','-m','Persist validated collection state')
        commit=git(self.path,'rev-parse','HEAD').stdout.strip()
        # Normal push has server-side fast-forward protection even after tip().
        pushed=git(self.path,'push','origin','HEAD:refs/heads/data/live',ok=(0,1,128))
        if pushed.returncode:
            actual=self.tip()  # Also handles an interrupted acknowledgement.
            if actual==commit:
                return commit,True
            if actual!=self.base:
                raise Conflict('remote_data_changed_retry_collection')
            raise StoreError('data_push_failed_no_deployment')
        return commit,True
