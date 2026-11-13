"""SYNTHETIC XLSX only. Official files/values stay in external Step 7 evidence."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.macro import aviation as a, aviation_series as ledger
from src.macro.engine import collect, public_view
from src.macro.xlsx import workbook
from tools.validate_aviation_foundation import private_config, test_config, safe_path, run
from test_macro import make_xlsx

NOW=dt.datetime(2026,11,13,12,tzinfo=dt.timezone.utc)


def values(period, corrected=False):
    n=(int(period[:4])-2021)*12+int(period[5:])
    ops=[100+n,110+n,210+2*n];pax=[1000+10*n,1100+10*n,2100+20*n]
    if corrected and period=='2021-01':
        ops[0]+=1;ops[2]+=1
    return dict(operations=ops,passengers=pax)


def headers(start,end,time=True):
    cells=dict(D1='시계열 통계' if time else '공항별 통계',A3='검색 기간',B3=start.replace('-','.')+'~'+end.replace('-','.'),
        A4='공항 구분',B4=','.join(a.AIRPORTS),A5='노선 구분',B5='국제선',C5='운항 구분',D5='전체',
        E5='여객기/화물기 구분',F5='전체',G5='여객 구분',H5='전체',I5='화물 구분',J5='전체',A7='공항명')
    cells.update(dict(B7='연도',C7='월',D7='운항(편)',G7='여객(명)',J7='화물(톤)',K5='연도/월 구분',L5='월별') if time
                 else dict(B7='운항(편)',E7='여객(명)',H7='화물(톤)'))
    for cols in ('DEF','GHI') if time else ('BCD','EFG'):
        cells.update({c+'8':s for c,s in zip(cols,('도착','출발','계'))})
    return cells


def entry(cells,start,end,time=True,corrected=False):
    filters=[['AIRPORT_CHK',c] for c in a.CODES]
    filters += [[k,v] for k,v in dict(LINE_TYPE='1',RAGUL_TYPE='',USE_TYPE='',PASS_TYPE='',CAGO_TYPE='',
        ST_YY=start[:4],EN_YY=end[:4],ST_MM=start[5:],EN_MM=end[5:]).items()]
    filters.append(['YM_TYPE','MMMM'] if time else ['INOUT_TYPE','0'])
    payload=make_xlsx({'MENU':cells})
    meta=dict(kind='national_time_series_original' if time else 'national_airport_breakdown_original',
        path=('history-' if time else 'airport-')+start+'-'+end+'.xlsx',bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),download_url=a.TIME_URL if time else a.AIRPORT_URL,
        retrieved_at='2026-11-13T03:00:00Z' if corrected else '2026-11-12T03:00:00Z',
        original_publication_at=None,finality='not_stated',filters=filters)
    return dict(payload=payload,metadata=meta)


def put(cells,row,vals,time=True):
    for metric,cols in zip(a.IDS,('DEF','GHI') if time else ('BCD','EFG')):
        cells.update({c+str(row):str(n) for c,n in zip(cols,vals[metric])})


def synthetic_file(start,end,corrected=False):
    c=headers(start,end);row=9;all_values=[]
    for month in range(int(start[5:]),int(end[5:])+1):
        selected=[]
        for year in range(int(start[:4]),int(end[:4])+1):
            p=f'{year:04}-{month:02}';v=values(p,corrected);selected.append(v);all_values.append(v)
            c.update({f'A{row}':'선택 공항',f'B{row}':str(year),f'C{row}':f'{month:02}'});put(c,row,v);row+=1
        c[f'B{row}']=f'{month:02}월 소계';put(c,row,{k:[sum(v[k][n] for v in selected) for n in range(3)] for k in a.IDS});row+=1
    c[f'A{row}']='합계';put(c,row,{k:[sum(v[k][n] for v in all_values) for n in range(3)] for k in a.IDS})
    return entry(c,start,end,corrected=corrected)


def breakdown(period):
    c=headers(period,period,False);c['A9']='인천';c['A10']='김포';c['A11']='합계'
    v=values(period);first={k:[n//2 for n in triple[:2]] for k,triple in v.items()}
    for k in first:first[k].append(sum(first[k]))
    rest={k:[v[k][n]-first[k][n] for n in range(3)] for k in a.IDS}
    put(c,9,first,False);put(c,10,rest,False);put(c,11,v,False)
    return entry(c,period,period,False)


def fixture(corrected=False):
    config=private_config();config['sources'][0].update(start_period='2021-01',end_period='2022-12')
    bundle=[synthetic_file('2021-01','2022-10',corrected),synthetic_file('2021-11','2022-12',corrected),
            breakdown('2021-09'),breakdown('2022-09')]
    return config,bundle


def changed(original,fn):
    e=copy.deepcopy(original);c=workbook(e['payload'])['MENU'];fn(c)
    e['payload']=make_xlsx({'MENU':c});e['metadata'].update(bytes=len(e['payload']),sha256=hashlib.sha256(e['payload']).hexdigest())
    return e


class AviationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.config,self.bundle=fixture();self.source=self.config['sources'][0];self.items=self.config['indicators']

    def snapshot(self,bundle=None):
        return a.snapshot(self.source,self.items,self.bundle if bundle is None else bundle,NOW)

    def test_matrix_months_complete_pair_integer_units_and_scope(self):
        first=a.parse_file(self.bundle[0],NOW)
        self.assertEqual(len(first['data']),20)
        snap=self.snapshot();self.assertEqual(sum(map(len,snap['records'].values())),48)
        for metric,key in a.IDS.items():
            rows=snap['records'][key];self.assertEqual(len(rows),24)
            self.assertEqual(rows['2021-01']['value'],values('2021-01')[metric][2])
            for r in rows.values():
                self.assertIs(type(r['value']),int);self.assertEqual(r['unit'],a.UNITS[metric])
                self.assertEqual(r['scope'],a.SCOPE);self.assertEqual(r['finality'],'not_stated')
                self.assertIsNone(r['original_publication_at']);self.assertIsNone(r['release_published_at'])
        self.assertEqual(snap['checked_breakdown_periods'],['2021-09','2022-09'])
        self.assertFalse(snap['independent_crosscheck_complete'])

    def test_hash_size_url_and_retrieval_provenance_fail_closed(self):
        for field,value in [('sha256','0'*64),('bytes',1),('download_url',a.AIRPORT_URL),
                            ('retrieved_at','2027-01-01T00:00:00Z'),('retrieved_at','2026-11-12'),
                            ('original_publication_at','2026-11-12'),('finality','final')]:
            bundle=copy.deepcopy(self.bundle);bundle[0]['metadata'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):self.snapshot(bundle)

    def test_html_relabelled_as_xlsx_is_rejected_even_with_matching_hash(self):
        e=copy.deepcopy(self.bundle[0]);e['payload']=b'<html>503 Service Unavailable</html>'
        e['metadata'].update(sha256=hashlib.sha256(e['payload']).hexdigest(),bytes=len(e['payload']))
        with self.assertRaisesRegex(ValueError,'xlsx'):self.snapshot([e,*self.bundle[1:]])

    def test_units_scope_direction_frequency_and_airport_labels_reject(self):
        for field,value in [('B5','국내선'),('D5','정기'),('F5','여객기'),('H5','유임'),('L5','연도별'),
                            ('D7','운항(천편)'),('G7','여객(천명)'),('D8','출발'),('B4',','.join(a.AIRPORTS[:-1]))]:
            e=changed(self.bundle[0],lambda c:c.update({field:value}))
            with self.subTest(field=field),self.assertRaises(ValueError):self.snapshot([e,*self.bundle[1:]])

    def test_actual_request_filters_cannot_disagree_with_export_labels(self):
        for key,value in [('LINE_TYPE','0'),('RAGUL_TYPE','정기'),('USE_TYPE','P'),('PASS_TYPE','1'),
                          ('YM_TYPE','YYYY'),('ST_MM','02')]:
            bundle=copy.deepcopy(self.bundle)
            for pair in bundle[0]['metadata']['filters']:
                if pair[0]==key:pair[1]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.snapshot(bundle)
        b=copy.deepcopy(self.bundle);b[0]['metadata']['filters']=[x for x in b[0]['metadata']['filters'] if x!=['AIRPORT_CHK','ICN']]
        with self.assertRaises(ValueError):self.snapshot(b)

    def test_duplicate_missing_out_of_range_rows_and_files_reject(self):
        changes=[lambda c:c.update(B10='2021',C10='01'),
                 lambda c:[c.pop(k) for k in list(c) if k.rstrip('0123456789') and k[len(k.rstrip('0123456789')):]=='9'],
                 lambda c:c.update(B9='2026',C9='11')]
        for fn in changes:
            with self.subTest(fn=fn),self.assertRaises(ValueError):self.snapshot([changed(self.bundle[0],fn),*self.bundle[1:]])
        with self.assertRaisesRegex(ValueError,'duplicate_file'):self.snapshot(self.bundle+[self.bundle[0]])
        other=changed(self.bundle[0],lambda c:c.update(A2='synthetic alternate export'))
        with self.assertRaisesRegex(ValueError,'overlapping'):self.snapshot(self.bundle+[other])
        with self.assertRaises(ValueError):self.snapshot(self.bundle[:1])

    def test_negative_decimal_exponent_blank_and_wrong_direction_totals_reject(self):
        for value in ['-1','0.5','1e2','','True','1,00']:
            with self.subTest(value=value),self.assertRaises(ValueError):self.snapshot([changed(self.bundle[0],lambda c:c.update(D9=value)),*self.bundle[1:]])
        with self.assertRaisesRegex(ValueError,'direction'):self.snapshot([changed(self.bundle[0],lambda c:c.update(F9='999')),*self.bundle[1:]])

    def test_supplement_range_shrink_and_partial_current_month_reject(self):
        self.source['end_period']='2022-11'
        with self.assertRaisesRegex(ValueError,'range_changed'):self.snapshot()
        self.source['end_period']='2022-12'
        with self.assertRaisesRegex(ValueError,'period_range'):a.snapshot(self.source,self.items,self.bundle,dt.datetime(2022,12,31,tzinfo=dt.timezone.utc))

    def test_breakdown_totals_duplicates_and_incheon_required(self):
        for fn in [lambda c:c.update(A9='김포'),lambda c:c.update(A9='제주'),lambda c:c.update(B11='999')]:
            e=changed(self.bundle[2],fn)
            with self.subTest(fn=fn),self.assertRaises(ValueError):self.snapshot([*self.bundle[:2],e,self.bundle[3]])
        e=copy.deepcopy(self.bundle[2]);e['metadata']['filters'][-1][1]='1'
        with self.assertRaises(ValueError):self.snapshot([*self.bundle[:2],e])

    def test_exact_yoy_uses_calendar_baseline_and_zero_is_not_missing(self):
        obs={'2021-01':{'value':3},'2022-01':{'value':4}}
        self.assertEqual(ledger.comparisons(obs,'2022-01')['yoy_pct'],'33.333333')
        self.assertIsNone(ledger.comparisons(obs,'2022-01')['mom_pct'])
        obs['2022-01']['value']=0
        self.assertEqual(ledger.comparisons(obs,'2022-01')['yoy_pct'],'-100.000000')
        obs['2021-01']['value']=0
        self.assertIsNone(ledger.comparisons(obs,'2022-01')['yoy_pct'])
        self.assertNotIn('ytd_value',ledger.comparisons(obs,'2022-01'))


class AviationLedgerTests(unittest.TestCase):
    setUp = AviationAdapterTests.setUp
    snapshot = AviationAdapterTests.snapshot
    def empty(self):return dict(schema_version=1,indicators={},sources={})

    def merged(self):return ledger.merge(self.empty(),self.source,self.items,self.snapshot(),NOW)[0]

    def test_idempotent_observations_revisions_and_original_vintage(self):
        old=self.merged();before=copy.deepcopy(old)
        new,counts=ledger.merge(old,self.source,self.items,self.snapshot(),NOW+dt.timedelta(days=1))
        self.assertEqual(counts['new_observations'],0);self.assertEqual(counts['unchanged_observations'],48)
        self.assertEqual(old,before);self.assertEqual(new['aviation_indicators'],old['aviation_indicators'])
        self.assertEqual(len(new['aviation_sources'][a.SOURCE]['vintages']),1)

    def test_changed_observation_keeps_before_after_and_first_collection(self):
        old=self.merged();cfg,bundle=fixture(True)
        snap=a.snapshot(cfg['sources'][0],cfg['indicators'],bundle,NOW+dt.timedelta(days=1))
        new,counts=ledger.merge(old,self.source,self.items,snap,NOW+dt.timedelta(days=1))
        key=a.IDS['operations'];prior=old['aviation_indicators'][key]['observations']['2021-01']
        revision=new['aviation_indicators'][key]['revisions'][0]
        self.assertEqual(counts['value_corrections'],1);self.assertEqual(revision['before'],prior)
        self.assertEqual(revision['kind'],'value_correction')
        self.assertEqual(revision['after']['first_collected_at'],prior['first_collected_at'])
        self.assertEqual(len(new['aviation_sources'][a.SOURCE]['vintages']),2)
        ledger.validate_archive(new,old)
        with self.assertRaisesRegex(ValueError,'stale'):ledger.merge(new,self.source,self.items,self.snapshot(),NOW+dt.timedelta(days=2))

    def test_identity_loss_unrecorded_revision_and_vintage_removal_reject(self):
        old=self.merged()
        for mode in ['unit','definition','scope','delete_month','delete_series','alter_value','delete_vintage']:
            broken=copy.deepcopy(old);key=a.IDS['operations'];s=broken['aviation_indicators'][key]
            if mode=='unit':s['unit']='천편'
            elif mode=='definition':s['definition']='changed definition'
            elif mode=='scope':s['scope']['direction']='departures_only'
            elif mode=='delete_month':s['observations'].pop('2021-02')
            elif mode=='delete_series':broken['aviation_indicators'].pop(key)
            elif mode=='delete_vintage':broken['aviation_sources'][a.SOURCE]['vintages']=[]
            else:s['observations']['2021-01']['value']+=1;s['observations']['2021-01']['arrivals']+=1
            with self.subTest(mode=mode),self.assertRaises(ValueError):ledger.validate_archive(broken,old)
        snap=self.snapshot();snap['records'][a.IDS['operations']].pop('2021-02')
        with self.assertRaises(ValueError):ledger.merge(old,self.source,self.items,snap,NOW+dt.timedelta(days=1))

    def test_invalid_second_metric_never_changes_old_pair(self):
        old=self.merged();before=copy.deepcopy(old);snap=self.snapshot()
        snap['records'][a.IDS['passengers']]['2021-01']['unit']='천명'
        with self.assertRaises(ValueError):ledger.merge(old,self.source,self.items,snap,NOW+dt.timedelta(days=1))
        self.assertEqual(old,before)

    def test_collection_and_publication_are_separate_and_default_off(self):
        config=private_config();source=config['sources'][0]
        self.assertFalse(source['enabled']);self.assertFalse(source['automatic_download'])
        self.assertTrue(all(not i['enabled'] for i in config['indicators']))
        self.assertTrue(all(not x['approved'] for x in source['approval'].values()))
        self.assertFalse(a.reviewed(source,NOW))
        for field in a.REVIEWS:
            cfg=test_config(self.config,NOW);cfg['sources'][0][field]['status']='review'
            self.assertFalse(a.reviewed(cfg['sources'][0],NOW))
        cfg=test_config(self.config,NOW)
        self.assertFalse(cfg['sources'][0]['approval']['publication']['approved'])
        archive=self.merged()
        for item in cfg['indicators']:item.update(enabled=True,publication_status='approved')
        cfg['sources'][0]['approval']['publication']['approved']=True
        self.assertEqual(public_view(cfg,archive,NOW)['indicators'],[])
        cfg['indicators'][0]['value_kind']='persons'
        self.assertEqual(public_view(cfg,archive,NOW)['indicators'],[])

    def test_engine_no_transport_default_off_or_without_manual_input(self):
        with tempfile.TemporaryDirectory() as tmp,patch('src.macro.engine.aviation.fetch',side_effect=AssertionError('no fetch')):
            p=Path(tmp)
            result=collect(self.config,p/'data',p/'state',now=NOW,force=True,aviation_bundle=self.bundle)
            self.assertEqual(result['attempted_sources'],0);self.assertFalse((p/'state/macro_archive.json').exists())
            cfg=test_config(self.config,NOW)
            result=collect(cfg,p/'data',p/'state',now=NOW,force=True)
            self.assertEqual(result['attempted_sources'],0)
            self.assertEqual(result['sources'][0]['collection_state'],'waiting_for_manual_input')
        with self.assertRaisesRegex(ValueError,'not_approved'):a.fetch(self.source,self.items,self.bundle,NOW)

    def test_engine_private_success_failure_and_legacy_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);state=p/'state';data=p/'data';state.mkdir();data.mkdir()
            old=self.empty();old['indicators']['legacy']=dict(unit='명',observations={'2021-01':dict(value=12,unit='명',first_collected_at='2021-02-01')},revisions=[])
            old['sources']['legacy']=dict(last_successful_check='2026-11-01')
            path=state/'macro_archive.json';path.write_text(json.dumps(old))
            public=data/'macro.json';public.write_text('{"indicators":[],"preserve":"EXACT BYTES"}')
            health=data/'macro_health.json';health.write_text('{"preserve":true}')
            before={f:f.read_bytes() for f in (public,health)}
            cfg=test_config(self.config,NOW)
            kwargs=dict(config=cfg,data_dir=data,state_dir=state,now=NOW,force=True,only_sources={a.SOURCE})
            result=collect(**kwargs,aviation_bundle=self.bundle)
            self.assertEqual(result['new_observations'],48)
            current=json.loads(path.read_text());self.assertEqual(current['indicators'],old['indicators']);self.assertEqual(current['sources'],old['sources'])
            self.assertTrue(all(f.read_bytes()==b for f,b in before.items()))
            saved=path.read_bytes();bad=copy.deepcopy(self.bundle);bad[0]['payload']=b'INVALID'
            result=collect(**kwargs,aviation_bundle=bad)
            self.assertEqual(result['successful_sources'],0);self.assertEqual(path.read_bytes(),saved)
            self.assertTrue(all(f.read_bytes()==b for f,b in before.items()))

    def test_offline_tool_rejects_checkout_existing_and_escaping_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):run(tmp,tmp,tmp,NOW)
            with self.assertRaises(ValueError):safe_path(Path(tmp),'../escape.xlsx')
            with self.assertRaises(ValueError):safe_path(Path(tmp),'/absolute.xlsx')
        root=Path(__file__).resolve().parents[1]
        with self.assertRaises(ValueError):run('/nonexistent','/nonexistent',root/'forbidden-step9-output',NOW)


if __name__=='__main__':unittest.main()
