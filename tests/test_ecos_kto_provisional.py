"""Synthetic-only regression tests; never use the repository's ECOS Secret."""
import datetime as dt
import json
import re
import unittest
from decimal import Decimal
from unittest.mock import patch
from src.macro import ecos, ecos_kto_provisional as c

NOW = dt.datetime(2026, 11, 6, 16, tzinfo=c.KST)
PERIODS = [f'2025-{i:02}' for i in (10, 11, 12)] + [f'2026-{i:02}' for i in range(1, 10)]

def manifest():
    return {
        'schema': 'kto_provisional_csv_digest_v1',
        'source_kind': 'user_uploaded_csv_unverified',
        'source_origin_review': 'pending',
        'source_sha256': 'a' * 64,
        'unit': '백만달러',
        'display_decimals': 1,
        'values_sha256': {p: {k: c.digest(p, k, Decimal('100.1')) for k in c.KINDS} for p in PERIODS}
    }

class DigestCheckTests(unittest.TestCase):
    def test_manifest_fixed_twelve_months_pending(self):
        p, entries = c.validate_manifest(manifest(), NOW)
        self.assertEqual(p, PERIODS)
        self.assertEqual(len(entries), 12)
        doc = manifest()
        doc['source_origin_review'] = 'official_file_verified'
        with self.assertRaises(ecos.EcosError):
            c.validate_manifest(doc, NOW)
        doc = manifest()
        doc['values_sha256'][PERIODS[0]]['receipts'] = 'not a digest'
        with self.assertRaises(ecos.EcosError):
            c.validate_manifest(doc, NOW)

    def test_periods_contiguous_and_past(self):
        doc = manifest()
        doc['values_sha256'][PERIODS[1]] = doc['values_sha256'].pop(PERIODS[0])
        with self.assertRaises(ecos.EcosError):
            c.validate_manifest(doc, NOW)
        doc = manifest()
        doc['values_sha256']['2026-11'] = doc['values_sha256'].pop(PERIODS[0])
        with self.assertRaises(ecos.EcosError):
            c.validate_manifest(doc, NOW)

    def test_decimal_half_up_digest(self):
        p = PERIODS[0]
        self.assertEqual(c.digest(p, 'receipts', Decimal('100.1499')),
                         c.digest(p, 'receipts', Decimal('100.1')))
        self.assertEqual(c.digest(p, 'receipts', Decimal('100.15')),
                         c.digest(p, 'receipts', Decimal('100.2')))
        self.assertNotEqual(c.digest(p, 'receipts', Decimal('100.1')),
                            c.digest(p, 'expenditure', Decimal('100.1')))

    def test_match_mismatch_missing_without_amounts_in_summary(self):
        meta = {'series': {k: {'start': PERIODS[0], 'end': PERIODS[-1]} for k in c.KINDS}}
        observations = {k: {p: Decimal('100.1') for p in PERIODS} for k in c.KINDS}
        with patch.object(c, 'candidate_metadata', return_value=meta), patch.object(
                c, 'values', side_effect=lambda client, inspector, metadata, kind, start, end, now: observations[kind]):
            good = c.compare_provisional(None, None, manifest(), NOW)
            self.assertEqual(len(good), 12)
            self.assertTrue(all(row[k] == 'matches_at_one_decimal' for row in good for k in c.KINDS))
            observations['receipts'][PERIODS[0]] = Decimal('100.21')
            observations['expenditure'].pop(PERIODS[1])
            mismatch = c.compare_provisional(None, None, manifest(), NOW)
        self.assertEqual(mismatch[0]['receipts'], 'different_at_one_decimal')
        self.assertEqual(mismatch[1]['expenditure'], 'missing')
        summary = c.render(mismatch)
        for forbidden in ('100.21', '100.1', 'ECOS_API_KEY'):
            self.assertNotIn(forbidden, summary)
        self.assertIn('KTO 공식 증빙: pending', summary)
        self.assertIn('운영 승인: not_granted', summary)

    def test_repository_manifest_is_digest_only(self):
        doc = json.loads(c.MANIFEST.read_text(encoding='utf-8'))
        periods, _ = c.validate_manifest(doc, NOW)
        self.assertEqual(periods, PERIODS)
        self.assertEqual(doc['source_origin_review'], 'pending')
        self.assertEqual(len(doc['source_sha256']), 64)
        for row in doc['values_sha256'].values():
            self.assertTrue(all(re.fullmatch('[0-9a-f]{64}', v) for v in row.values()))
        self.assertNotIn('1896.9', json.dumps(doc))

    def test_workflow_manual_readonly(self):
        text = (c.ROOT / '.github/workflows/ecos-kto-provisional.yml').read_text()
        self.assertIn('workflow_dispatch:', text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn('contents: read', text)
        self.assertIn('persist-credentials: false', text)
        self.assertEqual(text.count('${{ secrets.ECOS_API_KEY }}'), 1)
        for forbidden in ('schedule:', 'pull_request:', 'push:', 'contents: write',
                          'pages: write', 'upload-artifact', 'src.macro.engine', 'git push'):
            self.assertNotIn(forbidden, text)

if __name__ == '__main__':
    unittest.main()
