"""Workflow contracts now persist to data/live, never the application branch."""
from pathlib import Path
from test_pipeline import PipelineHarness
ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=(ROOT/'.github/workflows/collect.yml').read_text()
PIPELINE=(ROOT/'.github/workflows/pipeline.yml').read_text()
class WorkflowContractTests(PipelineHarness):
 def test_manual_schedule_and_main_only_deployment_remain(self):
  for value in ['workflow_dispatch:',"cron: '17 */2 * * *'","cron: '30 1 * * *'","if: github.ref == 'refs/heads/main'","      - 'relevance_reviews.json'",'uses: ./.github/workflows/pipeline.yml']:self.assertIn(value,WORKFLOW)
  self.assertIn('uses: actions/deploy-pages@v4',PIPELINE);self.assertIn('path: ${{ runner.temp }}/tourism-pages',PIPELINE)
  self.assertNotIn('git pull --rebase origin main',WORKFLOW+PIPELINE)
 def test_news_and_review_state_survive_fresh_checkout(self):
  self.run_pipeline(self.change);store=self.reader()
  for name in ['archive','review_queue','legacy_archive','decisions','discovery','source_metrics','run_summary','v02_snapshot']:
   self.assertEqual((self.code/f'collector_state/{name}.json').read_bytes(),(store.path/f'collector_state/{name}.json').read_bytes())
  self.assertEqual(store.tip('main'),self.main);self.assertFalse((self.root/'pages/collector_state').exists())
