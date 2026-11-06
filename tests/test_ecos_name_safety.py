"""Synthetic STAT_NAME cases; no real Secret or authenticated response."""
import base64
import unittest
from src.macro import ecos_preflight as p
from test_ecos_preflight import FAKE,Fixture,table

class NameSafetyTests(unittest.TestCase):
    def setUp(self):self.i=p.Inspector(FAKE)
    def reason(self,value,field='STAT_NAME'):
        with self.assertRaises(p.MetadataValidationError) as e:self.i.text(value,field=field)
        return p.diagnostic(e.exception)['classification']
    def test_normal_bilingual_numeric_punctuation(self):
        for name in ['1. 국제수지 (월별, 원계열)','Balance of Payments (BPM6) / USD',
                     '금리(연%) · 20%20 증가','연구 & 시장: A+B - C = 100','A<B, C>D (1<2, 3>2)',
                     r'수출\수입 비교','수입 &amp; 지급','증감률 %41 (단위 %)','지수 [2020=100] #1 | 비교']:
            with self.subTest(name=name):self.assertEqual(self.i.text(name,field='STAT_NAME'),name)
    def test_unsafe_categories_independently(self):
        for value,reason in [('https://example.invalid/a','forbidden_url_pattern'),
            ('javascript:alert(1)','forbidden_url_pattern'),('<script>alert(1)</script>','unsafe_markup'),
            ('&lt;img src=x&gt;','unsafe_markup'),('통계\u200b명','format_control'),
            ('통계\x00명','other_unicode_control'),('통계\u202e명','format_control'),
            (FAKE,'credential_reflection'),(''.join('%%%02X'%ord(c) for c in FAKE),'credential_reflection'),
            (base64.b64encode(FAKE.encode()).decode(),'credential_reflection'),
            (''.join('\\u%04x'%ord(c) for c in FAKE),'credential_reflection')]:
            with self.subTest(reason=reason):self.assertEqual(self.reason(value),reason)
    def test_nested_and_obfuscated_attacks(self):
        for value in ['https%253A%252F%252Fexample.invalid',r'\u003cscript\u003e',
            ''.join('\\\\u%04x'%ord(c) for c in FAKE),FAKE.replace('_','&#95;'),
            '<svg onload=alert(1)>','data:text/html,evil','www.example.invalid',r'\x00']:
            with self.subTest(value=value):self.reason(value)
    def test_encoded_pattern_and_controls_still_rejected_for_other_fields(self):
        self.assertEqual(self.reason('%41',field='ITEM_NAME'),'encoded_pattern')
        self.assertEqual(self.reason(r'A\B',field='ITEM_NAME'),'encoded_pattern')
        self.assertEqual(self.reason(r'\uAC00'),'encoded_pattern')
    def test_catalogue_name_allowed_but_codes_not_relaxed(self):
        r=table(name=r'국제수지 & 시장\분류 (20%20)',parent='*')
        self.assertIsNone(self.i.catalogue([r])['999Y999']['parent'])
        for field in ['STAT_CODE','P_STAT_CODE']:
            bad=r.copy();bad[field]='%41'
            with self.assertRaises(p.MetadataValidationError):self.i.catalogue([bad])
    def test_diagnostic_and_summary_never_print_bad_or_good_stat_names(self):
        c=Fixture();c.tables[0]['STAT_NAME']='https://private.invalid/'+FAKE
        result=p.inspect(c,self.i);body=p.summary(result)
        self.assertEqual(result['error_diagnostic'],dict(field='STAT_NAME',classification='credential_reflection',stage='raw'))
        self.assertNotIn(FAKE,body);self.assertNotIn('private.invalid',body)
        c=Fixture();result=p.inspect(c,self.i)
        self.assertNotIn(c.tables[0]['STAT_NAME'],p.summary(result))
    def test_no_row_is_silently_skipped(self):
        c=Fixture();c.tables.append(table('777Y777','<script>bad</script>'))
        result=p.inspect(c,self.i);self.assertEqual(result['status'],'failed')
        self.assertEqual(result['error_diagnostic']['classification'],'unsafe_markup')
    def test_escaping_remains_at_output_boundary(self):
        rendered=p.cell('A&B < 10 | [x](y)')
        self.assertIn('&amp;',rendered);self.assertIn('&lt;',rendered);self.assertIn('\\|',rendered)

if __name__=='__main__':unittest.main()
