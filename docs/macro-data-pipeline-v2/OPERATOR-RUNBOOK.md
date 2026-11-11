# Macro Monitor v2 — 1인 운영 매뉴얼

**현재 운영 상태: TOURGO 2021-01~2026-09 최초 69개월은 수집·게시 승인 및 홈페이지 공개가 완료됐습니다. 수집 승인 ≠ 게시 승인이며, 각 action의 기준월 범위는 독립적입니다.**

현재 설정은 TOURGO enabled=true, collection/publication approved=true입니다. 이는 승인된 2021-01~2026-09 범위에만 적용됩니다. **2026-10 이후는 수집·게시 모두 미승인**이며, 후속 기준월은 별도 승인과 설정 검토 전까지 요청·수집·저장·게시하지 않습니다. 이번 보완은 기존 승인·공개 데이터를 변경하거나 게시를 실행하지 않습니다.

**Step 1 기간 제한:** collection/publication 승인 기준월은 각각 `2021-01~2026-09`입니다. `valid_until`은 실행 승인 유효일이며 수록월 상한이 아닙니다. 2026-10 이후 파일을 준비·업로드·요청하지 마십시오. 기간을 사전에 확인할 수 없는 입력은 보류됩니다.

승인 범위 내 수동 갱신은 **공식 XLS 3개 준비 → 패키지 생성 한 번 → private 업로드 → 수동 실행 한 번**입니다. 현재 범위 밖의 새 월은 기존 승인으로 처리할 수 없습니다. 본문/원본 파일을 공개 저장소나 Actions artifact에 올리지 마십시오.

## 0. 최초 한 번 확인할 설정

1. 기존 private repo `Serhankeem/tourgo-private-input`을 유지합니다. bootstrap 6파일은 원래 branch에 보관합니다.
2. Environment `tourgo-production`: **Wait Timer 10분 이상, 관리자 bypass 금지, main branch 하나만 허용**, required reviewers 없음(기존 solo-owner 정책). 허용 owner 숫자 ID 하나를 유지합니다.
3. 기존 Environment Secrets를 재사용합니다. 토큰을 Codex/채팅/공개 로그에 복사하지 않습니다.

| Secret | 용도 | 반복 수정 |
| --- | --- | --- |
| `TOURGO_INPUT_TOKEN` | 기존 private repo Contents read + 환경 조회 Actions read | 토큰 갱신 시만 |
| `TOURGO_INPUT_REPOSITORY` | `Serhankeem/tourgo-private-input` | 저장소 변경 시만 |
| `TOURGO_ALLOWED_ACTOR_IDS` | 허용 owner 숫자 ID **하나** | 소유자 변경 시만 |
| `TOURGO_INPUT_COMMIT` | 초기/명시적 정정 검토 패키지의 고정 private commit | bootstrap/예외 검토 때만 |
| `TOURGO_MANIFEST_SHA256` | 위 검토 패키지 manifest의 고정 해시 | bootstrap/예외 검토 때만 |

새 Secrets·쓰기 토큰·유료 저장소를 추가할 필요가 없습니다. 코드에서 Secrets나 환경 설정을 수정하지 않습니다. 이번 API 관측에서 보호 환경의 timer/bypass가 지정 정책과 다르게 반환됐으므로 실제 실행 전 소유자가 Settings와 live API를 확인해야 합니다. 코드 차단 조건을 완화해서 맞추지 마십시오.

## 1. 새로운 통계 최초 등록 (Bootstrap · 완료된 절차 참고)

**기존 69개월의 최초 게시는 완료됐으므로 initial 게시를 재실행하지 않습니다.** 아래는 최초 등록 절차 참고이며, 기존 승인 범위 내 정정은 4절의 update 절차를 사용합니다. 향후 새 대상이 미승인 상태라면 비공개 staging/검토까지만 진행하며, 그 결과는 운영 승인이 아닙니다.

1. 공식 화면 <https://know.tour.go.kr/stat/koreaTourIncomeDis19Re.do>에서 수입·지출·수지 XLS 3개를 관리자가 준비합니다. 최초 대상은 고정 SHA의 2021-01~2026-09 69개월입니다.
2. 최종 검토된 최신 main을 읽기 전용 작업 checkout으로 사용하고 최신 `data/live`를 별도 안전한 경로에 복원합니다. 예시(관리자 로컬):

```sh
git fetch origin main refs/heads/data/live:refs/remotes/origin/data/live
mkdir -p /secure/baseline-new
git archive origin/data/live | tar -x -C /secure/baseline-new
```

3. 프로그램이 staging과 6파일을 생성하게 합니다. 관리자 환경에 `xlrd==2.0.2`가 필요합니다.

```sh
python -m src.macro.tourgo_staging release-package --profile initial \
  --baseline-root /secure/baseline-new --output /secure/bootstrap-new \
  --receipts /secure/originals/receipts.xls \
  --expenditure /secure/originals/expenditure.xls \
  --balance /secure/originals/balance.xls --official-source-reviewed
```

