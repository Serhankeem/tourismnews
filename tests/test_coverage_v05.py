"""Real headline regressions; artificial transport data stays in temp dirs."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from src import collector as c
from src.coverage import coverage
from src.editorial import exposure
from src.engine import execute
from src.relevance import assess
from src.publication import keywords
from test_collector import AT, feed
from test_discovery_v03 import source


class KoreaCoverageTests(unittest.TestCase):
    def test_real_operating_and_policy_headlines(self):
        cases = {
            '“MICE 예산 줄어드는데”…국회·업계, 지속적 투자 촉구': '여행산업',
            '가업상속공제 축소 우려에 관광업계 12개 단체 공동 대응': '관광정책',
            '중앙회, 가업상속공제 대상 관광업종 유지 촉구': '관광정책',
            '서울시, ‘의료친화 숙박시설’ 19개소 선정': '항공·숙박',
            '제주-싱가포르, 운항 확대에도 탑승률 85%대 진입': '항공·숙박',
            '창립 85주년 맞은 필리핀항공, 인천~마닐라 주 17회 증편… 차세대 A350-1000 투입': '항공·숙박',
            '아고다, AI 어시스턴트 도입': '여행산업',
        }
        for title, category in cases.items():
            with self.subTest(title=title):
                a = assess(title)
                self.assertEqual((a['label'], a['category']), ('Direct', category))
                self.assertTrue(a['signals'][0]['terms'])
                self.assertEqual(a['signals'][0]['field'], 'title')
                self.assertTrue(keywords(title))
                self.assertTrue(all(word in title for word in keywords(title)))

    def test_no_industry_broadening_for_promotions_or_generic_ai(self):
        for title in [
            '하나투어, ‘겨울여행 페스타’ 오픈',
            '노랑풍선, 겨울 캄보디아 여행상품 출시',
            '호텔스닷컴, 스카이패스 마일리지 3배 적립 혜택',
            '하나증권, 퇴직연금 ETF 적립식 매수 서비스 개시',
            '일반 기업 AI 어시스턴트 도입', '서울시, 의료시설 19개소 선정',
            '지역 축제 MICE 포토존 오픈', '일반 기업 가업상속공제 유지 촉구',
        ]:
            self.assertEqual(assess(title)['decision'], 'exclude', title)
        self.assertEqual(assess('태풍 때문에 인천 국제선 항공편 감편 증가')['label'], 'Indirect')

    def test_domestic_connection_is_not_publisher_country(self):
        for title, expected in [
            ('서울시, ‘의료친화 숙박시설’ 19개소 선정', 'korea_direct'),
            ('제주-싱가포르, 운항 확대에도 탑승률 85%대 진입', 'korea_direct'),
            ('아고다, AI 어시스턴트 도입', 'reference'),
            ('런던, 의료친화 숙박시설 19개소 선정', 'reference'),
        ]:
            a = assess(title)
            self.assertEqual(exposure({'title': title, 'source_id': 'traveldaily',
                'relevance_label': a['label'], 'relevance_evidence': a})['tier'], expected)

    def test_gated_coverage_outage_restoration_and_repeat(self):
        sources = [source(id='one'), source(id='held', url='https://example.org/held')]
        for s in sources:
            s['coverage'] = {'publisher_jurisdiction': 'KR', 'media_type': 'tourism_specialist',
                             'publisher': s['id'], 'supply_route': 'shared_api'}
        def load(url):
            return feed('한국 관광산업 지원정책 발표', link=url + '/article')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            first = execute(sources, p/'data', p/'state', at=AT, loader=load)
            q = first['quality']['domestic_coverage']
            self.assertEqual(q['domestic_publishing_sources'], 2)
            self.assertEqual(q['domestic_supply_routes'], 1)
            self.assertEqual(q['domestic_identified_publishers'], 2)
            self.assertEqual(q['new_domestic_publishing_sources'], ['held', 'one'])
            again = execute(sources, p/'data', p/'state', at=AT, loader=load)
            self.assertEqual(again['new_newsroom_items'], 0)
            self.assertEqual(again['quality']['domestic_coverage']['new_domestic_publishing_sources'], [])
            sources[1]['publication']['status'] = 'review'
            def offline(_): raise OSError('artificial offline')
            failed = execute(sources, p/'data', p/'state', at=AT, loader=offline)
            self.assertEqual(failed['quality']['domestic_coverage']['domestic_publisher_news_count'], 1)
            self.assertEqual(len(json.loads((p/'state/archive.json').read_text())['articles']), 2)
            sources[1]['publication']['status'] = 'approved'
            restored = execute(sources, p/'data', p/'state', at=AT, loader=offline)
            self.assertEqual(restored['quality']['domestic_coverage']['domestic_publisher_news_count'], 2)
            self.assertEqual(restored['new_newsroom_items'], 0)

    def test_date_only_unverified_and_foreign_are_not_domestic_recent_news(self):
        records = [{'source_id': 'one', 'category': '경제·시장', 'published_at': AT.isoformat(),
                    'editorial': {'tier': 'reference'}}]
        sources = [{'id': 'one', 'coverage': {'publisher_jurisdiction': 'KR'}}]
        for extra, expected in [({}, 1), ({'date_precision': 'date'}, 0),
                                ({'publication_time_verified_for_news': False}, 0),
                                ({'published_at': 'invalid'}, 0),
                                ({'published_at': (AT+dt.timedelta(days=1)).isoformat()}, 0)]:
            q = coverage([{**records[0], **extra}], sources, AT)
            self.assertEqual(q['domestic_publisher_news_last7d'], expected)
            self.assertEqual(q['domestic_korea_direct_news_last7d'], 0)
        q = coverage(records, [], AT)
        self.assertEqual(q['domestic_publishing_sources'], 0)
        self.assertEqual(q['unclassified_publisher_news_count'], 1)
        self.assertIsNone(q['domestic_top3_source_share'])


if __name__ == '__main__':
    unittest.main()
