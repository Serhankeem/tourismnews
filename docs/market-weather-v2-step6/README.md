# Market Weather v2 Step 6 — ECOS 인증 수집 Preflight

[Issue #49](https://github.com/Serhankeem/tourismnews/issues/49)의 Step 1~5와
병합된 [PR #50](https://github.com/Serhankeem/tourismnews/pull/50)에 이어,
인증키로 공식 월별 통계를 조회할 수 있는지 확인하는 수동 검증 경로입니다.
실제 인증 조회는 이 변경의 리뷰·병합 후 사용자가 별도로 승인하여 실행합니다.
구현·테스트 중에는 Actions나 인증 실수집을 실행하지 않습니다.

## 범위와 실행 순서

전용 Actions 이름은 **Market Weather ECOS Preflight**이며 파일은
[ecos-market-preflight.yml](../../.github/workflows/ecos-market-preflight.yml)입니다.
`workflow_dispatch`만 있고 일정·push·PR 자동 실행은 없습니다. `main` 이외의
브랜치에서는 검증 작업이 실행되지 않습니다. `contents: read`만 부여하며,
선택한 `github.sha`를 checkout하고 Git 인증 정보를 보존하지 않습니다.
기존 운영 수집 파이프라인이나 배포 워크플로를 호출하지 않습니다.

`src.macro.ecos_market_preflight`가 기존 `ecos.Client`의 인증·HTTPS·요청 제한과
`ecos_decimal.py`의 공식 코드·단위·월별 관측치 검증을 재사용합니다.
CLI 진입점도 `GITHUB_ACTIONS=true`, `workflow_dispatch`, `refs/heads/main`을
확인한 후에만 클라이언트를 만듭니다. Summary는 러너가 제공한 기존 일반
파일이며 `RUNNER_TEMP` 아래이자 저장소 밖인 경우에만 열고 추가 기록합니다.
임의 경로·저장소 파일·심볼릭 링크를 Summary 대상으로 사용하지 않습니다.

- **scope=fx**(기본값): `731Y004 / 0000001 / 0000100`의 원·달러
  **월평균** 환율의 최신 공표 3개월부터 검증합니다. 월말자료 `0000200`은 대상이 아닙니다.
- **scope=all**: 같은 실행에서 환율을 먼저 검증하고, 성공한 경우에만
  생산지수 2개와 CPI 6개의 최신 공표 3개월씩으로 진행합니다. 환율의 인증·조회·검증 실패를
  무시하고 나머지 8개를 조회하지 않습니다.
- 생산지수·CPI 코드는 PR #50의 등록 정의를 사용합니다. 다른 기준년,
  명목·계절조정 지수, 평균/월말 구분을 자동으로 바꿔 넣지 않습니다.
- Step 3의 **계열 ID·표/항목·단위·기준년·월 주기·기준월·정규화 Decimal 값**을
  함께 묶은 SHA-256 기준 패키지와 중복 기간을 비교합니다. 2021년 이후
  전 기간을 다시 수집하지 않습니다. 실제 원시 수치는 저장소에 추가하지 않습니다. 불일치는
  **정정 후보**로만 집계하며 공식 정정 확정이나 운영 원장 수정이 아닙니다.
  비교는 일치·정정 후보·기준 패키지 밖 신규 월·이번 미조회 월 건수로 구분합니다.
  비교 기준 패키지가 없거나 무효하면 성공으로 처리하지 않습니다.
- 환율 이후의 계열에서도 오류가 나면 그 실행을 중단합니다. 앞서 검증한 계열의
  안전한 집계와 `failed_indicator`를 남기고, 뒤의 계열을 계속 조회하지 않습니다.

## Step 3 비교 기준 패키지

기본 파일은 `fixtures/macro_market_step3_baseline.json`이며 9개 계열의 **628개
월별 fingerprint**를 포함합니다. 파일의 SHA-256은
`d9d5e2df5197be687d2b0f7a423961b9f9fd95dbd9b202c2a374b9af84ee6f84`로
코드에 고정되어 있습니다. 전체 파일 해시·계열 정의·월 집합·관측 수를 검증하고,
동일 값이라도 다른 기준월이나 계열의 fingerprint로 대체하지 못하게 합니다.
진단 결과에는 이 fingerprint나 실제 수치를 출력하지 않습니다.

격리 보관된 Step 3 원본을 가진 검토자는 다음처럼 **오프라인 후보 파일**을
재생성할 수 있습니다. 이 명령은 네트워크나 인증키를 사용하지 않습니다.

```sh
cd /workspace/tourismnews
python -m tools.build_market_preflight_baseline \
  --evidence-dir /workspace/work/weather49-step3 \
  --output /workspace/work/weather49-step6-baseline-candidate.json
```

생성기는 원본 63개 응답의 SHA-256·수집 메타데이터·Step 3 manifest 및
집계 결과의 일치를 확인합니다. 기준 파일을 갱신하려면 후보와 기존 자료의
변경 이유를 리뷰하고 코드의 고정 해시도 함께 갱신해야 합니다. Preflight가
새로 받은 응답으로 비교 기준을 자동 재생성하거나 갱신하지 않습니다.

## 실행 전 사용자 조치

1. 이 도구의 Draft PR을 리뷰한 뒤 `main`에 병합합니다. 이 문서가 있는
   PR은 실제 수집 실행 승인이나 운영 활성화 승인이 아닙니다.
2. GitHub 저장소 **Settings → Secrets and variables → Actions**에서
   이름이 정확히 `ECOS_API_KEY`인 Secret이 있는지 확인합니다. 새로 등록하거나
   갱신해야 한다면 GitHub의 보안 입력란을 사용합니다. 키를 Issue·PR·채팅·
   코드·Actions 입력값에 붙여 넣지 않습니다. `sample`은 정상 인증키가 아닙니다.
3. ECOS에서 키의 유효기간·등록 이용형태·사용 조건을 확인합니다. Secret의
   이름이 존재한다는 사실만으로 정상 인증이나 사용 승인을 판정하지 않습니다.
4. 사용자 승인 아래 먼저 **scope=fx** 실행을 선택합니다. 이번 개발 작업에서는
   이 실행을 수행하지 않았습니다.

## GitHub에서 정확히 수동 실행하기

1. [저장소 Actions](https://github.com/Serhankeem/tourismnews/actions)를 엽니다.
2. 왼쪽 워크플로 목록에서 **Market Weather ECOS Preflight**를 선택합니다.
3. **Run workflow**를 누르고 **Use workflow from: main**을 선택합니다.
4. `scope`를 **fx**로 유지한 뒤 **Run workflow**로 실행합니다.
5. 해당 실행의 **Summary**에서 환율의 인증·메타데이터·관측치 검증 결과를
   확인합니다. 미등록·인증 거절·접근 제한·데이터 검증 실패는 성공이 아닙니다.
6. 환율 검증 성공을 확인하고 확대 실행을 승인한 후, 같은 워크플로에서
   **main / scope=all**로 다시 수동 실행합니다. 이 실행도 환율을 먼저
   재검증하며, 환율이 실패하면 나머지 8개는 실행하지 않습니다.

워크플로가 보이지 않으면 해당 파일이 기본 브랜치 `main`에 병합됐는지
확인합니다. 검증 성공을 위해 수집/게시 플래그를 켜거나 운영 수집기를
수동 실행할 필요는 없습니다. 다른 워크플로 이름을 같은 검증으로 간주하지
않습니다.

## 안전한 결과의 의미

결과는 고정된 상태 코드와 허용된 진단 필드로만 GitHub Summary에 기록합니다.
확인할 항목은 인증 상태, 지표 식별자·표/항목 코드, 단위·기준년, 조회 범위·
최신월, 응답 건수, 결측·중복 및 기준 패키지와의 비교 집계입니다.
실제 수치·정정 전후 값·민감한 응답 원문·인증 URL·HTTP 헤더·키·원문 예외는
로그나 아티팩트로 남기지 않습니다. 아티팩트 업로드 단계도 없습니다.

인증 실패와 메타데이터/관측치 품질 실패는 구분합니다. 정상 키로 인증에
성공했더라도 단위·기준년·품목·기간 검증이 실패하면 해당 계열의 검증 성공으로
표시하지 않습니다. 검증 실패 시에는 Summary의 고정 상태를 확인하고,
문제 해결 뒤 사용자가 재실행 여부를 결정합니다. 한도 탐색이나 부하 테스트는
수행하지 않습니다.

## Summary 출력 형식 예시

아래는 **형식 설명을 위한 모의 결과**이며 실제 인증 성공 기록이 아닙니다.
주입한 테스트 응답은 모든 품질 검사를 통과해도 `simulation_only` /
`not_verified`로 표시합니다.

```text
## Market Weather ECOS Preflight

- Status: simulation_only
- Authentication: not_verified
- Scope: fx
- Expansion: not_requested
- Read-only diagnostic; no collection/publication approval or production writes.

### market_fxavg
- Table/items: 731Y004 / 0000001 / 0000100
- Unit/base year: 원 / None
- Validated monthly window: 2026-08..2026-10
- response_count: 3
- missing_count: 0
- duplicate_count: 0
- overlap_count: 3
- matched_count: 3
- correction_candidate_count: 0
- new_period_count: 0
- baseline_unqueried_count: 67
```

정상 Secret을 사용하는 실제 CLI에서 환율 메타데이터와 실측 관측치 검증까지
성공해야 `Authentication: verified_fx_observations`가 됩니다. 선택한 범위의
모든 검증을 마쳤을 때만 `Status: passed`를 기록합니다. 이는 원표 교차검증·
권리·게시 승인 완료를 뜻하지 않으며, 정정 후보가 0이라는 뜻도 아닙니다.

`scope=all`에서 환율 실패 시 `Expansion: blocked_by_fx`로 나머지 8개를
건너뜁니다. 환율 통과 후 오류가 발생하면 `stopped_on_failure`와
`Failed indicator`를 기록합니다. 실패한 계열은 검증 완료 행으로 출력하지
않습니다. `matched_count`는 **조회한 중복 기간 안의 일치 건수**이며,
`baseline_unqueried_count`가 나타내는 과거 전체 기간을 이번에 검증했다는
뜻이 아닙니다.

| 고정 Error 코드 | 의미 |
|---|---|
| `credential_missing` | 현재 검증 단계에 Secret이 전달되지 않음 |
| `authentication_rejected` | 키 형식/sample 또는 공식 API의 인증 거절 |
| `auth_or_access_denied` | HTTP 401/403 인증·접근 거절; 세부 원문은 출력하지 않음 |
| `rate_limited` | 과다 호출 제한; 반복 호출로 제한을 탐색하지 않음 |
| `network_or_tls_failure` | 네트워크 또는 TLS 실패로 인증을 판정하지 못함 |
| `baseline_invalid` | 고정 비교 패키지 누락·해시 또는 정의 불일치 |
| `metadata_regressed` | 원본 메타데이터의 최신월이 Step 3에서 확인한 최신월보다 과거로 후퇴함 |
| `baseline_change` | 단위/기준년 변경; 기존 계열에 접속하지 않음 |
| `missing_months` / `duplicate_months` | 조회 월 집합의 결측/중복 검증 실패 |

실패 시에도 응답 원문 대신 고정 Error 코드와 검증된 집계만 남깁니다.
Summary 경로 자체가 안전하지 않으면 기록하지 않고 실패합니다.

## CPI 기준년 변경과 운영 데이터 보존

Step 5에서 확인한 공식 공표문은 2025년 기준 CPI 개편을 2026년 12월에
공표할 예정이라고 설명합니다. 등록된 CPI 정의는 **2020=100**입니다.
메타데이터 또는 관측치가 **2025=100**으로 바뀌면 검증을 실패시키고 기존
2020년 기준 시계열과 자동 연결하지 않습니다. 기준년 변경을 단순한 수치
정정 후보로 처리하거나 새 지수를 기존 원장에 덮어쓰지 않습니다.

이 도구는 Macro 원장·TOURGO·뉴스·리서치·`data/live`·홈페이지·Pages를
수정하지 않습니다. 수집/게시 승인과 모든 운영 활성화 플래그는 그대로
비활성 상태를 유지합니다. 수집 가능성 검증은 별도 권리 검토·원표
교차검증·공개 구현·게시 승인을 완료했다는 뜻이 아닙니다. 새 날씨 점수나
가중치도 계산하지 않습니다.


## 이번 구현 검증 기록

- `python -m unittest discover -s tests -v`: 전체 **623개 통과**. 기존 KTO·TOURGO·뉴스·리서치·파이프라인 회귀를 포함합니다.
- 신규 집중 테스트 **29개**: 환율 선행 게이트, 기본 `fx` 범위, 9개 확장,
  Secret 미등록/sample·인증 거절·접근 제한·과다 호출 구분, 원문/예외 유출 차단,
  Summary 경로 보호, 기준 패키지 무결성, 정정 후보·신규 월·기간 후퇴,
  CPI 기준년 변경 차단 및 기존 Macro/TOURGO 원장 바이트 보존을 확인했습니다.
- 실제 Step 3 원본 63개 응답을 검증한 **오프라인 재생**에서, 9개 계열의
  최신 3개월 **27개 관측**이 기준 패키지와 일치했습니다. 가상 정정 1개와
  CPI 기준년 변경의 실패 처리도 확인했습니다.
- [검증 집계](verification.json)는 고정 코드·기간·건수만 포함하며 실제 수치는
  포함하지 않습니다. `simulation_only` 결과는 인증 실수집 성공이 아닙니다.
- 실제 인증 조회·Actions 실행은 **0회**입니다. 운영 데이터·소스 설정·기존
  컬렉터·TOURGO 승인·UI는 변경하지 않았습니다.
