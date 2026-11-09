"""Reduced real public HTML controls + synthetic XLS/HTTP boundaries; no live I/O."""
import copy
import datetime as dt
from email.message import Message
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import BaseHandler, HTTPCookieProcessor
from urllib.response import addinfourl
from src.macro import kto
from src.macro.engine import collect
from src.macro.transport import Loader, AccessError
from test_macro import make_xlsx, primary, CORE, CONFIG

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'fixtures/kto-release-discovery'
NOW=dt.datetime(2026,11,9,15,tzinfo=dt.timezone(dt.timedelta(hours=9)))
HOME=CONFIG['sources'][0]['catalog_url']
STATS=kto.BASE+kto.STATISTICS_PATH
BOARD=kto.BASE+kto.CATALOG_PATH+'?cbIdx=1603&tgtTypeCd=CATE_CONT&searchKey2=spt01'

def html(name):return (FIXTURE/(name+'.html')).read_bytes()

def pages():return {HOME:html('homepage'),STATS:html('statistics'),BOARD:html('board')}


class DiscoveryTests(unittest.TestCase):
    def test_real_controls_find_latest_despite_pinned_annual_notice(self):
        source=CONFIG['sources'][0];p=pages();calls=[]
        def load(url):calls.append(url);return p[url]
        period,url,catalog=kto.discover_release(source,load,NOW)
        self.assertEqual(period,'2026-09');self.assertIn('bcIdx=311425',url)
        self.assertIn('cbIdx=1603&cbIdx2=1127',url);self.assertEqual(catalog,BOARD)
        self.assertEqual(calls,[HOME,STATS,BOARD])

    def test_existing_go_url_and_corrected_titles_remain_supported(self):
        legacy='/site/portal/ex/bbs/View.do?cbIdx=1127&bcIdx=311425&cateCont=spt01'
        for title in ['2026년 9월 한국관광통계 공표','[정정] 2026년 9월 한국관광통계 공표','2026년 9월 한국관광통계 공표(수정)']:
            payload='<a href="javascript:goUrl(\''+legacy+'\',\'10504040000002021100613\',\'3\')">'+title+'</a>'
            calls=[]
            def load(url):calls.append(url);return payload
            self.assertEqual(kto.discover_release(CONFIG['sources'][0],load,NOW),( '2026-09',kto.BASE+legacy,HOME))
            self.assertEqual(calls,[HOME])

    def test_malformed_blocked_or_absent_catalog_is_failure_not_no_change(self):
        for target in [HOME,STATS,BOARD]:
            for raw in [b'<html>Access denied</html>',b'<html>maintenance</html>',b'',b'{"items":[]}']:
                p=pages();p[target]=raw
                with self.subTest(target=target,raw=raw),self.assertRaises(ValueError):kto.discover_release(CONFIG['sources'][0],p.__getitem__,NOW)

    def test_foreign_http_credentials_wrong_board_and_ambiguous_controls_rejected(self):
        for old,new in [('cbIdx2=1127','cbIdx2=1125'),('cateCont=spt01','cateCont=spt04'),('cbIdx=1603','cbIdx=1125'),('bcIdx=311425','bcIdx=311425&bcIdx=2')]:
            with self.subTest(new=new),self.assertRaisesRegex(ValueError,'unapproved_release_link'):
                kto.latest_release(html('board').decode().replace(old,new),NOW)
        release=kto.latest_release(html('board'),NOW)[1]
        for url in [release.replace('https:','http:'),release.replace('datalab.visitkorea.or.kr','evil.example'),release.replace('https://','https://user:pass@'),release+'#unverified']:
            with self.assertRaises(ValueError):kto.release_url(url)
        for name in ['homepage','statistics']:
            p=pages();key=HOME if name=='homepage' else STATS
            p[key]=html(name).decode().replace('/datalab/portal/ts/', 'https://evil.example/datalab/portal/ts/') if name=='homepage' else html(name).decode().replace('../../../site/','https://evil.example/site/')
            with self.assertRaises(ValueError):kto.discover_release(CONFIG['sources'][0],p.__getitem__,NOW)
        p=pages();p[STATS]=html('statistics')+html('statistics')
        with self.assertRaisesRegex(ValueError,'control_unverified'):kto.discover_release(CONFIG['sources'][0],p.__getitem__,NOW)

    def test_actual_release_rights_date_and_download_checks_retained(self):
        url=kto.latest_release(html('board'),NOW)[1]
        files,date=kto.release_files(html('release'),url,'2026-09',NOW)
        self.assertEqual(date,'2026-10-28T10:10:00+09:00');self.assertEqual(set(files),{'series','crosscheck'})
        for old,new,error in [('img_opentype00','img_opentype01','rights'),('2026.10.28 10:10','not a date','date_unverified'),('2026.10.28 10:10','2026.11.10 10:10','future_release_date'),('2026년 9월','2026년 8월','reference_mismatch'),('&#x27;1127&#x27;','&#x27;1125&#x27;','download_control')]:
            with self.subTest(error=error),self.assertRaisesRegex(ValueError,error):kto.release_files(html('release').decode().replace(old,new),url,'2026-09',NOW)

    def test_complete_fetch_uses_only_public_controls_and_checks_both_synthetic_workbooks(self):
        p=pages();_,release=kto.latest_release(p[BOARD],NOW);p[release]=html('release')
        downloads,_=kto.release_files(p[release],release,'2026-09',NOW)
        p[downloads['series']]=make_xlsx(primary())
        p[downloads['crosscheck']]=make_xlsx({'성별 입국(9월)':{'A1':'성별국적별입국 (2026년 9월)','C3':'인원(명)','C4':200,'D4':100},'성별 출국':{'A1':'성별출국','B3':'인원(명)','A13':'9월','B13':220,'C13':110}})
        calls=[]
        def load(url):calls.append(url);return p[url]
        r=kto.fetch(CONFIG['sources'][0],CORE,load,NOW)
        self.assertEqual(r['discovery_catalog_url'],BOARD);self.assertEqual(r['values']['kto_inbound']['2026-09'],200)
        self.assertEqual(len(calls),6);self.assertTrue(all('/portal/getChk' not in c and '/goUrl.do' not in c for c in calls))


