"""Bounded child process entry point; no deployment/ref writes here."""
import argparse
from pathlib import Path
from .layout import ROOT, read


def collect(engine, stage, force, days):
    data,state=stage/'site/data',stage/'collector_state'
    if engine=='news':
        from ..engine import execute
        result=execute(read(ROOT/'sources.json')['sources'],data,state,
                       read(ROOT/'relevance_reviews.json').get('approvals',{}),days=days)
        return result['publication_result']!='failed'
    if engine=='reports':
        from ..reports.engine import collect
        result=collect(read(ROOT/'reports_sources.json')['sources'],data,state,force=force)
    else:
        from ..macro.engine import collect
        result=collect(read(ROOT/'macro_sources.json'),data,state,force=force)
    return result['status'] not in ('failed','blocked')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('engine',choices=['news','reports','macro']);p.add_argument('--stage',type=Path,required=True);p.add_argument('--days',type=int,default=90);p.add_argument('--force',action='store_true');a=p.parse_args()
    try:
        status=0 if collect(a.engine,a.stage,a.force,a.days) else 1
    except Exception:
        status=2 # Unhandled failure: parent rolls back every staged file.
    raise SystemExit(status)
