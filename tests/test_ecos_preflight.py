"""Only synthetic metadata and a fake key. No network, real Secret or observations."""
import base64
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import quote
from src.macro import ecos
from src.macro import ecos_preflight as p

ROOT=Path(__file__).resolve().parents[1]
FAKE='SYNTHETIC_KEY_NOT_A_REAL_SECRET'


def table(code='999Y999',name='SYNTHETIC 국제수지',parent=None):
    return dict(STAT_CODE=code,STAT_NAME=name,P_STAT_CODE=parent,CYCLE='A,M',SRCH_YN='Y')


def item(code,name,parent=None,group='Group1',**kw):
    return dict(STAT_CODE='999Y999',STAT_NAME='SYNTHETIC 국제수지',GRP_CODE=group,
                ITEM_CODE=code,ITEM_NAME=name,P_ITEM_CODE=parent,CYCLE='M',
                UNIT_NAME='백만달러',START_TIME='202101',END_TIME='202608',**kw)


def items():
    return [item('B','국제수지'),item('C','경상수지','B'),item('S','서비스수지','C'),
            item('R','여행수입','S'),item('P','여행지급','S'),
            item('GR','일반여행','R'),item('GP','일반여행','P'),item('EDU','유학연수','R')]


class Fixture:
    def __init__(self):
        self.tables=[table(),table('888Y888','SYNTHETIC unrelated')]
        self.items=items();self.calls=[];self.response_hashes=['0'*64]
    def rows(self,svc,*args):
        self.calls.append((svc,args))
        if svc=='StatisticTableList':return copy.deepcopy([t for t in self.tables if not args or t['STAT_CODE']==args[0]])
        if svc=='StatisticItemList':return copy.deepcopy(self.items)
        raise AssertionError('NO StatisticSearch, collection or operational data allowed')


