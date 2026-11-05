"""Permission-separated, bounded provider discovery. No raw-result persistence.

Only records with verified permanent metadata storage AND public display grants
can leave this transient layer. Existing relevance and PublicationGate still run.
"""
import datetime as dt
import ipaddress
import json
import os
import re
import time
import urllib.parse as urlparse
import urllib.request
import urllib.error
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

if __package__:
    from . import collector as c
    from .discovery import Loader, USER_AGENT, items_from
    from .diversity import article_domain_allowed, publisher_key
else:
    import collector as c
    from discovery import Loader, USER_AGENT, items_from
    from diversity import article_domain_allowed, publisher_key

CONFIG = c.ROOT / 'discovery_providers.json'
CAPABILITIES = ('access', 'process', 'store', 'publish')
# Search plans, not broader classification rules. Never sent to unapproved APIs.
QUERY_GROUPS = {
    'policy': ('관광산업 정책 예산', '관광산업 고용 제도'),
    'demand': ('인바운드 관광객 수요', '아웃바운드 관광소비'),
    'air': ('항공 노선 좌석 여객 수요',),
    'lodging': ('호텔 공급 투자 실적',),
    'technology': ('OTA 여행기업 실적 인수합병',),
    'mice': ('MICE 국제회의 유치',),
    'balance': ('관광수지 관광수입 관광지출',),
}


class DiscoveryError(ValueError):
    """Fixed codes only: never exception text, request URL or response content."""


def configuration(code=None):
    path = Path(code) / CONFIG.name if code else CONFIG
    return c.read_json(path, {}).get('providers', [])


def permissions(provider):
    rights = provider.get('capabilities', {})
    approved = {k: (rights.get(k, {}).get('status') == 'approved'
                    and bool(rights[k].get('evidence_url'))
                    and bool(rights[k].get('basis'))
                    and bool(rights[k].get('verified_at'))) for k in CAPABILITIES}
    # This version deliberately has no metadata-retention scheduler. Do not
    # accept a time-limited storage grant and then keep candidates indefinitely.
    approved['store'] = approved['store'] and rights['store'].get('retention') == 'permanent_metadata'
    enabled = provider.get('enabled') is True
    state = ('blocked' if not enabled or not approved['access'] or not approved['process'] else
             'publishable' if all(approved.values()) else
             'manual_review' if approved['store'] and rights.get('publish', {}).get('status') == 'review' else
             'discovery_only')
    return {'state': state, **{k: bool(v) for k, v in approved.items()}}


def endpoint_allowed(provider):
    if not provider.get('endpoint_verified') or not provider.get('endpoint_evidence_url'):
        return False
    parts = urlparse.urlsplit(provider.get('endpoint') or '')
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.fragment or parts.hostname not in provider.get('endpoint_hosts', [])):
        return False
    try:
        if not ipaddress.ip_address(parts.hostname).is_global:
            return False
    except ValueError:
        if parts.hostname in ('localhost',) or parts.hostname.endswith(('.local', '.internal')):
            return False
    return not any(re.search(r'key|secret|token|password', k, re.I)
                   for k, _ in urlparse.parse_qsl(parts.query))


