"""Actions summary: observed data, pending authentication and failures stay distinct."""
import json
from pathlib import Path

def summary(health):
    rows=['## Macro Monitor v0.6',f"- Run status: {health.get('status','unknown')}",f"- Connected primary monthly indicators: {health.get('connected_primary_indicators','unknown')}/4",f"- All connected indicators: {health.get('connected_indicators','unknown')}",f"- Observations: {health.get('observation_count','unknown')}; new {health.get('new_observations',0)}, unchanged {health.get('unchanged_observations',0)}, value corrections {health.get('value_corrections',0)}",'', '| Source | Status | Latest reference | Last successful check | Reason |','| --- | --- | --- | --- | --- |']
    for s in health.get('sources',[]):
        values=[s.get('name'),s.get('status','unknown')+(' / '+s['collection_state'] if s.get('collection_state') else ''),s.get('reference_period','—'),s.get('last_successful_check') or '—',s.get('error_kind') or s.get('reason') or '—']
        rows.append('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in values)+' |')
    if health.get('error'):rows.append('\nError: '+health['error'])
    rows.append('\nPending sources are not successful collections. Existing validated values are retained on failure. API keys/credential URLs are never included.')
    return '\n'.join(rows)
if __name__=='__main__':
    p=Path(__file__).resolve().parents[2]/'site/data/macro_health.json'
    print(summary(json.loads(p.read_text()) if p.exists() else {'status':'health_unavailable'}))
