"""Tourism Pulse auto RSS collector: stdlib only, safe metadata-first processing.

This tool does not fetch article bodies. Publisher terms must be reviewed before
turning on reusable excerpts or integrating an AI summarizer.
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'site' / 'data'
USER_AGENT = 'TourismPulseRSS/0.2 (+metadata-only; contact repository maintainer)'
TRACKING = {'fbclid', 'gclid', 'ref', 'spm', 'source', 'igshid'}
if __package__:
    from .editorial import is_statistical, statistical_assessment
    from .relevance import CATEGORIES, LEGACY_CATEGORIES, RULE_VERSION, assess, approve
else:
    from editorial import is_statistical, statistical_assessment
    from relevance import CATEGORIES, LEGACY_CATEGORIES, RULE_VERSION, assess, approve


def now_kst():
    return dt.datetime.now(tz=KST)


def iso(value):
    return value.astimezone(KST).isoformat(timespec='seconds')


def stripped(value):
    v = html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))
    return re.sub(r'\s+', ' ', v).strip()


def timestamp(value, fallback=None):
    fallback = fallback or now_kst()
    if isinstance(value, dt.datetime):
        found = value
    else:
        raw = stripped(value)
        # Some Korean feeds use RFC dates with an ISO-style numeric offset.
        # email.utils otherwise silently drops '+09:00' and returns naive time.
        raw = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', raw) if not re.match(r'^\d{4}-', raw) else raw
        if re.fullmatch(r'\d{4}\.\d{2}\.\d{2}', raw):
            raw = raw.replace('.', '-')
        if not raw:
            return fallback
        try:
            found = dt.datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            try:
                if re.match(r'^\w+, \d{1,2} \d{2} \d{4} ', raw):
                    found = dt.datetime.strptime(raw, '%a, %d %m %Y %H:%M:%S %z')
                else:
                    found = email.utils.parsedate_to_datetime(raw)
            except (ValueError, TypeError):
                return fallback
    if found.tzinfo is None:
        found = found.replace(tzinfo=KST)
    return found.astimezone(KST)


def canonical_url(value):
    value = stripped(value)
    try:
        p = urllib.parse.urlsplit(value)
        if p.scheme.lower() not in ('https', 'http') or not p.hostname:
            return ''
        query = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        query = [(k, v) for k, v in query if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
        return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', urllib.parse.urlencode(query), ''))
    except ValueError:
        return ''


def url_identity(value):
    """Compare transport/tracking variants without changing stored article IDs.

    Do not merge independent reporting just because headlines are similar.
    """
    safe = canonical_url(value)
    if not safe:
        return ''
    parts = urllib.parse.urlsplit(safe)
    host = parts.hostname.removeprefix('www.')
    try:
        port = parts.port
    except ValueError:
        return safe
    if port and port not in (80, 443):
        host += ':' + str(port)
    return urllib.parse.urlunsplit(('', host, parts.path,
                                   urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))), ''))


def normalized_title(value):
    s = unicodedata.normalize('NFKC', stripped(value)).casefold()
    s = re.sub(r'\[[^]]{1,20}\]|\([^)]{1,14}\)', ' ', s)
    return re.sub(r'[^\w가-힣]+', '', s)


def similarity(a, b):
    na, nb = normalized_title(a), normalized_title(b)
    return SequenceMatcher(None, na, nb).ratio() if na and nb else 0.0


def classify(title, description=''):
    assessment = assess(stripped(title), stripped(description))
    return (assessment['category'] if assessment['decision'] == 'publish' else None,
            assessment['score'])


def xml_items(xml_bytes):
    root = ET.fromstring(xml_bytes)
    if root.tag.rsplit('}', 1)[-1] not in ('rss', 'feed', 'RDF'):
        raise ValueError('Response is not an RSS/Atom feed')
    # Defensive limits: no HTML body retrieval, 1MB maximum payload enforced at fetch.
    for node in root.iter():
        tag = node.tag.rsplit('}', 1)[-1]
        if tag not in ('item', 'entry'):
            continue
        data = {}
        for child in node:
            key = child.tag.rsplit('}', 1)[-1]
            value = (child.text or '').strip()
            if key == 'link':
                value = value or child.attrib.get('href', '')
                if child.attrib.get('rel', 'alternate') not in ('alternate', ''):
                    continue
            if key in ('title', 'link', 'pubDate', 'published', 'updated', 'description', 'summary') and value:
                data[key] = value
        yield data


def fetch_feed(url, timeout=15):
    safe = canonical_url(url)
    if not safe:
        raise ValueError('Invalid RSS URL')
    request = urllib.request.Request(safe, headers={'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(1024 * 1024 + 1)
        if len(payload) > 1024 * 1024:
            raise ValueError('RSS response too large')
        return payload


def article_from_item(item, source, at=None, reviews=None, include_held=False, max_age_days=45):
    at = at or now_kst()
    title = stripped(item.get('title', ''))
    description = stripped(item.get('description', item.get('summary', '')))
    url = canonical_url(item.get('link', ''))
    if not title or not url:
        return None
    date_value = item.get('pubDate') or item.get('published') or item.get('updated')
    if not date_value:
        return None  # Unknown publication date must never be labeled as fresh news.
    # Invalid dates must not silently become fresh news.
    published = timestamp(date_value, dt.datetime.min.replace(tzinfo=KST))
    if published > at or published < at - dt.timedelta(days=max_age_days):
        return None
    aid = hashlib.sha256(url.encode('utf-8')).hexdigest()[:18]
    assessment = statistical_assessment() if is_statistical(source) else assess(title, description)
    def review_date(value):
        sentinel = dt.datetime.min.replace(tzinfo=KST)
        parsed = timestamp(value, sentinel)
        return None if parsed == sentinel else parsed
    assessment = approve(assessment, title, url, (reviews or {}).get(aid), at, review_date)
    if assessment['decision'] == 'exclude' or (assessment['decision'] == 'hold' and not include_held):
        return None
    category, relevance = assessment['category'], assessment['score']
    reusable = bool(source.get('reuse_excerpt'))
    # Metadata-only by default; do not republish an unlicensed publisher excerpt.
    if reusable and description:
        desc = (description[:240].rstrip(' .') + ('…' if len(description) > 240 else ''))
        summary_type = 'rss_excerpt'
    else:
        desc = '원문 링크에서 보도자료 또는 기사 내용을 확인하세요. (본문 자동 분석 전)'
        summary_type = 'metadata_only'
    if is_statistical(source):
        desc = '통계 수록·갱신 자료입니다. 원문에서 조사 범위와 기준 시점을 확인하세요.'
    return {
        **({'record_type': 'statistical_release'} if is_statistical(source) else {}),
        'id': aid, 'published_at': iso(published), 'date': published.strftime('%Y.%m.%d'),
        'category': category, 'source': source['name'], 'source_id': source['id'],
        'title': title, 'desc': desc, 'insight': '원문을 확인한 후 산업적 시사점을 판단해 주세요.',
        'summary_type': summary_type, 'url': url, 'relevance': relevance,
        'relevance_label': assessment['label'], 'relevance_evidence': assessment,
        'related_sources': [source['name']]
    }


def deduplicate(items):
    out = []
    for article in sorted(items, key=lambda a: a['published_at'], reverse=True):
        match = next((old for old in out if (url_identity(old['url']) == url_identity(article['url'])) or
            (old.get('source_id', old['source']) == article.get('source_id', article['source']) and
             similarity(old['title'], article['title']) >= .92 and
             [n.replace(',', '') for n in re.findall(r'\d+(?:[.,]\d+)*', old['title'])] ==
             [n.replace(',', '') for n in re.findall(r'\d+(?:[.,]\d+)*', article['title'])] and
             abs((timestamp(old['published_at']) - timestamp(article['published_at'])).total_seconds()) < 72 * 3600)), None)
        if match:
            for src in article.get('related_sources', [article['source']]):
                if src not in match['related_sources']:
                    match['related_sources'].append(src)
        else:
            out.append(article)
    return out


def read_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        return fallback


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='tmp-', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def failure_details(exc):
    message = str(exc)
    if 'Tunnel connection failed' in message:
        kind = 'proxy_connect_denied'
    elif isinstance(exc, urllib.error.HTTPError):
        kind = 'redirect_loop' if exc.code in (301, 302, 303, 307, 308) else 'http_error'
    elif isinstance(exc, (ET.ParseError, ValueError)):
        kind = 'invalid_feed'
    else:
        kind = 'transport_error'
    details = {'error_kind': kind, 'error': f'{type(exc).__name__}: {exc}'[:250]}
    if isinstance(exc, urllib.error.HTTPError):
        details['http_status'] = exc.code
        try:
            body = exc.read(512).decode('utf-8', errors='replace')
        except OSError:
            body = ''
        if 'upstream connect error' in body:
            details['error_kind'] = 'gateway_upstream_error'
            details['response_detail'] = stripped(body)[:250]
    return details


def run(sources, fetcher=fetch_feed, at=None, demo=False, data_dir=DATA, reviews=None, state_dir=None, retention_days=45, max_articles=450):
    at = at or now_kst()
    state_dir = Path(state_dir) if state_dir is not None else data_dir / 'collector_state'
    news_file, brief_file, health_file = [data_dir / f for f in ('news.json', 'briefing.json', 'health.json')]
    old = read_json(news_file, {})
    prior_articles = old.get('articles', []) if old.get('mode') != 'fixture_demo' else []
    found, health, held, ok = [], [], [], 0
    seen_ids = set()
    decisions = []
    for source in sources:
        if not source.get('enabled', True):
            continue
        try:
            payload = fetcher(source['url'])
            items = list(xml_items(payload))
            for item in items:
                item_url = canonical_url(item.get('link', ''))
                item_date = timestamp(item.get('pubDate') or item.get('published') or item.get('updated'), dt.datetime.min.replace(tzinfo=KST))
                if item_url and at - dt.timedelta(days=retention_days) <= item_date <= at:
                    seen_ids.add(hashlib.sha256(item_url.encode()).hexdigest()[:18])
            evaluated = [article_from_item(item, source, at, reviews, include_held=True, max_age_days=retention_days) for item in items]
            news = [a for a in evaluated if a and a['relevance_evidence']['decision'] == 'publish']
            pending = [a for a in evaluated if a and a['relevance_evidence']['decision'] == 'hold']
            found.extend(news)
            held.extend(pending)
            labels = {label: 0 for label in ('Direct', 'Indirect', 'Irrelevant')}
            for item, article in zip(items, evaluated):
                assessment = statistical_assessment() if is_statistical(source) else assess(stripped(item.get('title', '')), stripped(item.get('description', item.get('summary', ''))))
                if assessment['label'] in labels:
                    labels[assessment['label']] += 1
                evidence = article['relevance_evidence'] if article else assessment
                item_url = canonical_url(item.get('link', ''))
                rejected_metadata = article is None and assessment['label'] != 'Irrelevant'
                decisions.append({'id': hashlib.sha256(item_url.encode()).hexdigest()[:18] if item_url else None,
                                  'title': stripped(item.get('title', '')), 'url': item_url,
                                  'source_id': source['id'], 'relevance_evidence': evidence,
                                  'decision': 'reject_invalid_metadata' if rejected_metadata else evidence['decision']})
            health.append({'id': source['id'], 'name': source['name'], 'url': source['url'], 'status': 'ok',
                           'rss_items': len(items), 'matched': len(news), 'held': len(pending),
                           'relevance_counts': labels,
                           'category_published': {c: sum(a['category'] == c for a in news) for c in CATEGORIES}})
            ok += 1
        except (ET.ParseError, ValueError, urllib.error.URLError, TimeoutError, OSError) as exc:
            health.append({'id': source['id'], 'name': source['name'], 'url': source['url'], 'status': 'error', **failure_details(exc)})
    status = 'ok' if ok == len(health) and ok else ('partial' if ok else 'failed')
    previous_success = old.get('last_successful_fetch')
    last_success = iso(at) if ok else previous_success
    write_atomic(health_file, {'checked_at': iso(at), 'last_successful_fetch': last_success, 'status': status, 'sources': health, 'source_count': len(health), 'successful_sources': ok})
    if not ok:
        # All sources failed: NEVER erase existing news or replace existing briefing.
        return {'status': 'failed', 'articles': len(prior_articles), 'sources_ok': 0}
    write_atomic(state_dir / 'decisions.json', {'schema_version': 2, 'checked_at': iso(at),
                                               'scope': 'successful_sources_this_run', 'items': decisions})
    # Successful runs migrate taxonomy and re-evaluate legacy metadata. An
    # outage never triggers migration: the early return above preserves bytes.
    retained, legacy_archive = [], []
    for article in ([] if demo else prior_articles):
        if 'relevance_evidence' not in article:
            legacy_archive.append(dict(article))
        if article['id'] in seen_ids:
            for fresh in found + held:
                if fresh['id'] == article['id'] and article['category'] in LEGACY_CATEGORIES:
                    fresh['legacy_category'] = article['category']
                elif fresh['id'] == article['id'] and article.get('legacy_category'):
                    fresh['legacy_category'] = article['legacy_category']
            continue
        previous = article.get('relevance_evidence', {})
        if previous.get('rule_version') == RULE_VERSION and previous.get('label') == 'Direct':
            retained.append(article)
            continue
        original = dict(article)
        if previous.get('rule_version') == RULE_VERSION and previous.get('label') == 'Indirect':
            pending = {**previous, 'decision': 'hold'}
            pending.pop('review', None)
            pending.pop('review_status', None)
            sentinel = dt.datetime.min.replace(tzinfo=KST)
            def parse_review(value):
                date = timestamp(value, sentinel)
                return None if date == sentinel else date
            checked = approve(pending, article['title'], article['url'], (reviews or {}).get(article['id']), at, parse_review)
            updated = {**article, 'relevance_evidence': checked}
            (retained if checked['decision'] == 'publish' else held).append(updated)
            continue
        source = {'id': article['source_id'], 'name': article['source'],
                  'reuse_excerpt': article.get('summary_type') == 'rss_excerpt'}
        migrated = article_from_item({'title': article['title'], 'link': article['url'],
                                     'pubDate': article['published_at'],
                                     'description': article.get('desc', '')}, source, at, reviews, include_held=True, max_age_days=retention_days)
        if migrated and migrated['relevance_evidence']['decision'] == 'publish':
            migrated['legacy_category'] = article.get('legacy_category', article['category'])
            retained.append(migrated)
        elif migrated:
            held.append(migrated)
        else:
            held.append({**original, 'category': LEGACY_CATEGORIES.get(article['category'], article['category']),
                         'migration_status': 'needs_refetch',
                         'relevance_evidence': {'rule_version': RULE_VERSION, 'decision': 'hold',
                                               'reason': '기존 데이터의 저장 메타데이터만으로 관련성을 재확인할 수 없어 원본을 보관합니다.'}})
    prior_queue = read_json(state_dir / 'review_queue.json', {}).get('articles', [])
    for pending in prior_queue:
        if pending['id'] in seen_ids or pending['id'] in {a['id'] for a in held + retained}:
            continue
        assessment = pending.get('relevance_evidence', {})
        if assessment.get('label') == 'Indirect':
            sentinel = dt.datetime.min.replace(tzinfo=KST)
            def parse_pending_date(value):
                date = timestamp(value, sentinel)
                return None if date == sentinel else date
            checked = approve(assessment, pending['title'], pending['url'],
                              (reviews or {}).get(pending['id']), at, parse_pending_date)
            if checked['decision'] == 'publish':
                retained.append({**pending, 'relevance_evidence': checked})
    candidates = found + retained
    combined = deduplicate(candidates)
    cutoff = at - dt.timedelta(days=retention_days)
    combined = [x for x in combined if timestamp(x['published_at']) >= cutoff][:max_articles]
    mode = 'fixture_demo' if demo else 'live_rss'
    write_atomic(news_file, {'schema_version': 2, 'rule_version': RULE_VERSION, 'generated_at': iso(at), 'last_successful_fetch': last_success, 'count': len(combined), 'mode': mode, 'articles': combined})
    # Queue/state lives outside Pages in the production CLI. Keep candidates
    # from unavailable sources and archive untouched originals for migration.
    held_ids = {a['id'] for a in held}
    published_ids = {a['id'] for a in combined}
    queue = held + [a for a in prior_queue if a['id'] not in held_ids | published_ids | seen_ids
                    and timestamp(a['published_at']) >= cutoff]
    queue = list({a['id']: a for a in reversed(queue) if timestamp(a['published_at']) >= cutoff}.values())[:450]
    write_atomic(state_dir / 'review_queue.json', {'schema_version': 2, 'updated_at': iso(at), 'articles': queue})
    if legacy_archive:
        archive = read_json(state_dir / 'legacy_archive.json', {}).get('articles', [])
        originals = {a['id']: a for a in archive}
        for a in legacy_archive:
            originals.setdefault(a['id'], a)
        write_atomic(state_dir / 'legacy_archive.json', {'schema_version': 1, 'articles': list(originals.values())})
    health_data = read_json(health_file, {})
    health_data.update({'schema_version': 2, 'rule_version': RULE_VERSION,
                        'category_counts': {c: sum(a['category'] == c for a in combined) for c in CATEGORIES},
                        'review_queue_count': len(queue[:450])})
    write_atomic(health_file, health_data)
    within_day = [x for x in combined if at - dt.timedelta(hours=24) <= timestamp(x['published_at']) <= at]
    selected = sorted(within_day, key=lambda x: (x['relevance'], timestamp(x['published_at'])), reverse=True)[:5]
    write_atomic(brief_file, {
        'schema_version': 2, 'generated_at': iso(at), 'status': 'demo' if demo else ('candidates_ready' if selected else 'no_recent_articles'),
        'mode': mode, 'title': '관광산업 주요 뉴스 브리핑 후보',
        'items': [{'id': x['id'], 'title': x['title'], 'source': x['source'], 'category': x['category'], 'url': x['url'], 'published_at': x['published_at'], 'desc': x['desc'], 'summary_type': x['summary_type'], 'relevance_label': x['relevance_label'], 'relevance_evidence': x['relevance_evidence']} for x in selected],
        'notice': '브리핑 후보만 자동 생성. 카카오톡 발송 및 본문 기반 AI 요약은 미구현.'
    })
    return {'status': status, 'articles': len(combined), 'sources_ok': ok, 'briefing_candidates': len(selected), 'mode': mode}


def main():
    # Keep the old CLI safe: live collection must pass the rights and editorial
    # gates even when an old README or job invokes collector.py directly.
    if '--demo' not in sys.argv[1:]:
        if __package__:
            from .engine import main as engine_main
        else:
            from engine import main as engine_main
        return engine_main()
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', help='Use clearly labeled synthetic test RSS instead of live sources')
    parser.add_argument('--reviews', default=str(ROOT / 'relevance_reviews.json'), help='Title-bound editorial approvals for Indirect candidates')
    parser.add_argument('--dir', default=str(DATA), help='Destination for site JSON')
    args = parser.parse_args()
    if Path(args.dir).resolve() == DATA.resolve():
        parser.error('Demo requires a separate --dir; production data must not be overwritten')
    sources = json.loads((ROOT / 'sources.json').read_text(encoding='utf-8'))['sources']
    if args.demo:
        demo_file = ROOT / 'fixtures' / 'sample.xml'
        sources = [{'id': 'fixture', 'name': '가상 테스트 피드', 'url': 'https://example.org/rss.xml', 'enabled': True, 'reuse_excerpt': True}]
        fetcher = lambda url: demo_file.read_bytes()
    else:
        fetcher = fetch_feed
    reviews = read_json(Path(args.reviews), {}).get('approvals', {})
    state_dir = ROOT / 'collector_state' if Path(args.dir).resolve() == DATA.resolve() else Path(args.dir) / 'collector_state'
    result = run(sources, fetcher=fetcher, demo=args.demo, data_dir=Path(args.dir), reviews=reviews, state_dir=state_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result['status'] == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())
