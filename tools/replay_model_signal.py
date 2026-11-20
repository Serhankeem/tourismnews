"""Offline public-snapshot audit. No network, collector, publication or ledger writes."""
import argparse
import hashlib
import json
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def add(period,n):
    year,month=map(int,period.split('-'));year,month=divmod(year*12+month-1+n,12)
    return f'{year:04}-{month+1:02}'


def percent(series,period):
    current,base=series[period],series[add(period,-12)]
    return Fraction(100*(current-base),base)


def rank(series,period):
    def smooth(p):return sum((percent(series,add(p,n)) for n in (-2,-1,0)),Fraction())/3
    value=smooth(period);refs=[smooth(add(period,n)) for n in range(-24,0)]
    return Fraction(100*(2*sum(v<value for v in refs)+sum(v==value for v in refs)),48),value


def decimal(value):
    with localcontext() as ctx:
        ctx.prec=80
        return format((Decimal(value.numerator)/Decimal(value.denominator)).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP),'f')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--macro',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--as-of',required=True)
    args=p.parse_args();output=args.output.resolve()
    if output==ROOT or ROOT in output.parents or output in ROOT.parents or output.exists():raise SystemExit('new_external_output_required')
    script=r'''
const fs=require('fs'),m=require('./site/market-signal-model.js');
const db=JSON.parse(fs.readFileSync(process.argv[1])),r=m.run(db,{as_of_period:process.argv[2]});
const revisionStress=[];
if(r.status==='observed')for(const id of m.IDS)for(const delta of [-1,1]){
 const changed=structuredClone(db),i=changed.indicators.find(i=>i.id===id),o=i.observations.find(o=>o.period===r.reference_period);
 o.value+=delta;o.revision_status='revised';
 const next=m.evaluate(changed,{reference_period:r.reference_period,as_of_period:process.argv[2]});
 revisionStress.push({kind:'counterfactual_copy_not_an_official_correction',indicator:id,delta_in_stored_unit:delta,status:next.status,score:next.score,weather:next.weather});
}
process.stdout.write(JSON.stringify({result:r,revision_stress:revisionStress}));
'''
    run=subprocess.run(['node','-e',script,str(args.macro.resolve()),args.as_of],cwd=ROOT,capture_output=True,text=True,check=True)
    report=json.loads(run.stdout);db=json.loads(args.macro.read_text());maps={i['id']:{o['period']:o['value'] for o in i['observations']} for i in db['indicators'] if i['id'] in ('kto_inbound','kto_tourism_receipts')}
    checks=0;sensitivity=[];changes=[]
    band=lambda v:'rain' if v<25 else 'cloudy' if v<50 else 'partly' if v<75 else 'sunny'
    for point in report['result']['backtest']['points']:
        if point['status']!='observed':continue
        ranks=[]
        for axis in point['axes']:
            period=point['reference_period'];series=maps[axis['indicator_id']];position,smoothed=rank(series,period)
            assert decimal(position)==axis['percentile']
            assert decimal(smoothed)==axis['smoothed_yoy_pct']
            assert decimal(percent(series,period))==axis['yoy_pct']
            ranks.append(position);checks+=3
        base=sum(ranks,Fraction())/2
        assert abs(float(base)-point['score'])<1e-12 and point['weather']==band(base);checks+=1
        variants=[]
        for weight in (Fraction(2,5),Fraction(3,5)):
            value=weight*ranks[0]+(1-weight)*ranks[1];changes.append(abs(value-base))
            variants.append(dict(weight_a=str(weight),weight_b=str(1-weight),score=decimal(value),weather=band(value)))
        sensitivity.append(dict(period=point['reference_period'],base=decimal(base),base_weather=band(base),variants=variants))
    report['weight_sensitivity']=sensitivity
    report.update(input_sha256=hashlib.sha256(args.macro.read_bytes()).hexdigest(),
        model_source_sha256=hashlib.sha256((ROOT/'site/market-signal-model.js').read_bytes()).hexdigest(),
        independent_fraction_oracle_checks=checks,independent_fraction_oracle_passed=True,
        sensitivity_summary=dict(variant_weather_changes=sum(v['weather']!=p['base_weather'] for p in sensitivity for v in p['variants']),
                                 evaluated_weight_variants=len(sensitivity)*2,
                                 maximum_score_change=decimal(max(changes,default=Fraction()))),
        raw_input_preserved=True,history_mode='retrospective_current_vintage',historical_as_of_verified=False,prediction_accuracy_measured=False)
    output.mkdir(parents=True,mode=0o700);(output/'replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    current=report['result'];audit=current['backtest']
    summary=f"""# Model Signal v1.0 read-only replay

Status: {current['status']} / reference: {current['reference_period']} / score: {current['score']} / weather: {current['weather']}.
Evaluated {audit['evaluated_months']} months; scored {audit['scored_months']}; withheld {audit['withheld_months']}; invariant failures {audit['invariant_failures']}.
Independent Python Fraction oracle: {checks} checks passed.
Weights 40:60 / 60:40 are research sensitivity variants only; production remains 50:50.
{report['sensitivity_summary']}
Input SHA-256: {report['input_sha256']}.
Source SHA-256: {report['model_source_sha256']}.

Current revised vintage only. Not a historical real-time backtest or measured predictive accuracy.
Original input is unchanged. Revision stress uses in-memory copies, not new official observations.
"""
    (output/'report.md').write_text(summary)
    print(summary)


if __name__=='__main__':main()
