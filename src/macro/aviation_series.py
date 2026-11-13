"""Private integer airport ledger within macro_archive.json; no public records."""
import copy
import hashlib
import json
import re
from . import aviation
from .model import decimal_comparisons, months, valid_period

IDENTITY = ('source_id','metric','unit','frequency','value_kind','storage','definition','publisher','scope')
COUNTS = ('value','arrivals','departures')


def comparisons(observations, period):
    result = decimal_comparisons({p: {'value': str(o['value'])} for p,o in observations.items()},period)
    result['aggregation_policy'] = 'monthly_airport_activity_not_unique_travelers'
    return result


def _record(record, item):
    if (not isinstance(record,dict) or any(type(record.get(k)) is not int
            or not 0 <= record[k] <= aviation.MAX_INTEGER for k in COUNTS)
            or record['arrivals']+record['departures'] != record['value']
            or any(record.get(k) != item[k] for k in ('unit','frequency','scope','publisher'))
            or record.get('collection_method') != aviation.METHOD
            or record.get('collection_mode') != 'offline_official_file_validation'
            or record.get('publication_status') != 'blocked' or record.get('finality') != 'not_stated'
            or record.get('original_publication_at') is not None or record.get('release_published_at') is not None
            or not re.fullmatch(r'[a-f0-9]{64}',record.get('file_sha256',''))
            or record.get('file_url') != aviation.TIME_URL or record.get('source_url') != aviation.CATALOG
            or not record.get('source_file') or record.get('sheet') != 'MENU'
            or type(record.get('excel_row')) is not int or record['excel_row'] < 9
            or aviation.timestamp(record.get('retrieved_at')) > aviation.timestamp(record.get('last_collected_at'))
            or aviation.timestamp(record.get('first_collected_at')) > aviation.timestamp(record.get('last_collected_at'))):
        raise ValueError('aviation_record_invalid')


