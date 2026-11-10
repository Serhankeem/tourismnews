# 검증 결과 및 범위

## 실행 결과

- `python -m unittest discover -s tests -v`: **558개 통과**, 신규 v2 15개 포함. 마지막 상태 보고/CAS 조정 후 v2 15개 재통과.
- 기존 브라우저 **23개 스위트 통과**, 320·390·768·1440px 포함. 최종 기관 권리 공통 게이트 변경 후 TOURGO 관련 3개 스위트 재통과.
- 브라우저 재검사 중 로컬 HTTP 서버 종료로 connection-refused가 발생했습니다. 제품 오류로 분류하지 않았으며 서버를 재검사 프로세스에서 직접 시작/종료하도록 하여 3개를 다시 통과시켰습니다.
- GitHub CI 최종 링크/결과는 PR 설명과 Checks에 기록합니다. PR CI에서는 실제 데이터 전달·수집·운영 저장·Pages 배포를 실행하지 않습니다.

[브라우저 개별 결과](browser-results.json) · [테스트 집계](tests.json).

## 신규 회귀 범위

| 테스트 | 확인 |
| --- | --- |
| bootstrap package | 고정 신뢰 경계의 69개월, 단위·69개 항등식, 138개 금액 관측, 기존 KTO 483개와 정정 이력, 6파일 프로그램 생성 |
| source package | owner의 공식 원본 확인 필요, 원장·영수증 없이 5파일 자동 생성, 개별 hash 자동 계산 |
| 입력 검증 | 월 누락/미래월/중복/잘못된 단위/수지 불일치/출처·hash 불일치 거부 |
| 일반 신규 월 | 70개월 시나리오, 금액 관측 2개 추가, 총 623개(기존 621개 유지) |
| 동일 데이터 | UNCHANGED, collector·Store.commit·Pages 조합 생략, 원장/성공시각/Git head 동일 |
| 정정·이상 변동 | REVIEW_REQUIRED, 이전 원장 유지, 영수증/manifest 자동 생성한 명시적 정정 경로에서만 반영 가능 |
| 수집 승인만 있음 | private staging 생성, 게시 미승인 사유 기록, 공개 저장/배포 없음 |
| 게시 승인 만료 | 재게시 차단, 기존 data/live 유지 |
| 기관 이용조건 철회 | 기존 공개 금액도 일반 policy 재투영에서 제거. source 수집/게시 승인만으로 우회 불가, 원장 621개 유지 |
| 동시 News 변경 | CAS 재시도 후 새 News 상태와 TOURGO 신규 월 모두 보존 |
| 동시 Macro 변경 | 최신 원장으로 재평가, 서로 다른 새 값이면 정정 검토로 전환, 최신 값 덮어쓰기 없음 |
| private delivery | live protection·private·owner·검증된 서명·고정 commit·파일 한정·원본 attestation 확인, 실패 시 입력 cleanup |
| 로그 | 상태·정정/신규/이상 건수·고정 사유만 Summary. URL/개인정보/토큰/원본 값·파일 내용/관리용 hash 미출력 |

기존 tests의 최초 원본 검증, 영수증 stale 방지, 공개 투영 rollback, 중단/Pages 실패/권한 철회/범주 혼합, 일일 manual_update_pending, News·Research·Macro·Weather·브리핑 회귀 테스트도 유지했습니다.

## 합성과 실제 원본 구분

**이번 환경에는 지정 SHA의 실제 원본 XLS 3개가 없습니다.** 실제 공식 69개월 재검증·private 입력 조회·실제 최초 게시를 수행하지 않았습니다.

새 테스트는 명시적으로 합성 JSON table을 `.xls` stand-in에 넣고 test-only `read_xls` callback을 통해 실제 `parse_rows` 및 이후 정규화·hash·원장·정정·staging·public gate·Git CAS를 검사합니다. 이것은 실제 BIFF 파일 디코딩 또는 기관 원본 바이트 검증의 증거가 아닙니다. production에는 이 callback/우회 옵션이 없고 실제 xlrd를 사용합니다. 기존 고정 공식 해시는 유지하며 합성 입력은 운영 데이터에 넣지 않았습니다.

사용자가 별도 환경에서 수행한 실제 PR #39의 69개월 실증은 인계 근거로만 취급하고 이번 코드 경로의 실증으로 보고하지 않습니다. 실제 실행 전에 새 구현 fingerprint·최신 원장을 기준으로 다시 staging해야 합니다.

[실원본 가용성](real-input-status.json) · [공식 웹 경로 실제 응답](source-access.json).

## 운영 데이터/설정 보존

검증용 read-only data/live snapshot: `ab44057` (전체 SHA는 preservation.json).

- News **81건**, Research **137건**, KTO **483개**.
- 기본 설정으로 공개 데이터를 재투영한 운영 파일 **30개 모두 SHA 동일**.
- `macro_sources.json`, `operating_policy.json`, 뉴스·리서치 설정, `site/**`, `collector_state/**`를 변경/커밋하지 않음.
- 실제 source enabled/collection/publication false 유지. 사용자의 현재 수집 승인 의사를 설정 변경으로 임의 적용하지 않음.
- data/live 원격 변경, Secrets/보호 환경 변경, 원본 공개 Git/artifact 업로드, Pages 배포, 자동 병합 없음.

[파일별 SHA 및 건수](preservation.json).

## 다음 실제 검증

1. owner가 이미 부여한 수집 승인 근거/기간을 별도 설정으로 기록하고, 미승인 게시 상태를 유지합니다.
2. live 보호 환경과 private token/repo 권한·signed owner commit을 확인합니다. 현재 관측과 지정 정책의 차이를 코드에서 우회하지 않습니다.
3. 실제 고정 원본으로 초기 staging을 재생성·검토합니다. 운영 게시 승인/활성화는 별도 결정입니다.
4. 최초 게시 이후 실제 신규 월 파일로 정상/동일/정정 분기 및 운영 Pages를 따로 검증합니다.
