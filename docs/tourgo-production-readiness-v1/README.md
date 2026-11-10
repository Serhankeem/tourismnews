# TOURGO Production Activation Readiness v1.0 — PR #39

**코드 준비 및 합성 검증 완료. 운영 승인은 false, 실제 게시·자동 병합 없음.**

기준 main: `22e4af850ad1425efbd263d4640f260c2cb2f649` (PR #38·#37 병합). 브랜치: `feat/tourgo-production-readiness-v1`.

## 실제 원본 검증 상태

사용자는 2026-11-10 별도 환경에서 PR #36의 원본 해시 3개와 69개월 Preview·항등식을 검증했다고 안내했습니다. 이 결과는 배경 근거로 유지합니다. **현재 개발 환경에는 지정 해시와 일치하는 실제 XLS 3개나 해당 69개월 비공개 원장이 없어, 이번 새 staging/트랜잭션 경로의 실제 원본 재검증은 미실시**입니다.

기존 68개월 보관본을 초기 69개월 입력으로 시도했을 때 안전하게 거부하고 출력 디렉터리도 만들지 않았습니다. 실데이터 검증 성공으로 대체 보고하지 않습니다. [입력 가용성 및 미검증 범위](real-input-status.json).

초기 게시 검증은 `2021-01~2026-09` 정확히 69개월 및 다음 원본 해시를 고정 확인합니다.

| 지표 | 원본 SHA-256 |
| --- | --- |
| 관광수입 | `780465a3e72886e94643dd6da5f2fa03d3f5d0a991200ce29313e969eae51f7d` |
| 관광지출 | `c21d857270a37d29251f3f3c0d2314c50b49c1b73259c7fbab50f7eb72e96ff1` |
| 관광수지 | `c2a3bd7ba225db9117fcb5535c0f8957ff80f0440801c18080080a74a3f2f721` |

해시 이름을 기록하는 것만으로 공식성을 증명하지 않습니다. 실제 XLS 입력은 바이트 해시를 파싱 전후 대조합니다. 비공개 원장 입력은 독립 검증된 원장 파일 해시와 원본별 provenance를 함께 확인합니다. 합성 fixture의 공식 형태·해시 라벨은 테스트 계약 검사용이며 실제 원본 증거가 아닙니다.

## 구현 파일과 동작

| 파일 | 구현 |
| --- | --- |
| `src/macro/tourgo_release.py` | 읽기 전용 staging CLI, 초기 69개월/후속 갱신 검증, 검토 영수증, 운영 트랜잭션용 `ReleaseRequest` |
| `src/macro/tourgo.py` | 공개 통계 필드 허용 목록, 비상업 조건 판정. 기존 XLS·단위·항등식 검증 재사용 |
| `src/macro/engine.py` | 원본 없는 정기 실행은 수동 갱신 대기, 명시적 입력은 당일에도 재검증, 비공개 metadata 제거, 수지 교차검증 변경 이력 구분 |
| `src/pipeline/runner.py` | 기존 트랜잭션 안에서만 수동 입력 재검증/재수집/검토 결과 대조. CAS 충돌 시 최신 스냅샷 재복원 후 재검증 |
| `src/pipeline/policy.py` | Macro 공개 데이터도 현재 승인·비공개 원장 투영과 일치하는지 배포 전 검증 |
| `site/macro.js`, `site/index.html` | 공개 최소 필드 지원, 수동 갱신 대기 표시, 실제 연결 상태에 따른 About 출처 설명 |
| `tests/test_tourgo_readiness.py`, `tests/tourgo-readiness.smoke.cjs` | 합성 69개월/138개 통합, 운영 게이트, 수동 정정, 동시 갱신, privacy, PC·모바일 검증 |

단위와 정의는 기존 코드를 재사용합니다: **일반여행 관광수입·지출**, 원본 **천 US$ → 정수 US$ → 백만 US$ 표시**. 수지는 공식 원본과 수입−지출이 일치해야 하며 전월·전년 동월 절대 금액만 표시합니다. 미표기된 공표일·확정 상태를 추정하지 않습니다. 방한·출국과 관광수지의 기준월은 별도로 표시하며 Percentage UI·시뮬레이션 계산식은 유지합니다.

## 안전한 최초 게시 준비

staging은 원본/검증 원장 → 기존 어댑터 → 현재 Macro 원장 통합 → 기존 검증·Pages 조합 순서입니다. PR #37 Preview 결과나 공개 JSON을 복사해 승격하지 않습니다.

1. 현재 `data/live`의 검증된 로컬 스냅샷을 입력받습니다. 기존 기간·최초 수집일·정정 이력의 삭제를 기존 pipeline validator가 거부합니다.
2. TOURGO에 해당하는 변경만 격리 디렉터리에 만듭니다. KTO의 기존 관측·정정 이력 및 다른 엔진 파일의 바이트를 대조합니다. staging에서 다른 출처는 호출하지 않고 기존 확인 시각을 보존합니다.
3. 기존 `compose()`를 통해 공개 파일 12개만 `pages/`로 조합합니다. 여기에는 검토용 banner가 표시됩니다. 실제 운영 config 대신 메모리 내 staging 설정으로만 승인 후 화면을 검증합니다.
4. `validated-input.json`과 `readiness.json`은 private 출력 최상단에 저장합니다. `candidate/collector_state`도 비공개입니다. **로컬 확인 시 `pages/`만 제공**해야 합니다.
5. 검토 영수증은 입력 원장 해시·현재 Macro 원장 해시·구현/정책 fingerprint·금액 공개 투영 해시를 묶습니다. 기존 Preview manifest는 이 형식을 만족하지 않습니다.

staging의 `operating_approval=false`는 운영 승인이 아닙니다. 메모리 내 staging 승인 근거를 실제 운영 승인으로 재사용하는 것도 운영 경로에서 거부합니다.

### 원본 XLS로 staging

신뢰된 Python 환경에서 `xlrd==2.0.2`를 설치하고, 원본과 출력은 저장소 밖에 둡니다.

```bash
python -m src.macro.tourgo_release \
  --profile initial \
  --receipts /secure/originals/receipts.xls \
  --expenditure /secure/originals/expenditure.xls \
  --balance /secure/originals/balance.xls \
  --baseline-root /secure/current-data-live-snapshot \
  --output /secure/tourgo-readiness-01
```

### 독립 검증된 비공개 원장으로 staging

```bash
python -m src.macro.tourgo_release \
  --profile initial \
  --ledger /secure/verified/tourgo_balance_private.json \
  --ledger-sha256 '<independently-reviewed-ledger-sha256>' \
  --baseline-root /secure/current-data-live-snapshot \
  --output /secure/tourgo-readiness-02
```

두 경로 모두 현재 원장의 483개 KTO 관측을 유지하면서 금액 관측 138개를 추가하는 구조입니다. 관광수지 69개월은 별도 계산/검증 객체이며 비음수 금액 관측에 중복 추가하지 않습니다. 합성 검증에서 총 원장은 **483+138=621개**였습니다.

## 최종 승인 이후에만 가능한 운영 반영

**이 PR은 다음을 수행하지 않습니다:** 원본 전달 workflow 연결, source/indicator 활성화, 운영 승인 변경, `data/live` push, Pages 배포. 실제 입력 전달 채널은 신뢰된 관리자 환경에서 별도 준비해야 하며 원본·원장을 Git/공개 artifact/로그에 올려서는 안 됩니다.

별도 활성화 검토에서 `macro_sources.json`의 두 금액 ID를 TOURGO로 명시적으로 선택하고 source/indicator를 활성화해야 합니다. `collection`과 `publication`에는 실제 사용자 운영 승인 근거, 유효 시작일과 **유한한 종료일**이 필요합니다. 기존 ECOS source는 모두 비활성으로 유지합니다. 비상업·광고 없음·유료 접근 없음도 다시 검사합니다. 기관의 2026-11-09 이용조건 안내는 운영 승인 자체가 아닙니다.

공개 지표 필드의 canonical 설정은 `activation_candidate()`가 생성하는 staging 계획과 동일해야 합니다. 이 함수는 운영 파일을 변경하지 않습니다. 실제 승인 근거는 staging 근거와 구별하여 별도 승인 변경에 적용해야 합니다.

검토와 승인이 완료된 후 기존 `pipeline.yml`의 **`tourism-pulse-publish` 공유 concurrency job 안에서**, 보호된 입력을 runner 임시 디렉터리에 전달한 뒤 기존 runner를 다음 옵션으로 호출할 수 있습니다. 새로운 별도 push/배포 스크립트는 제공하지 않습니다.

```bash
python -m src.pipeline.runner run \
  --requested macro \
  --work "$RUNNER_TEMP/tourism-pipeline" \
  --output "$RUNNER_TEMP/tourism-pages" \
  --tourgo-ledger /secure/reviewed/validated-input.json \
  --tourgo-ledger-sha256 '<reviewed-input-sha256>' \
  --tourgo-receipt /secure/reviewed/readiness.json \
  --tourgo-receipt-sha256 '<reviewed-receipt-sha256>'
```

이 명령의 운영 경로는 main Actions 컨텍스트와 현재 main/data head, 실제 승인, 입력·영수증 해시, 구현/정책, 현재 Macro 원장을 재검사합니다. staging 공개 파일을 읽지 않고 private 입력으로 다시 통합하며, 금액 공개 투영이 검토 결과와 다르면 되돌리고 실패를 기록합니다. Macro 원장이 staging 이후 달라졌으면 최신 스냅샷으로 staging을 다시 생성해야 합니다.

동시에 News만 갱신되어 Git CAS 충돌이 나면 기존 트랜잭션이 최신 snapshot을 복원하고 입력을 재검증합니다. 최신 News를 보존한 상태로 재시도하는 로컬 bare Git 테스트를 통과했습니다. 기존 validator·`Store.commit`의 fast-forward 보호·Pages head guard·Due Engine 정책은 유지합니다. 위 입력 옵션은 현재 workflow에 연결하지 않았으므로 PR 병합만으로 실행되지 않습니다.

## 수동 갱신 정책

- 정기 Macro 실행에 TOURGO 입력이 없으면 source `manual_update_pending` / `waiting_for_manual_input`입니다. 기존 관측과 `last_successful_check`를 유지하며 신규 성공으로 집계하지 않습니다.
- KTO 자동 수집은 정상 실행합니다. TOURGO 대기 때문에 불필요한 Failure를 만들지 않지만 실제 KTO 실패는 기존 상태 정책에 따라 기록됩니다.
- 원본을 명시적으로 제공한 실행은 같은 날 재입력해도 검증합니다. TOURGO 오류가 나면 KTO가 성공했어도 수동 요청은 failed로 기록합니다. 입력 검증 단계에서 실패하면 원장을 쓰지 않고 기존 runner 진단과 종료 코드로 실패를 알립니다.
- 새 XLS 또는 정정본은 `--profile update --hash-manifest /secure/reviewed/new-original-hashes.json`을 사용합니다. 해당 세 원본 해시는 운영자가 독립 검토해야 합니다. 같은 CLI의 파일/원장 입력을 재사용하고 새 staging과 검토 영수증을 생성한 뒤 승인된 트랜잭션으로 갱신합니다.
- 누락 과거 월은 기존 검증값을 유지하고, 값·확정 상태·공식 수지 교차검증 변경 이력을 분리해 보존합니다. ECOS↔TOURGO 기존 관측 혼합은 계속 차단합니다.

## 공개/비공개 분리

공개 JSON은 수치·기간·단위·공식 출처·확정 상태·확인 시각·공개 검증 상태·비교 결과만 제공합니다. TOURGO 원본 해시 묶음, raw source value 중복, 원장 역할, `data_origin`, 관리용 파일 경로, 검토 영수증 및 private 원장은 Pages에 포함하지 않습니다. 비공개 원장은 원본 단위·해시·원본 수지·정정 정보를 보존하며 공개 전 검증은 계속 이 정보를 사용합니다.

브라우저의 새로운 공개 필드 검사는 private metadata가 들어온 구형 Preview payload도 거부합니다. 서버의 Macro 공개 검증은 현재 source 승인과 private 원장 투영을 다시 대조합니다. 비상업 조건이 깨지거나 게시 승인이 취소되면 기존 보관 자료도 공개되지 않습니다.

## 검증 결과

- Python 전체 **527개 통과**, 신규 readiness 14개 포함. 기본 비활성, 초기 69개월/138개, 수지 음수/비교, 승인 취소·유효기간, 수동 대기·명시적 오류, 정정 이력, stale 영수증, Preview 비복사, projection 불일치 rollback, CAS 충돌, privacy, 비상업 조건을 검증했습니다.
- 브라우저 **22개 전체 스위트 통과**. 최신 운영 스냅샷의 News 81건·Research 137건·KTO 483개를 사용했고, 금액은 합성 fixture만 주입했습니다. 320/390/768/1440px에서 Overview·Macro, 69개월 차트, 단위·색상·음수 수지, 수동 대기·확인시각 보존, 개인정보/관리 metadata 차단, 시나리오 불변을 확인했습니다.
- 기존 브라우저 테스트 4개는 변경 전 main에서도 최신 데이터로 실패했습니다. 자료 수 135 고정 → 실제 snapshot/표시 수 대조, 최신순 테스트의 정렬 명시, 빈 브리핑의 현재 사유 대조, 표제 fixture의 단일 기사 격리로 보완했습니다. **뉴스·리서치·브리핑 운영 로직은 변경하지 않았습니다.**
- [브라우저 스위트 결과](browser-results.json), [실제 원본 미검증 범위](real-input-status.json), [기본 파일 보존 증거](preservation.json).
- 실제 활성화 없이 조합한 기본 파일 **30개 SHA-256 동일**. `macro_sources.json`, `operating_policy.json`, workflow, KTO/ECOS 수집기·매핑, 원장·운영 JSON, Percentage UI, 로고 원본은 변경하지 않았습니다.
- GitHub CI 최종 결과는 PR Checks와 PR 설명에 기록합니다. PR에서는 실제 수집·게시 job을 실행하지 않습니다.

합성 화면: [1440px](screenshots/synthetic-readiness-1440.png) / [390px](screenshots/synthetic-readiness-390.png). 화면에 합성 69개월·실제 TOURGO 수치 아님·운영 미활성을 표시했습니다. 실제 금액 데이터 화면은 제출하지 않았습니다. 브라우저 검증은 Chromium 기준입니다.

## 남은 승인·실행 사항

1. 지정 해시의 실제 69개월 원본 또는 독립 검증된 비공개 원장을 신뢰된 실행 환경에 제공하고 새 staging/공개 JSON·화면을 **실제로** 재검증합니다.
2. 사용자가 원본·단위·기간·staging 결과와 최초 게시를 검토한 뒤 별도 운영 활성화를 승인합니다. 승인 근거·유효기간·source 선택을 별도 변경으로 적용합니다.
3. 보호된 원장/영수증 입력 전달을 기존 공유 락 job에 연결한 뒤 최초 게시·Pages를 수행합니다. 현재 PR은 입력 전달 또는 자동 다운로드 workflow를 활성화하지 않습니다.
4. 게시 후 수동 입력 없는 정기 실행의 상태·기존 값 보존·KTO 자동 수집·Pages를 운영에서 별도 확인합니다.

기관의 추가 이용 허가나 새 TOURGO API 키는 이번 수동 경로에 필요하지 않습니다. 사용자 최종 운영 승인과 보호된 입력 전달이 남아 있습니다. **이번 PR에서는 운영 공개·자동 병합하지 않습니다.**