4. `/secure/bootstrap-new/staging/pages`의 JSON/PC·모바일 화면을 검토합니다. 수입·지출 69개씩, 공식 수지 항등식 69/69, 9월 단위/값, 기존 KTO·정정 이력 보존, 공개 비공개 필드 분리를 확인합니다. 실제 원본 없이 성공으로 판단하지 않습니다.
5. `/secure/bootstrap-new/input`의 **6파일만** private 입력 branch 루트에 업로드합니다. ledger/receipt/manifest를 수동 작성하지 않습니다. 이번 PR의 새 코드 fingerprint 때문에 이전 영수증은 새로 생성해야 합니다.
6. 별도 최종 게시 승인과 Activation Configuration 검토가 완료된 후에만 기존 고정 commit·manifest SHA Secrets를 지정합니다. 해시는 신뢰된 관리자 로컬에서 확인하고 Settings에 입력하며 공개 CI/채팅에 출력하지 않습니다.
7. `TOURGO initial publication (manual)`을 main에서 `profile=initial`, 명시적 확인=true로 실행합니다. 기존 보호 환경과 공유 pipeline이 영수증/원본/원장/승인/공개 투영을 다시 검사합니다. **지금 이 PR 작업에서는 실행하지 않았습니다.**

검토만 하는 명령은 운영 승인/Secrets/data/live를 바꾸지 않습니다. 수집만 승인한 상태로 운영 활성화 설정을 자동 생성/적용하지 마십시오.

## 2. 정상 월별 파일 업데이트

최초 게시가 완료되고 해당 **기준월 범위**의 collection/publication 승인이 유효할 때 사용합니다. 현재는 2026-09까지이며 이후 월은 별도 승인 전 차단합니다. 현재 TOURGO 공식 자동 다운로드는 미확인/비활성이므로 원본 준비는 관리자 단계입니다.

1. 같은 공식 화면에서 **승인된 2021-01~2026-09 전체 기간**의 XLS 3개를 준비합니다. 같은 기준기간과 원본 천 US$를 확인합니다. 일부 월만 받은 파일로 기존 월을 대체하지 않습니다.
2. 새 안전한 디렉터리에 한 명령으로 업로드 묶음을 만듭니다.

```sh
python -m src.macro.tourgo_staging source-package \
  --receipts /secure/new/receipts.xls \
  --expenditure /secure/new/expenditure.xls \
  --balance /secure/new/balance.xls \
  --output /secure/monthly-package-new --official-source-reviewed \
  --period-from 2021-01 --period-through 2026-09
```

`--official-source-reviewed`와 두 기간 인자는 소유자가 공식 원본과 그 범위를 확인했다는 뜻입니다. 생성 manifest의 `period_range`는 파일 해시에 묶여 서명된 입력 커밋에서 검증됩니다. 기간 선언은 원본을 읽기 전에 확인하고, 파싱 결과가 다르면 패키지를 저장하지 않습니다. 기존 고정 69개월 해시는 기간을 확인할 수 있는 예외로 계속 지원합니다. 기관/운영 게시 승인을 부여하거나 해시 자체로 공식성을 증명하는 옵션이 아닙니다.

3. GitHub 웹 UI에서 private repo의 **`updates` branch** 루트에 생성된 5파일을 업로드하고 owner 계정으로 commit합니다.

```
receipts.xls
expenditure.xls
balance.xls
source.json      # 자동 생성
manifest.json    # 자동 생성
```

전용 branch는 처음 한 번 깨끗한 루트로 준비합니다. 초기 입력 branch의 ledger/receipt/README 등이 `updates`에 남으면 계약 위반으로 거부됩니다. 초기 branch/기록은 삭제하지 말고 별도로 유지합니다. 웹 UI 업로드의 검증된 GitHub 서명 또는 검증 가능한 owner 서명을 사용합니다. unsigned commit이나 다른 author의 commit은 거부됩니다.

4. `TOURGO recurring update (manual)`을 main에서 `confirm_official_files=true`로 요청합니다. 기존 보호 환경 대기 후 최신 입력 ref를 commit으로 고정하고 **서명·owner·private 여부**를 검사합니다. 원장·영수증은 최신 data/live를 기준으로 내부에서 생성됩니다. 월별 Secret·해시 복사는 없습니다.
5. Summary에서 상태를 확인합니다.

| 결과 | 운영자가 할 일 |
| --- | --- |
| VALID / 저장·Pages 성공 | 기준월/값/원문/차트를 확인 |
| UNCHANGED | 할 일 없음. 원장·성공시각·health·배포를 갱신하지 않음 |
| REVIEW_REQUIRED | 정정/급변/승인·기간·mapping 사유 확인. 기존 정상값 유지 |
| REJECTED | 원본·해시·단위·누락·미래월·수지 오류 확인. 수정한 공식 입력으로 재시도 |

이 workflow는 수동 파일 갱신입니다. TOURGO 자동 다운로드·월별 cron을 활성화하지 않습니다. KTO 일일 자동 수집은 기존대로 실행됩니다.

## 3. 게시 미승인 상태에서 파일 검증만 할 때

