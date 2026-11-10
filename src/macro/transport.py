"""Bounded, robots-aware access to provided official public download links only."""
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import http.cookiejar
from ..discovery import NoRedirect

AGENT = 'currentourism-macro/0.5 (+https://github.com/Serhankeem/tourismnews; public statistical downloads)'
HOST = 'datalab.visitkorea.or.kr'
PATHS = {'/datalab/portal/main/getMainForm.do', '/site/portal/ex/bbs/View.do', '/common/board/Download.do',
         '/datalab/portal/ts/getEntcnyFrgnCust2Form.do', '/site/portal/ex/bbs/List.do'}

class AccessError(ValueError): pass

class Loader:
    def __init__(self, timeout=25):
        self.timeout=timeout; self.rules=None; self.last=0
        # Anonymous public navigation needs the session issued by the homepage.
        # Memory only: no login, cookie export, persisted credentials or JS APIs.
        self.opener=urllib.request.build_opener(NoRedirect,urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def __call__(self,url):
        for _ in range(5):
            p=urllib.parse.urlsplit(url)
            if p.scheme!='https' or p.hostname!=HOST or p.username or p.password or p.port not in (None,443) or p.fragment or p.path not in PATHS:
                raise AccessError('unapproved_public_statistical_endpoint')
            if p.path=='/site/portal/ex/bbs/List.do' and urllib.parse.parse_qs(p.query,keep_blank_values=True)!={'cbIdx':['1603'],'tgtTypeCd':['CATE_CONT'],'searchKey2':['spt01']}:
                raise AccessError('unapproved_public_statistical_catalog')
            if p.path=='/datalab/portal/ts/getEntcnyFrgnCust2Form.do' and (p.query or p.fragment):
                raise AccessError('unapproved_public_statistical_catalog')
            if self.rules is None:
                try:
                    with self.opener.open(urllib.request.Request('https://'+HOST+'/robots.txt',headers={'User-Agent':AGENT}),timeout=self.timeout) as r:body=r.read(200001)
                    if len(body)>200000 or b'<html' in body[:1000].lower():raise AccessError('robots_invalid')
                    rules=urllib.robotparser.RobotFileParser();rules.parse(body.decode('utf-8').splitlines());self.rules=rules
                except urllib.error.HTTPError as exc:
                    if exc.code!=404:raise AccessError('robots_http_'+str(exc.code)) from None
                    rules=urllib.robotparser.RobotFileParser();rules.parse([]);self.rules=rules
            if not self.rules.can_fetch(AGENT,url):raise AccessError('robots_disallowed')
            delay=max(.3,self.rules.crawl_delay(AGENT) or self.rules.crawl_delay('*') or 0)
            rate=self.rules.request_rate(AGENT) or self.rules.request_rate('*')
            if rate and rate.requests:delay=max(delay,rate.seconds/rate.requests)
            if delay>10:raise AccessError('crawl_delay_requires_deferred_fetch')
            time.sleep(max(0,delay-(time.monotonic()-self.last)));self.last=time.monotonic()
            try:
                with self.opener.open(urllib.request.Request(url,headers={'User-Agent':AGENT}),timeout=self.timeout) as r:body=r.read(16*1024*1024+1)
                if len(body)>16*1024*1024:raise AccessError('response_too_large')
                return body
            except urllib.error.HTTPError as exc:
                if exc.code in (301,302,303,307,308) and exc.headers.get('Location'):
                    url=urllib.parse.urljoin(url,exc.headers['Location']);continue
                raise AccessError('http_'+str(exc.code)) from None
        raise AccessError('redirect_limit')