def validate_archive(archive, before=None):
    series, sources = archive.get('aviation_indicators',{}), archive.get('aviation_sources',{})
    if not isinstance(series,dict) or not isinstance(sources,dict):
        raise ValueError('aviation_archive_invalid')
    if not series and not sources:
        if before and (before.get('aviation_indicators') or before.get('aviation_sources')):
            raise ValueError('aviation_history_lost')
        return
    if set(series) != set(aviation.IDS.values()) or set(sources) != {aviation.SOURCE}:
        raise ValueError('aviation_pair_or_source_lost')
    source = sources[aviation.SOURCE]
    if (not isinstance(source,dict) or not isinstance(source.get('vintages'),list)
            or not source['vintages'] or source.get('publication_status') != 'blocked'
            or source.get('automatic_download') is not False):
        raise ValueError('aviation_source_invalid')
    first,end = valid_period(source['start_period']),valid_period(source['reference_period'])
    vintage_ids = []
    for vintage in source['vintages']:
        digest = hashlib.sha256(json.dumps(vintage['files'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if digest != vintage['batch_sha256'] or digest in vintage_ids:
            raise ValueError('aviation_vintage_invalid')
        vintage_ids.append(digest)
        aviation.timestamp(vintage['first_validated_at'])
    for key,item in series.items():
        aviation.definition(dict(item,id=key))
        if (not isinstance(item.get('observations'),dict) or not isinstance(item.get('revisions'),list)
                or set(item['observations']) != set(months(first,end))):
            raise ValueError('aviation_archive_months_invalid')
        for period,record in item['observations'].items():
            valid_period(period);_record(record,item)
            if not any(record['file_sha256'] == f['sha256'] and record['retrieved_at'] == f['retrieved_at']
                       for v in source['vintages'] for f in v['files']):
                raise ValueError('aviation_record_vintage_missing')
        tails = {}
        for revision in item['revisions']:
            p = valid_period(revision['period'])
            if p not in item['observations'] or revision.get('kind') not in ('value_correction','source_vintage_change'):
                raise ValueError('aviation_revision_invalid')
            old,new = revision['before'],revision['after'];_record(old,item);_record(new,item)
            if (old == new or old['first_collected_at'] != new['first_collected_at']
                    or revision['detected_at'] != new['last_collected_at']
                    or aviation.timestamp(old['last_collected_at']) > aviation.timestamp(revision['detected_at'])
                    or (p in tails and tails[p] != old)):
                raise ValueError('aviation_revision_chain_invalid')
            tails[p] = new
        if any(item['observations'][p] != last for p,last in tails.items()):
            raise ValueError('aviation_revision_not_current')
    if before and before.get('aviation_indicators'):
        prior_source = before['aviation_sources'][aviation.SOURCE]
        if (source['start_period'] != prior_source['start_period']
                or end < prior_source['reference_period']
                or source['vintages'][:len(prior_source['vintages'])] != prior_source['vintages']):
            raise ValueError('aviation_vintage_history_lost')
        for key,prior in before['aviation_indicators'].items():
            current = series[key]
            if (any(current.get(k) != prior.get(k) for k in IDENTITY)
                    or not prior['observations'].keys() <= current['observations'].keys()
                    or current['revisions'][:len(prior['revisions'])] != prior['revisions']):
                raise ValueError('aviation_history_lost')
            for p,old in prior['observations'].items():
                new = current['observations'][p]
                if (new['first_collected_at'] != old['first_collected_at'] or (new != old and not any(
                        r['period'] == p and r['before'] == old and r['after'] == new
                        for r in current['revisions'][len(prior['revisions']):]))):
                    raise ValueError('aviation_revision_missing')


def merge(archive, source, items, snapshot, at):
    """Copy/stage the complete pair. Never mutate a previous validated archive."""
    validate_archive(archive)
    staged = copy.deepcopy(archive)
    if {i['id'] for i in items} != set(aviation.IDS.values()) or set(snapshot['records']) != set(aviation.IDS.values()):
        raise ValueError('aviation_pair_required')
    if (source.get('id') != aviation.SOURCE or snapshot['start_period'] != source['start_period']
            or snapshot['reference_period'] != source['end_period']
            or any(set(rows) != set(months(source['start_period'],source['end_period']))
                   for rows in snapshot['records'].values())):
        raise ValueError('aviation_snapshot_range_mismatch')
    saved_items = staged.setdefault('aviation_indicators',{})
    counts = dict(new_observations=0,unchanged_observations=0,value_corrections=0,status_changes=0)
    for item in items:
        aviation.definition(item)
        identity = {k:copy.deepcopy(item[k]) for k in IDENTITY}
        saved = saved_items.setdefault(item['id'],dict(**identity,observations={},revisions=[]))
        if any(saved.get(k) != identity[k] for k in IDENTITY):
            raise ValueError('aviation_identity_changed')
        for p,detail in snapshot['records'][item['id']].items():
            old = saved['observations'].get(p)
            if old and {k:v for k,v in old.items() if k not in ('first_collected_at','last_collected_at')} == detail:
                counts['unchanged_observations'] += 1
                continue
            if old and (aviation.timestamp(detail['retrieved_at']) < aviation.timestamp(old['retrieved_at'])
                    or (detail['file_sha256'] != old['file_sha256']
                        and aviation.timestamp(detail['retrieved_at']) == aviation.timestamp(old['retrieved_at']))):
                raise ValueError('aviation_stale_or_ambiguous_vintage')
            record = dict(copy.deepcopy(detail),first_collected_at=old['first_collected_at'] if old else at.isoformat(),
                          last_collected_at=at.isoformat())
            if old is None:
                counts['new_observations'] += 1
            else:
                changed = any(old[k] != record[k] for k in COUNTS)
                counts['value_corrections' if changed else 'status_changes'] += 1
                saved['revisions'].append(dict(period=p,detected_at=at.isoformat(),
                    kind='value_correction' if changed else 'source_vintage_change',before=copy.deepcopy(old),after=copy.deepcopy(record)))
            saved['observations'][p] = record
    saved_source = staged.setdefault('aviation_sources',{}).setdefault(aviation.SOURCE,dict(vintages=[]))
    files = sorted(copy.deepcopy(snapshot['files']),key=lambda f:(f['path'],f['sha256']))
    batch = hashlib.sha256(json.dumps(files,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if batch not in {v['batch_sha256'] for v in saved_source['vintages']}:
        saved_source['vintages'].append(dict(batch_sha256=batch,files=files,first_validated_at=at.isoformat(),
            checked_breakdown_periods=snapshot['checked_breakdown_periods']))
    saved_source.update(start_period=snapshot['start_period'],reference_period=snapshot['reference_period'],
        last_successful_check=at.isoformat(),collection_mode=snapshot['collection_mode'],
        automatic_download=False,publication_status='blocked',independent_crosscheck_complete=False)
    validate_archive(staged,archive)
    return staged,counts