class CookieFixture(BaseHandler):
    handler_order=100
    def __init__(self,redirect=False,robots=False):self.calls=[];self.redirect=redirect;self.robots=robots
    def https_open(self,req):
        self.calls.append(req.full_url);headers=Message();code=200
        if req.full_url.endswith('/robots.txt'):
            body=b'User-agent: *\n'+(b'Disallow: /site/portal/ex/bbs/List.do\n' if self.robots else b'Allow: /\n')
        elif req.full_url==HOME:
            headers['Set-Cookie']='KTO_PUBLIC_SESSION=SYNTHETIC_ONLY; Path=/; Secure; HttpOnly';body=html('homepage')
        elif req.full_url==STATS:body=html('statistics')
        else:
            if self.redirect or 'KTO_PUBLIC_SESSION=SYNTHETIC_ONLY' not in (req.get_header('Cookie') or ''):
                code=302;headers['Location']='http://datalab.visitkorea.or.kr/';body=b''
            else:body=html('board')
        response=addinfourl(io.BytesIO(body),headers,req.full_url,code);response.msg='Fixture response';return response


class TransportTests(unittest.TestCase):
    def test_anonymous_session_is_retained_without_cookie_files_or_login(self):
        loader=Loader();handler=CookieFixture();loader.opener.add_handler(handler)
        cookies=[h for h in loader.opener.handlers if isinstance(h,HTTPCookieProcessor)]
        self.assertEqual(len(cookies),1)
        with patch('src.macro.transport.time.sleep'):self.assertEqual(kto.discover_release(CONFIG['sources'][0],loader,NOW)[0],'2026-09')
        self.assertEqual(handler.calls,['https://datalab.visitkorea.or.kr/robots.txt',HOME,STATS,BOARD])
        self.assertEqual(len(cookies[0].cookiejar),1)

    def test_http_redirect_and_robots_denial_are_not_bypassed(self):
        for redirect,robots,code in [(True,False,'unapproved'),(False,True,'robots_disallowed')]:
            loader=Loader();handler=CookieFixture(redirect,robots);loader.opener.add_handler(handler)
            with patch('src.macro.transport.time.sleep'),self.assertRaisesRegex(AccessError,code):kto.discover_release(CONFIG['sources'][0],loader,NOW)
            self.assertTrue(all(u.startswith('https://') for u in handler.calls))

    def test_new_public_paths_reject_other_queries_before_network(self):
        for url in [BOARD.replace('spt01','spt04'),BOARD+'&searchKey2=spt01',BOARD.replace('1603','1125'),STATS+'?internal=true']:
            loader=Loader();handler=CookieFixture();loader.opener.add_handler(handler)
            with self.assertRaisesRegex(AccessError,'unapproved'):loader(url)
            self.assertEqual(handler.calls,[])


