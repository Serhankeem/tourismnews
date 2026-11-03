"""Title-bound domestic policy evidence, without changing publication rights."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from src import collector as c
from src.editorial import exposure, project
from src.relevance import assess
from src.briefing import select, save
from src.coverage import coverage
from src.engine import permission
from src.visibility import PublicationGate

ROOT = Path(__file__).resolve().parents[1]
TITLES = (
    '“MICE 예산 줄어드는데”…국회·업계, 지속적 투자 촉구',
    '가업상속공제 축소 우려에 관광업계 12개 단체 공동 대응',
    '중앙회, 가업상속공제 대상 관광업종 유지 촉구',
)


def article(title, source_id='unknown'):
    a = assess(title)
    return {'title': title, 'source_id': source_id, 'relevance_label': a['label'], 'relevance_evidence': a}


class PolicyEditorialTests(unittest.TestCase):
    def test_three_real_headlines_use_title_evidence_not_publisher(self):
        for title in TITLES:
            for sid in ('traveltimes', 'traveldaily', 'unknown_foreign_publisher'):
                result = exposure(article(title, sid))
                self.assertEqual(result['tier'], 'korea_direct', title)
                self.assertTrue(any(e['field'] == 'title' and e['rule'].startswith('korean_') for e in result['evidence']))

    def test_foreign_and_general_tax_budget_counterexamples(self):
        for title in (
            '일본 국회·업계, MICE 예산 줄어드는데 지속적 투자 촉구',
            '미국 관광업계, 가업상속공제 축소에 공동 대응',
            '해외 가업상속공제 대상 관광업종 유지 촉구',
            '영국 관광업종 가업상속공제 유지 촉구',
            '프랑스 국회·업계, MICE 예산 축소 대응',
            '관광업계, 각국 가업상속공제 축소 비교 대응',
            '국회, 일반 상속세 개편 논의',
            '중앙회, 가업상속공제 대상 제조업종 유지 촉구',
            'MICE 예산 축소, 업계 투자 촉구',
            '국회·업계, 반도체 예산 축소에 투자 촉구',
        ):
            self.assertNotEqual(exposure(article(title, 'traveltimes'))['tier'], 'korea_direct', title)

    def test_ota_ai_is_not_inferred_b2b_or_korean_scope(self):
        title = '아고다, AI 어시스턴트 도입'
        a = assess(title)
        self.assertEqual(a['rules'], ['ota_operating_technology_change'])
        self.assertIn('ai어시스턴트', a['signals'][0]['terms'])
        self.assertFalse(any('b2b' in t.lower() for t in a['signals'][0]['terms']))
        self.assertIn('추정하지 않습니다', a['reason'])
        self.assertEqual(exposure(article(title, 'traveldaily'))['tier'], 'reference')
        for title in ('하나투어, B2B 서비스 출시', '야놀자, B2B 플랫폼 도입'):
            self.assertEqual(assess(title)['rules'], ['ota_operating_technology_change'])

    def test_reference_label_is_geographically_neutral(self):
        result = exposure(article('아고다, AI 어시스턴트 도입', 'traveldaily'))
        self.assertEqual(result['label'], '산업 참고 자료')
        self.assertIn('국내·해외', result['reason'])

    def test_real_records_briefing_windows_kpi_and_confirmed_archive(self):
        archive = c.read_json(ROOT/'collector_state/archive.json', {})['articles']
        sources = c.read_json(ROOT/'sources.json', {})['sources']
        gate = PublicationGate(sources, permission, ROOT/'site/data')
        _, news, _, _ = gate.views(archive)
        targets = [a for a in news if a['title'] in TITLES]
        self.assertEqual(len(targets), 3)
        self.assertTrue(all(a['editorial']['tier'] == 'korea_direct' for a in targets))
        self.assertTrue(all(a.get('korea_priority') is True for a in targets))
        for a in targets:
            selected, _ = select([a], c.timestamp(a['published_at']) + dt.timedelta(hours=6))
            self.assertEqual([b['id'] for b in selected], [a['id']])
        at = c.timestamp('2026-11-03T15:13:02+09:00')
        self.assertEqual(select(targets, at)[0], [])  # No stale news to fill five.
        q = coverage(news, sources, at, news)
        self.assertGreaterEqual(q['domestic_korea_direct_news_count'], 28)
        self.assertGreaterEqual(q['domestic_korea_direct_news_last7d'], 21)
        held = next(a for a in archive if a.get('source_id') == 'hotelnewsresource')
        held = {**held, **article(TITLES[0], 'hotelnewsresource')}
        self.assertEqual(gate.views([held])[1], [])
        original = (ROOT/'site/data/briefing_archive.json').read_bytes()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d);p.mkdir(exist_ok=True)
            (p/'briefing_archive.json').write_bytes(original)
            save(news, p, p/'state', at, '2026-11-03T15:13:02+09:00')
            self.assertEqual((p/'briefing_archive.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
