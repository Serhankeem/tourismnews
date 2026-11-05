"""Publisher diversity and title-only signals; never infer original reporting.

Matching headlines suggest shared material, not proof of a copied press release.
Different headlines/bylines do not establish independent reporting either.
"""
import datetime as dt
import re
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlsplit

if __package__:
    from . import collector as c
else:
    import collector as c

SENTINEL = dt.datetime.min.replace(tzinfo=c.KST)


def article_domain_allowed(source, url):
    allowed = source.get('article_domains')
    if allowed is None:
        return True  # Unmapped sources retain their existing policy.
    parts = urlsplit(url)
    return (parts.scheme in ('http', 'https') and not parts.username and not parts.password
            and parts.hostname in allowed)


def publisher_key(source):
    cfg = source.get('coverage', {})
    return cfg.get('publisher_id') or cfg.get('publisher') or source['id']


def provenance(articles):
    """Conservative signals only; no article bodies, embeddings or dedup edits."""
    declared = {a['id'] for a in articles if a.get('id') and re.search(
        r'^\[(?:보도자료|뉴스와이어|PRNewswire|Business\s?Wire)\]|/\s*(?:PRNewswire|Business\s?Wire)\s*/',
        a.get('title', ''), re.I)}
    pairs = []
    for index, a in enumerate(articles):
        for b in articles[index + 1:]:
            if not all(x.get('id') and x.get('title') for x in (a, b)):
                continue
            pa = a.get('_publisher', a.get('source_id'))
            pb = b.get('_publisher', b.get('source_id'))
            if not pa or not pb or pa == pb:
                continue
            dates = [c.timestamp(x.get('published_at'), SENTINEL) for x in (a, b)]
            if SENTINEL in dates or abs((dates[0] - dates[1]).total_seconds()) > 72 * 3600:
                continue
            ta, tb = c.normalized_title(a['title']), c.normalized_title(b['title'])
            numbers_a = re.findall(r'\d+(?:[.,]\d+)*', a['title'])
            numbers_b = re.findall(r'\d+(?:[.,]\d+)*', b['title'])
            if numbers_a != numbers_b:
                continue
            similarity = SequenceMatcher(None, ta, tb).ratio() if ta and tb else 0
            if similarity >= .94:
                pairs.append({'article_ids': sorted([a['id'], b['id']]),
                              'signal': 'possible_shared_headline',
                              'title_similarity': round(similarity, 4),
                              'original_reporting': 'unverified'})
    return {
        'declared_distribution_news': len(declared),
        'possible_shared_headline_pairs': pairs,
        'unknown_origin_news': len(articles) - len(declared),
        'independent_reporting_verified': 0,
        'definition': 'title_metadata_signals_only; identical titles are not proof of syndication; '
                      'distinct titles are not proof of independent reporting; articles are not removed',
    }


def publisher_diversity(newsroom, sources, at):
    cfg = {s['id']: s for s in sources}
    domestic = [dict(a, _publisher=publisher_key(cfg[a['source_id']])) for a in newsroom
                if cfg.get(a.get('source_id'), {}).get('coverage', {}).get('publisher_jurisdiction') == 'KR']
    counts = Counter(a['_publisher'] for a in domestic)
    recent = [a for a in domestic if a.get('date_precision') != 'date'
              and a.get('publication_time_verified_for_news') is not False
              and at - dt.timedelta(days=7) <= c.timestamp(a['published_at'], SENTINEL) <= at]
    return {
        'domestic_publishers': len(counts),
        'news_by_publisher': dict(sorted(counts.items())),
        'domestic_top3_publisher_share': sum(sorted(counts.values(), reverse=True)[:3]) / len(domestic) if domestic else None,
        'domestic_news_last7d': len(recent),
        'korea_direct_news_last7d': sum(a.get('editorial', {}).get('tier') == 'korea_direct' for a in recent),
        'article_domains': dict(sorted(Counter(urlsplit(a.get('url', '')).hostname or 'unknown' for a in domestic).items())),
        'provenance': provenance(domestic),
        'definition': 'explicit_KR_publisher_registry; multiple feeds of the same publisher counted once; '
                      'media plurality is not verified independent reporting',
    }
