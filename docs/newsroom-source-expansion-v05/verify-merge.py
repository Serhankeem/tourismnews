"""One-off audit at this merge snapshot; not a scheduled, frozen-data test."""
import hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src import collector as c
P=json.loads((ROOT/'docs/newsroom-source-expansion-v05/MERGE-PRESERVATION.json').read_text())
R=lambda p:json.loads((ROOT/p).read_text())
class MergeAudit(unittest.TestCase):
 def test_record_identities_and_original_28_grades(self):
  rows={a['id']:a for a in R('collector_state/archive.json')['articles']}
  for side,old in P['article_identities'].items():
   for aid,a in old.items():self.assertEqual({k:rows[aid][k] for k in a},a)
  for aid in P['original_28_korea_ids']:self.assertEqual(rows[aid]['editorial']['tier'],'korea_direct')
  self.assertEqual(len(rows),P['archived']);self.assertEqual(len(P['pr_extra_article_ids']),7)
  self.assertFalse(any(a['source']=='Hotel News Resource' for a in R('site/data/newsroom.json')['articles']))
 def test_discovery_observations_and_clocks(self):
  rows=R('collector_state/discovery.json')['candidates'];clocks={(e['id'],e['field']):e for e in P['field_observations'] if e['field'] in ['last_seen_at','first_discovered_at']}
  for side,hashes in P['discovery_observation_hashes'].items():
   for aid,expected in hashes.items():
    v={k:rows[aid].get(k) for k in ['url','published_at','last_seen_at']}
    if (aid,'last_seen_at') in clocks:v['last_seen_at']=clocks[aid,'last_seen_at'][side]
    self.assertEqual(hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest(),expected)
  for (aid,k),e in clocks.items():self.assertEqual(rows[aid][k],(min if k=='first_discovered_at' else max)(e['pr'],e['main'],key=c.timestamp))
 def test_rights_events_and_counter_deltas(self):
  rows=R('collector_state/publication_visibility.json')['records']
  for side,records in P['visibility_transition_events'].items():
   for aid,events in records.items():self.assertTrue(all(e in rows[aid]['transitions'] for e in events))
  held=[r for r in rows.values() if r['source_id']=='hotelnewsresource'];self.assertEqual(len(held),3);self.assertTrue(all(r['status']=='rights_hold' and r['policy_status']=='review' for r in held))
  for sid,row in R('collector_state/source_metrics.json')['sources'].items():
   b,o,t=[P['source_metrics_inputs'][s]['sources'].get(sid,{}) for s in ['base','pr','main']]
   for k in ['attempts','successes']:self.assertEqual(row[k],o.get(k,0)+t.get(k,0)-b.get(k,0))
   for k,v in row['errors'].items():self.assertEqual(v,o.get('errors',{}).get(k,0)+t.get('errors',{}).get(k,0)-b.get('errors',{}).get(k,0))
 def test_latest_real_run_and_derived_projection(self):
  h=R('site/data/health.json');s=h['discovery'];self.assertEqual(h['checked_at'],P['latest_fetch']);self.assertEqual(h['last_successful_fetch'],P['latest_fetch']);self.assertEqual(h['sources'],P['main_health_sources']);self.assertEqual(s['sources'],P['main_sources']);self.assertEqual(s,R('collector_state/run_summary.json'));self.assertEqual(s['newsroom_korea_direct_count'],P['korea_direct']);self.assertEqual(s['newsroom_count'],P['public_news']);self.assertEqual(hashlib.sha256((ROOT/'collector_state/decisions.json').read_bytes()).hexdigest(),P['main_decisions_sha256'])
 def test_protected_files_and_confirmed_archive(self):
  for path,expected in P['unchanged_protected_files'].items():self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),expected,path)
if __name__=='__main__':unittest.main()
