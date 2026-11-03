"""Review the six real PR #17 records without writing the public database."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from src.publication import public_record, keywords, TERMS
from src.relevance import matches
from src.editorial import exposure
from src.briefing import select
from src.engine import permission, execute
from src import collector as c
from test_discovery_v03 import source
from test_collector import feed, AT
ROOT=Path(__file__).resolve().parents[1]
PROOF=json.loads((ROOT/'docs/newsroom-source-expansion-v04/comparison.json').read_text())
SIX=PROOF['new_articles']
ARCHIVE=json.loads((ROOT/'collector_state/archive.json').read_text())['articles']
class ReviewTests(unittest.TestCase):
 def test_all_six_have_literal_industry_keywords_and_six_fields(self):
  for a in SIX:
   r=public_record(a);self.assertEqual(len(r),6);self.assertTrue(r['keywords'],a['title'])
   for k in r['keywords']:self.assertIn(k,a['title'])
   for key in ['title','source','published_at','url','category']:self.assertEqual(r[key],a[key])
 def test_boundaries_case_and_no_generic_financial_or_ai_tags(self):
  self.assertEqual(keywords('Tourism Policy announcement for OTA agencies'),['Tourism Policy','OTA'])
  self.assertEqual(keywords('GLOBAL AIR PASSENGER DEMAND FALLS 0.5%'),['AIR PASSENGER DEMAND'])
  self.assertEqual(keywords('Hotelier Chairman: new AI platform drives revenue and growth'),[])
  self.assertEqual(keywords('An independent booking decision and ExpediaGroupish name'),[])
  self.assertEqual(keywords('Grand Hyatt opens; HYATT expands'),['Grand Hyatt','HYATT'])
 def test_korean_headlines_unchanged_against_previous_extractor(self):
  rows=[a for a in ARCHIVE if re.search('[가-힣]',a['title'])]
  self.assertGreaterEqual(len(rows),40)
  for a in rows:
   old=sorted(set(matches(a['title'],TERMS)),key=lambda s:(-len(s),s))[:8]
   self.assertEqual(keywords(a['title']),old,a['title'])
 def test_real_six_tiers_unchanged_and_direct_not_equal_to_global_major(self):
  original_urls={a['url'] for a in SIX}
  records=[a for a in ARCHIVE if a['url'] in original_urls]
  self.assertEqual(len(records),6)
  for a in records:
   tier=exposure(a)['tier'];self.assertEqual(tier,a['editorial']['tier'])
   self.assertEqual(a['relevance_label'],'Direct')
   self.assertEqual(tier,'global_major' if 'Global Air Passenger Demand' in a['title'] else 'reference')
  at=c.timestamp(PROOF['comparison_at']);chosen,_=select(records,at)
  self.assertEqual(len(chosen),1);self.assertIn('Global Air Passenger Demand',chosen[0]['title'])
  from src.visibility import PublicationGate
  sources=json.loads((ROOT/'sources.json').read_text())['sources']
  gate=PublicationGate(sources,permission,ROOT/'site/data')
  _,permitted,_,_=gate.views(records)
  self.assertEqual(select(permitted,at)[0],[])
 def test_company_scale_or_local_opening_does_not_prove_worldwide_change(self):
  for title in ['Hilton Worldwide opens a hotel in Doha','Marriott global company revenue increases 5%','Hyatt hotel revenue increases 20%','IHG opens 100 hotels in Qatar']:
   self.assertEqual(exposure({'title':title,'relevance_label':'Direct'})['tier'],'reference')
 def test_actual_config_distinguishes_local_feed_review_and_unresolved_rights(self):
  sources={s['id']:s for s in json.loads((ROOT/'sources.json').read_text())['sources']}
  hn=sources['hospitalitynet'];hrn=sources['hotelnewsresource']
  self.assertTrue(permission(hn));self.assertFalse(permission(hrn))
  for s in [hn,hrn]:self.assertFalse(s['publication']['publisher_written_permission_obtained'])
  self.assertIn('Info-legal.html',hrn['publication']['rights_review']['general_terms_url'])
 def test_review_gate_stops_new_records_without_deleting_previous(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);approved=source()
   execute([approved],p/'data',p/'state',at=AT,loader=lambda _:feed('국제선 항공노선 확대'))
   before=json.loads((p/'data/newsroom.json').read_text())['articles']
   held=source(publication={'status':'review'})
   result=execute([held],p/'data',p/'state',at=AT,loader=lambda _:feed('호텔업 매출 증가 발표',link='https://example.org/new-held'))
   self.assertEqual(result['new_newsroom_items'],0)
   self.assertEqual(json.loads((p/'data/newsroom.json').read_text())['articles'],[])
   self.assertTrue(any(a['url']==before[0]['url'] for a in json.loads((p/'state/archive.json').read_text())['articles']))
