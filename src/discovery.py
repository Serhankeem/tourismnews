"""Metadata-only discovery adapters and robots-aware, bounded HTTP access.

Never follows candidate article links. A successful discovery is not a licence
or proof of publication date. GDELT seen timestamps and Atom updated timestamps
are deliberately NOT mapped to published_at.
"""
import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET

USER_AGENT = 'TourismNews/0.3 (+https://github.com/Serhankeem/tourismnews; metadata-only)'


class AccessBlocked(OSError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Loader:
    def __init__(self, timeout=18):
        self.timeout, self.rules, self.last_request = timeout, {}, {}
        self.robot_errors = {}
        self.opener = urllib.request.build_opener(NoRedirect)

    def _open(self, req, redirects=False, retry_delay=0.5):
        """One bounded transient retry. Never retry denial/robots/cert errors.

        A longer server Retry-After is deferred to the next scheduled run.
        """
        for attempt in range(2):
            try:
                return (urllib.request.urlopen if redirects else self.opener.open)(req, timeout=self.timeout)
            except urllib.error.HTTPError as exc:
                if attempt or exc.code not in (500, 502, 503, 504):
                    raise
                raw = exc.headers.get('Retry-After') if exc.headers else None
                if raw is not None and (not raw.isdigit() or int(raw) > 2):
                    raise AccessBlocked('retry_after_requires_deferred_fetch') from exc
                time.sleep(max(retry_delay, int(raw) if raw is not None else 0.5))

    def _rules(self, url):
        parts = urllib.parse.urlsplit(url)
        base = parts.scheme + '://' + parts.netloc
        if base not in self.rules:
            try:
                req = urllib.request.Request(base + '/robots.txt', headers={'User-Agent': USER_AGENT})
                with self._open(req, redirects=True) as response:
                    body = response.read(200001)
                if len(body) > 200000:
                    raise AccessBlocked('robots_too_large')
                if b'<html' in body[:1000].lower() or b'<!doctype html' in body[:1000].lower():
                    raise AccessBlocked('robots_html_challenge')
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(body.decode('utf-8', 'replace').splitlines())
                self.rules[base] = parser
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    self.rules[base] = None
                    self.robot_errors[base] = 'http_' + str(exc.code)
                else:
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse([])
                    self.rules[base] = parser
            except (OSError, ValueError):
                self.rules[base] = None
        return base, self.rules[base]

    def __call__(self, url):
        visited = set()
        for _ in range(6):
            if url in visited:
                raise AccessBlocked('redirect_loop')
            visited.add(url)
            parts = urllib.parse.urlsplit(url)
            if parts.scheme != 'https' or parts.username or parts.password:
                raise AccessBlocked('https_public_endpoint_required')
            base, rules = self._rules(url)
            if rules is None:
                raise AccessBlocked('robots_unverified:' + self.robot_errors.get(base, 'transport_error'))
            if not rules.can_fetch(USER_AGENT, url):
                raise AccessBlocked('robots_disallowed')
            delay = max(0.15, rules.crawl_delay(USER_AGENT) or rules.crawl_delay('*') or 0)
            rate = rules.request_rate(USER_AGENT) or rules.request_rate('*')
            if rate and rate.requests:
                delay = max(delay, rate.seconds / rate.requests)
            if delay > 5:
                raise AccessBlocked('crawl_delay_requires_deferred_fetch')
            time.sleep(max(0, delay - (time.monotonic() - self.last_request.get(base, 0))))
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json, application/rss+xml, application/atom+xml, application/xml, text/xml'})
            self.last_request[base] = time.monotonic()
            try:
                with self._open(req, retry_delay=delay) as response:
                    data = response.read(2 * 1024 * 1024 + 1)
                if len(data) > 2 * 1024 * 1024:
                    raise ValueError('metadata_response_too_large')
                return data
            except urllib.error.HTTPError as exc:
                if exc.code not in (301, 302, 303, 307, 308):
                    raise
                location = exc.headers.get('Location')
                if not location:
                    raise
                # The next iteration checks the redirect target's robots too.
                url = urllib.parse.urljoin(url, location)
        raise AccessBlocked('redirect_loop')


def items_from(source, payload):
    adapter = source.get('adapter', 'rss')
    if adapter == 'rss':
        root = ET.fromstring(payload)
        if root.tag.rsplit('}', 1)[-1] not in ('rss', 'feed', 'RDF'):
            raise ValueError('not_rss_or_atom')
        for node in root.iter():
            if node.tag.rsplit('}', 1)[-1] not in ('item', 'entry'):
                continue
            item = {}
            for child in node:
                key = child.tag.rsplit('}', 1)[-1]
                if key == 'link' and child.get('rel', 'alternate') not in ('alternate', ''):
                    continue
                if key in ('title', 'link', 'pubDate', 'published', 'description', 'summary'):
                    item[key] = (child.text or child.get('href', '')).strip()
                elif key == 'date' and child.tag.startswith('{http://purl.org/dc/'):
                    item['published'] = (child.text or '').strip()
                elif key == 'updated':
                    item['modified_at'] = (child.text or '').strip()
            yield item
    elif adapter == 'sec_submissions':
        data = json.loads(payload)
        cik = str(int(data['cik']))
        if cik != str(int(source['cik'])):
            raise ValueError('SEC_company_identity_mismatch')
        filings = data['filings']['recent']
        if any(len(filings[field]) != len(filings['form']) for field in ('filingDate', 'accessionNumber', 'primaryDocument')):
            raise ValueError('inconsistent_SEC_metadata_columns')
        for i, form in enumerate(filings['form']):
            if form not in ('10-Q', '10-K', '20-F'):
                continue
            date = filings['filingDate'][i]
            accession = filings['accessionNumber'][i].replace('-', '')
            document = filings['primaryDocument'][i]
            if not accession.isdigit() or '/' in document or '..' in document:
                raise ValueError('invalid_SEC_document_identity')
            yield {'title': f"{data['name']} — {form} financial filing ({date})",
                   'link': f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}',
                   'published': date, 'date_precision': 'date',
                   'publication_date_basis': 'SEC_filingDate', 'record_type': 'regulatory_filing'}
    elif adapter == 'govuk_search':
        for row in json.loads(payload)['results']:
            if row.get('format') not in ('press_release', 'news_article', 'news_story'):
                continue
            yield {'title': row['title'], 'link': urllib.parse.urljoin('https://www.gov.uk', row['link']),
                   'published': '', 'modified_at': row.get('public_timestamp'), 'publication_date_basis': 'GOVUK_first_published_at_required'}
    elif adapter == 'federal_register':
        for row in json.loads(payload)['results']:
            yield {'title': row['title'], 'link': row['html_url'],
                   'published': row['publication_date'], 'date_precision': 'date',
                   'publication_date_basis': 'official_publication_date', 'record_type': 'government_notice'}
    elif adapter == 'gdelt':
        for row in json.loads(payload).get('articles', []):
            yield {'title': row['title'], 'link': row['url'], 'discovered_by_provider_at': row.get('seendate'),
                   'publisher': row.get('domain'), 'published': ''}
    else:
        raise ValueError('unsupported_metadata_adapter: ' + adapter)


def feed_bytes(items):
    """Internal handoff to the existing publication pipeline, never persisted."""
    root = ET.Element('rss')
    channel = ET.SubElement(root, 'channel')
    for item in items:
        node = ET.SubElement(channel, 'item')
        for key in ('title', 'link', 'pubDate', 'published', 'description', 'summary'):
            if item.get(key):
                ET.SubElement(node, key).text = item[key]
    return ET.tostring(root, encoding='utf-8')
