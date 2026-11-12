"""Calendar-aware comparisons. Missing/zero baselines never become invented rates."""
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP

def month_before(period):
    year,month=map(int,period.split('-'));return f'{year-1:04}-12' if month==1 else f'{year:04}-{month-1:02}'
def months(start,end):
    y,m=map(int,start.split('-'));ey,em=map(int,end.split('-'));out=[]
    while (y,m)<=(ey,em):
        out.append(f'{y:04}-{m:02}');y,m=(y+1,1) if m==12 else (y,m+1)
    return out

def valid_period(period):
    if not isinstance(period,str) or len(period)!=7:raise ValueError('invalid_period')
    year,month=map(int,period.split('-'))
    if not 1900<=year<=2100 or not 1<=month<=12 or period!=f'{year:04}-{month:02}':raise ValueError('invalid_period')
    return period

def comparisons(observations,period,exact=False):
    valid_period(period);year,month=map(int,period.split('-'))
    values={p:o['value'] for p,o in observations.items()}
    value=values.get(period)
    def rate(current,base):
        if current is None or base is None or base==0:return None
        if exact:return float(((Decimal(current)/Decimal(base)-1)*100).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))
        return round((current/base-1)*100,2)
    def ytd(y):
        keys=[f'{y:04}-{m:02}' for m in range(1,month+1)]
        if not all(p in values for p in keys):return None
        total=sum(values[p] for p in keys)
        return None if exact and total>2**53-1 else total
    total,previous=ytd(year),ytd(year-1)
    return dict(mom_pct=rate(value,values.get(month_before(period))),yoy_pct=rate(value,values.get(f'{year-1:04}-{month:02}')),ytd_value=total,ytd_yoy_pct=rate(total,previous),reference_period=period,mom_base_period=month_before(period),yoy_base_period=f'{year-1:04}-{month:02}',ytd_range=[f'{year:04}-01',period])


def decimal_value(raw):
    """Canonical JSON-safe exact decimals; never accept binary floats/exponents."""
    import re
    if not isinstance(raw, str) or not re.fullmatch(r'(?:0|[1-9]\d{0,29})(?:\.\d{1,18})?', raw):
        raise ValueError('decimal_value_invalid')
    value = Decimal(raw)
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def decimal_comparisons(observations, period):
    """Exact decimal inputs, percent strings rounded to 6dp; no index/FX YTD sum."""
    from decimal import localcontext
    valid_period(period)
    values = {p: Decimal(decimal_value(o['value'])) for p, o in observations.items()}
    def rate(base_period):
        current, base = values.get(period), values.get(base_period)
        if current is None or base is None or base == 0:
            return None
        with localcontext() as context:
            context.prec = 80
            return format(((current/base-1)*100).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP), 'f')
    prior = f'{int(period[:4])-1:04}-{period[5:]}'
    return dict(reference_period=period, mom_pct=rate(month_before(period)),
                yoy_pct=rate(prior), mom_base_period=month_before(period),
                yoy_base_period=prior, percentage_precision=6,
                aggregation_policy='no_ytd_sum_for_indices_or_exchange_rates')
