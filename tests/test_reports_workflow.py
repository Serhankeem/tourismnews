"""Research workflow keeps its schedule and durable cross-engine isolation."""
import datetime as dt
import json
from pathlib import Path
from src import collector as c
from src.reports.engine import approved
from test_pipeline import PipelineHarness
ROOT=Path(__file__).resolve().parents[1]
REPORTS=(ROOT/'.github/workflows/reports.yml').read_text()
NEWS=(ROOT/'.github/workflows/collect.yml').read_text()
PIPELINE=(ROOT/'.github/workflows/pipeline.yml').read_text()
class ReportsWorkflowTests(PipelineHarness):
    def test_weekly_korean_schedule_manual_execution_and_shared_lock(self):
        self.assertIn("cron: '40 22 * * 0'",REPORTS);self.assertIn('workflow_dispatch:',REPORTS)
        sunday=dt.datetime(2026,11,1,22,40,tzinfo=dt.timezone.utc).astimezone(c.KST)
        self.assertEqual((sunday.weekday(),sunday.hour,sunday.minute),(0,7,40))
        for workflow in (NEWS,REPORTS):
            self.assertIn('uses: ./.github/workflows/pipeline.yml',workflow)
            self.assertIn("if: github.ref == 'refs/heads/main'",workflow)
        self.assertIn('group: tourism-pulse-publish',PIPELINE);self.assertIn('cancel-in-progress: false',PIPELINE);self.assertIn('ref: main',PIPELINE)
    def test_exact_save_script_preserves_concurrent_news_and_report_state(self):
        self.run_pipeline(self.change)
        first=self.reader();news=(first.path/'site/data/health.json').read_bytes();archive=(first.path/'collector_state/archive.json').read_bytes()
        self.run_pipeline(self.change,requested='reports');last=self.reader()
        self.assertEqual((last.path/'site/data/health.json').read_bytes(),news)
        self.assertEqual((last.path/'collector_state/archive.json').read_bytes(),archive)
        self.assertTrue((last.path/'site/data/reports.json').exists());self.assertEqual(last.tip('main'),self.main)
    def test_primary_sources_and_review_only_candidates_not_active_or_counted(self):
        config=json.loads((ROOT/'reports_sources.json').read_text())
        self.assertEqual(len(config['sources']),11);self.assertEqual(len(config['phase2_candidates']),2)
        sources={s['id']:s for s in config['sources']}
        self.assertFalse(sources['iata']['enabled']);self.assertIn('no data scraping',sources['iata']['blocking_reason'])
        self.assertFalse(sources['yanolja']['allow_registered_date'])
        self.assertTrue(all(s.get('publication',{}).get('body_pdf_images')=='not_authorized' for s in sources.values()))
        self.assertFalse(set(s['id'] for s in config['phase2_candidates'])&set(sources))

    def test_noncommercial_permission_is_not_a_universal_body_licence(self):
        source=json.loads((ROOT/'reports_sources.json').read_text())['sources'][0]
        self.assertTrue(approved(source,{'mode':'noncommercial','ads_enabled':False,'paid_access':False}))
        for model in ({},{'mode':'commercial','ads_enabled':True,'paid_access':False},{'mode':'noncommercial','ads_enabled':False,'paid_access':True}):
            self.assertFalse(approved(source,model))
