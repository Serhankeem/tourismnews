"""Current source policy is authoritative, including failed fetches/restoration."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from src import collector as c
from src.engine import execute
from test_collector import AT, feed
from test_discovery_v03 import source

class VisibilityTests(unittest.TestCase):
 def setup_data(self,p):
  sources=[source(id='domestic',url='https://example.org/domestic'),source(id='target',url='https://example.org/target')]
  def load(url):return feed('한국 관광산업 지원정책 발표' if url.endswith('domestic') else '국제선 항공노선 확대',link=url+'/article')
  execute(sources,p/'data',p/'state',at=AT,loader=load)
  archive=json.loads((p/'state/archive.json').read_text())
  return sources,load,archive
 def test_review_revokes_existing_news_and_briefing_without_deleting_record(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);sources,load,before=self.setup_data(p);confirmed=(p/'data/briefing_archive.json').read_bytes()
   target=next(a for a in before['articles'] if a['source_id']=='target')
   sources[1]['publication']['status']='review'
   result=execute(sources,p/'data',p/'state',at=AT+dt.timedelta(hours=1),loader=load)
   after=json.loads((p/'state/archive.json').read_text());self.assertEqual(next(a for a in after['articles'] if a['id']==target['id']),target)
   self.assertEqual(len(after['articles']),2)
   for name,key in [('news','articles'),('newsroom','articles'),('briefing','items')]:
    self.assertTrue(all(a['url']!=target['url'] for a in json.loads((p/'data'/f'{name}.json').read_text())[key]))
   self.assertEqual((p/'data/briefing_archive.json').read_bytes(),confirmed)
   q=result['quality'];self.assertEqual(q['published_news_articles'],1);self.assertEqual(q['publishing_sources'],1);self.assertEqual(q['rights_held_news_count'],1)
   self.assertNotIn('target',q['news_by_source']);self.assertEqual(q['public_news_direct_ratio'],1)
 def test_all_failed_fetches_do_not_keep_revoked_records_public(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);sources,_,before=self.setup_data(p);raw=(p/'state/archive.json').read_bytes();sources[1]['publication']['status']='review'
   def offline(_):raise OSError('synthetic outage')
   result=execute(sources,p/'data',p/'state',at=AT+dt.timedelta(hours=1),loader=offline)
   self.assertEqual(result['publication_result'],'failed');self.assertEqual((p/'state/archive.json').read_bytes(),raw)
   self.assertEqual(json.loads((p/'data/newsroom.json').read_text())['count'],1)
   self.assertEqual(json.loads((p/'data/newsroom.json').read_text())['last_successful_fetch'],c.iso(AT))
   self.assertTrue(result['publication_visibility']['policy_reprojection'])
 def test_approval_restores_same_ids_dates_and_evidence_even_during_outage(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);sources,load,original=self.setup_data(p);target=next(a for a in original['articles'] if a['source_id']=='target')
   sources[1]['publication']['status']='review';execute(sources,p/'data',p/'state',at=AT+dt.timedelta(hours=1),loader=load)
   sources[1]['publication']['status']='approved'
   def offline(_):raise OSError('synthetic outage')
   r=execute(sources,p/'data',p/'state',at=AT+dt.timedelta(hours=2),loader=offline)
   self.assertEqual(r['new_newsroom_items'],0);self.assertEqual(r['newsroom_count'],2)
   current=json.loads((p/'state/archive.json').read_text())['articles'];self.assertEqual(next(a for a in current if a['id']==target['id']),target)
   record=json.loads((p/'state/publication_visibility.json').read_text())['records'][target['id']]
   self.assertEqual([e['to'] for e in record['transitions']],['public','rights_hold','public'])
   self.assertEqual(r['publication_visibility']['restored_this_run'],1)
   self.assertEqual(json.loads((p/'data/publication_visibility.json').read_text())['blocked_url_hashes'],[])
 def test_unchanged_outage_keeps_public_files_and_history_is_idempotent(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);sources,load,_=self.setup_data(p);sources[1]['publication']['status']='review';execute(sources,p/'data',p/'state',at=AT,loader=load)
   events=copy.deepcopy(json.loads((p/'state/publication_visibility.json').read_text())['records'])
   before={f.name:f.read_bytes() for f in (p/'data').glob('*.json') if f.name!='health.json'}
   def offline(_):raise OSError('synthetic outage')
   execute(sources,p/'data',p/'state',at=AT+dt.timedelta(hours=1),loader=offline)
   self.assertEqual(before,{f.name:f.read_bytes() for f in (p/'data').glob('*.json') if f.name!='health.json'})
   after=json.loads((p/'state/publication_visibility.json').read_text())['records']
   self.assertEqual({i:v['transitions'] for i,v in events.items()},{i:v['transitions'] for i,v in after.items()})
 def test_unknown_or_disabled_source_cannot_keep_existing_news_public(self):
  for change in ['missing','disabled']:
   with self.subTest(change=change),tempfile.TemporaryDirectory() as d:
    p=Path(d);sources,load,_=self.setup_data(p)
    if change=='missing':sources=sources[:1]
    else:sources[1]['enabled']=False
    r=execute(sources,p/'data',p/'state',at=AT,loader=load);self.assertEqual(r['newsroom_count'],1)
 def test_manifest_is_only_hashes_and_corrupt_history_not_erased(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);sources,load,before=self.setup_data(p);target=next(a for a in before['articles'] if a['source_id']=='target')
   path=p/'state/publication_visibility.json';path.write_text('{broken')
   sources[1]['publication']['status']='review';r=execute(sources,p/'data',p/'state',at=AT,loader=load)
   self.assertEqual(path.read_text(),'{broken');self.assertEqual(r['publication_visibility']['status'],'failed')
   self.assertEqual(r['newsroom_count'],1)
   manifest=(p/'data/publication_visibility.json').read_text();self.assertNotIn(target['url'],manifest);self.assertNotIn(target['title'],manifest)
   self.assertIn(hashlib.sha256(target['url'].encode()).hexdigest(),manifest)
