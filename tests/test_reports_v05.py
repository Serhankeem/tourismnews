"""Synthetic HTML and temporary state only. Never seeds the public DB."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.reports import engine
from src.reports.adapters import discover,verify
from src.reports.model import classify,parse_date
from src.reports.transport import CatalogLoader
from src.discovery import AccessBlocked
from test_reports import source,loader_for,catalog,landing,CATALOG,URL,AT

O='https://www.oecd.org/en/publications/'
K='https://www.koti.re.kr/user/bbs/'
def osource():return source(id='oecd',name='OECD',adapter='oecd',allowed_hosts=['www.oecd.org'],catalog_urls=[O+'series.html'])
def opage(year='2026',date='2026/06/30',doi='synthetic-2026'):
 title='OECD Tourism Trends and Policies '+year
 return f'<meta name="template" content="report-summary-page"><meta name="citation_title" content="{title}"><meta property="og:title" content="{title}"><meta name="citation_doi" content="https://doi.org/10.1787/{doi}"><meta name="citation_publication_date" content="{date}"><meta name="citation_author" content="OECD"><meta name="citation_publisher" content="OECD Publishing"><time itemprop="datePublished" datetime="{date.replace(chr(47),chr(45))}"></time><p>PROTECTED_ABSTRACT_NEVER_STORE</p>'.encode()
def ksource():return source(id='koti',name='Synthetic Transport Institute',region='국내',adapter='koti',requires_kogl=True,allowed_hosts=['www.koti.re.kr'],catalog_urls=[K+'bassRsrchReprtList.do'])
def kcatalog():return f'<div class="comm_pagination"></div><a class="txt" href="{K}bassRsrchReprtView.do?bbs_no=1234567890&pg=1"><p class="title">항공 여객시장 분석 연구</p></a>'.encode()
def kpage(date='2026.06.30',license=True):return ('<div class="view_detail_top"><div class="view_detail_top-title"><strong class="title">항공 여객시장 분석 연구</strong></div><ul><li><em>발간일</em><p>'+date+'</p></li><li><em>저자</em><p>인공 테스트 저자</p></li></ul><button onclick="commonFileDownload(123)">원문 다운로드</button></div>'+('<div class="kogl"><img src="/res/img/img_nuri_4.jpg"></div>' if license else '')+'<p>PROTECTED_BODY_NEVER_STORE</p>').encode()

class ReportsV05Tests(unittest.TestCase):
 def test_oecd_requires_bibliographic_date_doi_publisher_crosscheck(self):
  s=osource();c={'url':O+'oecd-tourism-trends-and-policies-2026_synthetic-2026.html'}
  r=verify(s,c,opage());self.assertEqual(r['published_at'],'2026-06-30');self.assertEqual(r['doi'],'https://doi.org/10.1787/synthetic-2026')
  for before,after in [(b'citation_publication_date',b'modified_date'),(b'citation_doi',b'not_doi'),(b'OECD Publishing',b'Third Party'),(b'datetime="2026-06-30"',b'datetime="2026-06-29"')]:
   with self.assertRaises(ValueError):verify(s,c,opage().replace(before,after))
 def test_koti_labeled_date_authors_and_individual_rights(self):
  c={'title':'항공 여객시장 분석 연구','url':K+'bassRsrchReprtView.do?bbs_no=1234567890'}
  r=verify(ksource(),c,kpage());self.assertEqual(r['date_kind'],'official_publication');self.assertEqual(r['kogl_type'],4)
  for payload in [kpage(license=False),kpage().replace('발간일'.encode(),'등록일'.encode()),kpage().replace('저자'.encode(),'작성자'.encode())]:
   with self.assertRaises(ValueError):verify(ksource(),c,payload)
 def test_koti_catalog_ignores_nonresearch_and_uses_stable_id(self):
  s=ksource();body=kcatalog()+f'<a class="txt" href="{K}bassRsrchReprtView.do?bbs_no=2"><p class="title">도로 화물 물류 분석</p></a><a href="{K}noticeView.do?bbs_no=3">항공 행사 안내</a>'.encode()
  rows=list(discover(s,lambda url,form=None:body));self.assertEqual(len(rows),1);self.assertEqual(rows[0]['provider_id'],'1234567890');self.assertNotIn('pg=',rows[0]['url'])
 def test_oecd_series_keeps_editions_not_chapters(self):
  s=osource();urls=[O+f'oecd-tourism-trends-and-policies-{y}_synthetic-{y}.html' for y in [2024,2026]]
  body=(''.join(f'<a href="{u}">Test edition</a>' for u in urls)+'<a href="'+O+'press-release.html">Press</a>').encode()
  rows=list(discover(s,lambda u,form=None:body));self.assertEqual(len(rows),2);self.assertNotEqual(rows[0]['provider_id'],rows[1]['provider_id'])
 def test_contextual_mice_air_hotel_and_false_positives(self):
  cases={'International congress market analysis':'MICE·비즈니스 이벤트','Business events trends':'MICE·비즈니스 이벤트','국제회의시설업 정책연구':'MICE·비즈니스 이벤트','MICE산업 동향':'MICE·비즈니스 이벤트','항공 여객시장 연구':'항공·교통산업','Airport passenger demand outlook':'항공·교통산업','Airlines and airports market outlook':'항공·교통산업','Hotels and accommodations outlook':'숙박·호텔산업','Short term rental market trends':'숙박·호텔산업','야영장 시설 제도 연구':'숙박·호텔산업','OECD Tourism Trends and Policies 2026':'관광정책·산업경제','Tourism market outlook 2026':'관광시장 전망·트렌드'}
  for title,expected in cases.items():self.assertEqual(classify(title,source(),{'url':URL})['category'],expected)
  for title in ['Meeting expectations in tourism recovery','Eventual recovery of travel','Convention on biological diversity','Retail travel market trends','Congress approves tourism policy']:
   category=classify(title,source(),{'url':URL})['category'];self.assertNotEqual(category,'MICE·비즈니스 이벤트');self.assertNotEqual(category,'항공·교통산업')
 def test_year_and_registered_date_policy_preserved(self):
  self.assertEqual(parse_date('2024',AT.date())[:2],('2024','year'))
  cfg=json.loads((Path(__file__).resolve().parents[1]/'reports_sources.json').read_text());self.assertFalse(next(s for s in cfg['sources'] if s['id']=='yanolja')['allow_registered_date'])
 def test_new_source_publication_repetition_attribution_and_private_evidence(self):
  s=ksource();url=K+'bassRsrchReprtView.do?bbs_no=1234567890';mapping={s['catalog_urls'][0]:kcatalog(),url:kpage()};calls=[]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);run=lambda:engine.collect([s],p/'public',p/'state',at=AT,force=True,loader_factory=loader_for(mapping,calls))
   first=run();second=run();self.assertEqual(first['new_reports_this_run'],1);self.assertEqual(second['new_reports_this_run'],0);self.assertEqual(second['published_reports'],1)
   doc=json.loads((p/'public/reports.json').read_text());self.assertEqual(doc['attributions'][url]['kogl_type'],4);self.assertTrue(doc['attributions'][url]['authors']);self.assertEqual(first['stage_counts_this_run']['rights_reviewed'],1)
   self.assertTrue(first['by_publisher'][s['name']]['last_successful_collection'])
   from src.reports.report import render
   self.assertIn('Last success',render(first));self.assertIn('rights_reviewed',render(first))
   for path in p.rglob('*.json'):self.assertNotIn('PROTECTED_',path.read_text());self.assertNotIn('img_nuri',path.read_text())
   self.assertTrue(all(not u.endswith('.pdf') for u,f in calls))
 def test_rights_unknown_blocks_without_fetch(self):
  s=ksource();s['publication']['status']='review';calls=[]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=engine.collect([s],p/'public',p/'state',at=AT,loader_factory=loader_for({},calls));self.assertEqual(calls,[]);self.assertEqual(r['published_reports'],0)
 def test_selected_source_does_not_remove_other_institution(self):
  one=source();two=source(id='two',name='Other Synthetic Institute',catalog_urls=['https://reports.example/second/'])
  mapping={CATALOG:catalog(),URL:landing(),two['catalog_urls'][0]:catalog()}
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);engine.collect([one,two],p/'public',p/'state',at=AT,loader_factory=loader_for(mapping));before=json.loads((p/'public/reports.json').read_text())['reports'];calls=[]
   engine.collect([one,two],p/'public',p/'state',at=AT,force=True,only_sources=['example'],loader_factory=loader_for(mapping,calls));self.assertEqual(before,json.loads((p/'public/reports.json').read_text())['reports']);self.assertNotIn((two['catalog_urls'][0],None),calls)
 def test_binary_office_paths_and_content_rejected(self):
  loader=CatalogLoader(['www.oecd.org'])
  for suffix in ['pdf','xlsx','xls','docx','pptx','png','svg','zip']:
   with self.assertRaises(AccessBlocked):loader('https://www.oecd.org/file.'+suffix)
  with patch('src.discovery.Loader.__call__',return_value=b'PK\x03\x04FAKE_OFFICE'):
   with self.assertRaises(AccessBlocked):loader('https://www.oecd.org/ambiguous')
