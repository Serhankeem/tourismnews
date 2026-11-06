"""PR33: discovery-only domestic press feeds must not bypass publication gates.

Synthetic fixtures only; no network, production ledger, or public data writes.
"""
import json
import tempfile
import unittest
from pathlib import Path

from src import collector as c
from src.discovery import items_from
from src.engine import execute, permission


ROOT = Path(__file__).resolve().parents[1]
IDS = {"mss_press", "msit_press"}
URLS = {
    "mss_press": "https://mss.go.kr/rss/smba/board/86.do",
    "msit_press": "https://www.msit.go.kr/user/rss/rss.do?bbsSeqNo=94",
}


class DomesticPressPR33Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))["sources"]
        cls.new_sources = [s for s in cls.sources if s["id"] in IDS]

    def test_only_expected_two_feed_sources_added_with_explicit_rights_hold(self):
        self.assertEqual({s["id"] for s in self.new_sources}, IDS)
        self.assertEqual(len(self.new_sources), 2)
        self.assertEqual(len({s["id"] for s in self.sources}), len(self.sources))
        for s in self.new_sources:
            with self.subTest(source=s["id"]):
                self.assertEqual(s["url"], URLS[s["id"]])
                self.assertEqual(s["adapter"], "rss")
                self.assertTrue(s["enabled"])
                self.assertTrue(s["discovery_allowed"])
                self.assertEqual(s["analysis_fields"], ["title"])
                self.assertFalse(s["reuse_excerpt"])
                self.assertEqual(s["publication"]["status"], "review")
                self.assertEqual(s["publication"]["scope"], "none")
                self.assertFalse(permission(s))
                self.assertEqual(s["backfill"]["mode"], "provided_feed_only")
                self.assertTrue(s["publication"]["terms_url"].startswith("https://"))

    def test_synthetic_direct_headline_is_held_and_not_public(self):
        from test_collector import AT

        def feed_for(url):
            self.assertIn(url, set(URLS.values()))
            host = "mss.go.kr" if "mss.go.kr" in url else "www.msit.go.kr"
            feed = (
                "<rss version='2.0'><channel><item>"
                "<title>한국 관광산업 국제선 항공노선 확대</title>"
                f"<link>https://{host}/news/123</link>"
                f"<pubDate>{AT.isoformat()}</pubDate>"
                "<description>DO NOT REPUBLISH THIS DESCRIPTION</description>"
                "</item></channel></rss>"
            )
            return feed.encode("utf-8")

        for s in self.new_sources:
            self.assertEqual(len(list(items_from(s, feed_for(s["url"])))), 1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = execute(self.new_sources, root / "site", root / "state", at=AT, loader=feed_for)
            self.assertEqual(summary["new_auto_published"], 0)
            self.assertEqual(summary["new_newsroom_items"], 0)
            discovery = json.loads((root / "state" / "discovery.json").read_text(encoding="utf-8"))
            matching = [x for x in discovery["candidates"].values() if x.get("source_id") in IDS]
            self.assertEqual(len(matching), 2)
            for item in matching:
                self.assertEqual(item["publication_status"], "rights_hold")
                self.assertIsNone(item["title"])
                self.assertTrue(item.get("title_sha256"))
            for page in ("news", "newsroom", "briefing"):
                doc = json.loads((root / "site" / f"{page}.json").read_text(encoding="utf-8"))
                self.assertNotIn("DO NOT REPUBLISH", json.dumps(doc, ensure_ascii=False))
                self.assertNotIn("국제선 항공노선 확대", json.dumps(doc, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
