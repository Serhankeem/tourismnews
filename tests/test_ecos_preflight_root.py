"""Official TableList root-marker SHAPE with synthetic IDs/names only.
No Repository Secret, full provider response or actual statistical values.
"""
import copy
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.macro import ecos_preflight as p
from test_ecos_preflight import Fixture, FAKE, table, items


def root_catalogue():
    return [
        dict(table('1000000000','SYNTHETIC 국제수지','*'),CYCLE=None,SRCH_YN='N'),
        dict(table('1000000001','SYNTHETIC 하위 분류','1000000000'),CYCLE=None,SRCH_YN='N'),
        dict(table('999Y999','SYNTHETIC 서비스 상세','1000000001'),CYCLE='M'),
    ]


def root_client():
    c=Fixture();c.tables=root_catalogue()
    for row in c.items:row['STAT_NAME']=c.tables[-1]['STAT_NAME']
    return c


class RootMarkerTests(unittest.TestCase):
    def setUp(self):self.i=p.Inspector(FAKE)
    def test_literal_root_parent_normalizes_to_none_only_in_catalogue(self):
        rows=root_catalogue();original=copy.deepcopy(rows);out=self.i.catalogue(rows)
        self.assertIsNone(out['1000000000']['parent'])
        self.assertEqual(out['1000000001']['parent'],'1000000000')
        self.assertEqual(out['999Y999']['parent'],'1000000001')
        self.assertEqual(rows,original)
    def test_null_empty_and_ordinary_parents_remain_compatible(self):
        for raw in [None,'','1000000001','999Y999']:
            out=self.i.catalogue([table(parent=raw)])
            self.assertEqual(out['999Y999']['parent'],raw or None)
    def test_classifications_never_become_monthly_table_queries(self):
        c=root_client();r=p.inspect(c,self.i)
        self.assertEqual(r['status'],'inspection_complete');self.assertEqual(r['candidate_count'],1)
        self.assertEqual(p.assessment(r),'pair_candidates_found')
        self.assertEqual(c.calls,[('StatisticTableList',()),('StatisticTableList',('999Y999',)),('StatisticItemList',('999Y999',))])
        self.assertEqual([row['direction'] for row in r['tables'][0]['items']],['receipts_candidate','expenditure_candidate'])
    def test_rootless_sibling_is_not_inherited_from_other_root(self):
        rows=root_catalogue()+[table('888Y888','SYNTHETIC unrelated','*')]
        self.assertEqual([t['code'] for t in self.i.candidates(self.i.catalogue(rows))],['999Y999'])
    def test_marker_is_not_a_stat_code_or_item_code(self):
        with self.assertRaises(p.MetadataValidationError) as e:self.i.catalogue([table(code='*')])
        self.assertEqual(p.diagnostic(e.exception),dict(field='STAT_CODE',classification='invalid_code'))
        for field in ['ITEM_CODE','P_ITEM_CODE']:
            rows=items();rows[-3][field]='*'
            with self.subTest(field=field),self.assertRaises(p.MetadataValidationError) as e:self.i.items(dict(code='999Y999',name='SYNTHETIC 국제수지'),rows)
            self.assertEqual(p.diagnostic(e.exception),dict(field=field,classification='invalid_code'))
    def test_marker_variants_and_code_wildcards_are_still_denied(self):
        for value in ['**','*suffix','suffix*',' * ','＊','%2A','&#42;']:
            with self.subTest(value=value),self.assertRaises(p.EcosError):self.i.catalogue([table(parent=value)])
            with self.assertRaises(p.EcosError):self.i.code(value)
    def test_parent_special_case_does_not_bypass_secret_guards(self):
        # Even the marker is content-checked before its structural interpretation.
        with self.assertRaises(p.MetadataValidationError):p.Inspector('*').catalogue([table(parent='*')])
        with self.assertRaises(p.MetadataValidationError):self.i.catalogue([table(parent=FAKE)])


