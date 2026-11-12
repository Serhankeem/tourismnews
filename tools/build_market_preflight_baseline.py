"""Offline fingerprint builder; reads Step 3 originals, never credentials/network."""
import argparse
import hashlib
import json
from pathlib import Path
from src.macro.ecos_market_preflight import SPECS, fingerprint, validate_baseline
from tools.validate_market_weather_foundation import load_evidence, private_config


def build(folder):
    config=private_config()
    rows,hashes=load_evidence(folder,config)
    result=dict(schema_version=1,provenance=dict(issue=49,step=3,observations=628,
        original_response_count=len(hashes),original_manifest_sha256=hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest()),series={})
    for key,(table,codes,unit,base,_) in SPECS.items():
        data={}
        for row in rows[key]:
            period=row['TIME'][:4]+'-'+row['TIME'][4:]
            if period in data:raise ValueError('duplicate_period')
            if row['STAT_CODE']!=table or row['UNIT_NAME']!=unit or [row.get('ITEM_CODE'+str(n)) for n in range(1,len(codes)+1)]!=codes:
                raise ValueError('identity_mismatch')
            data[period]=fingerprint(key,period,row['DATA_VALUE'])
        result['series'][key]=dict(stat_code=table,item_codes=codes,unit=unit,base_year=base,fingerprints=data)
    return validate_baseline(result)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence-dir',required=True,type=Path);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    raw=(json.dumps(build(args.evidence_dir),ensure_ascii=False,indent=2)+'\n').encode()
    args.output.write_bytes(raw)
    print('628 monthly fingerprints; sha256='+hashlib.sha256(raw).hexdigest())
