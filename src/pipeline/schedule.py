"""Due-slot reconciliation recovers scheduled work replaced in Actions' queue."""
import datetime as dt
from ..collector import KST


def slots(now):
    local=now.astimezone(KST)
    utc=now.astimezone(dt.timezone.utc)
    # Latest due 2-hour news slot (:17 UTC) plus separate KST 10:30 edition.
    regular=utc.replace(hour=utc.hour//2*2,minute=17,second=0,microsecond=0)
    if regular>utc:regular-=dt.timedelta(hours=2)
    brief=local.replace(hour=10,minute=30,second=0,microsecond=0)
    if brief>local:brief-=dt.timedelta(days=1)
    news=max(regular,brief)
    macro=local.replace(hour=12,minute=20,second=0,microsecond=0)
    if macro>local:macro-=dt.timedelta(days=1)
    reports=(local-dt.timedelta(days=local.weekday())).replace(hour=7,minute=40,second=0,microsecond=0)
    if reports>local:reports-=dt.timedelta(days=7)
    return {k:v.astimezone(dt.timezone.utc).isoformat() for k,v in [('news',news),('reports',reports),('macro',macro)]}


def pending(control, now, requested='none'):
    current=slots(now)
    done=control.get('completed_slots',{})
    return {engine:slot for engine,slot in current.items() if done.get(engine,'')<slot or engine==requested}
