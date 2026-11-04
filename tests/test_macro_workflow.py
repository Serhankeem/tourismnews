"""Macro durable transaction and unchanged schedule."""
import datetime as dt
from pathlib import Path
from test_pipeline import PipelineHarness
ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=(ROOT/'.github/workflows/macro.yml').read_text()
class MacroWorkflowTests(PipelineHarness):
    def test_daily_schedule_kst_and_main_only_publication(self):
        t=dt.datetime(2026,10,30,3,20,tzinfo=dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=9)))
        self.assertEqual((t.hour,t.minute),(12,20));self.assertIn("cron: '20 3 * * *'",WORKFLOW);self.assertIn('workflow_dispatch:',WORKFLOW)
        self.assertIn("if: github.ref == 'refs/heads/main'",WORKFLOW);self.assertIn('uses: ./.github/workflows/pipeline.yml',WORKFLOW)
    def test_exact_save_step_persists_macro_and_preserves_concurrent_news(self):
        self.run_pipeline(self.change);before=self.reader()
        paths=['site/data/news.json','collector_state/archive.json','site/data/reports.json','collector_state/reports_archive.json']
        original={p:(before.path/p).read_bytes() for p in paths}
        self.run_pipeline(self.change,requested='macro');after=self.reader()
        self.assertEqual(original,{p:(after.path/p).read_bytes() for p in paths});self.assertEqual(after.tip('main'),self.main)
        self.assertFalse((self.root/'pages/collector_state').exists())
