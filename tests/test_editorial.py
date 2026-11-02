import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from src import collector as c
from src.editorial import exposure, project
from src.engine import execute
from test_collector import AT, SRC, feed
from test_discovery_v03 import source


def article(title, source_id='test', record_type='news'):
    result=c.article_from_item({'title':title,'link':'https://example.org/'+str(abs(hash(title))), 'pubDate':AT.isoformat()},SRC,AT)
    if result is None:
        result={'title':title,'relevance_label':'Direct','relevance_evidence':{'rules':[]},'published_at':AT.isoformat()}
    return {**result,'source_id':source_id,'record_type':record_type}


class EditorialTests(unittest.TestCase):
    def test_filings_are_preserved_but_not_in_newsroom(self):
        data=[article('대한항공 매출 증가'),article('Booking Holdings financial filing',record_type='regulatory_filing')]
        original=copy.deepcopy(data)
        stored,news,filings=project(data)
        self.assertEqual(data,original)
        self.assertEqual(len(stored),2)
        self.assertEqual(len(news),1)
        self.assertEqual(len(filings),1)
        self.assertEqual(filings[0]['record_type'],'regulatory_filing')

    def test_domestic_business_subject_has_evidence(self):
        result=exposure(article('대한항공 매출 증가'))
        self.assertEqual(result['tier'],'korea_direct')
        self.assertTrue(result['evidence'])

    def test_inbound_title_proves_korea_link(self):
        result=exposure(article('방한객 증가와 관광통계 발표'))
        self.assertEqual(result['tier'],'korea_direct')

    def test_official_local_tourism_has_contextual_proof(self):
        result=exposure(article('서울 웰니스 트래블 사업 운영',source_id='seoul_culture'))
        self.assertEqual(result['tier'],'korea_direct')

    def test_foreign_story_not_korean_merely_because_publisher_is_korean(self):
        result=exposure(article('영국 호텔업 매출 증가',source_id='seoul_economy'))
        self.assertEqual(result['tier'],'reference')
        self.assertEqual(result['korea_connection'],'not_established')

    def test_global_familiar_brand_does_not_prove_korea_link(self):
        result=exposure(article('Hilton Worldwide hotel revenue increases 10%'))
        self.assertEqual(result['tier'],'reference')

    def test_local_uk_industry_policy_is_reference_not_global_major(self):
        result=exposure(article('Stronger safeguards for disabled air passengers',source_id='govuk_aviation'))
        self.assertEqual(result['tier'],'reference')

    def test_explicit_quantified_worldwide_change_is_global_major(self):
        result=exposure(article('Global air passenger demand increases 7%'))
        self.assertEqual(result['tier'],'global_major')
        self.assertEqual(result['korea_connection'],'not_established')
        self.assertTrue(result['evidence'])

    def test_old_korea_priority_flag_is_not_editorial_evidence(self):
        data={**article('UK hotel revenue increases'),'korea_priority':True}
        self.assertEqual(exposure(data)['tier'],'reference')

    def test_north_korea_is_not_assumed_to_mean_south_korea(self):
        self.assertEqual(exposure(article('North Korean tourism revenue increases'))['tier'],'reference')

    def test_negated_korea_connection_is_not_promoted(self):
        self.assertEqual(exposure(article('Hotel revenue increase unrelated to South Korea'))['tier'],'reference')

    def test_publication_date_precedes_editorial_rank(self):
        core=article('방한객 증가');core['published_at']=(AT-dt.timedelta(days=3)).isoformat()
        foreign=article('UK airline revenue increases')
        _,news,_=project([foreign,core])
        self.assertEqual(news[0]['title'],foreign['title'])

    def test_ambiguous_worldwide_company_is_not_industry_scope(self):
        self.assertEqual(exposure(article('Marriott global company revenue increases 5%'))['tier'],'reference')

    def test_engine_exports_separate_views_and_news_only_metrics(self):
        sec={'cik':123,'name':'Booking Holdings','filings':{'recent':{'form':['10-Q'],'filingDate':['2026-10-25'],'accessionNumber':['000123-26-000001'],'primaryDocument':['report.htm']}}}
        sources=[source(),source(id='sec',url='https://example.org/sec',adapter='sec_submissions',cik='123')]
        def loader(url):return json.dumps(sec).encode() if url.endswith('/sec') else feed('대한항공 매출 증가')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            summary=execute(sources,root/'site',root/'state',at=AT,loader=loader)
            self.assertEqual(summary['total_archived'],2)
            self.assertEqual(summary['newsroom_count'],1)
            self.assertEqual(summary['filings_count'],1)
            self.assertEqual(summary['newsroom_korea_direct_count'],1)
            self.assertEqual(summary['newsroom_originally_published_last24h'],1)
            self.assertEqual(summary['new_newsroom_items'],1)
            self.assertEqual(summary['new_filings'],1)
            self.assertEqual(json.loads((root/'state/archive.json').read_text())['count'],2)
            self.assertEqual(json.loads((root/'site/news.json').read_text())['count'],1)
            self.assertEqual(json.loads((root/'site/newsroom.json').read_text())['count'],1)
            self.assertEqual(json.loads((root/'site/filings.json').read_text())['count'],1)
            self.assertTrue(all(set(a)=={'title','source','published_at','url','category','keywords'} for a in json.loads((root/'site/briefing.json').read_text())['items']))

    def test_reference_news_does_not_fill_daily_briefing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            execute([source()],root/'site',root/'state',at=AT,loader=lambda _:feed('UK hotel revenue increases'))
            self.assertEqual(json.loads((root/'site/newsroom.json').read_text())['count'],1)
            self.assertEqual(json.loads((root/'site/briefing.json').read_text())['items'],[])

    def test_failure_preserves_archive_and_all_public_projections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            execute([source()],root/'site',root/'state',at=AT,loader=lambda _:feed('대한항공 매출 증가'))
            files=[root/'state/archive.json']+[root/'site'/n for n in ('news.json','newsroom.json','filings.json','research.json','briefing.json')]
            before={p:p.read_bytes() for p in files}
            def fail(_):raise OSError('outage')
            execute([source()],root/'site',root/'state',at=AT,loader=fail)
            for path,expected in before.items():self.assertEqual(path.read_bytes(),expected)

    def test_korean_company_as_commentator_is_not_market_evidence(self):
        data=article('대한항공이 본 미국 항공사 매출 증가')
        self.assertEqual(exposure(data)['tier'],'reference')

    def test_expired_records_remain_archived_without_latest_news_exposure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'site').mkdir()
            past=AT-dt.timedelta(days=100)
            old=c.article_from_item({'title':'관광정책 발표','link':'https://example.org/old','pubDate':past.isoformat()},SRC,past)
            c.write_atomic(root/'site/news.json',{'mode':'live_rss','count':1,'articles':[old]})
            summary=execute([source()],root/'site',root/'state',at=AT,loader=lambda _:b'<rss><channel/></rss>')
            kept=json.loads((root/'state/archive.json').read_text())['articles'][0]
            self.assertEqual(kept['id'],old['id'])
            self.assertEqual(kept['published_at'],old['published_at'])
            self.assertTrue(kept['archived_only'])
            self.assertEqual(summary['total_archived'],1)
            self.assertEqual(summary['newsroom_count'],0)

    def test_foreign_brand_needs_explicit_local_operation_not_familiarity(self):
        self.assertEqual(exposure(article('Hilton opens a hotel in Seoul'))['tier'],'korea_direct')
        self.assertEqual(exposure(article('Hilton opens a hotel in London'))['tier'],'reference')

    def test_confirmed_indirect_impact_can_have_explicit_korea_link(self):
        data=article('환율 상승으로 방한 수요 감소')
        data.update(relevance_label='Indirect',relevance_evidence={'review_status':'approved'})
        self.assertEqual(exposure(data)['tier'],'korea_direct')
        data['relevance_evidence']={}
        self.assertEqual(exposure(data)['tier'],'reference')

    def test_legacy_live_cli_uses_rights_and_editorial_engine(self):
        from unittest.mock import patch
        with patch('sys.argv',['collector.py','--dir','/tmp/unused']),patch('src.engine.main',return_value=0) as entry:
            self.assertEqual(c.main(),0)
            entry.assert_called_once()

    def test_demo_cannot_overwrite_default_production_database(self):
        import contextlib,io
        from unittest.mock import patch
        with patch('sys.argv',['collector.py','--demo']),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):c.main()

    def test_corrupt_archive_is_not_replaced_by_news_only_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'site').mkdir()
            (root/'site/archive.json').write_bytes(b'invalid archive')
            c.write_atomic(root/'site/news.json',{'articles':[],'count':0})
            with self.assertRaises(ValueError):
                execute([source()],root/'site',root/'state',at=AT,loader=lambda _:feed('관광정책 발표'))
            self.assertEqual((root/'site/archive.json').read_bytes(),b'invalid archive')

    def test_kosis_statistics_timestamp_is_not_fresh_news(self):
        data=article('항공통계 (8)',source_id='kosis_recent')
        data['published_at']=AT.isoformat()
        stored,news,filings=project([data])
        self.assertEqual(len(stored),1)
        self.assertEqual(stored[0]['published_at'],AT.isoformat())
        self.assertEqual(stored[0]['record_type'],'statistical_release')
        self.assertFalse(stored[0]['publication_time_verified_for_news'])
        self.assertEqual(news,[])
        self.assertEqual(filings,[])


class StatisticsRegressionTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((c.ROOT/'fixtures/kosis-main-20261028.json').read_text())
        self.records = self.snapshot['articles']
        self.at = c.timestamp(self.snapshot['generated_at'])

    def test_latest_main_oct28_general_statistics_lose_news_labels(self):
        self.assertEqual({a['title'] for a in self.records if a['date']=='2026.10.28'},
                         {'전라남도완도군기본통계 ( 62 )','경기도양주시기본통계 ( 109 )'})
        before = copy.deepcopy(self.records)
        stored, news, filings = project(self.records)
        self.assertEqual(self.records, before)
        self.assertEqual(news, [])
        self.assertEqual(filings, [])
        self.assertEqual({a['id'] for a in stored}, {a['id'] for a in before})
        for record, original in zip(stored, before):
            self.assertEqual(record['record_type'], 'statistical_release')
            self.assertEqual(record['category'], '통계자료')
            self.assertEqual(record['relevance_label'], 'NotApplicable')
            self.assertEqual(record['relevance'], 0)
            self.assertEqual(record['editorial']['tier'], 'not_news')
            self.assertEqual(record['legacy_news_classification']['category'], original['category'])
            self.assertEqual(record['published_at'], original['published_at'])
            self.assertEqual(record['url'], original['url'])
        self.assertEqual(project(stored)[0], stored)  # migration is idempotent

    def test_new_general_dataset_does_not_use_description_as_news_evidence(self):
        src = source(id='kosis_recent', record_type='statistical_release')
        item = {'title':'경기도양주시기본통계 ( 109 )', 'link':'https://kosis.kr/data/yangju',
                'pubDate': self.at.isoformat(), 'description':'관광숙박 숙박업 관광객수 국제선'}
        article = c.article_from_item(item, src, at=self.at)
        self.assertEqual(article['record_type'], 'statistical_release')
        self.assertEqual(article['category'], '통계자료')
        self.assertEqual(article['relevance_label'], 'NotApplicable')
        self.assertEqual(article['relevance_evidence']['signals'], [])

    def test_live_pipeline_statistics_are_preserved_without_news_or_freshness(self):
        src = source(id='kosis_recent', record_type='statistical_release')
        payload = b'<?xml version="1.0"?><rss><channel></channel></rss>'
        from src.discovery import feed_bytes
        payload = feed_bytes([{'title':'일반지역기본통계', 'link':'https://kosis.kr/data/new',
                               'published':self.at.isoformat(), 'description':'관광숙박 숙박업 관광객수'}])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            c.write_atomic(root/'data/news.json', {'mode':'live_rss','articles':self.records,'count':len(self.records)})
            result=execute([src],root/'data',root/'state',at=self.at,loader=lambda _:payload)
            self.assertEqual(result['total_archived'],4)
            self.assertEqual(result['newsroom_count'],0)
            self.assertEqual(result['newsroom_korea_direct_count'],0)
            self.assertEqual(result['newsroom_originally_published_last24h'],0)
            self.assertEqual(result['originally_published_last24h'],0)
            self.assertEqual(result['other_research_count'],4)
            self.assertEqual(result['sources'][0]['classifications'],{'Direct':0,'Indirect':0,'Irrelevant':0})
            self.assertEqual(result['sources'][0]['statistical_records'],1)
            self.assertEqual(sum(result['category_counts'].values()),0)
            self.assertEqual(json.loads((root/'data/research.json').read_text())['count'],4)
            self.assertEqual(json.loads((root/'data/briefing.json').read_text())['items'],[])
            again=execute([src],root/'data',root/'state',at=self.at,loader=lambda _:payload)
            self.assertEqual(again['total_archived'],4)
            self.assertEqual(again['new_auto_published'],0)
            self.assertEqual(again['duplicate_observations'],1)

    def test_official_oct28_inbound_performance_is_not_foreign_reference(self):
        title='최휘영 장관, ‘역대 최대 외래관광객 달성’ 성과 및 ‘3천만‧4천만 명 시대 준비’ 역점 과제 공유'
        self.assertEqual(exposure(article(title, source_id='mcst_press'))['tier'], 'korea_direct')
        self.assertEqual(exposure(article('일본 외래관광객 역대 최대 달성', source_id='mcst_press'))['tier'], 'reference')

    def test_failed_legacy_statistics_run_preserves_bytes_but_not_false_news_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original={'mode':'live_rss','articles':self.records,'count':len(self.records)}
            c.write_atomic(root/'data/news.json',original)
            before=(root/'data/news.json').read_bytes()
            def fail(_):raise OSError('test outage')
            result=execute([source()],root/'data',root/'state',at=self.at,loader=fail)
            self.assertEqual(result['publication_result'],'failed')
            self.assertEqual(result['newsroom_count'],0)
            self.assertEqual(sum(result['category_counts'].values()),0)
            self.assertEqual((root/'data/news.json').read_bytes(),before)
            self.assertFalse((root/'data/archive.json').exists())
