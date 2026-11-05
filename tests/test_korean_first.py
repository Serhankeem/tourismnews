"""Presentation registry only: synthetic mutations never reach operating JSON."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
import subprocess
import tempfile
import shutil
import re
from tools.build_content_locale import ROOT,approved_entries,build,withdraw


class KoreanFirstTests(unittest.TestCase):
    def setUp(self):
        self.production=json.loads((ROOT/'content_localization.json').read_text())
        self.registry={'entries':[]}
        self.records={('research',r['url']):r for r in json.loads((ROOT/'site/data/reports.json').read_text())['reports']}
        self.allowed={'research':{'OECD'},'news':set()}
        # Isolated approval fixture: tests must still run after every real label
        # has been withdrawn. Never depend on an active production approval.
        r=next(r for r in self.records.values() if r['publisher']=='OECD' and '2026' in r['title'])
        self.registry['entries'].append({'kind':'research','url':r['url'],'publisher':r['publisher'],
            'published_at':r['published_at'],'original_title':r['title'],
            'original_title_sha256':hashlib.sha256(r['title'].encode()).hexdigest(),
            'status':'approved','ko_title':'OECD 관광 보고서 2026','mode':'independent_factual_label',
            'rights':{'status':'approved','title_only':True,'evidence_url':'https://example.org/fixture','basis':'test-only grant','verified_at':'2026-11-05'},
            'accuracy':{'status':'approved','basis':'test-only title facts','reviewed_at':'2026-11-05','preserved_tokens':['OECD']},
            'note':'test-only','attribution':'test-only','history':[]})

    def approved(self):return next(r for r in self.registry['entries'] if r['status']=='approved')

    def test_generated_asset_matches_current_review_and_publisher_config(self):
        self.assertEqual(build(),(ROOT/'site/assets/content-localization.json').read_text())
        expected=[r for r in self.production['entries'] if r['status']=='approved']
        actual=approved_entries(self.production,self.records,self.allowed)
        self.assertEqual(len(actual),len(expected))
        self.assertTrue(all(r['mode']=='independent_factual_label' for r in actual))

    def test_no_pending_korean_draft_in_registry_or_generated_asset(self):
        for r in self.production['entries']:
            if r['status']!='approved':self.assertNotIn('ko_title',r)
        self.registry['entries'].append({'kind':'research','url':'https://example.org/unapproved-test-only','status':'review','ko_title':'ISOLATED_UNAPPROVED_SENTINEL'})
        with self.assertRaisesRegex(ValueError,'unapproved_text'):approved_entries(self.registry,self.records,self.allowed)
        self.assertNotIn('ISOLATED_UNAPPROVED_SENTINEL',build())

    def test_withdrawal_removes_text_but_keeps_bound_review_history(self):
        r=self.approved();title=r['ko_title'];old=copy.deepcopy(r['history'])
        new=withdraw(self.registry,r['kind'],r['url'],'2026-11-05')
        entry=next(x for x in new['entries'] if x['url']==r['url'])
        self.assertNotIn('ko_title',entry);self.assertEqual(entry['history'][:-1],old)
        self.assertEqual(entry['history'][-1]['ko_title_sha256'],hashlib.sha256(title.encode()).hexdigest())
        self.assertFalse(any(x['url']==r['url'] for x in approved_entries(new,self.records,self.allowed)))
        self.assertEqual(r['ko_title'],title)

    def test_wrong_year_and_entity_do_not_publish(self):
        r=self.approved();r['ko_title']=r['ko_title'].replace('2026','2099').replace('2024','2099')
        with self.assertRaisesRegex(ValueError,'inaccurate'):approved_entries(self.registry,self.records,self.allowed)
        self.setUp();r=self.approved();r['ko_title']=r['ko_title'].replace('OECD','UNKNOWN')
        with self.assertRaisesRegex(ValueError,'inaccurate'):approved_entries(self.registry,self.records,self.allowed)

    def test_stale_original_date_and_title_fail_closed(self):
        r=self.approved();self.records[(r['kind'],r['url'])]['published_at']='2099-01-01'
        with self.assertRaisesRegex(ValueError,'stale'):approved_entries(self.registry,self.records,self.allowed)
        self.setUp();r=self.approved();self.records[(r['kind'],r['url'])]['title']+=' revised'
        with self.assertRaisesRegex(ValueError,'stale'):approved_entries(self.registry,self.records,self.allowed)

    def test_duplicates_cannot_arbitrarily_choose_a_heading(self):
        self.registry['entries'].append(copy.deepcopy(self.approved()))
        with self.assertRaisesRegex(ValueError,'duplicate'):approved_entries(self.registry,self.records,self.allowed)

    def test_unapproved_publisher_and_rights_are_excluded(self):
        self.assertEqual(approved_entries(self.registry,self.records,{}),[])
        for field in ('rights','accuracy'):
            candidate=copy.deepcopy(self.registry)
            for r in candidate['entries']:
                if r['status']=='approved':r[field]['status']='review'
            self.assertEqual(approved_entries(candidate,self.records,self.allowed),[])

    def test_machine_translation_or_missing_evidence_is_not_approval(self):
        for change in ('mode','evidence'):
            candidate=copy.deepcopy(self.registry)
            for r in candidate['entries']:
                if r['status']=='approved':
                    if change=='mode':r['mode']='unreviewed_translation'
                    else:r['rights']['evidence_url']=''
            self.assertEqual(approved_entries(candidate,self.records,self.allowed),[])

    def test_input_contracts_and_originals_are_not_mutated(self):
        before=copy.deepcopy(self.records)
        approved_entries(self.registry,self.records,self.allowed)
        self.assertEqual(self.records,before)
        fields={'title','publisher','published_at','report_type','category','url','keywords','access_type'}
        self.assertTrue(all(set(r)==fields for r in self.records.values()))

    def test_browser_presentation_unit_contract(self):
        result=subprocess.run(['node',str(ROOT/'tests/korean-first.unit.cjs')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_generator_respects_current_report_and_provider_publication_gates(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ['sources.json','reports_sources.json','operating_policy.json','discovery_providers.json','content_localization.json']:
                shutil.copyfile(ROOT/name,root/name)
            shutil.copytree(ROOT/'site/data',root/'site/data')
            shutil.copytree(ROOT/'collector_state',root/'collector_state')
            reports=json.loads((root/'reports_sources.json').read_text())
            for s in reports['sources']:
                if s['name']=='OECD':s['publication']['status']='review'
            (root/'reports_sources.json').write_text(json.dumps(reports))
            self.assertEqual(json.loads(build(root))['headings'],[])
            # A publisher approval alone cannot override a withdrawn API route.
            news=json.loads((root/'site/data/newsroom.json').read_text())['articles']
            r=news[0]
            template=copy.deepcopy(self.approved());token=r['title'].split()[0]
            template.update(kind='news',url=r['url'],publisher=r['source'],published_at=r['published_at'],
                original_title=r['title'],original_title_sha256=hashlib.sha256(r['title'].encode()).hexdigest(),
                ko_title=token+' 격리 검증 안내 '+' '.join(re.findall(r'\d+(?:[.,]\d+)*',r['title'])))
            template['accuracy']['preserved_tokens']=[token]
            (root/'content_localization.json').write_text(json.dumps({'entries':[template]}))
            archive=json.loads((root/'collector_state/archive.json').read_text())
            for a in archive['articles']:
                if a['url']==r['url']:a['discovery_origin']={'provider_id':'fixture-held-route'}
            (root/'collector_state/archive.json').write_text(json.dumps(archive))
            (root/'discovery_providers.json').write_text(json.dumps({'providers':[{'id':'fixture-held-route','enabled':False}]}))
            self.assertEqual(json.loads(build(root))['headings'],[])

    def test_registry_contains_no_summaries_or_findings(self):
        actual=approved_entries(self.registry,self.records,self.allowed)
        self.assertTrue(all(set(r)<=set(['kind','url','publisher','published_at','original_title','ko_title','mode','note','attribution','status','rights_status','accuracy_status','evidence_url','preserved_tokens']) for r in actual))


if __name__=='__main__':unittest.main()
