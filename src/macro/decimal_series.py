"""Private exact-decimal series. No public projection or financial-ledger migration."""
import copy
import re
from .model import decimal_value, valid_period

KINDS = {'decimal_index', 'decimal_exchange_rate'}
HASH = re.compile(r'[a-f0-9]{64}')
IDENTITY = ('unit', 'frequency', 'base_year', 'value_kind', 'definition', 'stat_code', 'item_codes', 'source_id', 'publisher', 'provider', 'storage')


def validate_archive(archive, before=None):
    """Optional extension of macro_archive.json, separate from integer indicators."""
    series = archive.get('decimal_indicators', {})
    if not isinstance(series, dict) or not isinstance(archive.get('decimal_sources', {}), dict):
        raise ValueError('decimal_archive_invalid')
    for item in series.values():
        if (not isinstance(item, dict) or item.get('value_kind') not in KINDS
                or item.get('frequency') != 'M' or not isinstance(item.get('observations'), dict)
                or not isinstance(item.get('revisions'), list)):
            raise ValueError('decimal_archive_invalid')
        for p, record in item['observations'].items():
            valid_period(p)
            if not isinstance(record, dict):
                raise ValueError('decimal_record_invalid')
            if (decimal_value(record.get('value')) != record['value']
                    or decimal_value(record.get('source_value')) != record['value']
                    or any(record.get(k) != item.get(k) for k in ('unit', 'frequency', 'base_year', 'stat_code', 'item_codes'))
                    or record.get('finality') not in ('not_stated', 'provisional', 'final')
                    or not record.get('first_collected_at') or not record.get('last_collected_at')
                    or record.get('release_published_at') is not None
                    or record.get('original_publication_at') is not None
                    or not isinstance(record.get('response_sha256'), list)
                    or not record.get('response_sha256')
                    or any(not isinstance(h, str) or not HASH.fullmatch(h) for h in record['response_sha256'])):
                raise ValueError('decimal_record_invalid')
        for revision in item['revisions']:
            if not isinstance(revision, dict):
                raise ValueError('decimal_revision_invalid')
            valid_period(revision['period'])
            if not revision.get('before') or not revision.get('after') or not revision.get('detected_at'):
                raise ValueError('decimal_revision_invalid')
    if before:
        for key, old in before.get('decimal_indicators', {}).items():
            new = series.get(key, {})
            if (any(new.get(k) != old.get(k) for k in IDENTITY)
                    or not old['observations'].keys() <= new.get('observations', {}).keys()
                    or not all(r in new.get('revisions', []) for r in old['revisions'])):
                raise ValueError('decimal_history_lost')
            for p, prior in old['observations'].items():
                current = new['observations'][p]
                if prior['first_collected_at'] != current['first_collected_at']:
                    raise ValueError('decimal_first_collection_changed')
                if any(prior[k] != current[k] for k in ('value', 'finality')) and not any(
                        r['period'] == p and r['before'] == prior and r['after'] == current
                        for r in new['revisions']):
                    raise ValueError('decimal_revision_missing')


def merge(archive, source, items, snapshot, at):
    """Stage the complete source before accepting any changes; old vintages retained."""
    validate_archive(archive)
    staged = copy.deepcopy(archive)
    saved_items = staged.setdefault('decimal_indicators', {})
    counts = dict(new_observations=0, unchanged_observations=0, value_corrections=0, status_changes=0)
    for item in items:
        identity = {k: item[k] for k in IDENTITY}
        saved = saved_items.setdefault(item['id'], dict(**identity, observations={}, revisions=[]))
        if any(saved.get(k) != identity[k] for k in IDENTITY):
            raise ValueError('decimal_identity_changed')
        for period, detail in snapshot['records'][item['id']].items():
            old = saved['observations'].get(period)
            record = dict(**detail, first_collected_at=old['first_collected_at'] if old else at.isoformat(),
                          last_collected_at=at.isoformat())
            if old is None:
                counts['new_observations'] += 1
            elif any(old[k] != record[k] for k in ('value', 'finality')):
                changed = old['value'] != record['value']
                counts['value_corrections' if changed else 'status_changes'] += 1
                saved['revisions'].append(dict(period=period, detected_at=at.isoformat(),
                    kind='value_correction' if changed else 'finality_change', before=copy.deepcopy(old), after=copy.deepcopy(record)))
            else:
                counts['unchanged_observations'] += 1
            saved['observations'][period] = record
    staged.setdefault('decimal_sources', {})[source['id']] = dict(
        reference_period=snapshot['reference_period'], last_successful_check=at.isoformat(),
        collection_mode=snapshot['collection_mode'], authentication_verified=snapshot['authentication_verified'],
        response_sha256=snapshot['response_sha256'])
    validate_archive(staged, archive)
    return staged, counts