class Transport(Loader):
    """Robots before credentials; HTTPS only; never redirect credentials."""
    def _open(self, req, redirects=False, retry_delay=.5):
        # One budgeted API attempt; 429/503 defer instead of invisible retries.
        return (urllib.request.urlopen if redirects else self.opener.open)(req, timeout=self.timeout)

    def __call__(self, provider, params):
        if permissions(provider)['state'] == 'blocked':
            raise DiscoveryError('access_or_processing_not_approved')
        if not endpoint_allowed(provider):
            raise DiscoveryError('endpoint_not_verified_https')
        endpoint = provider['endpoint']
        _, rules = self._rules(endpoint)
        if rules is None or not rules.can_fetch(USER_AGENT, endpoint):
            raise DiscoveryError('robots_not_allowed_or_unverified')
        delay = max(.15, rules.crawl_delay(USER_AGENT) or rules.crawl_delay('*') or 0)
        rate = rules.request_rate(USER_AGENT) or rules.request_rate('*')
        if rate and rate.requests:
            delay = max(delay, rate.seconds / rate.requests)
        if delay > 5:
            raise DiscoveryError('crawl_delay_requires_deferred_fetch')
        host = urlparse.urlsplit(endpoint).netloc
        time.sleep(max(0, delay - (time.monotonic() - self.last_request.get(host, 0))))
        self.last_request[host] = time.monotonic()
        # API credentials are applied only after the non-secret endpoint check.
        if any(re.search(r'key|secret|token|password', k, re.I) for k in params):
            raise DiscoveryError('credentials_not_allowed_in_query_plan')
        headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json, application/xml'}
        query = dict(urlparse.parse_qsl(urlparse.urlsplit(endpoint).query))
        query.update(params)
        for binding in provider.get('auth', []):
            value = os.environ.get(binding['env'])
            if not value:
                raise DiscoveryError('credentials_missing')
            if binding['placement'] == 'query':
                query[binding['name']] = value
            elif binding['placement'] == 'header':
                headers[binding['name']] = value
            else:
                raise DiscoveryError('invalid_auth_binding')
        parts = urlparse.urlsplit(endpoint)
        url = urlparse.urlunsplit((parts.scheme, parts.netloc, parts.path,
                                  urlparse.urlencode(query), ''))
        request = urllib.request.Request(url, headers=headers)
        # Loader's opener disables redirects. Do not use urlopen, and do not
        # log errors from this operation (HTTPError contains the credential URL).
        with self._open(request) as response:
            payload = response.read(2 * 1024 * 1024 + 1)
        if len(payload) > 2 * 1024 * 1024:
            raise DiscoveryError('response_too_large')
        return payload


def parse(provider, payload):
    """Explicitly configured list contracts only; no guessed field aliases."""
    adapter = provider['adapter']
    if adapter == 'rss':
        for item in items_from({'adapter': 'rss'}, payload):
            if provider.get('fixed_publisher_code'):
                item['publisher_code'] = provider['fixed_publisher_code']
            yield item
        return
    if adapter == 'naver_news':
        doc = json.loads(payload)
        if 'errorCode' in doc or not isinstance(doc.get('items'), list):
            raise DiscoveryError('provider_error_or_invalid_schema')
        for row in doc['items']:
            # originallink, not Naver's relay link. Publisher remains unverified
            # unless a provider publisher code mapping was separately supplied.
            yield {'title': row.get('title'), 'link': row.get('originallink'),
                   'published': row.get('pubDate'), 'publisher_code': row.get('publisher_code')}
        return
    schema = provider.get('response', {})
    if schema.get('contract_verified') is not True:
        raise DiscoveryError('response_contract_unverified')
    if adapter == 'json_rows':
        rows = json.loads(payload)
        if isinstance(rows, dict) and any(rows.get(k) for k in ('error', 'errorCode', 'error_code')):
            raise DiscoveryError('provider_error_or_invalid_schema')
        if schema.get('success_path'):
            status = rows
            for key in schema['success_path']:
                status = status[key]
            if str(status) not in schema['success_values']:
                raise DiscoveryError('provider_reported_failure')
        for key in schema['rows_path']:
            rows = rows[key]
        if not isinstance(rows, list):
            raise DiscoveryError('invalid_rows')
    elif adapter == 'xml_rows':
        root = ET.fromstring(payload)
        if root.tag != schema.get('root_tag') or root.find(schema.get('container_path', './__unconfigured__')) is None:
            raise DiscoveryError('invalid_xml_envelope')
        if schema.get('success_path') and root.findtext(schema['success_path']) not in schema['success_values']:
            raise DiscoveryError('provider_reported_failure')
        rows = [{k: row.findtext(v) for k, v in schema['fields'].items()}
                for row in root.findall(schema['rows_path'])]
        for row in rows:
            yield row
        return
    else:
        raise DiscoveryError('unknown_adapter')
    for row in rows:
        yield {key: row.get(column) for key, column in schema['fields'].items()}


def binding(provider, code, sources, url):
    if any(re.search(r'key|secret|token|password', k, re.I) for k, _ in urlparse.parse_qsl(urlparse.urlsplit(url).query)):
        return None
    mapped = provider.get('publishers', {}).get(str(code), {})
    source = sources.get(mapped.get('source_id'))
    if (not source or not mapped.get('verified') or not mapped.get('evidence_url')
            or mapped.get('publisher_id') != publisher_key(source)
            or not source.get('article_domains') or not mapped.get('article_domains')
            or not article_domain_allowed(source, url) or not article_domain_allowed(mapped, url)):
        return None
    return source