class SafeDiagnosticsTests(unittest.TestCase):
    def setUp(self):self.i=p.Inspector(FAKE)
    def result(self,field,value,location='catalogue'):
        client=root_client()
        if location=='catalogue':client.tables[0][field]=value
        else:client.items[-3][field]=value
        return p.inspect(client,self.i)
    def test_parent_rejection_reports_only_field_and_category(self):
        r=self.result('P_STAT_CODE','**')
        self.assertEqual(r['errors'],['preflight_unsafe_metadata'])
        self.assertEqual(r['error_diagnostic'],dict(field='P_STAT_CODE',classification='invalid_code'))
        self.assertIn(p.cell('P_STAT_CODE')+' / invalid\\_code',p.summary(r))
        self.assertNotIn('**',p.summary(r))
    def test_missing_fields_types_and_formats_have_fixed_diagnostics(self):
        client=root_client();del client.tables[0]['STAT_NAME']
        r=p.inspect(client,self.i);self.assertEqual(r['error_diagnostic'],dict(field='STAT_NAME',classification='missing_field'))
        r=self.result('P_STAT_CODE',123)
        self.assertEqual(r['error_diagnostic'],dict(field='P_STAT_CODE',classification='invalid_type'))
        r=self.result('CYCLE','bad-cycle')
        self.assertEqual(r['error_diagnostic'],dict(field='CYCLE',classification='invalid_format'))
    def test_item_errors_have_field_context_not_arbitrary_value(self):
        for field in ['ITEM_CODE','ITEM_NAME','GRP_CODE','P_ITEM_CODE','P_ITEM_NAME','UNIT_NAME','START_TIME','END_TIME']:
            r=self.result(field,'https://private.example/'+FAKE,'items')
            d=r['tables'][0]['error_diagnostic'];self.assertEqual(d['field'],field)
            self.assertIn(d['classification'],p.SAFE_CLASSIFICATIONS)
            summary=p.summary(r);self.assertNotIn(FAKE,summary);self.assertNotIn('private.example',summary)
    def test_bad_period_and_unit_type_context_are_not_lost(self):
        r=self.result('END_TIME','202613','items')
        self.assertEqual(r['tables'][0]['error_diagnostic'],dict(field='END_TIME',classification='invalid_format'))
        r=self.result('UNIT_NAME',123,'items')
        self.assertEqual(r['tables'][0]['error_diagnostic'],dict(field='UNIT_NAME',classification='invalid_type'))
    def test_unknown_exception_attributes_cannot_enter_diagnostics(self):
        e=p.MetadataValidationError(FAKE,{'value':'https://private.example/'+FAKE})
        self.assertEqual(p.diagnostic(e),dict(field='unknown',classification='validation_failed'))
        for malicious in [dict(field=FAKE,classification='unsafe_content'),dict(field='STAT_NAME',classification=FAKE),FAKE]:
            text=p.diagnostic_line(malicious)
            self.assertNotIn(FAKE,text);self.assertIn(p.cell('validation_failed'),text)
        self.assertIsNone(p.diagnostic(ValueError(FAKE)))
    def test_new_diagnostics_do_not_echo_encoded_secret_or_original_values(self):
        for field in ['STAT_CODE','P_STAT_CODE','STAT_NAME','CYCLE']:
            r=self.result(field,''.join('%%%02X'%ord(c) for c in FAKE))
            text=p.summary(r)
            self.assertNotIn(FAKE,text);self.assertNotIn('%53',text)
            self.assertIn(p.cell(field),text)
    def test_actual_entrypoint_prints_no_diagnostic_values_or_raw_response(self):
        client=root_client();client.tables[0]['STAT_NAME']='https://private.example/'+FAKE
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'summary.md';stdout=io.StringIO()
            with patch.dict(os.environ,{'ECOS_API_KEY':FAKE,'GITHUB_STEP_SUMMARY':str(target)},clear=True),patch.object(p,'Client',return_value=client),patch('sys.stdout',stdout):
                self.assertEqual(p.main(),1)
            body=target.read_text();self.assertIn(p.cell('STAT_NAME'),body)
            self.assertNotIn(FAKE,body+stdout.getvalue());self.assertNotIn('private.example',body+stdout.getvalue())
            self.assertEqual([x.name for x in Path(d).iterdir()],['summary.md'])

if __name__=='__main__':unittest.main()
