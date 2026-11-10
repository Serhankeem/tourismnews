# TOURGO Production Activation & Initial Publication v1.0

**구현·사전 검증 PR입니다. 운영 활성화/승인 적용/실데이터 게시/자동 병합을 실행하지 않았습니다.**

기준 main: `e574603` (PR #39 병합). 작업 브랜치: `feat/tourgo-production-activation-v1`.

## 이번에 완성한 경로

| 파일 | 변경 |
| --- | --- |
| `src/macro/tourgo_activation.py` | 실제 설정을 수정하지 않는 외부 Activation Configuration 제안 생성기. 기관 이용조건과 별도 collection/publication 승인 참조, 시작일·유한한 종료일·비상업/무료/무광고/출처표시 조건 검증 |
| `src/macro/tourgo_delivery.py` | 보호 환경·관리자 ID 확인 → 비공개 GitHub 저장소 고정 커밋 → 검토 manifest/개별 파일 해시 확인 → runner 임시 디렉터리 전달. 고정 오류 코드만 출력 |
| `src/macro/tourgo_release.py` | PR #39 영수증/원장/공개 투영 검증 유지. 전달된 원본 3개를 다시 파싱하고 원장 전체 금액과 대조. 파서 진단 stdout/stderr 차단. 새 구현·workflow도 영수증 fingerprint에 포함 |
| `src/pipeline/runner.py` | `--tourgo-input-dir`로 기존 ReleaseRequest를 생성. 수동 TOURGO 검증 실패 시 다른 수집기 성공과 관계없이 **Store.commit 전 중단** |
| `.github/workflows/tourgo-publish.yml` | 수동 요청 + 명시적 확인만 최초 게시 경로 진입. PR에서는 전체 테스트만 실행 |
| `.github/workflows/pipeline.yml` | 동일 `tourism-pulse-publish` 공유 lock/Store/CAS/Pages guard 재사용. 수동 요청에만 보호 환경·private 전달·XLS parser 적용. 임시 입력 always cleanup |
| `tests/test_tourgo_activation.py`, `tests/test_tourgo_readiness.py` | 보호 환경·승인·입력 손상·원장 변경·노출·중단·배포 전 조합 실패 검증 |
| `tests/tourgo-activation.smoke.cjs` | 합성 69개월 + 사용자 제공 기대값의 표시/단위/수지/비교/69개월 차트/4개 너비 검증 |

News·Research·KTO·ECOS 어댑터와 통계 계산, 웹 UI 소스, Percentage UI, 기존 일정은 변경하지 않았습니다. 새로운 독립 Git push/Pages 배포 스크립트를 만들지 않았습니다.

## 실제 검증과 합성 검증

사용자는 2026-11-10 별도 환경에서 PR #39 실제 원본 해시 3/3, 69개월, 항등식 69/69, KTO 483 + TOURGO 138 = 621의 staging 검증 성공을 전달했습니다. **이 작업 환경에서는 일치하는 실제 원본 3개를 찾지 못했습니다. 그 실증을 재현했다고 보고하지 않습니다.**

[실제 원본 가용성](real-input-status.json)에 별도로 기록했습니다. 8개 spreadsheet 후보를 검사했으나 지정 해시 일치 0개입니다. 기존 68개월 비공개 원장 크기는 182,368바이트로 GitHub Secret 48KB 제한보다 큽니다. 파일을 쪼개 Secrets에 넣거나 공개 artifact로 전달하지 않습니다. Secret은 작은 토큰·좌표·검토 해시만 담습니다.

합성 테스트의 해시 라벨/official 형식은 신뢰된 관리자 입력 계약을 검사하기 위한 fixture입니다. 실제 XLS 바이트 검증의 증거가 아닙니다. 원본 확인 없는 합성 자료를 운영 원장에 넣지 않았습니다.

공식 초기 입력의 고정 해시·기간 검사는 PR #39 그대로 유지합니다.

- 원문: <https://know.tour.go.kr/stat/koreaTourIncomeDis19Re.do>
- 2021-01~2026-09, 69개월, 수입/지출 각 69개
- 원본 천 US$ → 정확한 정수 US$ → 화면 백만 US$
- 원본 3계열 전체 월별 항등식, 단위·결측·미래월·provenance 검증
- 잠정/확정·공표일이 미표기된 경우 추정하지 않음
- 9월 기대값 2,460.8 / 2,958.8 / -498.0백만 US$는 **표시 테스트의 입력값**이며, 그것만으로 공식성을 인정하지 않음

## 보호된 입력 전달 설계와 현재 차단 상태

개발 시 읽기 전용 GitHub API 확인 결과, 저장소의 environment 목록에는 `github-pages`만 있었습니다. 이 환경은 required reviewer가 없고 `can_admins_bypass=true`여서 수동 금융 게시용 보호 조건을 충족하지 않습니다. Secrets/variables/self-hosted runner 목록 조회는 현재 연결 권한으로 HTTP 403이었으며, 그 내용을 확인했다고 가정하지 않았습니다. 설정·Secret을 생성하거나 변경하지 않았습니다.

**따라서 실제 전달/최초 게시 경로는 현재 구성 완료로 간주할 수 없습니다.** 아래 관리자 설정과 최종 승인이 필요합니다. 기본 비활성 설정에서는 private repository를 읽기 전 차단합니다.

### 관리자가 설정할 GitHub Environment

`Serhankeem/tourismnews` → Settings → Environments → **`tourgo-production`**:

1. Required reviewers: 신뢰된 최종 승인자 지정. Prevent self-review 활성화. 요청자와 별도의 승인자가 필요합니다.
2. 관리자 protection bypass 금지 (`can_admins_bypass=false`).
3. Deployment branches/tags: selected branch **main 하나만**, 태그 허용 없음.
4. 아래 5개 **Environment Secrets** 등록. Repository Secrets로 대신 등록하지 않습니다.

| Secret | 내용/범위 |
| --- | --- |
| `TOURGO_INPUT_TOKEN` | 관리자가 발급한 만료 가능한 읽기 전용 fine-grained token. 선택 저장소: 비공개 입력 저장소 + tourismnews. Contents read, 환경 보호 조회를 위한 Actions read. 쓰기 권한 불필요 |
| `TOURGO_INPUT_REPOSITORY` | `owner/private-repository` 형식. 입력 저장소가 실제 private인지 API로 재확인 |
| `TOURGO_INPUT_COMMIT` | 검토한 비공개 입력 커밋 전체 40자리 SHA. branch/tag/latest URL 사용 금지 |
| `TOURGO_MANIFEST_SHA256` | 아래 manifest 원본 바이트의 SHA-256. 검토 승인 때 고정 |
| `TOURGO_ALLOWED_ACTOR_IDS` | 수동 실행을 허용할 관리자 GitHub 숫자 ID, 쉼표로 구분(공백 없음) |

좌표·관리용 해시도 Secret으로 마스킹해 runner의 기본 env 출력에 노출되지 않게 합니다. 개발 환경에 토큰을 전달하지 않습니다. 실제 Git 쓰기는 기존 job의 `github.token`만 사용하며 입력 읽기 토큰은 전달 step에만 주입합니다.

공식 권한 참고: [Get environment](https://docs.github.com/en/rest/deployments/environments#get-an-environment), [deployment branch policies](https://docs.github.com/en/rest/deployments/branch-policies#list-deployment-branch-policies). 토큰이 해당 환경 조회를 못 하면 고정 `private_input_api_unavailable`로 차단됩니다. 토큰/URL/응답 원문은 Summary에 넣지 않습니다.

### 전용 비공개 저장소의 고정 입력 계약

전용 비공개 저장소의 **루트에 아래 6개 regular blob만** 둡니다. 공개 저장소·README·중첩 폴더·symlink·zip·리디렉션은 허용하지 않습니다.

```
manifest.json
ledger.json       # 새 staging/validated-input.json의 정확한 원본 바이트
receipt.json      # 새 staging/readiness.json의 정확한 원본 바이트
receipts.xls      # 고정 해시에 맞는 실제 원본
expenditure.xls
balance.xls
```

manifest 구조:

```json
{
  "schema_version": 1,
  "profile": "initial",
  "files": {
    "ledger.json": "<independently-reviewed-sha256>",
    "receipt.json": "<independently-reviewed-sha256>",
    "receipts.xls": "<pinned-original-sha256>",
    "expenditure.xls": "<pinned-original-sha256>",
    "balance.xls": "<pinned-original-sha256>"
  }
}
```

루트 파일명·개별 해시·manifest 해시·커밋을 관리자가 검토합니다. API JSON 응답 상한 8MiB, 개별 원본/원장 상한 4MiB를 적용합니다. 임의 사용자 URL을 받지 않으며 GitHub API의 고정 host/path만 사용합니다. 리디렉션·공개 저장소·잘못된 SHA·잘린 tree·중복 JSON 키·추가 파일은 거부합니다.

비공개 원장 원본 파일과 원본 XLS는 Pages/공개 artifact/Git 운영 데이터에 복사하지 않습니다. 기존 Macro 원장에는 기존 계약에 따른 **정규화된 검증 관측값 및 정정 근거**만 들어갑니다. `data/live`는 공개 저장소의 branch이므로 그 Macro 원장을 비밀 저장소로 취급해서는 안 됩니다. 비공개 파일에 개인정보/승인 원문/토큰을 넣지 마세요. 원본 입력 파일 자체는 별도 비공개 저장소에서 관리합니다.

## 승인 후 관리자가 수행할 순서

### 1. Activation Configuration을 별도 검토

운영 승인이 없는 지금은 이 단계를 실행/적용하지 않았습니다. 관리자는 신뢰된 환경에서 승인 파일을 준비합니다. `terms_evidence_ref`는 기관 이용조건 근거, `collection`/`publication`은 **별도 최종 운영 승인** 참조이며 서로 다른 불투명 ID를 사용합니다. 이메일·개인정보·URL을 넣지 않습니다.

```json
{
  "terms_evidence_ref": "<terms-reference-id>",
  "conditions": {"noncommercial": true, "free_access": true, "no_ads": true, "attribution": true},
  "collection": {"evidence_ref": "<collection-approval-id>", "valid_from": "YYYY-MM-DD", "valid_until": "YYYY-MM-DD"},
  "publication": {"evidence_ref": "<publication-approval-id>", "valid_from": "YYYY-MM-DD", "valid_until": "YYYY-MM-DD"}
}
```

```sh
python -m src.macro.tourgo_activation --approval /secure/owner-approval.json --output /secure/new-activation-plan
```

이 명령은 checkout 밖 새 0700 폴더에 0600 `macro_sources.proposed.json`만 만듭니다. 실제 파일이나 권한을 바꾸지 않습니다. 생성 결과를 별도 **Activation Configuration PR**에서 검토해야 합니다. TOURGO 기존 source와 두 기존 금액 ID만 연결하고 ECOS는 비활성으로 유지합니다. 무기한·누락·만료·staging 승인·상업 조건은 거부합니다. PR #40 병합만으로 적용되지 않습니다.

### 2. 최신 원장/최신 구현으로 실제 staging을 다시 생성

승인 설정과 코드가 최종 검토된 후 신뢰된 실행 환경에서 최신 `main`과 `data/live`를 읽기 전용으로 가져옵니다. **수치는 483개로 고정해 덮어쓰지 않습니다.** 최신 Macro 원장 전체를 baseline으로 사용합니다.

```sh
python -m src.macro.tourgo_release --profile initial \
  --baseline-root /secure/latest-data-live --output /secure/new-reviewed-staging \
  --receipts /secure/original/receipts.xls \
  --expenditure /secure/original/expenditure.xls \
  --balance /secure/original/balance.xls
```

관리자 환경에는 `xlrd==2.0.2`가 필요합니다. 기존 `pages/`의 JSON·PC/모바일 화면, 출처/기준월/확인일/비공개 필드 제외, 기존 관측값 보존, 138개 추가를 검토합니다. 출력 ledger/receipt 바이트를 바꾸지 않고 위 비공개 입력 저장소에 제공합니다. manifest와 고정 커밋을 검토한 후 Environment Secrets를 갱신합니다. 예전 PR #39 영수증을 그대로 재사용하지 않습니다. 새 코드/workflow fingerprint가 달라 거부됩니다.

### 3. 명시적 수동 실행 + 보호 환경 승인

최종 운영 승인과 위 준비 이후에만 GitHub Actions의 **TOURGO initial publication (manual)**에서 main을 선택하고 `confirm_reviewed_initial_publication=true`로 실행합니다. 관리자 allowlist와 보호 환경 승인이 모두 필요합니다. PR/push/schedule은 게시를 트리거하지 않습니다.

공유 lock 안에서 최신 main checkout → 실제 활성화/비상업/보호 설정 확인 → 비공개 입력 전달 → Store 최신 snapshot → ReleaseRequest 및 원본 재파싱 → 수집/공개 투영 대조 → validation → 기존 Store.commit/CAS → Pages guard/공개 artifact/배포 순서입니다. staging HTML/JSON을 운영으로 복사하지 않습니다.

Macro 원장이 staging 이후 변경됐으면 중단하고 새 staging을 요구합니다. News만 동시 갱신되면 기존 CAS 재시도로 그 변경을 보존합니다. 보호 설정이나 입력이 잘못되면 게시하지 않고 고정 오류만 남깁니다. 전달 파일은 runner 임시 디렉터리 0700/파일 0600으로만 사용하며 always cleanup합니다. 강제 취소로 cleanup이 끝나지 않아도 GitHub-hosted 임시 runner가 폐기되며 public artifact에 입력을 포함하지 않습니다.

## 실패/복구 및 최초 게시 이후

- 승인/입력/원본/투영 검증 실패: 수동 트랜잭션을 **커밋 전에** 중단. 기존 data/live 보존, Pages 미실행.
- 취소가 Store.commit 이전에 발생: 이전 snapshot 유지. commit 도중 중단은 기존 Store의 서버 fast-forward/ACK 확인 정책을 따름.
- Git 저장 이후 Pages 조합/배포 실패: Git과 Pages는 원자적 단일 저장소가 아닙니다. **검증 완료해 이미 저장된 vintage는 삭제하지 않으며** 기존 공개 페이지와 저장 상태를 구분해 보고합니다. 기존 `deploy.yml` 수동 재배포로 최신 snapshot 재투영/검증/guard 후 복구합니다. 초기 입력을 반복해 강제로 덮어쓰지 않습니다.
- 정상 게시 후 일일 Macro: 입력 없으면 `manual_update_pending`, 이전 값과 성공 시각 유지. 새 성공으로 기록하지 않고 KTO 자동 수집은 유지.
- 이용/게시 승인이 만료·철회되면 기존 기록도 공개 투영에서 차단. 원장/정정 이력 삭제 안 함.
- 최초 게시 후 Overview/Macro와 public JSON, 69개월 차트, 수지 -498, 수입/지출 비교, 출처/기준월/확인일, 다른 엔진 보존을 운영에서 별도 확인해야 함.
- 이후 수동 갱신은 PR #39 `--profile update`로 새로운 세 해시를 독립 검토합니다. 이번 workflow 전달 계약은 **최초 게시 initial 전용**입니다. 자동 다운로드와 반복 갱신 UI는 PR #41 후속 범위입니다.

## 검증 결과

[Python/브라우저 결과](tests.json), [브라우저 상세](browser-results.json), [운영 기본 투영 보존](preservation.json).

- Python 전체 **540개 통과**(신규 13개: 전달/승인 9, 트랜잭션 4). 수동 실패와 투영 불일치의 기존 2개 테스트도 커밋 전 중단으로 강화.
- 브라우저 전체 **23개 스위트 통과**, 320/390/768/1440px. 합성 69개월/138개 + 기존 KTO 483개, 단위·음수·비교·소스·수동 대기·모바일·공개 필드 검증.
- 최신 read-only `data/live` snapshot `2c1c71e6a981d33938b9ba6da07aae0a589d200f`: News 81, Research 137, KTO 483. 기본 설정으로 재투영한 30개 운영 파일 모두 SHA 동일.
- 기본 `macro_sources.json`, `operating_policy.json`, news/research 설정, 전체 운영 JSON, 로고와 UI 코드는 main과 동일. ECOS·TOURGO 실제 승인값 false 유지.
- GitHub CI 최종 링크/결과는 PR Checks와 PR 설명에 기록. PR CI는 실제 입력·수집·게시 작업을 실행하지 않음.

화면은 **합성/실제 원본 검증 아님/운영 미활성** 표기: [1440px](screenshots/synthetic-activation-1440.png) · [390px](screenshots/synthetic-activation-390.png).

실제 최초 게시의 잔여 조건은 **운영 승인 및 Activation Configuration 별도 검토, 보호 환경과 비공개 입력 설정, 최신 실제 원본 staging 재검증**입니다. 새 TOURGO/ECOS API 키는 필요하지 않습니다. 현재 실제 전달/게시 성공 또는 운영 연동 완료로 보고하지 않습니다.