class InspectionTests(unittest.TestCase):
    def setUp(self):self.client=Fixture();self.inspector=p.Inspector(FAKE)
    def run_inspect(self,limit=12):return p.inspect(self.client,self.inspector,limit)
    def test_existing_metadata_function_is_reused_by_cli_and_preflight(self):
        result=ecos.metadata(self.client,'999Y999')
        self.assertEqual(result['items'],items());self.assertEqual(result['tables'],[table()])
        self.assertEqual([s for s,a in self.client.calls],['StatisticTableList','StatisticItemList'])
        source=(ROOT/'src/macro/ecos.py').read_text();self.assertIn('result = metadata(client, args.table_code)',source)
    def test_candidate_hierarchy_directions_units_and_coverage(self):
        result=self.run_inspect();self.assertEqual(result['status'],'inspection_complete')
        self.assertEqual(result['authentication'],'verified_catalogue');self.assertEqual(result['candidate_count'],1)
        found=result['tables'][0]['items'];self.assertEqual(len(found),2)
        self.assertEqual([i['direction'] for i in found],['receipts_candidate','expenditure_candidate'])
        self.assertEqual(found[0]['path'],'B: 국제수지 → C: 경상수지 → S: 서비스수지 → R: 여행수입 → GR: 일반여행')
        self.assertEqual(found[0]['unit'],'백만달러');self.assertEqual((found[0]['start'],found[0]['end']),('202101','202608'))
        self.assertTrue(found[0]['metadata_complete']);self.assertNotIn('EDU',[i['code'] for i in found])
        self.assertTrue(all(s in ('StatisticTableList','StatisticItemList') for s,a in self.client.calls))
    def test_descendants_of_matching_catalogue_group_are_inspected(self):
        self.client.tables=[dict(table('1000000000','국제수지'),SRCH_YN='N'),table('999Y999','서비스 상세','1000000000')]
        candidates=self.inspector.candidates(self.inspector.catalogue(self.client.tables))
        self.assertEqual([t['code'] for t in candidates],['999Y999'])
    def test_annual_only_and_nonqueryable_are_not_requested(self):
        self.client.tables[0]['CYCLE']='A';self.assertEqual(self.run_inspect()['errors'],['preflight_no_candidates'])
        self.assertFalse(any(s=='StatisticItemList' for s,a in self.client.calls))
    def test_empty_response_does_not_verify_authentication(self):
        self.client.tables=[];result=self.run_inspect();self.assertEqual(result['authentication'],'not_verified')
        self.assertEqual(result['errors'],['preflight_empty_catalogue'])
    def test_no_general_travel_leaves_is_reported_without_total_substitution(self):
        self.client.items=[i for i in self.client.items if i['ITEM_CODE'] not in ('GR','GP')]
        result=self.run_inspect();body=p.summary(result);self.assertIn('일반여행 항목 후보 0개',body)
        self.assertIn('일반여행 항목 미발견',body);self.assertFalse(result['tables'][0]['items'])
    def test_general_leaf_alone_never_proves_direction(self):
        self.client.items=[item('GR','일반여행')];self.assertEqual(self.run_inspect()['tables'][0]['items'][0]['direction'],'direction_unverified')
        self.client.items=[item('B','여행수입·지급'),item('GR','일반여행','B')]
        self.assertEqual(self.run_inspect()['tables'][0]['items'][0]['direction'],'direction_unverified')
    def test_conflicting_receipt_payment_ancestors_never_form_a_pair(self):
        self.client.items=[item('GR','일반여행수입'),item('GP','일반여행지급','GR')]
        result=self.run_inspect();self.assertEqual(result['tables'][0]['items'][1]['direction'],'direction_unverified')
        self.assertEqual(p.assessment(result),'review_required')

    def test_nonmonetary_unit_cannot_complete_financial_pair(self):
        for row in self.client.items:row['UNIT_NAME']='명'
        self.assertEqual(p.assessment(self.run_inspect()),'review_required')

    def test_education_ancestor_never_promoted(self):
        self.client.items=[item('ED','유학연수수입'),item('GR','일반여행','ED')]
        self.assertEqual(self.run_inspect()['tables'][0]['items'][0]['direction'],'direction_unverified')
    def test_missing_parent_cycles_duplicates_and_parent_name_mismatch(self):
        variants=[]
        a=items();a[-3]['P_ITEM_CODE']='MISSING';variants.append((a,'preflight_missing_parent'))
        a=items();a[0]['P_ITEM_CODE']='GR';variants.append((a,'preflight_parent_cycle'))
        a=items();a.append(a[-2].copy());variants.append((a,'preflight_duplicate_item'))
        a=items();a[-3]['P_ITEM_NAME']='wrong';variants.append((a,'preflight_parent_name_mismatch'))
        for data,error in variants:
            self.client.items=data;r=self.run_inspect();self.assertEqual(r['status'],'partial');self.assertEqual(r['tables'][0]['error'],error)
    def test_pair_status_keeps_missing_units_ambiguity_and_extra_dimensions_under_review(self):
        self.assertEqual(p.assessment(self.run_inspect()),'pair_candidates_found')
        self.client.items[-3]['UNIT_NAME']='';self.assertEqual(p.assessment(self.run_inspect()),'review_required')
        self.client.items=[item('GR','일반여행')];self.assertEqual(p.assessment(self.run_inspect()),'review_required')
        self.client.items=items()+[item('N','원계열',group='Group2')];self.assertEqual(p.assessment(self.run_inspect()),'review_required')
        self.client.items=[];self.assertEqual(p.assessment(self.run_inspect()),'not_found')

    def test_authentication_later_rejected_is_not_reported_as_current_success(self):
        original=self.client.rows
        def rows(service,*args):
            if service=='StatisticItemList':raise ecos.EcosError('ecos_auth_invalid')
            return original(service,*args)
        self.client.rows=rows
        self.assertEqual(self.run_inspect()['authentication'],'rejected_after_catalogue')

    def test_other_groups_are_counted_without_invented_selection(self):
        self.client.items.append(item('N','원계열',group='Group2'))
        r=self.run_inspect();self.assertEqual(r['tables'][0]['groups']['Group2'],1)
        self.assertIn('추가 차원',p.summary(r))
    def test_missing_units_or_coverage_are_review_not_filled(self):
        self.client.items[-3]['UNIT_NAME']='';self.client.items[-3]['END_TIME']=''
        row=self.run_inspect()['tables'][0]['items'][0];self.assertFalse(row['metadata_complete']);self.assertEqual(row['unit'],'')
    def test_mismatched_table_or_nonmonthly_time_rejected(self):
        for field,value in [('STAT_NAME','wrong'),('STAT_CODE','999Y998'),('END_TIME','202613')]:
            self.client.items=items();self.client.items[-3][field]=value
            self.assertEqual(self.run_inspect()['tables'][0]['status'],'failed')
    def test_unauthorized_and_unexpected_errors_are_safe(self):
        for error,auth in [(ecos.EcosError('ecos_auth_invalid'),'rejected'),(ecos.EcosError('ecos_auth_or_access_denied'),'access_denied'),(ValueError(FAKE+' https://bad.example/'),'not_verified')]:
            self.client.rows=Mock(side_effect=error);r=self.run_inspect();self.assertEqual(r['authentication'],auth)
            self.assertNotIn(FAKE,p.summary(r));self.assertNotIn('bad.example',p.summary(r))
    def test_partial_failures_and_limit_do_not_become_complete(self):
        self.client.tables=[table(f'999Y{n:03}') for n in range(8)]
        for row in self.client.tables:row['STAT_NAME']='국제수지'
        # Every selected table is explicitly observed to fail; no raw messages copied.
        original=self.client.rows
        def rows(svc,*args):
            if svc=='StatisticItemList':raise RuntimeError(FAKE)
            return original(svc,*args)
        self.client.rows=rows;r=self.run_inspect(6);self.assertEqual(r['candidate_count'],8);self.assertEqual(len(r['tables']),6);self.assertEqual(r['status'],'partial')
        self.assertNotIn(FAKE,p.summary(r))
    def test_key_echo_urls_controls_encodings_blocked_before_summary(self):
        cases=[FAKE,quote(FAKE,safe=''),''.join('%%%02X'%ord(c) for c in FAKE),base64.b64encode(FAKE.encode()).decode(),
               'https://ecos.bok.or.kr/api/StatisticSearch/'+FAKE,'https%3A%2F%2Fevil.example','www.example.com','/api/secret','a\nb','a\x1bb','a\u202eb','<img src=x>',FAKE.replace('_','&#95;'),''.join('\\u%04x'%ord(c) for c in FAKE)]
        for text in cases:
            with self.subTest(text=text),self.assertRaises(ecos.EcosError):self.inspector.text(text)
        for variant in [base64.b64encode(b'TEST_ONLY_KEY_123456').decode().rstrip('='),b'TEST_ONLY_KEY_123456'.hex()]:
            with self.assertRaises(ecos.EcosError):p.Inspector('TEST_ONLY_KEY_123456').text(variant)

    def test_raw_extra_fields_never_enter_summary_and_markdown_is_escaped(self):
        self.client.items[-3]['SECRET_URL']='https://bad.example/'+FAKE
        self.client.items[-3]['ITEM_NAME']='일반여행 | [fake](target) *bold*'
        text=p.summary(self.run_inspect());self.assertNotIn(FAKE,text);self.assertNotIn('SECRET_URL',text)
        self.assertIn(r'\|',text);self.assertIn(r'\[fake\]',text);self.assertNotIn('[fake](target)',text)
    def test_unlisted_exception_identifier_cannot_echo_secret(self):
        self.assertEqual(p.safe_error(ecos.EcosError('ecos_'+FAKE)),'preflight_failed')
    def test_invalid_limits_and_duplicate_catalogue_fail_closed(self):
        with self.assertRaises(ecos.EcosError):self.run_inspect(1000)
        self.client.tables.append(table());self.assertEqual(self.run_inspect()['status'],'failed')


