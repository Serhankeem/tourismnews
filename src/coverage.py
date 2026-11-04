"""Coverage of CURRENT rights-gated news, never discovery/filing totals.

Publisher jurisdiction and Korean-market relevance are separate dimensions.
Unknown publishers stay unknown. A relay's route is not an issuing institution.
"""
import datetime as dt
from collections import Counter
if __package__:
    from . import collector as c
    from .editorial import publication_order
else:
    import collector as c
    from editorial import publication_order

MEDIA_TYPES = ('tourism_specialist', 'general_economy', 'corporate', 'public', 'unknown')


def coverage(newsroom, sources, at, previous_newsroom=()):
    configs = {s['id']: s.get('coverage', {}) for s in sources}

    def domestic(a):
        return configs.get(a.get('source_id'), {}).get('publisher_jurisdiction') == 'KR'

    def korean(a):
        return a.get('editorial', {}).get('tier') == 'korea_direct'

    def recent(a):
        # Fail closed; never turn registration/discovery time or date-only data
        # into a verified rolling-window publication timestamp.
        if a.get('date_precision') == 'date' or a.get('publication_time_verified_for_news') is False:
            return False
        stamp = -publication_order(a)[0]
        return (at - dt.timedelta(days=7)).timestamp() <= stamp <= at.timestamp()

    domestic_news = [a for a in newsroom if domestic(a)]
    counts = Counter(a['source_id'] for a in domestic_news)
    previous = {a['source_id'] for a in previous_newsroom if domestic(a)}
    mix = Counter(configs[a['source_id']].get('media_type', 'unknown') for a in domestic_news)
    # Only configured verified publisher identity is counted. A future multi-
    # agency adapter must supply validated origin metadata before activation.
    institutions = {configs[a['source_id']]['publisher'] for a in domestic_news
                    if configs[a['source_id']].get('publisher')}
    routes = {configs[a['source_id']].get('supply_route', a['source_id']) for a in domestic_news}
    return {
        'definition': 'domestic_publisher=explicit_KR_configuration; korean_market=editorial_korea_direct; counts=current_public_news_only',
        'domestic_publishing_sources': len(counts),
        'new_domestic_publishing_sources': sorted(set(counts) - previous),
        'domestic_publisher_news_count': len(domestic_news),
        'domestic_publisher_news_last7d': sum(recent(a) for a in domestic_news),
        'domestic_korea_direct_news_count': sum(korean(a) for a in domestic_news),
        'domestic_korea_direct_news_last7d': sum(korean(a) and recent(a) for a in domestic_news),
        'korea_direct_news_all_publishers': sum(korean(a) for a in newsroom),
        'domestic_top3_source_share': sum(sorted(counts.values(), reverse=True)[:3]) / len(domestic_news) if domestic_news else None,
        'domestic_news_by_source': dict(sorted(counts.items())),
        'domestic_news_by_media_type': {kind: mix[kind] for kind in MEDIA_TYPES},
        'domestic_news_by_category': {kind: sum(a.get('category') == kind for a in domestic_news) for kind in c.CATEGORIES},
        'domestic_supply_routes': len(routes),
        'domestic_identified_publishers': len(institutions),
        'unclassified_publisher_news_count': sum(not configs.get(a.get('source_id'), {}).get('publisher_jurisdiction') for a in newsroom),
    }
