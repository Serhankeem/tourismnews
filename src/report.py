"""Render existing telemetry for GitHub Actions, without credentials or bodies."""
import json
from pathlib import Path


def render(data):
    rows = ['## Tourism News collection', '', 'Checked: ' + data.get('checked_at', 'unknown'), '',
            '| Metric | Value |', '| --- | ---: |']
    for key in ('total_archived', 'newsroom_count', 'filings_count', 'other_research_count', 'newsroom_korea_direct_count',
                'newsroom_korea_direct_last7d', 'newsroom_originally_published_last24h', 'newsroom_originally_published_last7d', 'newsroom_newly_added_last24h', 'new_newsroom_items', 'new_filings', 'received', 'new_discoveries', 'duplicate_observations', 'new_auto_published',
                'total_published', 'new_backfilled', 'auto_published_last24h', 'auto_published_last7d',
                'originally_published_last24h', 'originally_published_last7d'):
        rows.append(f'| {key} | {data.get(key, 0)} |')
    quality = data.get('quality', {})
    if quality:
        rows += ['', '### News coverage quality (discovery vs publication)', '', '| Metric | Value |', '| --- | ---: |']
        for key in ('configured_sources', 'attempted_sources', 'successful_sources', 'publication_approved_sources',
                    'publishing_sources', 'new_news_articles', 'published_news_articles', 'rights_held_news_count', 'public_news_direct_ratio', 'originally_published_last24h',
                    'originally_published_last7d', 'direct_ratio', 'top3_source_share', 'duplicate_ratio'):
            rows.append(f'| {key} | {quality.get(key)} |')
        rows += ['', 'Direct ratio: ' + quality['direct_ratio_denominator'],
                 'Duplicate ratio: ' + quality['duplicate_ratio_denominator']]
        domestic = quality.get('domestic_coverage')
        if domestic:
            rows += ['', '### Domestic coverage (current public news only)', '',
                     '| Metric | Value |', '| --- | ---: |']
            for key in ('domestic_publishing_sources', 'new_domestic_publishing_sources',
                        'domestic_publisher_news_count', 'domestic_publisher_news_last7d',
                        'domestic_korea_direct_news_count', 'domestic_korea_direct_news_last7d',
                        'domestic_top3_source_share', 'domestic_supply_routes', 'domestic_identified_publishers'):
                rows.append(f'| {key} | {domestic[key]} |')
            rows += ['', 'Publisher country is not evidence of Korean-market relevance.', '',
                     '| Domestic media type | Public news |', '| --- | ---: |']
            rows += [f'| {kind} | {count} |' for kind, count in domestic['domestic_news_by_media_type'].items()]
    rows += ['', 'Outcome: ' + data.get('outcome', 'unknown'), '',
             '| Source | Status | Received | New | Archive added | Newsroom added | Rights holds | Error |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for source in data.get('sources', []):
        values = [source.get('id'), source.get('status'), source.get('received', 0),
                  source.get('new_discoveries', 0), source.get('new_auto_published', 0), source.get('new_newsroom_items', 0),
                  source.get('rights_holds', 0), source.get('error', '')]
        rows.append('| ' + ' | '.join(str(v).replace('|', '/').replace('\n', ' ') for v in values) + ' |')
    rows += ['', '| Newsroom source | Published | Issued last 7d | Korea direct | New this run |', '| --- | ---: | ---: | ---: | ---: |']
    for sid, counts in data.get('newsroom_by_source', {}).items():
        rows.append('| ' + ' | '.join(str(v) for v in (sid, counts['count'], counts['originally_published_last7d'], counts['korea_direct'], counts['new_this_run'])) + ' |')
    rows += ['', 'Archive admissions (legacy new_auto_published) include filings. Newsroom metrics count news only. Newly added items are NOT necessarily newly issued news. See original publication dates and date precision.']
    return '\n'.join(rows) + '\n'


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'site/data/health.json'
    if path.exists():
        data = json.loads(path.read_text()).get('discovery')
        print(render(data) if data else 'No v0.3 telemetry available; inspect collector logs and health.json.')
    else:
        print('No collection health file available; inspect collector logs.')
