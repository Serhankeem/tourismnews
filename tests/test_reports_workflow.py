"""Run the real Research save step through a concurrent news-commit scenario."""
import datetime as dt
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from src import collector as c
from src.reports.engine import approved

ROOT=Path(__file__).resolve().parents[1]
REPORTS=(ROOT/'.github/workflows/reports.yml').read_text()
NEWS=(ROOT/'.github/workflows/collect.yml').read_text()

class ReportsWorkflowTests(unittest.TestCase):
    def test_weekly_korean_schedule_manual_execution_and_shared_lock(self):
        self.assertIn("cron: '40 22 * * 0'",REPORTS);self.assertIn('workflow_dispatch:',REPORTS)
        sunday=dt.datetime(2026,11,1,22,40,tzinfo=dt.timezone.utc).astimezone(c.KST)
        self.assertEqual((sunday.weekday(),sunday.hour,sunday.minute),(0,7,40))
        for workflow in (NEWS,REPORTS):
            self.assertIn('group: tourism-pulse-publish',workflow)
            self.assertIn('cancel-in-progress: false',workflow)
            publish=workflow.split('  collect-and-publish:',1)[1]
            self.assertIn("if: github.ref == 'refs/heads/main'",publish)
            self.assertIn('ref: main',publish);self.assertIn('git pull --rebase origin main',publish)
            self.assertIn('uses: actions/deploy-pages@v4',publish)
        self.assertIn("cron: '17 */2 * * *'",NEWS);self.assertIn("cron: '30 1 * * *'",NEWS)

    def test_exact_save_script_preserves_concurrent_news_and_report_state(self):
        block=REPORTS.split('      - name: Save Research data only\n        run: |\n',1)[1].split('      - name:',1)[0]
        script='\n'.join(line[10:] for line in block.rstrip().splitlines())
        def git(*args,cwd):return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);remote=root/'remote.git';writer=root/'writer';actor=root/'news-writer';reader=root/'reader'
            git('init','--bare',str(remote),cwd=root);git('init','-b','main',str(writer),cwd=root)
            git('config','user.name','Workflow Test',cwd=writer);git('config','user.email','test@example.invalid',cwd=writer)
            (writer/'site/data').mkdir(parents=True);(writer/'collector_state').mkdir()
            for name in ('news','newsroom','briefing','research','filings'):
                (writer/'site/data'/f'{name}.json').write_text(json.dumps({'version':1,'kind':name}))
            (writer/'collector_state/archive.json').write_text('news archive unchanged')
            git('add','.',cwd=writer);git('commit','-m','Seed news',cwd=writer);git('remote','add','origin',str(remote),cwd=writer);git('push','-u','origin','main',cwd=writer)
            git('clone','-b','main',str(remote),str(actor),cwd=root)
            git('config','user.name','Independent News Job',cwd=actor);git('config','user.email','news@example.invalid',cwd=actor)
            (actor/'site/data/news.json').write_text(json.dumps({'version':2,'kind':'news'}))
            git('add','site/data/news.json',cwd=actor);git('commit','-m','Concurrent news update',cwd=actor);git('push',cwd=actor)
            for name in ('reports','reports_health'):(writer/'site/data'/f'{name}.json').write_text(json.dumps({'real_step_fixture':name}))
            for name in ('reports_archive','reports_candidates','reports_source_metrics','reports_run_summary'):
                (writer/'collector_state'/f'{name}.json').write_text(json.dumps({'retained':name}))
            subprocess.run(['bash','-e','-c',script],cwd=writer,check=True,capture_output=True)
            git('clone','-b','main',str(remote),str(reader),cwd=root)
            self.assertEqual(json.loads((reader/'site/data/news.json').read_text())['version'],2)
            for name in ('newsroom','briefing','research','filings'):
                self.assertEqual((reader/'site/data'/f'{name}.json').read_bytes(),(writer/'site/data'/f'{name}.json').read_bytes())
            self.assertEqual((reader/'collector_state/archive.json').read_text(),'news archive unchanged')
            self.assertEqual((reader/'collector_state/reports_archive.json').read_bytes(),(writer/'collector_state/reports_archive.json').read_bytes())
            self.assertTrue((reader/'site/data/reports.json').exists())
            self.assertFalse((reader/'site/collector_state').exists())

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