def record_allowed(record, providers, sources):
    origin = record.get('discovery_origin')
    if 'discovery_origin' not in record:
        return True  # Legacy source-based records retain their existing policy.
    if not isinstance(origin, dict) or not origin:
        return False
    provider = next((p for p in providers if p['id'] == origin.get('provider_id')), {})
    source = binding(provider, origin.get('publisher_code'), sources, record['url'])
    return bool(permissions(provider)['state'] == 'publishable' and source
                and source['id'] == record.get('source_id'))


@dataclass(repr=False)
class Batch:
    # No dict/JSON serialization of unlicensed metadata. Only fully publishable
    # candidates cross the boundary; review/discovery-only use numeric diagnostics.
    by_source: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    cursors: dict = field(default_factory=dict)


def discover(providers, sources, at, previous=None, loader=None, archive=(), max_calls=8, publisher_permission=None):
    """One bounded page per configured query; cursor timestamps only, no raw cache."""
    if publisher_permission is None:
        if __package__:
            from .engine import permission as publisher_permission
        else:
            from engine import permission as publisher_permission
    previous = previous or {}
    loader = loader or Transport()
    cfg = {s['id']: s for s in sources}
    batch = Batch()
    existing_urls = {c.canonical_url(a['url']) for a in archive}
    existing_official = {(a['discovery_origin']['publisher_id'], a['discovery_origin'].get('official_namespace', a['discovery_origin']['provider_id']), a['discovery_origin']['official_id'])
                        for a in archive if a.get('discovery_origin', {}).get('official_id')}
    seen_urls, seen_official = set(), set()
    remaining = max(0, min(max_calls, 50))
    for provider in providers:
        if provider.get('enabled') is not True:
            continue
        pid = provider['id']
        rights = permissions(provider)
        row = {'state': rights['state'], 'status': 'blocked', 'calls': 0, 'received': 0,
               'relevant_candidates': 0, 'irrelevant': 0, 'duplicates': 0, 'attribution_holds': 0,
               'date_holds': 0, 'rights_holds': 0, 'non_news_holds': 0, 'authorized_handoffs': 0,
               'verified_publishers': [], 'unpublishable_candidate_metadata_persisted': 0,
               'success_rate': None}
        batch.metrics[pid] = row
        prior = previous.get(pid, {})
        batch.cursors[pid] = dict(prior)
        if rights['state'] == 'blocked':
            row['error_kind'] = 'access_or_processing_not_approved'
            continue
        if provider.get('record_type') != 'news':
            row['error_kind'] = 'news_contract_not_verified'
            continue
        if not endpoint_allowed(provider):
            row['error_kind'] = 'endpoint_not_verified_https'
            continue
        retry_at = c.timestamp(prior.get('retry_after_at'), dt.datetime.min.replace(tzinfo=c.KST))
        if retry_at > at:
            row.update(status='deferred', error_kind='rate_limit_deferred')
            continue
        last = c.timestamp(prior.get('last_successful_at'), dt.datetime.min.replace(tzinfo=c.KST))
        if (at - last).total_seconds() < max(60, provider.get('interval_seconds', 7200)):
            row['status'] = 'not_due'
            continue
        if not remaining:
            row.update(status='deferred', error_kind='call_budget_exhausted')
            continue
        plans = provider.get('queries', [{}])
        limit = max(1, min(provider.get('max_calls_per_run', 1), 8))
        # All plans must fit. Never advance the cursor after querying only part
        # of a source's configured scope; later runs would otherwise skip gaps.
        if not isinstance(plans, list) or not plans or len(plans) > min(limit, remaining):
            row.update(status='deferred', error_kind='query_plan_exceeds_budget')
            continue
        staged, publishers = {}, set()
        local_urls, local_official = set(), set()
        try:
            for query in plans:
                params = dict(query)
                if provider.get('since_parameter') and prior.get('last_successful_at'):
                    # Overlap one day for corrections; old/fresh results still
                    # deduplicate by official ID and canonical original URL.
                    params[provider['since_parameter']] = c.iso(last - dt.timedelta(days=1))
                row['calls'] += 1
                remaining -= 1
                payload = loader(provider, params)
                for item in parse(provider, payload):
                    row['received'] += 1
                    if item.get('record_type', 'news') != 'news':
                        row['non_news_holds'] += 1
                        continue
                    title = c.stripped(item.get('title') or '')
                    url = c.canonical_url(item.get('link') or '')
                    if not title or not url:
                        row['attribution_holds'] += 1
                        continue
                    assessment = c.assess(title, '')
                    if assessment['label'] == 'Irrelevant':
                        row['irrelevant'] += 1
                        continue
                    row['relevant_candidates'] += 1
                    stamp = item.get('pubDate') or item.get('published') or ''
                    published = c.timestamp(stamp, dt.datetime.min.replace(tzinfo=c.KST))
                    if (re.fullmatch(r'\d{4}-\d{2}-\d{2}', stamp.strip())
                            or not at - dt.timedelta(days=90) <= published <= at + dt.timedelta(minutes=5)):
                        row['date_holds'] += 1
                        continue
                    source = binding(provider, item.get('publisher_code'), cfg, url)
                    if not source:
                        row['attribution_holds'] += 1
                        continue
                    publishers.add(publisher_key(source))
                    official_id = str(item.get('official_id') or '')
                    namespace = provider.get('official_id_namespace') or pid
                    official = (publisher_key(source), namespace, official_id)
                    if (url in local_urls or url in seen_urls or url in existing_urls or
                            official_id and (official in local_official or official in seen_official or official in existing_official)):
                        row['duplicates'] += 1
                        continue
                    # Policy is evaluated before durable IDs/URL/title storage.
                    # Unpublished search results never enter the permanent ledger.
                    if (rights['state'] != 'publishable' or not source.get('enabled', True)
                            or not publisher_permission(source)):
                        row['rights_holds'] += 1
                        continue
                    local_urls.add(url)
                    if official_id:
                        local_official.add(official)
                    origin = {'provider_id': pid, 'publisher_code': str(item.get('publisher_code')),
                              'publisher_id': publisher_key(source), 'official_id': official_id,
                              'official_namespace': namespace}
                    staged.setdefault(source['id'], []).append({'title': title, 'link': url,
                        'published': c.iso(published), 'discovery_origin': origin})
            seen_urls.update(local_urls)
            seen_official.update(local_official)
            for sid, items in staged.items():
                batch.by_source.setdefault(sid, []).extend(items)
            row.update(status='ok', authorized_handoffs=sum(len(v) for v in staged.values()),
                       verified_publishers=sorted(publishers))
            # This cursor is minimal operational diagnostic information; no
            # raw response, candidate title/URL/ID, query text or credentials.
            batch.cursors[pid] = {k: v for k, v in {**prior, 'last_successful_at': c.iso(at)}.items() if k != 'retry_after_at'}
        except Exception as exc:
            # Fixed codes only; even a URL-bearing HTTPError cannot escape.
            kind = (str(exc) if isinstance(exc, DiscoveryError) else
                    'rate_limited' if isinstance(exc, urllib.error.HTTPError) and exc.code == 429 else
                    'http_' + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else
                    'provider_request_or_schema_failed')
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (429, 503):
                raw = exc.headers.get('Retry-After') if exc.headers else None
                try:
                    when = at + dt.timedelta(seconds=int(raw)) if raw and raw.isdigit() else parsedate_to_datetime(raw)
                    if when.tzinfo and when > at:
                        batch.cursors[pid]['retry_after_at'] = c.iso(when)
                except (TypeError, ValueError, OverflowError):
                    pass
            row.update(status='error', error_kind=kind if re.fullmatch(r'[a-z0-9_]+', kind) else 'provider_failed')
        cursor = batch.cursors[pid]
        cursor.update(attempts=prior.get('attempts', 0) + 1,
                      successes=prior.get('successes', 0) + (row['status'] == 'ok'),
                      calls_total=prior.get('calls_total', 0) + row['calls'])
        row['success_rate'] = cursor['successes'] / cursor['attempts']
        row['handoffs_per_call'] = row['authorized_handoffs'] / row['calls'] if row['calls'] else None
    return batch