class PreservationTests(unittest.TestCase):
    def test_483_observations_survive_failure_retry_no_change_and_regression(self):
        cfg=copy.deepcopy(CONFIG);cfg['sources']=[cfg['sources'][0]]
        cfg['indicators']=[i for i in cfg['indicators'] if i['source_id']=='kto_monthly_statistics']
        old=json.loads((ROOT/'collector_state/macro_archive.json').read_text());self.assertEqual(sum(len(i['observations']) for i in old['indicators'].values()),483)
        with tempfile.TemporaryDirectory() as tmp:
            data,state=Path(tmp)/'data',Path(tmp)/'state';data.mkdir();state.mkdir()
            paths=[data/'macro.json',state/'macro_archive.json']
            paths[0].write_bytes((ROOT/'site/data/macro.json').read_bytes());paths[1].write_text(json.dumps(old))
            protected=[data/'newsroom.json',data/'reports.json',state/'archive.json']
            for p in protected:p.write_bytes(b'PRESERVE_OTHER_ENGINE_DATA')
            before=[p.read_bytes() for p in paths]
            def failed(url):return b'<html>Access denied</html>'
            h=collect(cfg,data,state,loader=failed,now=NOW,force=True)
            self.assertEqual(h['status'],'failed');self.assertEqual([p.read_bytes() for p in paths],before)
            snapshot=copy.deepcopy(old['sources']['kto_monthly_statistics']);snapshot['values']={k:{p:o['value'] for p,o in s['observations'].items()} for k,s in old['indicators'].items()}
            snapshot['locations']={k:dict(sheet=next(i['sheet'] for i in cfg['indicators'] if i['id']==k),cells={p:o['cell'] for p,o in s['observations'].items()}) for k,s in old['indicators'].items()}
            with patch('src.macro.kto.fetch',return_value=snapshot):h=collect(cfg,data,state,now=NOW,force=False)
            self.assertEqual(h['status'],'ok');self.assertEqual(h['new_observations'],0);self.assertEqual(h['unchanged_observations'],483)
            saved=json.loads(paths[1].read_text())
            for k,i in old['indicators'].items():
                self.assertEqual(saved['indicators'][k]['revisions'],i['revisions']);self.assertEqual(set(saved['indicators'][k]['observations']),set(i['observations']))
            # A source regressing behind the verified month is a failure, not success.
            snapshot['reference_period']='2026-08';stable=[p.read_bytes() for p in paths]
            with patch('src.macro.kto.fetch',return_value=snapshot):h=collect(cfg,data,state,now=NOW+dt.timedelta(days=1),force=True)
            self.assertEqual(h['sources'][0]['error_kind'],'older_official_snapshot_rejected');self.assertEqual([p.read_bytes() for p in paths],stable)
            for p in protected:self.assertEqual(p.read_bytes(),b'PRESERVE_OTHER_ENGINE_DATA')
