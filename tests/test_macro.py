"""Synthetic fixtures stay in temporary directories; published data is real official XLSX."""
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from xml.sax.saxutils import escape
from src.macro import kto
from src.macro.engine import collect
from src.macro.model import comparisons, months, valid_period
from src.macro.xlsx import workbook
from src.macro.transport import Loader

NOW=dt.datetime(2026,10,30,12,tzinfo=dt.timezone(dt.timedelta(hours=9)))
ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'macro_sources.json').read_text())
CORE=[copy.deepcopy(i) for i in CONFIG['indicators'] if i['id'] in ('kto_inbound','kto_outbound')]

def make_xlsx(sheets):
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'+''.join(f'<sheet name="{escape(name)}" sheetId="{n}" r:id="rId{n}"/>' for n,name in enumerate(sheets,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships>'+''.join(f'<Relationship Id="rId{n}" Target="worksheets/sheet{n}.xml"/>' for n in range(1,len(sheets)+1))+'</Relationships>')
        for n,cells in enumerate(sheets.values(),1):
            rows={}
            for key,value in cells.items():
                row=''.join(c for c in key if c.isdigit());rows.setdefault(row,[]).append(f'<c r="{key}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
            z.writestr(f'xl/worksheets/sheet{n}.xml',f'<worksheet xmlns="{ns}"><sheetData>'+''.join(f'<row r="{r}">'+''.join(cells)+'</row>' for r,cells in rows.items())+'</sheetData></worksheet>')
    return buffer.getvalue()

def primary():
    return {'입국':{'A1':'［ 입 국 ］','A3':'Country','A4':'G.TOTAL','A6':'Foreign Visitors','C3':'2025.9월','D3':'2026.8월','E3':'2026.9월','F3':'2026.10월','C4':100,'D4':180,'E4':200,'E6':190},'출국':{'A1':'［ 출 국 ］','A3':'Destination','A4':'G.TOTAL','A6':'Departures Korean','C3':'2025.9월','D3':'2026.8월','E3':'2026.9월','C4':110,'D4':210,'E4':220,'E6':200}}

def snapshot():
    values={CORE[0]['id']:{'2025-09':100,'2026-08':180,'2026-09':200},CORE[1]['id']:{'2025-09':110,'2026-08':210,'2026-09':220}}
    return dict(reference_period='2026-09',source_url='https://datalab.visitkorea.or.kr/site/portal/ex/bbs/View.do?cbIdx=1127&bcIdx=1&cateCont=spt01',release_published_at='2026-10-28T10:10:00+09:00',values=values,locations={k:dict(sheet='입국' if k=='kto_inbound' else '출국',cells={p:'E4' for p in v}) for k,v in values.items()},file_url='https://datalab.visitkorea.or.kr/common/board/Download.do?fixture.xlsx',file_sha256='synthetic-fixture-only',crosscheck_url='https://datalab.visitkorea.or.kr/common/board/Download.do?crosscheck.xlsx',crosscheck_sha256='synthetic-fixture-only',rights='KOGL-0',method='official_public_xlsx')

class CalendarTests(unittest.TestCase):
    def test_separate_mom_and_yoy(self):
        r=comparisons({p:{'value':v} for p,v in [('2025-09',100),('2026-08',150),('2026-09',200)]},'2026-09');self.assertEqual(r['yoy_pct'],100);self.assertEqual(r['mom_pct'],33.33)
    def test_missing_calendar_month_not_previous_available(self):
        self.assertIsNone(comparisons({'2026-07':{'value':100},'2026-09':{'value':200}},'2026-09')['mom_pct'])
    def test_zero_baseline_no_rate(self):
        self.assertIsNone(comparisons({'2025-09':{'value':0},'2026-09':{'value':10}},'2026-09')['yoy_pct'])
    def test_zero_current_is_real_negative_hundred(self):
        self.assertEqual(comparisons({'2025-09':{'value':10},'2026-09':{'value':0}},'2026-09')['yoy_pct'],-100)
    def test_ytd_requires_complete_calendar(self):
        self.assertIsNone(comparisons({'2026-02':{'value':10}},'2026-02')['ytd_value'])
    def test_ytd_and_prior_ytd_not_monthly_yoy(self):
        obs={p:{'value':v} for p,v in [('2025-01',10),('2025-02',30),('2026-01',20),('2026-02',40)]}
        r=comparisons(obs,'2026-02');self.assertEqual(r['ytd_value'],60);self.assertEqual(r['ytd_yoy_pct'],50);self.assertEqual(r['yoy_pct'],33.33)
    def test_january_mom_uses_december(self):
        self.assertEqual(comparisons({'2025-12':{'value':10},'2026-01':{'value':20}},'2026-01')['mom_pct'],100)
    def test_period_and_missing_month_span(self):
        self.assertEqual(months('2025-12','2026-02'),['2025-12','2026-01','2026-02'])
        for bad in ['2026','2026-13','2026-00','2026-1']:
            with self.assertRaises(ValueError):valid_period(bad)

class OfficialFileTests(unittest.TestCase):
    def test_total_rows_include_defined_crews_and_overseas_categories(self):
        values,_=kto.parse_series(make_xlsx(primary()),'2026-09',CORE,'2025-01');self.assertEqual(values['kto_inbound']['2026-09'],200);self.assertEqual(values['kto_outbound']['2026-09'],220)
    def test_future_blank_is_missing_not_zero(self):
        v,_=kto.parse_series(make_xlsx(primary()),'2026-09',CORE,'2025-01');self.assertNotIn('2026-10',v['kto_inbound'])
    def test_populated_future_cell_rejected(self):
        p=primary();p['입국']['F4']=10
        with self.assertRaisesRegex(ValueError,'data_after_release'):kto.parse_series(make_xlsx(p),'2026-09',CORE,'2025-01')
    def test_changed_total_header_rejected(self):
        p=primary();p['입국']['A4']='Foreign Visitors'
        with self.assertRaisesRegex(ValueError,'total_row'):kto.parse_series(make_xlsx(p),'2026-09',CORE,'2025-01')
    def test_duplicate_months_rejected(self):
        p=primary();p['입국']['F3']='2026.9월';p['입국']['F4']=200
        with self.assertRaisesRegex(ValueError,'duplicate_reference'):kto.parse_series(make_xlsx(p),'2026-09',CORE,'2025-01')
    def test_negative_decimal_nonfinite_counts_rejected(self):
        for value in ['-1','1.5','NaN','inf']:
            with self.assertRaises(ValueError):kto.count(value)
    def test_html_challenge_not_a_workbook(self):
        with self.assertRaisesRegex(ValueError,'not_html'):workbook(b'<html>Access blocked</html>')
    def test_public_release_discovery_rejects_future_or_absent_headline(self):
        with self.assertRaisesRegex(ValueError,'future_reference'):kto.latest_release(b'<a>2026\xeb\x85\x84 10\xec\x9b\x94 \xed\x95\x9c\xea\xb5\xad\xea\xb4\x80\xea\xb4\x91\xed\x86\xb5\xea\xb3\x84 \xea\xb3\xb5\xed\x91\x9c</a>',NOW)
        with self.assertRaisesRegex(ValueError,'not_advertised'):kto.latest_release(b'<html>maintenance</html>',NOW)
    def test_explicit_corrected_release_headlines_keep_original_period(self):
        for title in ['[정정] 2026년 9월 한국관광통계 공표','2026년 9월 한국관광통계 공표(수정)']:
            html='<a href="https://datalab.visitkorea.or.kr/site/portal/ex/bbs/View.do?cbIdx=1127&amp;bcIdx=2&amp;cateCont=spt01">'+title+'</a>'
            self.assertEqual(kto.latest_release(html,NOW)[0],'2026-09')
    def test_units_and_latest_separate_tables_crosscheck(self):
        v,_=kto.parse_series(make_xlsx(primary()),'2026-09',CORE,'2025-01')
        x={'성별 입국(9월)':{'A1':'성별국적별입국 (2026년 9월)','C3':'인원(명)','C4':200,'D4':100},'성별 출국':{'A1':'성별출국','B3':'인원(명)','A13':'9월','B13':220,'C13':110}}
        kto.crosscheck(make_xlsx(x),'2026-09',v,CORE)
        x['성별 출국']['B13']=221
        with self.assertRaisesRegex(ValueError,'tables_disagree'):kto.crosscheck(make_xlsx(x),'2026-09',v,CORE)
    def test_thousand_person_unit_not_accepted_as_persons(self):
        v,_=kto.parse_series(make_xlsx(primary()),'2026-09',CORE,'2025-01')
        x={'성별 입국(9월)':{'A1':'성별국적별입국 (2026년 9월)','C3':'인원(천명)','C4':200},'성별 출국':{'A1':'성별출국','B3':'인원(명)','A13':'9월','B13':220,'C13':110}}
        with self.assertRaisesRegex(ValueError,'unit_unverified'):kto.crosscheck(make_xlsx(x),'2026-09',v,CORE)
    def test_release_rights_not_generic_ai_notice(self):
        url='https://datalab.visitkorea.or.kr/site/portal/ex/bbs/View.do?cbIdx=1127&bcIdx=1&cateCont=spt01'
        html='<p class="table-title">2026년 9월 한국관광통계 공표</p><div class="nuri"><img src="/images/portal/kogl/img_opentype01.png"></div>'
        with self.assertRaisesRegex(ValueError,'rights_changed'):kto.release_files(html,url,'2026-09',NOW)
    def test_transport_rejects_private_http_foreign_and_internal_api(self):
        for url in ['http://datalab.visitkorea.or.kr/','https://evil.example/file.xlsx','https://datalab.visitkorea.or.kr/datalab/internal/getData.do']:
            with self.assertRaisesRegex(ValueError,'unapproved'):Loader()(url)

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.data=self.base/'data';self.state=self.base/'state';self.config={'sources':[copy.deepcopy(CONFIG['sources'][0])],'indicators':copy.deepcopy(CORE)}
    def run_collect(self,payload=None,now=NOW,force=True,error=None):
        with patch('src.macro.kto.fetch',side_effect=error,return_value=payload or snapshot()):return collect(self.config,self.data,self.state,now=now,force=force)
    def archive(self):return json.loads((self.state/'macro_archive.json').read_text())
    def test_first_and_repeat_have_no_duplicate_months(self):
        self.assertEqual(self.run_collect()['new_observations'],6);r=self.run_collect();self.assertEqual(r['new_observations'],0);self.assertEqual(r['unchanged_observations'],6);self.assertEqual(len(self.archive()['indicators']['kto_inbound']['observations']),3)
    def test_official_correction_replaces_same_month_with_history(self):
        self.run_collect();s=snapshot();s['values']['kto_inbound']['2026-09']=201;s['file_sha256']='changed-fixture';r=self.run_collect(s);a=self.archive()['indicators']['kto_inbound'];self.assertEqual(r['value_corrections'],1);self.assertEqual(a['observations']['2026-09']['value'],201);self.assertEqual(len(a['observations']),3);self.assertEqual(a['revisions'][0]['before']['value'],200);self.assertEqual(a['revisions'][0]['after']['revision_status'],'revised')
    def test_provisional_final_transition_retained_separately(self):
        s=snapshot();s['finality']='provisional';self.run_collect(s);s['finality']='final';r=self.run_collect(s);self.assertEqual(r['status_changes'],6);self.assertEqual(r['value_corrections'],0)
    def test_network_failure_preserves_public_and_archive_bytes(self):
        self.run_collect();before=[p.read_bytes() for p in [self.data/'macro.json',self.state/'macro_archive.json']];r=self.run_collect(error=OSError('private credential example should not serialize'));self.assertEqual(r['status'],'failed');self.assertEqual(before,[p.read_bytes() for p in [self.data/'macro.json',self.state/'macro_archive.json']]);self.assertNotIn('credential example',json.dumps(r))
    def test_validation_failure_preserves_previous_data(self):
        self.run_collect();before=(self.data/'macro.json').read_bytes();s=snapshot();s['values']['kto_inbound']['2026-09']=-1;self.assertEqual(self.run_collect(s)['status'],'failed');self.assertEqual((self.data/'macro.json').read_bytes(),before)
    def test_older_release_never_rolls_back_newer_snapshot(self):
        self.run_collect();s=snapshot();s['reference_period']='2026-08';self.assertEqual(self.run_collect(s)['sources'][0]['error_kind'],'older_official_snapshot_rejected')
    def test_unit_or_definition_change_requires_review(self):
        self.run_collect();self.config['indicators'][0]['unit']='천 명';r=self.run_collect();self.assertEqual(r['status'],'failed');self.assertIn('unit_or_definition',r['sources'][0]['error_kind'])
    def test_missing_past_month_retains_prior_proof_and_flags_partial(self):
        self.run_collect();old=self.archive()['indicators']['kto_inbound']['observations']['2025-09'];s=snapshot();del s['values']['kto_inbound']['2025-09'];r=self.run_collect(s);self.assertEqual(r['status'],'partial');self.assertEqual(self.archive()['indicators']['kto_inbound']['observations']['2025-09'],old)
    def test_corrupt_or_missing_archive_never_recreated_from_public(self):
        self.run_collect();before=(self.data/'macro.json').read_bytes();(self.state/'macro_archive.json').write_text('{}');self.assertEqual(self.run_collect()['status'],'failed');self.assertEqual((self.data/'macro.json').read_bytes(),before);(self.state/'macro_archive.json').unlink();self.assertEqual(self.run_collect()['status'],'failed')
    def test_wrong_top_level_and_source_shapes_report_error_preserve_public(self):
        self.run_collect();before=(self.data/'macro.json').read_bytes()
        for invalid in [[],{'schema_version':1,'indicators':{},'sources':{'kto_monthly_statistics':[]}}]:
            (self.state/'macro_archive.json').write_text(json.dumps(invalid));self.assertEqual(self.run_collect()['status'],'failed');self.assertEqual((self.data/'macro.json').read_bytes(),before)
    def test_api_key_absence_is_pending_not_fetch_error(self):
        self.config['sources'].append(copy.deepcopy(CONFIG['sources'][1]))
        with patch.dict(os.environ,{},clear=True):r=self.run_collect()
        self.assertEqual(r['sources'][1]['status'],'not_connected');self.assertEqual(r['sources'][1]['credential_status'],'not_configured');self.assertEqual(r['status'],'ok')
    def test_daily_interval_respects_korean_day(self):
        self.run_collect()
        with patch('src.macro.kto.fetch',side_effect=AssertionError('should skip')):self.assertEqual(collect(self.config,self.data,self.state,now=NOW+dt.timedelta(hours=1))['status'],'not_due')
        self.assertEqual(self.run_collect(now=NOW+dt.timedelta(days=1),force=False)['status'],'ok')
    def test_pending_credentials_not_counted_or_logged(self):
        self.config['sources'].append(copy.deepcopy(CONFIG['sources'][1]))
        with patch.dict(os.environ,{'ECOS_API_KEY':'TEST_SENTINEL_NOT_A_REAL_KEY'}):r=self.run_collect()
        self.assertEqual(r['successful_sources'],1);self.assertEqual(r['sources'][1]['credential_status'],'configured_pending_mapping');self.assertNotIn('TEST_SENTINEL',json.dumps(r))
    def test_missing_month_and_zero_comparisons_stay_distinct(self):
        s=snapshot();s['values']['kto_inbound']['2025-09']=0;self.run_collect(s);p=json.loads((self.data/'macro.json').read_text())['indicators'][0];self.assertIsNone(p['latest']['comparisons']['yoy_pct']);self.assertIn('2025-10',p['missing_periods']);self.assertEqual(p['observations'][0]['value'],0)
    def test_unrelated_databases_not_written(self):
        self.data.mkdir();self.state.mkdir()
        protected=[self.data/'news.json',self.data/'reports.json',self.data/'research.json',self.state/'archive.json']
        for p in protected:p.write_text('PRESERVE THIS UNRELATED DB')
        self.run_collect()
        for p in protected:self.assertEqual(p.read_text(),'PRESERVE THIS UNRELATED DB')

class ConfigurationTests(unittest.TestCase):
    def test_distinct_financial_definitions_and_yearly_surveys(self):
        rows={i['id']:i for i in CONFIG['indicators']};self.assertNotEqual(rows['kto_tourism_receipts']['definition'],rows['bok_travel_credit']['definition']);self.assertFalse(rows['kto_tourism_receipts']['enabled']);self.assertEqual(rows['tourism_employment']['frequency'],'A');self.assertIsNone(rows['kto_tourism_receipts']['unit'])
    def test_same_publication_lock_and_no_archive_in_pages(self):
        for name in ['collect','reports','macro']:
            self.assertIn('uses: ./.github/workflows/pipeline.yml',(ROOT/f'.github/workflows/{name}.yml').read_text())
        text=(ROOT/'.github/workflows/pipeline.yml').read_text();self.assertIn('group: tourism-pulse-publish',text);self.assertIn('path: ${{ runner.temp }}/tourism-pages',text);self.assertNotIn('path: collector_state',text)

if __name__=='__main__':unittest.main()
