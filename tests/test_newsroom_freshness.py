"""Real Nov 2 metadata regression; synthetic boundary cases never touch public DB."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src import collector as c
from src.editorial import project, publication_order, exposure
from src.briefing import save, select
from src.engine import execute
from test_discovery_v03 import source
from test_collector import feed

AT=dt.datetime.fromisoformat('2026-11-02T11:59:00+09:00')
REAL=json.loads((Path(__file__).parent/'fixtures/newsroom-nov02.json').read_text())

class FreshnessTests(unittest.TestCase):
 def test_real_snapshot_reproduces_rank_bug_and_fixes_order(self):
  rows=REAL['articles'];_,news,_=project(rows)
  legacy=sorted(rows,key=lambda a:(a['editorial']['rank'],-c.timestamp(a['published_at']).timestamp()))
  self.assertIn('10-29',legacy[0]['published_at'])
  self.assertIn('11-02',news[0]['published_at'])
  self.assertEqual([a['published_at'] for a in rows],REAL['original_dates'])
  recent=[a for a in news if AT-dt.timedelta(hours=24)<=c.timestamp(a['published_at'])<=AT]
  self.assertEqual(len(recent),3)
  self.assertEqual([a['title'] for a in select(news,AT)[0]],['문광연, ‘지역관광개발 하반기 워크숍’ 개최'])
 def test_agency_evidence_does_not_promote_bare_domestic_publisher(self):
  for a in REAL['articles'][:3]:
   e=exposure(a)
   self.assertEqual(e['tier'],'korea_direct' if '문광연' in a['title'] else 'reference')
  self.assertEqual(exposure(dict(title='영국 지역관광개발 워크숍 개최',source_id='traveldaily',relevance_label='Direct'))['tier'],'reference')
  self.assertEqual(exposure(dict(title='문광연, 지역관광개발 하반기 워크숍과 무관',relevance_label='Direct'))['tier'],'reference')
 def test_timezones_ties_precision_and_invalid_dates(self):
  rows=[dict(url='b',published_at='2026-11-02T01:00:00+09:00'),dict(url='a',published_at='2026-11-01T16:00:00Z'),dict(url='c',published_at='2026-11-01T23:00:00+09:00'),dict(url='d',published_at='2026-11-02'),dict(url='x',published_at='invalid')]
  original=json.dumps(rows)
  self.assertEqual([a['url'] for a in sorted(rows,key=publication_order)],['a','b','d','c','x'])
  self.assertEqual(sorted(rows,key=publication_order),sorted(reversed(rows),key=publication_order))
  self.assertEqual(json.dumps(rows),original)
 def test_empty_reasons_and_partial_coverage_independent(self):
  _,news,_=project(REAL['articles'])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);partial={'sources':[{'status':'ok'},{'status':'error'}]}
   out=save(news[:2],p,p/'state',AT,None,collection=partial)
   self.assertEqual(out['status'],'no_eligible_recent_articles');self.assertEqual(out['recent_news_count'],2)
   self.assertEqual(out['collection']['status'],'partial')
   immutable=(p/'briefing_archive.json').read_bytes()
   out=save(news,p,p/'state',AT,None,collection=partial)
   self.assertEqual(out['status'],'candidates_ready');self.assertEqual(len(out['items']),1)
   self.assertEqual((p/'briefing_archive.json').read_bytes(),immutable)
   out=save([],p,p/'state',AT,None)
   self.assertEqual(out['status'],'no_recent_articles')
 def test_generation_failure_is_health_failure_not_empty(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);public=p/'public';state=p/'state';public.mkdir();previous=b'{"previous":"verified"}'
   (public/'briefing.json').write_bytes(previous)
   with patch('src.engine.save_briefing',side_effect=OSError('private details')):
    execute([source()],public,state,at=AT,loader=lambda _:feed('대한항공 매출 증가',AT.isoformat()))
   h=json.loads((public/'health.json').read_text())
   self.assertEqual(h['briefing']['status'],'failed')
   self.assertNotIn('private details',json.dumps(h))
   self.assertEqual((public/'briefing.json').read_bytes(),previous)
