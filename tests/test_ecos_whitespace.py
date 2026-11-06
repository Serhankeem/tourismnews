"""Synthetic names/keys only; never use a Repository Secret or raw API data."""
import copy
import unittest
from unittest.mock import patch
from src.macro import ecos_preflight as p
from test_ecos_preflight import Fixture,FAKE,table

class WhitespaceTests(unittest.TestCase):
    def setUp(self):self.i=p.Inspector(FAKE)
    def failure(self,value,kind,stage='raw',field='STAT_NAME'):
        with self.assertRaises(p.MetadataValidationError) as error:self.i.text(value,field=field)
        self.assertEqual(p.diagnostic(error.exception),dict(field=field,classification=kind,stage=stage))
    def test_cr_lf_tab_collapse_to_single_space_and_keep_words(self):
        for value in ['국제\r수지','국제\n수지','국제\t수지','  국제 \r\n\t 수지  ']:
            self.assertEqual(self.i.text(value,field='STAT_NAME'),'국제 수지')
        self.assertEqual(self.i.text('Balance\r\nof\tPayments (BPM6)',field='STAT_NAME'),'Balance of Payments (BPM6)')
    def test_original_and_normalized_names_have_distinct_internal_roles(self):
        rows=[table(name='국제\n수지',parent='*')];before=copy.deepcopy(rows)
        result=self.i.catalogue(rows)['999Y999']
        self.assertEqual(result['raw_name'],'국제\n수지');self.assertEqual(result['name'],'국제 수지');self.assertEqual(rows,before)
        self.assertEqual([x['code'] for x in self.i.candidates({'999Y999':result})],['999Y999'])
    def test_table_recheck_and_item_recheck_share_canonicalization(self):
        c=Fixture();c.tables[0]['STAT_NAME']='SYNTHETIC 국제\n수지'
        for row in c.items:row['STAT_NAME']='SYNTHETIC 국제\t 수지'
        orig=c.rows
        def rows(service,*args):
            value=orig(service,*args)
            if service=='StatisticTableList' and args:value[0]['STAT_NAME']='SYNTHETIC 국제\r\n수지'
            return value
        c.rows=rows;r=p.inspect(c,self.i)
        self.assertEqual(r['status'],'inspection_complete');self.assertEqual(p.assessment(r),'pair_candidates_found')
        self.assertNotIn('raw_name',p.summary(r));self.assertNotIn('SYNTHETIC 국제',p.summary(r))
    def test_real_name_change_is_not_hidden_by_normalization(self):
        c=Fixture()
        for row in c.items:row['STAT_NAME']='DIFFERENT TABLE'
        r=p.inspect(c,self.i);self.assertEqual(r['tables'][0]['error'],'preflight_table_mismatch')
    def test_zero_width_bidi_and_other_format_controls_blocked(self):
        for ch in ['\u200b','\u200c','\u200d','\ufeff','\u202e','\u2066','\u2069']:
            self.failure('명칭'+ch,'format_control')
    def test_nul_other_cc_surrogate_private_and_unassigned_blocked(self):
        for ch in ['\x00','\x01','\x0b','\x0c','\x7f','\ud800','\ue000','\u0378']:
            self.failure('명칭'+ch,'other_unicode_control')
    def test_codes_and_item_names_keep_strict_whitespace_checks(self):
        for field in ['STAT_CODE','P_STAT_CODE','ITEM_CODE','P_ITEM_CODE','ITEM_NAME']:
            for ch in ['\r','\n','\t']:self.failure('A'+ch+'B','whitespace_control',field=field)
    def test_decoded_controls_are_blocked_instead_of_silently_normalized(self):
        for text in ['명칭%0A','명칭%2509','명칭&#10;','명칭&amp;#9;',r'명칭\u000d',r'명칭\x00','명칭&#0;','명칭&#xD800;',r'명칭\u200b']:
            self.failure(text,'encoded_control','decoded')
    def test_nested_encoded_url_and_markup_still_blocked(self):
        self.failure('https%253A%252F%252Fprivate.invalid','forbidden_url_pattern','decoded')
        self.failure('&amp;lt;script&amp;gt;','unsafe_markup','decoded')
    def test_secret_split_across_raw_or_decoded_whitespace_is_blocked(self):
        for split in ['\r','\n','\t',' ','\r\n\t']:
            self.failure(FAKE[:5]+split+FAKE[5:],'credential_reflection')
        self.failure(FAKE[:5]+'%0A'+FAKE[5:],'credential_reflection','decoded')
        self.failure(''.join('%%%02X'%ord(c) for c in FAKE),'credential_reflection','decoded')
    def test_checks_run_on_both_original_and_normalized_surface(self):
        with patch.object(self.i,'_surface',wraps=self.i._surface) as check:
            self.i.text('국제\n수지',field='STAT_NAME')
        self.assertEqual(check.call_args_list[0].args[0],'국제\n수지')
        self.assertEqual(check.call_args_list[1].args[0],'국제 수지')
    def test_stage_attributes_are_allowlisted_twice_and_no_position_is_exposed(self):
        e=p.MetadataValidationError('STAT_NAME','format_control',stage='raw '+FAKE)
        self.assertEqual(p.diagnostic(e),dict(field='unknown',classification='validation_failed'))
        line=p.diagnostic_line(dict(field='STAT_NAME',classification='format_control',stage=FAKE,position=123,raw=FAKE))
        self.assertNotIn(FAKE,line);self.assertNotIn('123',line)
    def test_failure_summary_has_only_fixed_class_and_stage(self):
        c=Fixture();c.tables[0]['STAT_NAME']='PRIVATE_NAME\u200b'
        r=p.inspect(c,self.i);self.assertEqual(r['error_diagnostic']['stage'],'raw')
        body=p.summary(r);self.assertNotIn('PRIVATE_NAME',body);self.assertNotIn('200b',body)
        self.assertIn(p.cell('format_control'),body);self.assertIn('raw',body)
    def test_root_marker_and_classification_hierarchy_still_work(self):
        c=Fixture();c.tables=[dict(table('1000000000','국제\n수지','*'),SRCH_YN='N',CYCLE=None),table(parent='1000000000')]
        r=p.inspect(c,self.i);self.assertEqual(r['candidate_count'],1)
        self.assertTrue(all(not a or a[0]=='999Y999' for s,a in c.calls))

if __name__=='__main__':unittest.main()
