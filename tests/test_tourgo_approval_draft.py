"""The TOURGO owner-review draft must fail closed; it is not an operational grant."""
import json
import unittest
from pathlib import Path

from src.macro.tourgo_activation import plan
from src.macro.tourgo_release import ROOT
from src.pipeline.layout import read

FOLDER = ROOT / "docs/tourgo-activation-owner-review"


class TourgoOwnerApprovalDraftTests(unittest.TestCase):
    def test_draft_cannot_be_accepted_as_an_activation_approval(self):
        draft = json.loads((FOLDER / "approval.DRAFT.json").read_text())
        config = read(ROOT / "macro_sources.json")
        policy = read(ROOT / "operating_policy.json")
        import datetime as dt
        now = dt.datetime(2026, 11, 10, tzinfo=dt.timezone(dt.timedelta(hours=9)))
        with self.assertRaises((ValueError, TypeError, KeyError)):
            plan(config, policy, draft, now)

    def test_collection_only_grant_is_finite_and_publication_remains_off(self):
        cfg = read(ROOT / "macro_sources.json")
        src = next(s for s in cfg["sources"] if s["id"] == "tourgo_tourism_balance")
        self.assertFalse(src["enabled"])
        collection = src["approval"]["collection"]
        self.assertTrue(collection["approved"])
        self.assertEqual(collection["scope"], "general_travel_monthly")
        self.assertEqual(collection["evidence_ref"], "owner-collection-20261110-tourgo69m")
        self.assertEqual(collection["valid_from"], "2026-11-10")
        self.assertEqual(collection["valid_until"], "2027-02-08")
        self.assertFalse(src["approval"]["publication"]["approved"])
        for id_ in ("kto_tourism_receipts", "kto_tourism_expenditure"):
            item = next(x for x in cfg["indicators"] if x["id"] == id_)
            self.assertFalse(item["enabled"])
            self.assertNotEqual(item["source_id"], "tourgo_tourism_balance")
        self.assertFalse(any(s["enabled"] for s in cfg["sources"] if s["id"].startswith("ecos_")))

    def test_draft_uses_pending_dates_and_distinct_unapproved_references(self):
        draft = json.loads((FOLDER / "approval.DRAFT.json").read_text())
        self.assertEqual(draft["collection"]["valid_from"], "YYYY-MM-DD")
        self.assertEqual(draft["publication"]["valid_until"], "YYYY-MM-DD")
        refs = [draft["terms_evidence_ref"], draft["collection"]["evidence_ref"], draft["publication"]["evidence_ref"]]
        self.assertEqual(len(set(refs)), 3)
        self.assertTrue(all(x.startswith("PENDING_") for x in refs))
        self.assertEqual(draft["conditions"], {"noncommercial":True,"free_access":True,"no_ads":True,"attribution":True})


if __name__ == "__main__":
    unittest.main()
