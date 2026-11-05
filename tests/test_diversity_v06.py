"""Artificial headlines/transport are isolated; no operational data writes."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from src import collector as c
from src.diversity import article_domain_allowed, publisher_diversity, provenance
from src.engine import execute
from test_collector import AT, feed
from test_discovery_v03 import source


class DiversityTests(unittest.TestCase):
    def test_exact_origin_host_not_suffix_or_relay(self):
        cfg = {'article_domains': ['publisher.example', 'www.publisher.example']}
        for url in ['https://publisher.example/a', 'http://www.publisher.example/a']:
            self.assertTrue(article_domain_allowed(cfg, url))
        for url in ['https://publisher.example.evil/a', 'https://evil.publisher.example/a',
                    'https://publisher.example@evil.example/a', 'https://user@publisher.example/a',
                    'https://relay.example/a', 'javascript:publisher.example']:
            self.assertFalse(article_domain_allowed(cfg, url), url)
        self.assertTrue(article_domain_allowed({}, 'https://unmapped.example/a'))
        self.assertFalse(article_domain_allowed({'article_domains': []}, 'https://publisher.example/a'))

    def test_domain_hold_preserves_stored_ids_and_original_date(self):
        cfg = source(article_domains=['example.org'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            execute([cfg], root/'data', root/'state', at=AT,
                    loader=lambda _: feed('한국 관광산업 지원 정책 발표', link='https://example.org/a'))
            old = json.loads((root/'state/archive.json').read_text())['articles'][0]
            result = execute([cfg], root/'data', root/'state', at=AT + dt.timedelta(hours=2),
                    loader=lambda _: feed('한국 관광산업 지원 정책 발표', link='https://relay.example/a'))
            self.assertEqual(result['sources'][0]['attribution_holds'], 1)
            self.assertEqual(result['sources'][0]['news_conversion_last7d']['observed_unique'], 0)
            stored = json.loads((root/'state/archive.json').read_text())['articles']
            self.assertEqual(len(stored), 1)
            for key in ['id', 'url', 'published_at', 'first_discovered_at', 'first_published_by_engine_at']:
                self.assertEqual(stored[0][key], old[key])

    def test_conversion_is_unique_current_cohort_not_cumulative_stock(self):
        cfg = source()
        data = feed('한국 관광산업 지원 정책 발표')
        # The same URL twice is two feed observations but one conversion candidate.
        data = data.replace(b'</channel>', data[data.index(b'<item>'):data.index(b'</item>')+7]+b'</channel>')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = execute([cfg], root/'data', root/'state', at=AT, loader=lambda _: data)
            row = first['sources'][0]['news_conversion_last7d']
            self.assertEqual((row['observed_unique'], row['industry_candidates'], row['approved_candidates'],
                              row['public_observed_candidates'], row['new_public_candidates']), (1, 1, 1, 1, 1))
            again = execute([cfg], root/'data', root/'state', at=AT, loader=lambda _: data)
            self.assertEqual(again['sources'][0]['news_conversion_last7d']['new_public_candidates'], 0)
            self.assertEqual(again['sources'][0]['news_conversion_last7d']['public_observed_candidates'], 1)
            empty = execute([cfg], root/'data', root/'state', at=AT,
                            loader=lambda _: b'<rss><channel/></rss>')
            self.assertEqual(empty['sources'][0]['news_conversion_last7d']['industry_candidates'], 0)
            self.assertIsNone(empty['sources'][0]['news_conversion_last7d']['candidate_to_public'])
            self.assertEqual(empty['newsroom_count'], 1)

    def test_review_is_not_approval_or_publication_and_failure_is_unknown(self):
        cfg = source(publication={'status': 'review'})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = execute([cfg], root/'data', root/'state', at=AT,
                             loader=lambda _: feed('한국 관광산업 지원 정책 발표'))
            row = result['sources'][0]['news_conversion_last7d']
            self.assertEqual((row['industry_candidates'], row['rights_held_unique'],
                              row['approved_candidates'], row['public_observed_candidates']), (1, 1, 0, 0))
            def fail(_): raise OSError('isolated test outage')
            failed = execute([cfg], root/'data', root/'state', at=AT, loader=fail)
            self.assertIsNone(failed['sources'][0]['news_conversion_last7d'])

    def test_indirect_without_approval_and_date_only_do_not_inflate_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = execute([source()], root/'data', root/'state', at=AT,
                             loader=lambda _: feed('태풍 때문에 인천 국제선 항공편 감편 증가'))
            row = result['sources'][0]['news_conversion_last7d']
            self.assertEqual(row['industry_candidates'], 1)
            self.assertEqual(row['approved_candidates'], 0)
            self.assertEqual(row['public_observed_candidates'], 0)
            date_only = feed('한국 관광산업 지원 정책 발표', pub=AT.date().isoformat())
            result = execute([source()], root/'data', root/'state', at=AT, loader=lambda _: date_only)
            self.assertEqual(result['sources'][0]['news_conversion_last7d']['observed_unique'], 0)

    def article(self, aid, sid, title='국내 관광산업 투자 확대 20%', **extra):
        return {'id': aid, 'source_id': sid, 'title': title, 'published_at': AT.isoformat(),
                'url': 'https://'+sid+'.example/'+aid, 'editorial': {'tier': 'reference'}, **extra}

    def test_multiple_feeds_are_one_publisher_not_korea_direct_evidence(self):
        sources = [{'id': sid, 'coverage': {'publisher_jurisdiction': 'KR', 'publisher_id': 'one'}}
                   for sid in ['feed1', 'feed2']]
        articles = [self.article('a', 'feed1'), self.article('b', 'feed2')]
        result = publisher_diversity(articles, sources, AT)
        self.assertEqual(result['domestic_publishers'], 1)
        self.assertEqual(result['news_by_publisher'], {'one': 2})
        self.assertEqual(result['korea_direct_news_last7d'], 0)
        self.assertEqual(result['provenance']['possible_shared_headline_pairs'], [])
        self.assertEqual(articles[0].keys(), self.article('a', 'feed1').keys())

    def test_identical_titles_only_signal_possible_shared_material(self):
        articles = [self.article('a', 'one'), self.article('b', 'two')]
        result = provenance(articles)
        self.assertEqual(len(result['possible_shared_headline_pairs']), 1)
        self.assertEqual(result['independent_reporting_verified'], 0)
        self.assertEqual(result['possible_shared_headline_pairs'][0]['original_reporting'], 'unverified')
        self.assertEqual(result['unknown_origin_news'], 2)
        self.assertEqual(len(articles), 2)

    def test_numbers_and_time_prevent_false_shared_headline_signal(self):
        articles = [self.article('a', 'one'), self.article('b', 'two', title='국내 관광산업 투자 확대 30%')]
        self.assertEqual(provenance(articles)['possible_shared_headline_pairs'], [])
        articles[1] = self.article('b', 'two', published_at=(AT-dt.timedelta(days=4)).isoformat())
        self.assertEqual(provenance(articles)['possible_shared_headline_pairs'], [])

    def test_different_headlines_do_not_prove_original_reporting(self):
        articles = [self.article('a', 'one'), self.article('b', 'two', title='서울 호텔 객실 공급 35% 증가')]
        result = provenance(articles)
        self.assertEqual(result['independent_reporting_verified'], 0)
        self.assertEqual(result['unknown_origin_news'], 2)
        articles[1]['title'] = '[보도자료] 서울 호텔 객실 공급 35% 증가'
        self.assertEqual(provenance(articles)['declared_distribution_news'], 1)

    def test_legacy_domain_bindings_cover_frozen_archive_without_rights_changes(self):
        sources = json.loads((c.ROOT/'sources.json').read_text())['sources']
        cfg = {s['id']: s for s in sources}
        archive = json.loads((c.ROOT/'collector_state/archive.json').read_text())['articles']
        self.assertTrue(all(article_domain_allowed(cfg[a['source_id']], a['url']) for a in archive))
        self.assertEqual(cfg['hotelnewsresource']['publication']['status'], 'review')


if __name__ == '__main__':
    unittest.main()
