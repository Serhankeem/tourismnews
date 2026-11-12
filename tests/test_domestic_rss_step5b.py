"""V4 Step 5-B: rights-held RSS expansion, dates, dedup and preservation."""
import copy
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.robotparser import RobotFileParser

from src import collector as c
from src.discovery import Loader, MAX_METADATA_BYTES, items_from
from src.engine import execute, permission, valid_date
from src.publication import PUBLIC_FIELDS
from src.relevance import assess

ROOT = Path(__file__).resolve().parents[1]
AT = dt.datetime(2026, 11, 12, 14, 45, tzinfo=c.KST)


def feed(title='대한항공, 인천~뉴어크 신규 취항', url='https://example.org/a', date=None):
    from src.discovery import feed_bytes
    return feed_bytes([{'title': title, 'link': url, 'pubDate': date or AT.isoformat(),
                        'description': 'UNLICENSED DESCRIPTION'}])


class DomesticRSSStep5BTests(unittest.TestCase):
    def test_32_distinct_candidates_discovery_only_and_existing_specialists_kept(self):
        sources = json.loads((ROOT/'sources.json').read_text())['sources']
        new = [s for s in sources if s.get('validation', {}).get('issue_url', '').endswith('6815838202')]
        self.assertEqual(len(new), 32)
        self.assertEqual(len({s['coverage']['publisher_id'] for s in new}), 32)
        self.assertEqual(len({s['id'] for s in sources}), len(sources))
        self.assertEqual(len({c.url_identity(s['url']) for s in sources}), len(sources))
        self.assertEqual({s['coverage']['media_type'] for s in new},
                         {'economic_news', 'general_news', 'regional_news', 'broadcast_news'})
        self.assertEqual([s['name'] for s in new[:3]], ['아주경제', '파이낸셜뉴스', '헤럴드경제'])
        for s in new:
            self.assertEqual(s['adapter'], 'rss')
            self.assertTrue(s['enabled'] and s['discovery_allowed'])
            self.assertTrue(s['url'].startswith('https://'))
            self.assertEqual(s['analysis_fields'], ['title'])
            self.assertFalse(s['reuse_excerpt'])
            self.assertFalse(permission(s))
            self.assertEqual(s['publication']['scope'], 'none')
            self.assertTrue(s['article_domains'])
        for sid in ('traveltimes', 'traveldaily', 'ttlnews'):
            old = next(s for s in sources if s['id'] == sid)
            self.assertTrue(old['enabled'] and permission(old))

    def test_dates_offsets_numeric_month_and_naive_domestic_clock(self):
        expected = dt.datetime(2026, 11, 12, 14, 43, 29, tzinfo=c.KST)
        for raw in ('Thu, 12 Nov 2026 14:43:29 +09:00',
                    'Thu, 12 Nov 2026 14:43:29 +0900',
                    'Thu, 12 Nov 2026 05:43:29 GMT',
                    '2026-11-12T05:43:29Z', '2026-11-12 14:43:29',
                    'Thu, 12 11 2026 14:43:29 +0900'):
            self.assertEqual(c.timestamp(raw), expected, raw)
        self.assertEqual(c.timestamp('2024.10.29'), dt.datetime(2024, 10, 29, tzinfo=c.KST))
        # No inferred minus-nine-hours correction for a publisher's explicit GMT.
        future = 'Thu, 12 Nov 2026 13:10:56 GMT'
        self.assertEqual(c.timestamp(future).hour, 22)
        self.assertIsNone(valid_date({'pubDate': future}, AT, 7))
        self.assertIsNone(valid_date({'pubDate': (AT+dt.timedelta(seconds=1)).isoformat()}, AT, 7))
        self.assertIsNone(valid_date({'pubDate': 'bad'}, AT, 7))
        self.assertIsNone(valid_date({'updated': AT.isoformat()}, AT, 7))

    def test_recent_seven_day_boundaries_respect_instants(self):
        cutoff = AT-dt.timedelta(days=7)
        self.assertIsNotNone(valid_date({'pubDate': cutoff.astimezone(dt.timezone.utc).isoformat()}, AT, 7))
        self.assertIsNone(valid_date({'pubDate': (cutoff-dt.timedelta(seconds=1)).isoformat()}, AT, 7))
        item = list(items_from({}, b'<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item><title>x</title><dc:date>2026-11-12 14:40:00</dc:date></item></channel></rss>'))[0]
        self.assertEqual(valid_date(item, AT, 7).hour, 14)

    def test_loader_accepts_aju_sized_feed_but_keeps_hard_limit(self):
        loader = Loader()
        rules = RobotFileParser(); rules.parse(['User-agent: *', 'Disallow:'])
        loader.rules['https://example.org'] = rules
        for size, valid in ((3*1024*1024, True), (MAX_METADATA_BYTES+1, False)):
            with patch.object(loader, '_open', return_value=io.BytesIO(b'x'*size)):
                if valid:
                    self.assertEqual(len(loader('https://example.org/rss')), size)
                else:
                    with self.assertRaisesRegex(ValueError, 'too_large'):
                        loader('https://example.org/rss')

    def test_direct_operating_news_and_incidental_venue_exclusions(self):
        for title in ('인천항 크루즈 방문객 20만명 돌파…개항 이후 최대실적',
                      '문체부, 방한 단체관광 쇼핑 수수료 손본다',
                      '목포 고하도, 체류형 관광섬 조성',
                      '관광공사, 관광벤처 투자 돕는다…데모데이 개최',
                      '울산시 관광재단 분리 추진',
                      'K관광…방한 외래객 2000만명 돌파',
                      '대한항공, 인천~뉴어크 신규 취항'):
            self.assertEqual(assess(title)['label'], 'Direct', title)
        self.assertEqual(assess('한류 콘서트로 외래관광객 증가')['label'], 'Indirect')
        for title in ('15세 소녀 숙박업소서 살해…진술 거부',
                      '관광객 불법촬영 사건',
                      '대한항공, 아라우조 활약에 배구 3연승',
                      '주말 여행 가볼 만한 곳',
                      '특가 여행상품 할인쿠폰'):
            self.assertEqual(assess(title)['label'], 'Irrelevant', title)

    def test_same_article_variants_dedup_but_independent_publishers_survive(self):
        source = {'id': 'one', 'name': 'one'}
        one = c.article_from_item({'title': '대한항공, 인천~뉴어크 신규 취항',
                                  'link': 'http://www.example.org/a?b=2&a=1', 'pubDate': AT.isoformat()}, source, AT)
        alias = {**one, 'url': 'https://example.org/a?a=1&b=2&utm_source=feed', 'related_sources': ['one']}
        independent = {**one, 'source_id': 'two', 'source': 'two', 'url': 'https://independent.org/a', 'related_sources': ['two']}
        self.assertEqual(len(c.deduplicate([one, alias, independent])), 2)

    def test_rights_held_discovery_keeps_public_data_and_legacy_ids(self):
        sources = [dict(id='legacy', name='기존', url='https://example.org/legacy', enabled=True,
                        publication=dict(status='approved', scope='metadata_only', terms_url='https://example.org/terms', basis='fixture')),
                   dict(id='new', name='신규', url='https://example.org/rss', enabled=True,
                        analysis_fields=['title'], publication=dict(status='review', scope='none'))]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp);data=p/'site';state=p/'state'
            execute(sources[:1], data, state, at=AT, loader=lambda _: feed(), providers=[])
            old = json.loads((state/'archive.json').read_text())['articles'][0]
            before = {f.name:f.read_bytes() for f in data.glob('*.json') if f.stem in ('news','newsroom','research','filings','briefing')}
            for name in ('reports', 'macro'):
                (data/(name+'.json')).write_text('{"preserve":true}')
            def load(url):
                if url.endswith('legacy'):
                    raise OSError('existing feeds outside this isolated test scope')
                return feed(url='http://www.example.org/a?utm_source=rss')
            summary = execute(sources, data, state, at=AT, loader=load, providers=[])
            self.assertEqual(summary['new_newsroom_items'], 0)
            for name, raw in before.items():
                self.assertEqual((data/name).read_bytes(), raw)
            for name in ('reports','macro'):
                self.assertEqual((data/(name+'.json')).read_text(), '{"preserve":true}')
            archive = json.loads((state/'archive.json').read_text())['articles']
            self.assertEqual(archive, [old])
            ledger = json.loads((state/'discovery.json').read_text())['candidates']
            self.assertEqual(list(ledger), [old['id']])
            self.assertEqual(ledger[old['id']]['url'], old['url'])
            self.assertEqual(summary['sources'][1]['duplicates'], 1)
            for record in json.loads((data/'newsroom.json').read_text())['articles']:
                self.assertEqual(set(record), set(PUBLIC_FIELDS))

    def test_future_dates_held_in_health_and_new_titles_not_persisted(self):
        s = dict(id='new', name='신규', url='https://example.org/rss', enabled=True,
                 publication=dict(status='review', scope='none'))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            summary=execute([s],p/'data',p/'state',at=AT,
                            loader=lambda _:feed(date=(AT+dt.timedelta(minutes=1)).isoformat()),providers=[])
            self.assertEqual(summary['sources'][0]['future_date_holds'],1)
            self.assertEqual(summary['sources'][0]['news_conversion_last7d']['observed_unique'],0)
            summary=execute([s],p/'data',p/'state',at=AT,loader=lambda _:feed(),providers=[])
            row=next(iter(json.loads((p/'state/discovery.json').read_text())['candidates'].values()))
            self.assertEqual(row['publication_status'],'rights_hold')
            self.assertIsNone(row['title']);self.assertTrue(row['title_sha256'])
            self.assertEqual(summary['new_auto_published'],0)


if __name__ == '__main__':
    unittest.main()
