"""Generate a review-only activation configuration OUTSIDE the checkout.

Never edits active settings, commits, calls an API or grants user approval.
The generated macro_sources.json requires a separate configuration PR/review.
"""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import re
from . import tourgo
from .tourgo_release import ROOT, activation_candidate, operating_configuration
from ..pipeline.layout import read


def plan(config, policy, approval, now):
    if not isinstance(approval,dict) or set(approval)!={'collection','publication','terms_evidence_ref','conditions'}:
        raise ValueError('tourgo_activation_approval_incomplete')
    if approval['conditions']!={'noncommercial':True,'free_access':True,'no_ads':True,'attribution':True}:
        raise ValueError('tourgo_activation_conditions_required')
    refs=[approval['terms_evidence_ref']]
    for action in ('collection','publication'):
        g=approval[action]
        if not isinstance(g,dict) or set(g)!={'evidence_ref','valid_from','valid_until'}:
            raise ValueError('tourgo_activation_dated_approval_required')
        start,end=dt.date.fromisoformat(g['valid_from']),dt.date.fromisoformat(g['valid_until'])
        if not start<=now.date()<=end or end==dt.date.max:
            raise ValueError('tourgo_activation_finite_current_approval_required')
        refs.append(g['evidence_ref'])
    # Opaque reviewed reference IDs only; never names/emails/URLs or staging grants.
    if any(not isinstance(r,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._:-]{2,159}',r)
           or r.lower().startswith(('staging','isolated-preview')) for r in refs):
        raise ValueError('tourgo_activation_reference_invalid')
    if len(set(refs))!=3:raise ValueError('tourgo_terms_and_operating_approvals_must_be_distinct')
    proposed=activation_candidate(config,now)
    source=next(s for s in proposed['sources'] if s['id']==tourgo.SOURCE)
    for action in ('collection','publication'):
        source['approval'][action]=dict(copy.deepcopy(approval[action]),approved=True,scope='general_travel_monthly')
    source['activation_terms_evidence_ref']=approval['terms_evidence_ref']
    source['activation_conditions']=copy.deepcopy(approval['conditions'])
    operating_configuration(proposed,policy,now)
    return proposed


def main():
    p=argparse.ArgumentParser(description='Generate external review-only TOURGO activation plan')
    p.add_argument('--approval',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    try:
        target=args.output.resolve()
        if target.exists() or ROOT==target or ROOT in target.parents:
            raise ValueError('tourgo_activation_new_external_directory_required')
        proposed=plan(read(ROOT/'macro_sources.json'),read(ROOT/'operating_policy.json'),read(args.approval),dt.datetime.now(dt.timezone(dt.timedelta(hours=9))))
        target.mkdir(mode=0o700,parents=True)
        (target/'macro_sources.proposed.json').write_text(json.dumps(proposed,ensure_ascii=False,indent=2)+'\n')
        (target/'macro_sources.proposed.json').chmod(0o600)
        print('tourgo_activation_plan_created; active_configuration_unchanged; separate_review_required')
        return 0
    except Exception:
        print('tourgo_activation_plan_failed; active_configuration_unchanged')
        return 1


if __name__=='__main__':raise SystemExit(main())