운영 데이터에 입력하지 않고 로컬에서 검사합니다.

```sh
python -m src.macro.tourgo_staging inspect --profile initial \
  --baseline-root /secure/baseline-new --output /secure/inspection-new \
  --receipts /secure/originals/receipts.xls \
  --expenditure /secure/originals/expenditure.xls \
  --balance /secure/originals/balance.xls
```

bootstrap 이후 데이터라면 `--profile update`를 사용합니다. `quality.json`의 data_status와 최종 status/publication_allowed를 구분합니다. 검증 결과가 생성되어도 게시 승인을 뜻하지 않습니다. 실제 승인 설정이 없는 protected 실행은 private API 사용 전 차단합니다. collection만 dated 설정에 기록됐으면 private staging은 가능하지만 공개 트랜잭션은 실행되지 않습니다.

## 4. 과거 통계 정정 / 비정상 변동

1. 자동 경로는 과거 값/최종 상태 변경 또는 새 월 급변(전월 대비 75% 초과)을 REVIEW_REQUIRED로 남기며 운영 값을 쓰지 않습니다. 원본 손상인지 진짜 공식 정정인지 확인합니다.
2. 공식 표/정정 안내와 과거 값을 대조합니다. 변경을 정당화할 근거가 없으면 게시하지 않습니다.
3. 최신 baseline으로 `release-package --profile update`를 실행해 private Preview와 6파일을 자동 생성합니다. 생성 명령은 1절의 `profile=update`에 `--period-from 2021-01 --period-through 2026-09`를 추가합니다. 허용 범위를 설정값에서 자동 추정하지 않습니다.
4. 변경 값·기존 원장 보존·정정 이력·공개 투영을 검토합니다. 기존 source 승인을 새로 만들지 않습니다. 범위/기간/조건이 유효한지 재확인합니다.
5. 검토된 예외 패키지만 기존 pin 방식으로 지정하고 `TOURGO initial publication (manual)`의 **profile=update**를 명시해 실행합니다. 이름은 기존 초기 게시 workflow와 호환을 위해 유지합니다. 이 확인은 특정 정정 데이터에 대한 검토이며 새 데이터 유형에 대한 포괄 승인이 아닙니다.

## 5. 실패·동시 실행·승인 변경

- 해시/원본/단위/월/항등식 실패: 기존 data/live 보존. 원문을 로그에 출력하지 않고 고정 오류 분류만 확인합니다.
- 원장이 바뀜: 초기/명시적 정정 영수증은 새로 생성합니다. 일반 반복 갱신은 CAS 재시도에서 최신 원장으로 비교/staging을 다시 수행합니다. 새 충돌이 정정이 되면 중단합니다.
- 동일 데이터: collector/Store.commit/Pages를 생략합니다. 다른 정기 수집 job의 동작은 바꾸지 않습니다.
- 정상 코드/데이터 저장 뒤 Pages만 실패: 이미 저장한 검증값을 삭제하지 않습니다. 기존 `Deploy latest code with durable data` 수동 실행으로 최신 snapshot을 재투영하고 guard 후 배포합니다. 저장과 배포 상태를 각각 확인합니다.
- 게시 승인 만료/철회: source·기간·근거를 별도 설정 PR에서 변경하고 일반 배포의 policy 재투영으로 기존 공개 금액도 차단합니다. 원장/정정 이력은 보존합니다.
- 기관 이용조건 철회/변경: `rights_evidence`를 검토 상태로 바꾸고 collection/publication 범위를 재검토합니다. 기존 공개 투영에도 기관 이용조건 검사를 적용하므로, 재투영 시 금액 공개가 차단됩니다.
- 비영리/무료/무광고 조건 변경: 즉시 해당 권한과 공개를 재검토합니다. 기관 회신을 새 운영 승인으로 해석하지 않습니다.
- private 서명/권한 오류: API 응답·토큰·계정 정보를 로그로 보내지 마십시오. owner와 검증된 서명, Contents read/Actions read, 정확한 private repo와 root 파일 구성을 확인합니다.

## 6. 게시 후 확인 목록

실제 최종 승인 후에만 확인합니다. 이 PR에서는 실데이터를 배포하지 않았습니다.

- 저장된 Macro 원장의 기존 관측과 정정 이력이 유지됐는가?
- 새 월은 수입/지출 2개 관측값으로 추가되고 수지는 공식 값과 일치하는가?
- Overview/Macro의 기준월·백만 US$·출처·원문 링크·확인일이 맞는가?
- 수지는 음수를 유지하고 절대 증감액으로 표시하는가?
- PC·모바일 차트/기존 방한·출국·국적별 통계가 유지되는가?
- News/Research/브리핑/Market Weather가 그대로인가?
- private 원본/입력 원장/영수증/manifest가 public artifact나 Pages에 없는가?
- 다음 일일 실행에서 TOURGO manual_update_pending과 마지막 검증값/성공 시각이 유지되는가?

[설계와 조사 근거](ARCHITECTURE.md) · [검증 범위](VALIDATION.md).
