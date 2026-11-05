# ECOS Preflight — 수동 메타데이터 사전검증

기준 main `214ac7c` (PR #24 병합), 브랜치 `feat/ecos-manual-preflight`.
이 작업은 Secret을 Actions 안에서 사용하기 위한 수동 검사 경로만 추가한다.
**실인증 실행·일반여행 코드 확정·실측 수치 확보·운영 연동 완료는 아직 아니다.**

## 실행 방법과 현재 확인 범위

새 workflow_dispatch 파일은 기본 브랜치에 존재해야 실행할 수 있다.
PR에서 Secret을 이용하거나 기존 Macro workflow를 실행해 우회하지 않는다.

1. PR의 코드·검사 결과를 검토하고 **사용자가 직접 main 병합 여부를 결정**한다.
2. GitHub → **Actions → ECOS Preflight → Run workflow**.
3. Branch는 **main**, `max_tables`는 우선 **12**를 선택한다. 수동 main 실행만 허용한다.
4. 실행의 **Summary**에서 인증, 목록/후보/검사 수, 일반여행 수입·지급 코드 후보와
   계층·원본 단위·수록 기간·추가 그룹 수를 확인한다.
5. 후보 제한으로 partial이면 검사 결과를 확인한 뒤 24로 늘려 수동 재검사할 수 있다.
   24개 이후의 범위, 서버 오류, 메타데이터 구조 변경은 추가 검토가 필요하다.

이미 등록된 Repository Secret **`ECOS_API_KEY`**를 그대로 사용한다. Secret의 값을
Codex 개발 환경으로 복사하지 않았고, 조회하지도 않았다. workflow 실행 시 이 Secret을
단일 사전검증 step에만 주입한다. PR CI와 테스트에는 실제 Secret을 제공하지 않는다.
실인증을 한 뒤 공유할 내용은 아래의 제한된 Actions Summary뿐이다.

**이번 개발에서 실제 등록 Secret으로 수행한 API 요청은 0회다.** 사용자 병합 전에는 새
수동 workflow를 실행할 수 없으므로 인증 여부와 실제 통계표·항목 코드는 미확인이다.
통과한 fixture·CI는 이 사실을 바꾸지 않는다. 실측 수치를 요청하는 StatisticSearch도 없다.

## 구현

- `.github/workflows/ecos-preflight.yml`: `workflow_dispatch`만 구독. schedule, push,
  pull_request, pull_request_target, workflow_call, workflow_run 없음.
- main ref만 허용하고 dispatch 시점의 **github.sha**를 checkout해 실행 중 코드 변경을 피한다.
  `contents: read`, `persist-credentials: false`, 15분 제한, 독립 concurrency 사용.
  Pages 권한·환경·배포·Git push·artifact 업로드 없음.
- `src/macro/ecos.py`: 기존 metadata CLI 블록을 `metadata(client, table_code=None)`로 분리.
  CLI와 새 preflight가 동일 기능과 기존 HTTPS/robots/리디렉션 차단/크기·페이지·호출 제한을 재사용한다.
  기존 CLI의 출력 형식과 금액 수집 어댑터·승인 게이트는 유지한다.
- `src/macro/ecos_preflight.py`: 전체 StatisticTableList에서 국제수지·일반여행·여행수지·관광수지
  명칭 및 하위 표를 찾고, 검색 가능한 월간 표만 제한된 수만큼 검사한다. 선택 표의 TableList를
  재검증한 뒤 StatisticItemList의 월간 일반여행 항목과 전체 부모 계층을 분석한다.
- 원본 응답은 **메모리에서만 처리**한다. raw JSON, 인증 URL, 원본 응답 파일을 저장하거나 업로드하지 않는다.
  쓰기 대상은 저장소 밖의 GitHub step Summary 파일뿐이다. 로그에는 고정된 완료 문장만 출력한다.

## Summary에 공개하는 최소 메타데이터

| 범위 | 허용 항목 |
| --- | --- |
| 실행 | 인증 상태, 검사 상태, 일반여행 판정, 표·후보·검사 건수, 고정된 오류 ID |
| 후보 표 | 공식 코드·명칭·주기·검사 상태 |
| 일반여행 항목 | 그룹, 항목 코드·명칭, 부모 코드, 전체 코드/명칭 계층, 수입/지급 방향 후보 |
| 단위·수록 | 원본 UNIT_NAME, START_TIME·END_TIME, 미확인 표시 |
| 선택 조건 | 그룹별 월간 항목 수. 추가 그룹의 선택 조합은 자동 추정하지 않음 |

DATA_VALUE·WEIGHT·임의 응답 필드·provider MESSAGE·원본 URL·응답 본문·키는 공개하지 않는다.
수록 종료월은 **메타데이터 수록 기간**이며 실제 금액 수신이나 공식 공표일을 확인한 것이 아니다.

- 문자열 길이, 제어문자·bidi, URL, HTML, 인코딩 표현을 검사한다.
- Secret의 원문·URL/HTML/Unicode escape·Base64/Base64URL(패딩 유무)·hex 반사를 차단한다.
- 허용 필드만 선택하고 Markdown/HTML을 escape한다. 전체 Summary 크기는 500KB 이하로 제한한다.
- 인증 URL이 포함될 수 있는 예외 원문은 출력하지 않는다. 기존 EcosError라도 알려진 고정 ID만 허용한다.
- 안전성 검증 실패 시 해당 결과를 공개하지 않고 일반 오류 상태만 남긴다.
- 키 없음, 인증 거절, 접근 거절, 네트워크/robots/제한, 구조/계층 불일치, 단위·방향 미확인,
  검사 범위 부족을 구분한다. 이후 항목 조회에서 인증이 거절되어도 앞선 목록 인증 성공으로 덮지 않는다.

## 상태와 해석

| 상태 | 의미 / 작업 |
| --- | --- |
| `verified_catalogue` | 인증된 비어 있지 않은 통계표 목록 수신. 일반여행 항목 검증 완료와 별개 |
| `credential_missing` / `rejected` | Secret 미전달 또는 키 형식·인증 거절. 키 값이 아닌 등록/유효성만 확인 |
| `access_denied` / `*_after_catalogue` | 현재/후속 접근·인증 거절. 이전 목록 성공을 현재 정상 인증으로 간주하지 않음 |
| `inspection_complete` | 제한 범위의 후보 표를 모두 검사했다는 뜻 |
| `partial` / `failed` | 후보 제한·표별 오류·목록 실패. 기존 좋은 검사 결과는 Summary에 유지 |
| `pair_candidates_found` | 단일 차원에 완전한 계층·기간과 동일한 지원 달러 단위를 가진 수입·지급 후보 1쌍 |
| `not_found` | 일반여행 항목 없음. 전체 여행수입·지급으로 대체하지 않음 |
| `review_required` | 방향 모호·계층 충돌·추가 차원·단위/기간 미확인·여러 쌍 등으로 선택 확정 불가 |
| `incomplete` | 일부 검사 실패 또는 범위 미완료 |

전체 계층의 수입·지급 전용 근거가 서로 충돌하면 방향 미확인으로 처리한다.
단순 `일반여행` 이름만으로 수입/지급을 확정하지 않으며, 유학연수 계층을 승격하지 않는다.
부모 누락·순환·중복·표/명칭 불일치는 오류다. 다른 그룹에 수입/지급·통화 차원이 있는 경우
교차 그룹 조합을 추측하지 않고 review_required로 남긴다.

workflow는 **pair_candidates_found에서만 성공**, 나머지 판정은 실패 상태로 끝나 추가 검토가
필요함을 표시한다. 성공해도 **매핑 승인·권리 검증·실수집·KTO 교차검증·운영 활성화는 하지 않는다.**
확인된 코드·단위는 후속 검토 PR의 근거로만 사용한다. `macro_sources.json`은 변경하지 않는다.

## 금지 경로와 보존

- `StatisticSearch`, `src.macro.engine`, 뉴스/Research collector, pipeline runner 실행 없음.
- data/live checkout·쓰기·커밋·push, 운영 JSON 저장·정정, Pages 배포 없음.
- 기존 Macro 일일 스케줄·뉴스/Research 자동화 workflow 변경 없음.
- 수입·지출 source 비활성, TOURGO 승인 게이트, 기존 원장·UI·데이터 불변.
- raw artifact를 내려받아 Codex에서 처리하거나 Secret을 별도 환경으로 전달하는 경로 없음.

## 테스트와 CI

테스트는 **합성 metadata와 명시적인 가짜 키만** 사용한다. 네트워크·실제 Secret·실제 수치는 없다.
신규 29개 테스트는 계층·방향·단위·빈 결과·차원·부모/중복·인증 후속 실패·부분 검사·출력 안전성·
비밀 반사·Summary 단독 쓰기·수동 main/최소 권한·운영 실행 부재를 검증한다.
기존 전체 Python 회귀도 실행한다. UI·데이터 변경이 없어 브라우저 변경 테스트는 추가하지 않는다.
로컬 검증: **Python 전체 399개 통과(기존 370 + 신규 29), actionlint 통과**, git diff --check 통과. PR CI 링크는 제출 후 아래에 기록한다.
운영 JSON 30개와 기존 workflow 5개는 최신 main과 바이트 단위로 동일함을 확인했다.

## 수동 실행 후 확인할 사항

사용자가 병합·수동 실행한 뒤 인증 결과와 실제 표/항목/단위·수록 기간을 Summary에서 검토한다.
미확인·실패·추가 차원이 있으면 그대로 보류한다. 확인된 최소 메타데이터만 후속 논의에 사용하고
raw 로그나 인증키가 포함된 URL을 공유하지 않는다. 이 워크플로로 운영 연결 완료를 선언하지 않는다.

## PR CI 근거

[PR #25](https://github.com/Serhankeem/tourismnews/pull/25), 기능 커밋 `042f0f2e956aea55b6ccb3838f35681b20b9c9ff`: 기존 CI의 Python test 3개 모두 통과.

- [Macro Monitor official statistics](https://github.com/Serhankeem/tourismnews/actions/runs/41996456426/job/127140713683): SUCCESS.
- [Research Library weekly collector](https://github.com/Serhankeem/tourismnews/actions/runs/41996456312/job/127140713316): SUCCESS.
- [Tourism Pulse RSS collector](https://github.com/Serhankeem/tourismnews/actions/runs/41996456319/job/127140713236): SUCCESS.

운영 collect-and-publish 3개는 SKIPPED. ECOS Preflight는 수동 전용이므로 PR CI에서 실행되지 않았고 실제 Secret 사용 0회다. 후속 커밋은 이 검사 결과를 기록하는 문서 변경뿐이다.