class MainTests(unittest.TestCase):
    def run_main(self,key=FAKE,client=None):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'summary.md';env={'GITHUB_STEP_SUMMARY':str(out),'ECOS_API_KEY':key}
            stdout=io.StringIO();stderr=io.StringIO()
            with patch.dict(os.environ,env,clear=True),patch.object(p,'Client',return_value=client or Fixture()),contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
                status=p.main()
            files=[v.name for v in Path(d).iterdir()]
            return status,out.read_text(),stdout.getvalue()+stderr.getvalue(),files
    def test_summary_is_only_file_and_stdout_contains_no_metadata(self):
        code,summary,logs,files=self.run_main();self.assertEqual(code,0);self.assertEqual(files,['summary.md'])
        self.assertIn('999Y999',summary);self.assertNotIn('999Y999',logs);self.assertNotIn(FAKE,summary+logs)
    def test_missing_or_invalid_secret_has_no_traceback_or_raw_message(self):
        for message,expected in [('ecos_auth_required','credential_missing'),('ecos_auth_invalid','rejected')]:
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':d+'/summary'},clear=True),patch.object(p,'Client',side_effect=ecos.EcosError(message)),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(),1);body=Path(d+'/summary').read_text();self.assertIn(p.cell(expected),body);self.assertNotIn('Traceback',body)
    def test_unsafe_payload_reports_safe_failure_not_data(self):
        client=Fixture();client.items[-3]['ITEM_NAME']='일반여행'+FAKE
        code,body,logs,files=self.run_main(client=client);self.assertEqual(code,1);self.assertNotIn(FAKE,body+logs);self.assertIn('preflight',body)
    def test_no_general_travel_pair_is_a_failed_job_with_honest_summary(self):
        client=Fixture();client.items=[]
        status,body,logs,files=self.run_main(client=client)
        self.assertEqual(status,1);self.assertIn('not\\_found',body);self.assertNotIn(FAKE,body+logs)

    def test_no_summary_or_repository_target_cannot_write(self):
        original=(ROOT/'macro_sources.json').read_bytes()
        for env in [{},{'GITHUB_STEP_SUMMARY':str(ROOT/'macro_sources.json')}]:
            with patch.dict(os.environ,env,clear=True),patch.object(p,'Client') as client:
                self.assertEqual(p.main(),1);client.assert_not_called()
        self.assertEqual(original,(ROOT/'macro_sources.json').read_bytes())


