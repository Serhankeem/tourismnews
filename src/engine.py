"""v0.3: discovery ledger -> rights/date gate -> existing publication pipeline."""
import argparse
import datetime as dt
import hashlib
import json
import re
import tempfile
import urllib.parse
from pathlib import Path

if __package__:
    from . import collector as c
    from .briefing import save as save_briefing
    from .discovery import Loader, AccessBlocked, items_from, feed_bytes
    from .publication import public_record
    from .visibility import PublicationGate
    from .coverage import coverage
    from . import news_discovery as nd
    from .diversity import article_domain_allowed
    from .editorial import project, exposure, is_statistical, statistical_assessment
else:
    import collector as c
    from briefing import save as save_briefing
    from discovery import Loader, AccessBlocked, items_from, feed_bytes
    from publication import public_record
    from visibility import PublicationGate
    from coverage import coverage
    import news_discovery as nd
    from diversity import article_domain_allowed
    from editorial import project, exposure, is_statistical, statistical_assessment


def valid_date(item, at, days):
    # 'updated' and provider 'seen' are intentionally not publication dates.
    raw = item.get('pubDate') or item.get('published')
    if not raw:
        return None
    parsed = c.timestamp(raw, dt.datetime.min.replace(tzinfo=c.KST))
    return parsed if at - dt.timedelta(days=days) <= parsed <= at + dt.timedelta(minutes=5) else None


OPERATING_POLICY = c.ROOT / 'operating_policy.json'


def permission(source):
    policy = source.get('publication', {})
    if policy.get('noncommercial_only'):
        model = c.read_json(OPERATING_POLICY, {})
        if model.get('mode') != 'noncommercial' or model.get('ads_enabled') is not False or model.get('paid_access') is not False:
            return False
    return (policy.get('status') == 'approved' and policy.get('scope') == 'metadata_only'
            and bool(policy.get('terms_url')) and bool(policy.get('basis')))


