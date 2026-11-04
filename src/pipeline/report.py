"""Human-readable Actions status; collection, persistence and deployment differ."""
import argparse
from pathlib import Path
from .layout import read


def render(result, deployment):
    lines=['## 데이터 파이프라인 실행 결과','', '| 항목 | 결과 |','| --- | --- |',
           '| 단계 | '+result.get('phase','시작 실패')+' |',
           '| main 자동 데이터 커밋 | 없음 |',
           '| 요청 자동화 | '+result.get('requested','미확인')+' |',
           '| 최초 데이터 이전 | '+(('초기화 저장 확인' if result.get('data_commit') else '초기화 시도 — 저장 미확인') if result.get('bootstrap') else '기존 상태 복원 또는 미실행')+' |',
           '| 데이터 영속 저장 | '+('확인: '+result['data_commit'] if result.get('data_commit') else '실패 또는 미실행')+' |',
           '| Pages 배포 | '+({'success':'성공','failure':'실패/미확인 — Pages environment 확인 필요','skipped':'미실행','cancelled':'취소'}.get(deployment,'미확인'))+' |']
    for engine,row in result.get('engines',{}).items():lines.append('| '+engine+' 수집 | '+row['status']+(' / '+row['error_kind']+': '+row['error'] if row.get('error') else '')+' |')
    for engine,count in result.get('new_records',{}).items():lines.append('| '+engine+' 신규 저장 | '+str(count)+' |')
    for key,value in result.get('counts',{}).items():lines.append('| '+key+' | '+str(value)+' |')
    if result.get('error'):lines+=['','운영자 조치: '+result['error']+' — 최신 main에서 해당 workflow_dispatch를 다시 실행하세요. main 자동 커밋으로 되돌리지 않습니다.']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--deployment',default='skipped');args=p.parse_args()
    path=args.work/'result.json';print(render(read(path) if path.exists() else {},args.deployment))
if __name__=='__main__':main()