class WorkflowTests(unittest.TestCase):
    def test_manual_main_readonly_secret_step_only(self):
        text=(ROOT/'.github/workflows/ecos-preflight.yml').read_text()
        self.assertIn('name: ECOS Preflight',text);self.assertIn('workflow_dispatch:',text)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'",text)
        self.assertIn('contents: read',text);self.assertIn('persist-credentials: false',text);self.assertIn('ref: ${{ github.sha }}',text)
        self.assertEqual(text.count('${{ secrets.ECOS_API_KEY }}'),1)
        self.assertIn('run: python -m src.macro.ecos_preflight',text)
        for forbidden in ['schedule:','pull_request:','pull_request_target:','push:','workflow_call:','workflow_run:','contents: write','pages:','id-token:', 'upload-artifact','upload-pages','deploy-pages','src.macro.engine','src.pipeline','git push','environment:']:
            self.assertNotIn(forbidden,text)
    def test_preflight_has_no_operational_or_observation_entrypoint(self):
        source=(ROOT/'src/macro/ecos_preflight.py').read_text()
        for forbidden in ['StatisticSearch','from .engine','from ..pipeline','subprocess','write_atomic','--validate','urllib.request','print(result','print(body']:
            self.assertNotIn(forbidden,source)

if __name__=='__main__':unittest.main()
