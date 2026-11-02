"""Reuse existing robots/TLS/redirect guards. POST is public catalog search only."""
import time
import urllib.parse
import urllib.request
import urllib.error
from ..discovery import Loader, USER_AGENT, AccessBlocked

class CatalogLoader(Loader):
    def __init__(self,allowed_hosts,allowed_forms=()):
        super().__init__();self.allowed_hosts=set(allowed_hosts);self.allowed_forms=set(allowed_forms)
        original_open=self.opener.open
        def checked_open(request, *args, **kwargs):
            try:
                response=original_open(request,*args,**kwargs)
            except urllib.error.HTTPError as exc:
                if exc.code in (301,302,303,307,308):
                    target=urllib.parse.urljoin(request.full_url,exc.headers.get('Location',''))
                    if urllib.parse.urlsplit(target).hostname not in self.allowed_hosts:raise AccessBlocked('unapproved_report_redirect_host')
                raise
            if response.headers.get('Content-Type','').lower().startswith(('application/pdf','image/','application/zip','application/octet-stream','application/vnd.ms','application/vnd.openxmlformats')):
                response.close();raise AccessBlocked('report_binary_response_prohibited')
            return response
        self.opener.open=checked_open
    def __call__(self,url,form=None):
        parts=urllib.parse.urlsplit(url)
        if parts.scheme!='https' or parts.hostname not in self.allowed_hosts or parts.username or parts.password:raise AccessBlocked('unapproved_report_endpoint')
        if parts.path.lower().endswith(('.pdf','.jpg','.jpeg','.png','.webp','.svg','.gif','.avif','.xls','.xlsx','.doc','.docx','.ppt','.pptx','.zip')):raise AccessBlocked('report_binary_download_prohibited')
        if form is None:
            # Loader checks each redirect's robots. A redirect cannot silently
            # switch the source identity to another domain.
            result=super().__call__(url)
        else:
            if url not in self.allowed_forms:raise AccessBlocked('unapproved_catalog_form')
            base,rules=self._rules(url)
            if rules is None:raise AccessBlocked('robots_unverified')
            if not rules.can_fetch(USER_AGENT,url):raise AccessBlocked('robots_disallowed')
            delay=max(.15,rules.crawl_delay(USER_AGENT) or rules.crawl_delay('*') or 0)
            rate=rules.request_rate(USER_AGENT) or rules.request_rate('*')
            if rate and rate.requests:delay=max(delay,rate.seconds/rate.requests)
            if delay>5:raise AccessBlocked('crawl_delay_requires_deferred_fetch')
            time.sleep(max(0,delay-(time.monotonic()-self.last_request.get(base,0))))
            req=urllib.request.Request(url,data=urllib.parse.urlencode(form).encode(),headers={'User-Agent':USER_AGENT,'Content-Type':'application/x-www-form-urlencoded'})
            self.last_request[base]=time.monotonic()
            with self.opener.open(req,timeout=self.timeout) as response:
                if response.headers.get('Content-Type','').lower().startswith(('application/pdf','image/','application/zip','application/octet-stream','application/vnd.ms','application/vnd.openxmlformats')):raise AccessBlocked('report_binary_response_prohibited')
                result=response.read(2*1024*1024+1)
        if len(result)>2*1024*1024:raise ValueError('catalog_metadata_response_too_large')
        if result.lstrip().startswith((b'%PDF',b'PK\x03\x04')):raise AccessBlocked('report_binary_response_prohibited')
        return result
