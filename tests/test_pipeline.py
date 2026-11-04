"""Real layouts and ephemeral bare Git remotes. Never production refs/Pages."""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from src import collector as c
from src.pipeline.layout import ROOT, CONTROL, configuration, copy_data, hashes, files, read
from src.pipeline.validation import validate
from src.pipeline.store import Store, StoreError, Conflict, git
from src.pipeline.runner import transact, compose, require_main
from src.pipeline.schedule import slots,pending
from src.pipeline.policy import project,verify_public

AT=c.timestamp('2026-11-04T13:30:00+09:00')

class PipelineHarness(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.code=self.root/'code';self.code.mkdir();self.remote=self.root/'remote.git'
  git(self.root,'init','--bare',str(self.remote));git(self.code,'init','-b','main')
  git(self.code,'config','user.name','Pipeline Test');git(self.code,'config','user.email','test@example.invalid')
  shutil.copytree(ROOT/'site',self.code/'site');shutil.copytree(ROOT/'collector_state',self.code/'collector_state')
  for name in ['pipeline.json','sources.json','reports_sources.json','macro_sources.json','operating_policy.json','relevance_reviews.json']:shutil.copyfile(ROOT/name,self.code/name)
  git(self.code,'add','.');git(self.code,'commit','-m','Seed main');git(self.code,'remote','add','origin',str(self.remote));git(self.code,'push','origin','main')
  self.main=git(self.code,'rev-parse','HEAD').stdout.strip();self.cfg=configuration(self.code);self.counts=validate(self.code,self.cfg);self.at=max(AT,c.timestamp(read(self.code/'site/data/health.json')['last_successful_fetch']))
 def run_pipeline(self,collector=lambda *a:True,requested='none',force=False):
  work=self.root/('run-'+str(len(list(self.root.glob('run-*')))))
  return transact(self.code,str(self.remote),work,self.root/'pages',requested,force,collector=collector,at=self.at)
 def change(self,engine,stage,force,days):
  name={'news':'site/data/health.json','reports':'site/data/reports_health.json','macro':'site/data/macro_health.json'}[engine]
  data=read(stage/name);data['pipeline_test_marker']=engine;c.write_atomic(stage/name,data);return True
 def reader(self):
  path=self.root/('read-'+str(len(list(self.root.glob('read-*')))))
  store=Store(path,str(self.remote),self.cfg);self.assertFalse(store.load(self.code,self.main));return store

class PipelineTests(PipelineHarness):
 def test_bootstrap_orphan_preserves_hashes_and_main_and_private_boundary(self):
  result=self.run_pipeline();self.assertTrue(result['bootstrap']);self.assertTrue(result['ready'])
  store=self.reader();self.assertEqual(hashes(store.path,files(self.cfg)),hashes(self.code,files(self.cfg)))
  self.assertEqual(store.tip('main'),self.main)
  names=git(store.path,'ls-tree','-r','--name-only','HEAD').stdout.splitlines();self.assertEqual(set(names),set(files(self.cfg)+['control.json','.data-manifest.json']))
  self.assertNotIn('src/engine.py',names);self.assertFalse((self.root/'pages/collector_state').exists())
  self.assertEqual(len(git(store.path,'rev-list','--parents','HEAD').stdout.splitlines()),1)
 def test_sequential_owned_updates_restore_all_other_data_and_noop(self):
  self.run_pipeline(self.change)
  initial=self.reader();first=hashes(initial.path,files(self.cfg));sha=initial.base
  self.run_pipeline(lambda *a:True,requested='news')
  again=self.reader();self.assertEqual(again.base,sha)
  def reports(engine,stage,*_):
   self.assertEqual(engine,'reports');self.assertEqual(read(stage/'site/data/health.json')['pipeline_test_marker'],'news')
   h=read(stage/'site/data/reports_health.json');h['version_test']=2;c.write_atomic(stage/'site/data/reports_health.json',h);return True
  self.run_pipeline(reports,requested='reports');last=self.reader()
  for p,h in first.items():
   if p!='site/data/reports_health.json':self.assertEqual(hashes(last.path,[p])[p],h)
  self.assertEqual(last.tip('main'),self.main)
 def test_existing_branch_never_reseeds_from_stale_main(self):
  self.run_pipeline(self.change);(self.code/'site/data/news.json').write_text('corrupt seed unused')
  self.assertTrue(self.run_pipeline(requested='macro')['ready'])
 def test_failed_collection_keeps_data_but_can_persist_health(self):
  self.run_pipeline()
  before=self.reader();archive=(before.path/'collector_state/archive.json').read_bytes()
  def fail(engine,stage,*_):
   h=read(stage/'site/data/health.json');h['status']='failed';c.write_atomic(stage/'site/data/health.json',h);return False
  r=self.run_pipeline(fail,requested='news');self.assertFalse(r['collection_ok']);self.assertTrue(r['ready']);self.assertEqual((self.reader().path/'collector_state/archive.json').read_bytes(),archive)
 def test_partial_corruption_and_cross_engine_write_roll_back(self):
  self.run_pipeline();baseline=self.reader();h=hashes(baseline.path,files(self.cfg))
  for corrupt in [False,True]:
   def bad(engine,stage,*_):
    if corrupt:(stage/'collector_state/archive.json').write_text('{broken')
    else:(stage/'site/data/reports_health.json').write_text('{}')
    return True
   r=self.run_pipeline(bad,requested='news');self.assertFalse(r['collection_ok']);self.assertEqual(hashes(self.reader().path,files(self.cfg)),h)
 def test_lost_records_fail_validation(self):
  stage=self.root/'stage';copy_data(self.code,stage,self.cfg)
  doc=read(stage/'collector_state/archive.json');doc['articles'].pop();c.write_atomic(stage/'collector_state/archive.json',doc)
  with self.assertRaises(ValueError):validate(stage,self.cfg,before=self.code)
 def test_corrupt_existing_snapshot_does_not_bootstrap(self):
  self.run_pipeline();writer=self.reader();(writer.path/'site/data/news.json').write_text('{}');git(writer.path,'add','.');git(writer.path,'commit','-m','Synthetic corruption');git(writer.path,'push','origin','HEAD:refs/heads/data/live')
  with self.assertRaises(StoreError):self.run_pipeline()
 def test_competing_remote_write_retries_from_latest_state(self):
  self.run_pipeline();calls=[]
  def conflict(engine,stage,*_):
   calls.append(engine)
   if len(calls)==1:
    other=self.reader();backup=self.root/'other-before';copy_data(other.path,backup,self.cfg)
    stage_other=self.root/'other-stage';copy_data(other.path,stage_other,self.cfg);shutil.copyfile(other.path/CONTROL,stage_other/CONTROL)
    d=read(stage_other/'site/data/reports_health.json');d['concurrent_test']='retained';c.write_atomic(stage_other/'site/data/reports_health.json',d)
    other.commit(stage_other,self.main,backup)
   else:self.assertEqual(read(stage/'site/data/reports_health.json')['concurrent_test'],'retained')
   return self.change(engine,stage,False,90)
  r=self.run_pipeline(conflict,requested='news');self.assertEqual(r['attempt'],2);self.assertEqual(len(calls),2)
 def test_rejected_push_never_prepares_new_pages(self):
  self.run_pipeline();old=(self.root/'pages/data/news.json').read_bytes()
  hook=self.remote/'hooks/pre-receive';hook.write_text('#!/bin/sh\nexit 1\n');hook.chmod(0o755)
  with self.assertRaises(StoreError):self.run_pipeline(self.change,requested='news')
  self.assertEqual((self.root/'pages/data/news.json').read_bytes(),old)
 def test_main_change_mid_collection_aborts_without_data_overwrite(self):
  self.run_pipeline();before=self.reader().base
  def changed(*_):
   (self.code/'new-code.txt').write_text('new code');git(self.code,'add','.');git(self.code,'commit','-m','New main code');git(self.code,'push','origin','main');return True
  with self.assertRaisesRegex(StoreError,'main_changed'):self.run_pipeline(changed,requested='news')
  self.assertEqual(self.reader().base,before)
 def test_review_hides_stored_records_on_non_news_run_and_restores(self):
  self.run_pipeline();old=read(self.code/'sources.json');cfg=copy.deepcopy(old);target=next(s for s in cfg['sources'] if s['id']=='traveltimes');target['publication']['status']='review';c.write_atomic(self.code/'sources.json',cfg)
  git(self.code,'add','sources.json');git(self.code,'commit','-m','Rights hold');git(self.code,'push','origin','main');self.main=git(self.code,'rev-parse','HEAD').stdout.strip()
  self.run_pipeline(requested='macro');store=self.reader();news=read(store.path/'site/data/newsroom.json')['articles'];self.assertFalse(any(a['source']=='여행신문' for a in news));self.assertEqual(read(store.path/'collector_state/archive.json')['count'],self.counts['archive'])
  self.assertEqual((store.path/'site/data/briefing_archive.json').read_bytes(),(self.code/'site/data/briefing_archive.json').read_bytes())
  c.write_atomic(self.code/'sources.json',old);git(self.code,'add','.');git(self.code,'commit','-m','Rights restore');git(self.code,'push','origin','main');self.main=git(self.code,'rev-parse','HEAD').stdout.strip()
  self.run_pipeline(requested='macro');self.assertTrue(any(a['source']=='여행신문' for a in read(self.reader().path/'site/data/newsroom.json')['articles']))
 def test_pages_failure_can_recompose_from_persisted_snapshot(self):
  self.run_pipeline();store=self.reader();original=hashes(store.path,files(self.cfg));output=self.root/'restored'
  with patch('src.pipeline.runner.shutil.copytree',side_effect=OSError('Synthetic artifact error')):
   with self.assertRaises(OSError):compose(self.code,store.path,output,self.cfg)
  compose(self.code,store.path,output,self.cfg);self.assertEqual(hashes(store.path,files(self.cfg)),original)
  self.assertEqual((output/'data/news.json').read_bytes(),(store.path/'site/data/news.json').read_bytes())
 def test_invalid_seed_cannot_create_a_branch(self):
  (self.code/'collector_state/archive.json').unlink()
  with self.assertRaises(ValueError):self.run_pipeline()
  self.assertEqual(git(self.code,'ls-remote','origin','refs/heads/data/live').stdout,'')
 def test_branch_target_and_pr_guard(self):
  cfg={**self.cfg,'branch':'main'}
  with self.assertRaises(StoreError):Store(self.root/'bad',str(self.remote),cfg)
  with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REF':'refs/pull/19/merge','GITHUB_EVENT_NAME':'pull_request'}):
   with self.assertRaises(StoreError):require_main()
 def test_policy_is_rechecked_after_collection_and_day_change_blocks_deploy(self):
  from src.pipeline.runner import main
  before=c.timestamp('2026-11-04T23:59:00+09:00');after=c.timestamp('2026-11-05T00:01:00+09:00')
  work=self.root/'midnight'
  with patch('src.pipeline.runner.now_kst',side_effect=[before,after]):
   result=transact(self.code,str(self.remote),work,self.root/'pages',collector=lambda *a:True)
  self.assertEqual(read(work/'deployment.json')['policy_evaluated_on'],'2026-11-05')
  c.write_atomic(work/'result.json',result)
  with patch('src.pipeline.runner.ROOT',self.code),patch('src.pipeline.runner.now_kst',return_value=before),patch.dict(os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'push'}),patch('sys.argv',['runner','guard','--work',str(work)]):
   self.assertEqual(main(),1)
  failed=read(work/'result.json');self.assertEqual(failed['error'],'policy_day_changed_retry_before_deploy');self.assertEqual(failed['data_commit'],result['data_commit']);self.assertFalse(failed['ready'])
 def test_real_engine_fixture_repeat_and_other_engine_failures_preserve_data(self):
  from src.engine import execute
  from src.reports.engine import collect as reports_collect
  from src.macro.engine import collect as macro_collect
  def offline(*a,**k):raise OSError('isolated fixture transport')
  def collect(engine,stage,*_):
   data,state=stage/'site/data',stage/'collector_state'
   if engine=='news':
    sources=read(self.code/'sources.json')['sources'];url=next(s['url'] for s in sources if s['id']=='traveltimes')
    def feed(u):
     if u!=url:return offline()
     return ('<rss><channel><item><title>한국 관광산업 지원 정책 발표</title><link>https://example.invalid/pipeline-fixture-only</link><pubDate>'+self.at.isoformat()+'</pubDate></item></channel></rss>').encode()
    result=execute(sources,data,state,at=self.at,loader=feed)
    self.assertEqual(result['newsroom_count'],self.counts['news']+1)
    return result['publication_result']!='failed'
   if engine=='reports':
    reports_collect(read(self.code/'reports_sources.json')['sources'],data,state,at=self.at,loader_factory=lambda *a,**k:offline)
   else:macro_collect(read(self.code/'macro_sources.json'),data,state,now=self.at,loader=offline)
   return False
  self.run_pipeline(collect);first=self.reader();news=read(first.path/'site/data/newsroom.json')['articles']
  self.run_pipeline(collect,requested='news');second=self.reader();self.assertEqual(read(second.path/'site/data/newsroom.json')['articles'],news)
  self.assertEqual(read(second.path/'site/data/reports.json')['count'],self.counts['reports'])
  self.assertEqual(len(read(second.path/'collector_state/archive.json')['articles']),self.counts['archive']+1)
  self.assertEqual(second.tip('main'),self.main)

class DueTests(unittest.TestCase):
 def test_kst_cadence_and_replaced_pending_work_catchup(self):
  now=c.timestamp('2026-11-09T13:00:00+09:00');s=slots(now)
  self.assertEqual(c.timestamp(s['reports']).strftime('%a %H:%M'),'Mon 07:40')
  self.assertEqual(c.timestamp(s['macro']).strftime('%H:%M'),'12:20')
  self.assertEqual(set(pending({'completed_slots':{}},now,'news')),{'news','reports','macro'})
  self.assertEqual(pending({'completed_slots':s},now),{})
  brief=slots(c.timestamp('2026-11-09T10:30:00+09:00'))['news'];self.assertEqual(c.timestamp(brief).strftime('%H:%M'),'10:30')
 def test_failed_slot_not_acknowledged_is_retried(self):
  now=c.timestamp('2026-11-09T13:00:00+09:00');s=slots(now);del s['reports']
  self.assertIn('reports',pending({'completed_slots':s},now,'news'))