def execute(sources, data_dir, state_dir, reviews=None, at=None, loader=None, days=90, providers=None, provider_loader=None):
    at = at or c.now_kst()
    loader = loader or Loader()
    data_dir, state_dir = Path(data_dir), Path(state_dir)
    archive_path = state_dir / 'archive.json'
    legacy_archive = data_dir / 'archive.json'
    fallback = legacy_archive if legacy_archive.exists() else data_dir / 'news.json'
    original = c.read_json(archive_path, None) if archive_path.exists() else c.read_json(fallback, None if legacy_archive.exists() else {})
    if not isinstance(original, dict) or not isinstance(original.get('articles', []), list):
        raise ValueError('invalid_archive_stop_without_replacing_data')
    old_articles = original.get('articles', []) if original.get('mode') != 'fixture_demo' else []
    if any('id' not in a for a in old_articles):
        raise ValueError('public_projection_requires_internal_archive')
    gate = PublicationGate(sources, permission, data_dir, providers=nd.configuration() if providers is None else providers)
    previous_newsroom = gate.views(old_articles)[1]
    old_ids = {a['id'] for a in old_articles}
    ledger = c.read_json(state_dir / 'discovery.json', {}).get('candidates', {})
    previous_ids = set(ledger)
    original_by_id = {a['id']: a for a in old_articles}
    metrics_doc = c.read_json(state_dir / 'source_metrics.json', {})
    source_metrics = metrics_doc.get('sources', {})
    providers = nd.configuration() if providers is None else providers
    batch = nd.discover(providers, sources, at, metrics_doc.get('discovery_providers', {}),
                        loader=provider_loader, archive=old_articles, publisher_permission=permission) if any(p.get('enabled') for p in providers) else None
    prepared, errors, health, metadata = {}, {}, [], {}
    run_ids = set()
    cohorts = {}
    for source in sources:
        if not source.get('enabled', True):
            continue
        sid = source['id']
        cohort = cohorts[sid] = {k: set() for k in ('observed', 'candidates', 'approved', 'rights_held', 'irrelevant')}
        row = {'id': sid, 'name': source['name'], 'url': source['url'], 'group': source.get('group', 'public'),
               'fetch_attempted': False, 'news_classifications': {k: 0 for k in ('Direct', 'Indirect', 'Irrelevant')},
               'received': 0, 'new_discoveries': 0, 'duplicates': 0, 'rights_holds': 0, 'date_holds': 0, 'invalid_metadata': 0, 'outside_window': 0, 'attribution_holds': 0,
               'classifications': {k: 0 for k in ('Direct', 'Indirect', 'Irrelevant')},
               'publication_policy': source.get('publication', {'status': 'review'}),
               'backfill': source.get('backfill', {'mode': 'provided_feed_only', 'max_days': days})}
        try:
            if not source.get('discovery_allowed', True):
                raise AccessBlocked('discovery_not_authorized')
            row['fetch_attempted'] = True
            try:
                payload = loader(source['url'])
                items = list(items_from(source, payload))
            except (OSError, ValueError, KeyError, TypeError, c.ET.ParseError):
                if not batch or not batch.by_source.get(sid):
                    raise
                items = []
                row['primary_feed_status'] = 'failed_using_verified_provider_fallback'
            if batch:
                items.extend(batch.by_source.get(sid, []))
            source_days = min(days, source.get('backfill', {}).get('max_days', days))
            if source.get('record_type'):
                items = [{**item, 'record_type': source['record_type']} for item in items]
            row['received'] = len(items)
            approved_items = []
            date_lookups = 0
            for item in items:
                title, url = c.stripped(item.get('title', '')), c.canonical_url(item.get('link', ''))
                if not title or not url:
                    row['invalid_metadata'] += 1
                    continue
                if not article_domain_allowed(source, url):
                    # Do not attribute a relay/third-party URL to this publisher.
                    # Existing stored records remain untouched.
                    row['attribution_holds'] += 1
                    continue
                if 'description' not in source.get('analysis_fields', ['title']):
                    item = {k: v for k, v in item.items() if k not in ('description', 'summary')}
                aid = hashlib.sha256(url.encode()).hexdigest()[:18]
                if (not item.get('discovery_origin')
                        and original_by_id.get(aid, {}).get('discovery_origin')):
                    # An RSS echo cannot erase the original API's date, identity
                    # or rights provenance. Corrections require that contract.
                    row['duplicates'] += 1
                    continue
                assessment = statistical_assessment() if is_statistical(source) else c.assess(title, c.stripped(item.get('description', item.get('summary', ''))))
                raw_date = item.get('pubDate') or item.get('published')
                if raw_date:
                    parsed_date = c.timestamp(raw_date, dt.datetime.min.replace(tzinfo=c.KST))
                    if parsed_date != dt.datetime.min.replace(tzinfo=c.KST) and not at - dt.timedelta(days=source_days) <= parsed_date <= at + dt.timedelta(minutes=5):
                        row['outside_window'] += 1
                        continue
                modified = c.timestamp(item.get('modified_at'), dt.datetime.min.replace(tzinfo=c.KST))
                if source.get('adapter') == 'govuk_search' and modified != dt.datetime.min.replace(tzinfo=c.KST) and modified < at - dt.timedelta(days=source_days):
                    # An old last-modified upper bound cannot hide a newer first publication.
                    row['outside_window'] += 1
                    continue
                if source.get('adapter') == 'govuk_search' and assessment['label'] != 'Irrelevant':
                    prior_date = ledger.get(aid, {}).get('provider_publication_value')
                    if prior_date and ledger[aid].get('publication_date_basis') == 'GOVUK_first_published_at':
                        item = {**item, 'published': prior_date, 'publication_date_basis': 'GOVUK_first_published_at'}
                    elif date_lookups < source.get('max_date_lookups', 10):
                        date_lookups += 1
                        try:
                            path = urllib.parse.urlsplit(url).path
                            doc = json.loads(loader('https://www.gov.uk/api/content' + path))
                            if not isinstance(doc, dict):
                                raise ValueError('invalid_GOVUK_metadata_object')
                            item = {**item, 'published': doc.get('first_published_at', ''),
                                    'publication_date_basis': 'GOVUK_first_published_at'}
                        except (OSError, ValueError, KeyError) as exc:
                            row['date_lookup_error'] = str(exc)[:160]
                sentinel = dt.datetime.min.replace(tzinfo=c.KST)
                actual_date = c.timestamp(item.get('pubDate') or item.get('published'), sentinel)
                if actual_date != sentinel and not at - dt.timedelta(days=source_days) <= actual_date <= at + dt.timedelta(minutes=5):
                    row['outside_window'] += 1
                    continue
                if assessment['label'] in row['classifications']:
                    row['classifications'][assessment['label']] += 1
                    if not is_statistical(source) and item.get('record_type', 'news') == 'news':
                        row['news_classifications'][assessment['label']] += 1
                else:
                    row['statistical_records'] = row.get('statistical_records', 0) + 1
                first_seen = ledger.get(aid, {}).get('first_discovered_at', c.iso(at))
                already_seen = aid in previous_ids or aid in run_ids
                row['duplicates' if already_seen else 'new_discoveries'] += 1
                run_ids.add(aid)
                published = valid_date(item, at, source_days)
                if assessment['label'] != 'Irrelevant' and not permission(source):
                    row['rights_holds'] += 1
                if assessment['label'] != 'Irrelevant' and not published:
                    row['date_holds'] += 1
                if (published and at - dt.timedelta(days=7) <= published <= at
                        and item.get('date_precision') != 'date'
                        and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(item.get('pubDate') or item.get('published') or '').strip())
                        and item.get('publication_time_verified_for_news') is not False
                        and not is_statistical(source) and item.get('record_type', 'news') == 'news'):
                    cohort['observed'].add(aid)
                    if assessment['label'] == 'Irrelevant':
                        cohort['irrelevant'].add(aid)
                    else:
                        cohort['candidates'].add(aid)
                        if not permission(source):
                            cohort['rights_held'].add(aid)
                        elif c.article_from_item({**item, 'title': title, 'link': url}, source, at, reviews or {}):
                            cohort['approved'].add(aid)
                status = ('exclude' if assessment['decision'] == 'exclude' else
                          'rights_hold' if not permission(source) else
                          'date_hold' if not published else assessment['decision'])
                candidate = {'id': aid, 'title': title, 'url': url, 'source_id': sid,
                             'source_ids': sorted(set(ledger.get(aid, {}).get('source_ids', [])) | {sid}),
                             'source': source['name'], 'first_discovered_at': first_seen,
                             'last_seen_at': c.iso(at), 'published_at': c.iso(actual_date) if actual_date != sentinel else None,
                             'provider_publication_value': item.get('pubDate') or item.get('published'),
                             'provider_seen_at': item.get('discovered_by_provider_at'),
                             'provider_modified_at': item.get('modified_at'),
                             'publication_date_basis': item.get('publication_date_basis', 'feed_publication_date'),
                             'date_precision': item.get('date_precision', 'timestamp'),
                             'record_type': item.get('record_type', 'news'),
                             'is_backfill': bool(published and published < at - dt.timedelta(days=30)),
                             'relevance_evidence': assessment, 'publication_status': status,
                             'publication_policy': source.get('publication', {'status': 'review'}),
                             'relevance_label': assessment['label']}
                if item.get('discovery_origin'):
                    candidate['discovery_origin'] = item['discovery_origin']
                candidate['editorial'] = exposure(candidate)
                candidate['korea_priority'] = candidate['editorial']['tier'] == 'korea_direct'
                # A discovery-only service cannot overwrite a previously licensed
                # publisher's validated date/permission for the same URL.
                prior = ledger.get(aid)
                if prior and prior.get('discovery_origin') and not candidate.get('discovery_origin'):
                    candidate['discovery_origin'] = prior['discovery_origin']
                if prior and prior.get('publication_status') == 'published' and status in ('rights_hold', 'date_hold'):
                    candidate = {**prior, 'last_seen_at': c.iso(at), 'source_ids': candidate['source_ids']}
                ledger[aid] = candidate
                if permission(source) and published:
                    item = {**item, 'title': title, 'link': url}
                    approved_items.append(item)
                    metadata[aid] = candidate
            prepared[source['url']] = feed_bytes(approved_items)
            row['status'] = 'ok'
        except (OSError, ValueError, KeyError, TypeError, c.ET.ParseError) as exc:
            errors[source['url']] = exc
            row.update({'status': 'error', 'error_kind': 'access_policy' if isinstance(exc, AccessBlocked) else c.failure_details(exc)['error_kind'],
                        'error': str(exc)[:250]})
        metric = source_metrics.setdefault(sid, {'attempts': 0, 'successes': 0, 'errors': {}})
        metric['attempts'] += 1
        metric['successes'] += row['status'] == 'ok'
        if row['status'] != 'ok':
            kind = row['error_kind']
            metric['errors'][kind] = metric['errors'].get(kind, 0) + 1
        row['success_rate'] = metric['successes'] / metric['attempts']
        metric['last_checked_at'] = c.iso(at)
        health.append(row)

    def publication_feed(url):
        if url in errors:
            raise OSError(str(errors[url]))
        return prepared[url]
    if old_articles and original.get('schema_version', 1) <= 2 and not (state_dir / 'v02_snapshot.json').exists():
        c.write_atomic(state_dir / 'v02_snapshot.json', original)
    approved_sources = [s for s in sources if s.get('enabled', True) and permission(s)]
    # The legacy collector stages all record types privately. A public news.json
    # must never transiently contain filings, including for old open browser tabs.
    state_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='publication-', dir=state_dir) as staging:
        stage = Path(staging)
        c.write_atomic(stage / 'news.json', original)
        result = c.run(approved_sources, fetcher=publication_feed, at=at, data_dir=stage,
                       state_dir=state_dir, reviews=reviews, retention_days=days, max_articles=4500)
        news = c.read_json(stage / 'news.json', original)
        stage_health = c.read_json(stage / 'health.json', {})
    articles = news.get('articles', [])
    briefing_health = None
    # Never stamp first_seen/published timestamps onto old records on every run.
    if result['status'] != 'failed':
        selected_ids = {a['id'] for a in articles}
        for old_record in old_articles:
            if old_record['id'] not in selected_ids:
                articles.append({**old_record, 'archived_only': True,
                                 'archive_reason': 'not_selected_by_current_publication_window_or_rules'})
        for article in articles:
            prior_origin = original_by_id.get(article['id'], {}).get('discovery_origin')
            if prior_origin and not article.get('discovery_origin'):
                article['discovery_origin'] = prior_origin
            candidate = metadata.get(article['id'])
            if candidate:
                for key in ('first_discovered_at', 'publication_date_basis', 'date_precision', 'record_type', 'korea_priority', 'is_backfill'):
                    article[key] = candidate[key]
                article['publication_policy'] = candidate['publication_policy']
                if candidate.get('discovery_origin'):
                    article['discovery_origin'] = candidate['discovery_origin']
                prior_first = original_by_id.get(article['id'], {}).get('first_published_by_engine_at')
                if prior_first:
                    article['first_published_by_engine_at'] = prior_first
                elif article['id'] not in old_ids:
                    article['first_published_by_engine_at'] = c.iso(at)
                if candidate['publication_policy'].get('attribution'):
                    article['desc'] = '원문 링크에서 공식 자료를 확인하세요. ' + candidate['publication_policy']['attribution']
                ledger[article['id']]['publication_status'] = 'published' if gate.allows(article) else 'rights_hold'
        articles, newsroom, filings, other_views = gate.views(articles)
        news['articles'] = articles
        news['count'] = len(articles)
        news['records_scope'] = 'all_stored_records_including_rights_holds_and_filings'
        news['schema_version'] = 3
        # Persist the complete archive before replacing a legacy mixed news.json.
        c.write_atomic(archive_path, news)
    policy_reprojection = gate.needs_reprojection(articles, state_dir)
    gate.write_manifest(articles, data_dir, at)
    if result['status'] != 'failed' or policy_reprojection:
        _, newsroom, filings, other_views = gate.views(articles)
        for name, items in (('news', newsroom), ('newsroom', newsroom), ('filings', filings),
                            ('research', other_views)):
            c.write_atomic(data_dir / (name + '.json'), {'schema_version': 4, 'mode': news.get('mode', 'live_rss'),
                           'generated_at': news.get('generated_at'), 'last_successful_fetch': news.get('last_successful_fetch'),
                           'count': len(items), 'public_fields': list(public_record(items[0])) if items else ['title', 'source', 'published_at', 'url', 'category', 'keywords'],
                           'articles': [public_record(a) for a in items]})
        try:
            current_briefing = save_briefing(newsroom, data_dir, state_dir, at, news.get('last_successful_fetch'),
                                             news.get('mode','live_rss'), collection={'sources': health})
            briefing_health = {'status': 'ok', 'checked_at': c.iso(at), 'selection_status': current_briefing['status']}
        except (OSError, ValueError, TypeError, KeyError):
            # Do not confuse a failed generator/write with an empty candidate set.
            # No exception payload (which can contain credentials) is public.
            briefing_health = {'status': 'failed', 'checked_at': c.iso(at),
                               'error_kind': 'generation_or_write_failed', 'previous_data_preserved': True}
        if result['status'] != 'failed' and legacy_archive.exists():
            legacy_archive.unlink()  # full original is preserved outside the Pages directory
    # A network failure preserves stored records. An explicit rights change
    # still removes/restores public views without inventing a successful fetch.
    metric_articles, newsroom, filings, other_views = gate.views(articles)
    try:
        visibility_health = gate.write_history(articles, state_dir, at)
    except (OSError, ValueError, KeyError, TypeError):
        visibility_health = {'status': 'failed', 'error_kind': 'visibility_history_write_failed'}
    public_records = newsroom + filings + other_views
    published_ids = {a['id'] for a in public_records}
    new_published = published_ids - old_ids
    for row in health:
        cohort = cohorts[row['id']]
        # Compare unique IDs in this run's 7-day cohort, never cumulative stock
        # against a feed's observation count. An outage is unknown, not zero.
        public = {a['id'] for a in newsroom if a['source_id'] == row['id']}
        n, approved = len(cohort['candidates']), len(cohort['approved'])
        visible = len(cohort['candidates'] & public)
        row['news_conversion_last7d'] = None if row['status'] != 'ok' else {
            'observed_unique': len(cohort['observed']), 'industry_candidates': n,
            'approved_candidates': approved, 'public_observed_candidates': visible,
            'new_public_candidates': len(cohort['candidates'] & public & new_published),
            'irrelevant_unique': len(cohort['irrelevant']), 'rights_held_unique': len(cohort['rights_held']),
            'candidate_to_approved': approved / n if n else None,
            'candidate_to_public': visible / n if n else None,
            'definition': 'unique_URL_IDs_in_successful_feed_this_run; verified_publication_in_last7d; approval_includes_Indirect_review; public_count_requires_matching_source_id; new_excludes_existing_archive; non_news_excluded'}
        row['new_auto_published'] = sum(a['id'] in new_published and a['source_id'] == row['id'] for a in articles)
        row['new_newsroom_items'] = sum(a['id'] in new_published and a['source_id'] == row['id'] for a in newsroom)
        row['outcome'] = ('fetch_failed' if row['status'] != 'ok' else 'auto_published' if row['new_auto_published'] else
                          'no_new_candidate' if not row['new_discoveries'] else 'discovered_not_publishable')
    summary = {'schema_version': 3, 'checked_at': c.iso(at), 'publication_result': result['status'],
               'discovery_status': 'failed' if not any(h['status'] == 'ok' for h in health) else
                                   'ok' if all(h['status'] == 'ok' for h in health) else 'partial',
               'received': sum(h['received'] for h in health),
               'new_discoveries': sum(h['new_discoveries'] for h in health),
               'duplicate_observations': sum(h['duplicates'] for h in health),
               'new_auto_published': len(new_published), 'total_published': len(public_records),
               'total_published_scope': 'current_public_views_all_record_types',
               'total_archived': len(articles), 'newsroom_count': len(newsroom), 'filings_count': len(filings),
               'other_research_count': len(other_views),
               'new_newsroom_items': sum(a['id'] in new_published for a in newsroom),
               'new_filings': sum(a['id'] in new_published for a in filings),
               'newsroom_korea_direct_count': sum(a['editorial']['tier'] == 'korea_direct' for a in newsroom),
               'newsroom_korea_direct_last7d': sum(a['editorial']['tier'] == 'korea_direct' and a.get('date_precision') != 'date' and at - dt.timedelta(days=7) <= c.timestamp(a['published_at']) <= at for a in newsroom),
               'newsroom_by_source': {sid: {'count': sum(a['source_id'] == sid for a in newsroom),
                    'originally_published_last7d': sum(a['source_id'] == sid and a.get('date_precision') != 'date' and at - dt.timedelta(days=7) <= c.timestamp(a['published_at']) <= at for a in newsroom),
                    'korea_direct': sum(a['source_id'] == sid and a['editorial']['tier'] == 'korea_direct' for a in newsroom),
                    'new_this_run': sum(a['source_id'] == sid and a['id'] in new_published for a in newsroom)} for sid in sorted({a['source_id'] for a in newsroom})},
               'newsroom_category_counts': {category: sum(a['category'] == category for a in newsroom) for category in c.CATEGORIES},
               'newsroom_tier_counts': {tier: sum(a['editorial']['tier'] == tier for a in newsroom) for tier in ('korea_direct', 'global_major', 'reference')},
               'newsroom_originally_published_last24h': sum(a.get('publication_time_verified_for_news') is not False and a.get('date_precision') != 'date' and at - dt.timedelta(days=1) <= c.timestamp(a['published_at']) <= at for a in newsroom),
               'newsroom_originally_published_last7d': sum(a.get('date_precision') != 'date' and at - dt.timedelta(days=7) <= c.timestamp(a['published_at']) <= at for a in newsroom),
               'newsroom_newly_added_last24h': sum(bool(a.get('first_published_by_engine_at')) and c.timestamp(a['first_published_by_engine_at']) >= at - dt.timedelta(days=1) for a in newsroom),
               'new_backfilled': sum(a['id'] in new_published and a.get('is_backfill', False) for a in articles),
               'record_type_counts': {kind: sum(a.get('record_type', 'news') == kind for a in metric_articles) for kind in ('news', 'regulatory_filing', 'statistical_release', 'government_notice')},
               'category_counts': {k: sum(a['category'] == k for a in public_records) for k in c.CATEGORIES},
               'discovered_last24h': sum(c.timestamp(a['first_discovered_at']) >= at - dt.timedelta(days=1) for a in ledger.values()),
               'discovered_last7d': sum(c.timestamp(a['first_discovered_at']) >= at - dt.timedelta(days=7) for a in ledger.values()),
               'auto_published_last24h': sum(bool(a.get('first_published_by_engine_at')) and c.timestamp(a['first_published_by_engine_at']) >= at - dt.timedelta(days=1) for a in articles),
               'auto_published_last7d': sum(bool(a.get('first_published_by_engine_at')) and c.timestamp(a['first_published_by_engine_at']) >= at - dt.timedelta(days=7) for a in articles),
               'originally_published_last24h': sum(a.get('publication_time_verified_for_news') is not False and a.get('date_precision') != 'date' and at - dt.timedelta(days=1) <= c.timestamp(a['published_at']) <= at for a in articles),
               'originally_published_last7d': sum(a.get('publication_time_verified_for_news') is not False and at - dt.timedelta(days=7) <= c.timestamp(a['published_at']) <= at for a in articles),
               'sources': health}
    source_counts = {sid: sum(a['source_id'] == sid for a in newsroom) for sid in sorted({a['source_id'] for a in newsroom})}
    news_classifications = {label: sum(row['news_classifications'][label] for row in health) for label in ('Direct', 'Indirect', 'Irrelevant')}
    evaluated = sum(news_classifications.values())
    observed = summary['new_discoveries'] + summary['duplicate_observations']
    old_news_sources = {a.get('source_id') for a in old_articles if a.get('record_type', 'news') == 'news' and not a.get('archived_only')}
    public_labels = {label: sum(a.get('relevance_label') == label for a in newsroom) for label in ('Direct', 'Indirect', 'Irrelevant')}
    summary['quality'] = {
        'configured_sources': len(sources), 'enabled_sources': sum(s.get('enabled', True) for s in sources),
        'attempted_sources': sum(row['fetch_attempted'] for row in health),
        'successful_sources': sum(row['status'] == 'ok' for row in health),
        'publication_approved_sources': len(approved_sources), 'publishing_sources': len(source_counts),
        'new_publishing_sources': sorted(set(source_counts) - old_news_sources),
        'new_news_articles': summary['new_newsroom_items'], 'published_news_articles': len(newsroom),
        'originally_published_last24h': summary['newsroom_originally_published_last24h'],
        'originally_published_last7d': summary['newsroom_originally_published_last7d'],
        'evaluated_news_classifications': news_classifications,
        'direct_ratio': news_classifications['Direct'] / evaluated if evaluated else None,
        'direct_ratio_denominator': 'classified_news_feed_observations_within_window_excluding_filings_and_statistics',
        'top3_source_share': sum(sorted(source_counts.values(), reverse=True)[:3]) / len(newsroom) if newsroom else None,
        'duplicate_ratio': summary['duplicate_observations'] / observed if observed else None,
        'duplicate_ratio_denominator': 'valid_discovery_observations_new_plus_previously_seen_not_removed_independent_reports',
        'news_by_source': source_counts,
        'public_news_relevance_counts': public_labels,
        'public_news_direct_ratio': public_labels['Direct'] / len(newsroom) if newsroom else None,
        'rights_held_news_count': sum(a['record_type']=='news' and not gate.allows(a) for a in metric_articles),
        'rights_held_news_by_source': {sid: sum(a['record_type']=='news' and (a.get('source_id') or 'unregistered')==sid for a in metric_articles) for sid in sorted({a.get('source_id') or 'unregistered' for a in metric_articles if a['record_type']=='news' and not gate.allows(a)})},
        'public_record_count': len(public_records),
        'public_metrics_as_of': c.iso(at),
        'stored_news_count': sum(a['record_type']=='news' for a in metric_articles),
        'failed_sources': [{'id': row['id'], 'error_kind': row.get('error_kind'), 'error': row.get('error')} for row in health if row['status'] != 'ok'],
        'source_gates': [{'id': s['id'], 'enabled': s.get('enabled', True),
                          'discovery_allowed': s.get('discovery_allowed', True), 'publication_approved': permission(s)} for s in sources]}
    if batch:
        for pid, metric in batch.metrics.items():
            metric['persisted_candidate_count'] = sum(a.get('discovery_origin', {}).get('provider_id') == pid for a in ledger.values())
            metric['new_stored_records'] = sum(a['id'] not in old_ids and a.get('discovery_origin', {}).get('provider_id') == pid for a in articles)
            metric['new_public_news'] = sum(a['id'] in new_published and a.get('discovery_origin', {}).get('provider_id') == pid for a in newsroom)
            metric['public_news_count'] = sum(a.get('discovery_origin', {}).get('provider_id') == pid for a in newsroom)
        summary['discovery_providers'] = batch.metrics
        if summary['discovery_status'] == 'ok' and (any(r['status'] == 'error' for r in batch.metrics.values()) or any(h.get('primary_feed_status') for h in health)):
            summary['discovery_status'] = 'partial'
        metrics_doc['discovery_providers'] = batch.cursors
    summary['publication_visibility'] = {**visibility_health, 'policy_reprojection': policy_reprojection}
    summary['quality']['domestic_coverage'] = coverage(newsroom, sources, at, previous_newsroom)
    if briefing_health is not None:
        summary['briefing'] = briefing_health
    summary['outcome'] = ('all_fetches_failed' if summary['discovery_status'] == 'failed' else
                          'publication_blocked_by_rights' if not approved_sources else
                          'publication_sources_failed' if result['status'] == 'failed' else
                          'new_newsroom_news' if summary['new_newsroom_items'] else
                          'new_filings_archived' if summary['new_filings'] else
                          'new_archive_records' if new_published else
                          'no_new_publications_with_source_errors' if summary['discovery_status'] == 'partial' else
                          'no_new_publications')
    # Ledger and metrics survive even if all publication sources fail; public
    # news/briefing are still protected by the existing collector's failure path.
    for candidate in ledger.values():
        if not permission({'publication': candidate.get('publication_policy', {})}):
            # This state is committed to Git, which may be public. Do not turn
            # a discovery-only RSS headline into unlicensed republication there.
            if candidate.get('title'):
                candidate['title_sha256'] = hashlib.sha256(candidate['title'].encode()).hexdigest()
            candidate['title'] = None
            candidate['title_storage'] = 'withheld_until_metadata_reuse_approved'
    c.write_atomic(state_dir / 'discovery.json', {'schema_version': 3, 'candidates': ledger})
    c.write_atomic(state_dir / 'source_metrics.json', {**metrics_doc, 'schema_version': 3, 'sources': source_metrics})
    c.write_atomic(state_dir / 'run_summary.json', summary)
    health_doc = stage_health
    health_doc['discovery'] = summary
    health_doc['publication_visibility'] = summary['publication_visibility']
    if briefing_health is not None:
        health_doc['briefing'] = briefing_health
    c.write_atomic(data_dir / 'health.json', health_doc)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', default=str(c.DATA))
    parser.add_argument('--backfill-days', type=int, choices=range(30, 91), default=90,
                        help='Only use provider-returned metadata within 30..90 days; no archive crawling')
    parser.add_argument('--reviews', default=str(c.ROOT / 'relevance_reviews.json'))
    parser.add_argument('--sources', default=str(c.ROOT / 'sources.json'))
    args = parser.parse_args()
    sources = c.read_json(Path(args.sources), {})['sources']
    data = Path(args.dir)
    state = c.ROOT / 'collector_state' if data.resolve() == c.DATA.resolve() else data / 'collector_state'
    reviews = c.read_json(Path(args.reviews), {}).get('approvals', {})
    summary = execute(sources, data, state, reviews, days=args.backfill_days)
    print(json.dumps({k: v for k, v in summary.items() if k != 'sources'}, ensure_ascii=False))
    return 1 if summary['publication_result'] == 'failed' or summary.get('briefing', {}).get('status') == 'failed' or summary.get('publication_visibility', {}).get('status') == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
