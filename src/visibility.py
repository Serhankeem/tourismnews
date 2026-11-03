"""Current source permission gates *all* public projections, including old records.

The canonical archive is never used as proof of current permission. Holds are
reversible projection state, separate from retention/archived_only and dates.
"""
import json
import hashlib
if __package__:
    from . import collector as c
    from .editorial import project
else:
    import collector as c
    from editorial import project


class PublicationGate:
    def __init__(self, sources, permission, data_dir):
        self.sources = {s['id']: s for s in sources}
        self.authorized = {s['id'] for s in sources if s.get('enabled', True) and permission(s)}
        self.previous_urls = set()
        self.legacy_urls = set()
        for name in ('newsroom', 'news', 'filings', 'research', 'briefing'):
            doc = c.read_json(data_dir/(name+'.json'), {})
            urls = {a.get('url') for a in doc.get('articles', doc.get('items', []))}
            self.legacy_urls.update(urls)
            if doc.get('schema_version', 0) >= 4:
                self.previous_urls.update(urls)

    def allows(self, record):
        return record.get('source_id') in self.authorized

    def views(self, articles):
        stored, news, filings = project(articles)
        other = [r for r in stored if r['record_type'] not in ('news', 'regulatory_filing') and self.allows(r)]
        return stored, [r for r in news if self.allows(r)], [r for r in filings if self.allows(r)], other

    def needs_reprojection(self, articles, state_dir):
        if any(not self.allows(r) and (r.get('url') in self.previous_urls or
               (r.get('source_id') in self.sources and r.get('url') in self.legacy_urls)) for r in articles):
            return True
        path = state_dir/'publication_visibility.json'
        # Malformed history must not suppress a known rights withdrawal above.
        try:
            previous = json.loads(path.read_text())['records'] if path.exists() else {}
        except (ValueError, KeyError):
            return False
        _, news, filings, other = self.views(articles)
        return any(previous.get(r['id'], {}).get('status') == 'rights_hold' for r in news+filings+other)

    def write_manifest(self, articles, data_dir, at):
        # No titles, source text or raw URLs in this public display gate.
        # Confirmed briefing files stay immutable; their UI uses these hashes.
        hashes = sorted({hashlib.sha256(r['url'].encode()).hexdigest()
                         for r in articles if not self.allows(r)})
        path = data_dir/'publication_visibility.json'
        if not hashes and not path.exists():
            return
        if c.read_json(path, {}).get('blocked_url_hashes') != hashes:
            c.write_atomic(path, {'schema_version': 1, 'checked_at': c.iso(at),
                                  'blocked_url_hashes': hashes})

    def write_history(self, articles, state_dir, at):
        path = state_dir/'publication_visibility.json'
        doc = json.loads(path.read_text()) if path.exists() else {'schema_version': 1, 'records': {}}
        if not isinstance(doc.get('records'), dict):
            raise ValueError('invalid_publication_visibility_history')
        stored, news, filings, other = self.views(articles)
        public_ids = {r['id'] for r in news+filings+other}
        hidden = restored = 0
        for r in stored:
            sid = r.get('source_id'); source = self.sources.get(sid, {})
            status = 'rights_hold' if not self.allows(r) else 'public' if r['id'] in public_ids else 'archived'
            policy_status = source.get('publication', {}).get('status', 'policy_missing' if sid in self.sources else 'source_missing')
            old = doc['records'].get(r['id'], {})
            previous = old.get('status', 'public' if r.get('url') in self.previous_urls else 'untracked')
            transitions = list(old.get('transitions', []))
            if previous != status or (old and old.get('policy_status') != policy_status):
                transitions.append({'at': c.iso(at), 'from': previous, 'to': status,
                                    'policy_status': policy_status, 'source_enabled': source.get('enabled', False),
                                    'reason': 'current_source_permission' if self.allows(r) else 'current_source_permission_not_confirmed'})
                hidden += previous == 'public' and status == 'rights_hold'
                restored += previous == 'rights_hold' and status == 'public'
            doc['records'][r['id']] = {**old, 'source_id': sid, 'status': status,
                                      'policy_status': policy_status, 'last_evaluated_at': c.iso(at),
                                      'transitions': transitions}
        doc['checked_at'] = c.iso(at)
        c.write_atomic(path, doc)
        held = [r for r in stored if r['record_type']=='news' and not self.allows(r)]
        return {'status': 'ok', 'rights_held_news_count': len(held),
                'hidden_this_run': hidden, 'restored_this_run': restored,
                'public_news_count': len(news)}
