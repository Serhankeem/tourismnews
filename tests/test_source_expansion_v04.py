"""Artificial transport/metadata cases stay in temporary test directories."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request
from src import collector as c
from src.discovery import Loader, AccessBlocked, items_from
from src.engine import execute
from src.relevance import assess
from test_collector import AT, SRC, feed
from test_discovery_v03 import source

class ExpansionTests(unittest.TestCase):
 def test_identical_independent_headlines_from_two_publishers_survive(self):
  item={'title':'방한 외래관광객 증가 및 관광수요 발표','link':'https://example.org/a','pubDate':AT.isoformat()}
  a=c.article_from_item(item,SRC,AT)
  b=c.article_from_item({**item,'link':'https://other.org/b'},{**SRC,'id':'other','name':'다른 언론'},AT)
  self.assertEqual(len(c.deduplicate([a,b])),2)
  self.assertEqual(len(c.deduplicate([a,{**b,'url':a['url']}])),1)
 def test_numbers_and_independent_analysis_not_fuzzy_merged(self):
  a=c.article_from_item({'title':'방한 외래관광객 10% 증가 분석','link':'https://example.org/a','pubDate':AT.isoformat()},SRC,AT)
  b={**a,'url':'https://other.org/b','source_id':'other','source':'other','title':'방한 외래관광객 10% 증가 분석, 소비 회복은 지연'}
  self.assertEqual(len(c.deduplicate([a,b])),2)
 def test_generic_hospitality_and_promotions_not_news(self):
  for title in ['How to Use Hotel Market Segmentation to Boost Revenue','Behind the moments: Our biggest lessons in hospitality','Hotel deals: discount coupons for holiday stays','General economic news and celebrity concert','A fatal road accident on the highway']:
   self.assertEqual(assess(title)['label'],'Irrelevant',title)
  self.assertEqual(assess('Accor & Corinthia Group launch strategic collaboration to bring Verdi Hotels to Handwritten Collection')['label'],'Direct')
  self.assertEqual(assess('Oil prices increase and affect travel demand')['label'],'Indirect')
 def test_rss_gmt_and_atom_offsets_preserve_instant(self):
  rss=b'<rss><channel><item><title>Hotel revenue increases</title><link>https://example.org/a</link><pubDate>Tue, 03 Nov 2026 02:28:00 GMT</pubDate></item></channel></rss>'
  atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Hotel revenue increases</title><link href="https://example.org/a"/><published>2026-11-03T11:28:00+09:00</published></entry></feed>'
  one=list(items_from({},rss))[0];two=list(items_from({},atom))[0]
  self.assertEqual(c.timestamp(one['pubDate']),c.timestamp(two['published']))
 def test_quality_counts_distinguish_configuration_discovery_publication(self):
  sources=[source(id='one'),source(id='held',url='https://example.org/held',publication={'status':'review'}),source(id='disabled',enabled=False)]
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);r=execute(sources,root/'data',root/'state',at=AT,loader=lambda _:feed('국제선 항공노선 확대'))
   from src.report import render
   self.assertIn('configured_sources',render(r));self.assertIn('classified_news_feed_observations',render(r))
   q=r['quality'];self.assertEqual((q['configured_sources'],q['attempted_sources'],q['successful_sources'],q['publication_approved_sources'],q['publishing_sources']),(3,2,2,1,1))
   self.assertEqual(q['direct_ratio'],1);self.assertEqual(q['top3_source_share'],1)
   again=execute(sources,root/'data',root/'state',at=AT+dt.timedelta(hours=2),loader=lambda _:feed('국제선 항공노선 확대'))
   self.assertEqual(again['quality']['new_news_articles'],0);self.assertEqual(again['quality']['duplicate_ratio'],1)
 def test_new_source_failure_isolated_and_existing_records_kept(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);s=source();execute([s],p/'data',p/'state',at=AT,loader=lambda _:feed('국제선 항공노선 확대'))
   before=json.loads((p/'data/newsroom.json').read_text())['articles']
   def fetch(url):
    if url.endswith('/failed'):raise OSError('synthetic timeout')
    return feed('국제선 항공노선 확대')
   r=execute([s,source(id='new',url='https://example.org/failed')],p/'data',p/'state',at=AT,loader=fetch)
   self.assertEqual(r['quality']['successful_sources'],1);self.assertEqual(r['quality']['failed_sources'][0]['id'],'new')
   self.assertEqual(json.loads((p/'data/newsroom.json').read_text())['articles'],before)
 def test_empty_success_is_not_failure(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=execute([source()],p/'data',p/'state',at=AT,loader=lambda _:b'<rss><channel/></rss>')
   self.assertEqual(r['quality']['successful_sources'],1);self.assertEqual(r['quality']['publishing_sources'],0)
   self.assertIsNone(r['quality']['direct_ratio']);self.assertEqual(r['sources'][0]['outcome'],'no_new_candidate')
 def test_transient_retry_bounded_and_denial_never_retried(self):
  req=Request('https://example.org/rss');loader=Loader()
  for status,calls in [(403,1),(429,1),(503,2)]:
   err=HTTPError(req.full_url,status,'error',{},None)
   with patch.object(loader.opener,'open',side_effect=err) as op,patch('src.discovery.time.sleep'):
    with self.assertRaises(HTTPError):loader._open(req)
    self.assertEqual(op.call_count,calls)
 def test_long_retry_after_deferred_not_ignored(self):
  req=Request('https://example.org/rss');loader=Loader()
  with patch.object(loader.opener,'open',side_effect=HTTPError(req.full_url,503,'busy',{'Retry-After':'120'},None)) as op:
   with self.assertRaises(AccessBlocked):loader._open(req)
   self.assertEqual(op.call_count,1)

 def test_retry_respects_existing_crawl_delay(self):
  req=Request('https://example.org/rss');loader=Loader()
  err=HTTPError(req.full_url,503,'busy',{},None)
  with patch.object(loader.opener,'open',side_effect=err),patch('src.discovery.time.sleep') as sleep:
   with self.assertRaises(HTTPError):loader._open(req,retry_delay=4)
   sleep.assert_called_once_with(4)
