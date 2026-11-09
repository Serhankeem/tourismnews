# TOURGO Macro Monitor Integration v1.0 — PR #37

**통합 준비 완료, 운영 활성화는 보류.** 기준 main은 PR #36 병합 커밋 `6e97cf30c12591a4be1ca4cb35a206e58f20fe42`이며 브랜치는 `feat/tourgo-macro-integration-v1`입니다.

## 구현과 호환성

| 파일 | 역할 |
| --- | --- |
| `src/macro/tourgo.py` | 기존 `balance.py` 파서·원장·항등식·승인·비교 함수 재사용, XLS/비공개 원장 해시 검사, 정확한 US$ 매핑, 보관 자료의 공개 재검증 |
| `src/macro/tourgo_preview.py` | 공식 파일 또는 검증 원장을 명시적으로 입력받는 오프라인 격리 미리보기 CLI |
| `src/macro/engine.py` | 선택한 출처만 수동 통합, 정정/누락/실패 보존, ECOS와의 혼입 차단, 출처별 공개 게이트 |
| `macro_sources.json` | TOURGO 수동 파일 방식과 이용조건 확인 근거 문서화. enabled/collection/publication은 계속 false |
| `site/macro.js` | TOURGO 전용 검증, 기존 수입·지출 KPI/차트/홈 연동 준비, 공식 원본과 일치하는 관광수지·절대 증감액 |
| `site/index.html` | 비상업 정책과 Data Sources에 이용조건 확인 및 운영 미연동 상태를 구분해 설명 |
| `tests/test_macro_tourgo.py` | 신규 Python 검증 18개 및 반례 |
| `tests/macro-tourgo.smoke.cjs` | 어댑터가 생성한 합성 출력의 브라우저 검증, 기본 미연동 화면, 모바일·보존 검증 |

기존 `kto_tourism_receipts` / `kto_tourism_expenditure` ID를 재사용합니다. 체크인 설정의 두 지표는 기존 ECOS source_id와 disabled 상태를 유지합니다. `tourgo.select_source(config)`는 복사본에서만 두 ID를 TOURGO로 전환하고 ECOS 경로를 끄며, 지표 활성화나 승인 부여를 하지 않습니다. 기존 ECOS archive가 존재하면 자동 전환·덮어쓰기 대신 `financial_source_change_requires_review`로 중단합니다. TOURGO→ECOS 전환도 같은 원칙입니다.

현재 공개 JSON 스키마는 유지됩니다. 향후 TOURGO 두 지표가 모두 승인되어 검증된 경우에만 `tourism_balance` 객체를 추가합니다. 그 객체는 공식 수지와 차감 계산의 일치 여부, 원장 US$, 기간별 절대 변화, 비율 미적용 정책을 포함합니다. 음수 수지를 기존 비음수 관측 배열에 넣지 않습니다.

## 정의와 단위

- 원문: [한국문화관광연구원 관광지식정보시스템(TOURGO) 한국관광수지](https://know.tour.go.kr/stat/koreaTourIncomeDis19Re.do).
- 2026-11-09 공식 페이지 HTTPS **HTTP 200** 확인. 페이지의 “관광수지의 원자료는 한국은행 일반여행수지” 및 “관광수입, 관광지출, 관광수지 단위는 1,000 US$” 안내를 확인했습니다.
- 관광수입은 일반여행수입, 관광지출은 일반여행지급으로 연결하며 유학연수를 포함한 전체 국제수지 여행수입·지급과 구분합니다. 기존 KTO 정의 참조도 유지합니다.
- 원본·비공개 원장: 정수 **천 US$**. Macro 원장: 원본 × 1,000의 정수 **US$**. 화면: 원장 ÷ 1,000,000의 **백만 US$**. 예시 변환 `2,460,800천 US$ → 2,460,800,000 US$ → 2,460.8백만 US$`를 검증합니다.
- 정수 안전 범위·유한값·음수 수입/지출 거부·음수 수지 허용을 검사합니다. 원본 파서의 더 엄격한 금액 범위도 유지합니다. 기존 Decimal 비교·소수점 표시·Percentage UI는 그대로입니다.
- 관광수지는 수입−지출과 공식 수지 원본이 일치해야 합니다. 전월·전년 동월 **절대 금액**만 비교하고 백분율은 생성·표시하지 않습니다. 비교월이 없으면 `—`입니다.
- XLS에 공표일·확정 플래그가 없으면 `release_published_at=null`, `finality=not_stated`입니다. 확인 시각을 공표일로 바꾸지 않습니다. 공식 웹페이지에는 2023년 잠정치 안내가 있지만 이를 다른 기준월·다운로드 빈티지의 확정 여부로 확대 해석하지 않았습니다. 향후 빈티지별 공표 상태 검토가 필요합니다. 수지 원본의 상태도 수입의 상태와 별도로 보존합니다.
- 방한객과 관광수지의 기준월은 각각 표시합니다. 1인당 금액은 이번에 계산하지 않습니다.

## 승인과 입력 신뢰 경계

2026-11-09 담당 기관 회신에 따라 **비상업적 목적·TOURGO 출처 명시** 조건에서 수치의 외부 게시, 시계열/증감률 가공, 정기 자동 수집이 가능하다는 이용조건을 기록했습니다. 공개 저장소에는 회신 요지만 두고 개인 연락처·이메일 전문은 보관하지 않습니다. 여행기류는 TOURGO의 공식 운영·제휴 서비스가 아닙니다. 이 확인은 ECOS API 이용 승인과 별개입니다.

이용조건 확인과 운영 활성화 승인은 분리했습니다. 체크인 `enabled=false`, `approval.collection.approved=false`, `approval.publication.approved=false`, 기존 유효일·근거 값은 그대로입니다. `enabled`만 켜거나 `requires_approval`을 제거해도 통과할 수 없습니다. 원장에 이미 있는 자료에도 현재의 publication 승인과 TOURGO 전용 provenance/단위/항등식 검사를 적용합니다.

공식성은 `data_origin` 문자열이나 수치 일치만으로 증명되지 않습니다. 입력 운영자는 공식 다운로드에서 선택한 지표 역할과 원본 해시를 독립적으로 검토해야 합니다. 원본 입력은 검토된 3개 SHA-256과 파싱 전후 바이트를 대조합니다. 비공개 원장 입력은 독립 검증한 원장 파일 해시를 필수로 받고 내부의 원본 해시·공식 출처·기간·단위·정정 기록을 재검증합니다. 임의 생성 원장을 official로 변경하거나 해시를 붙여 승격하는 절차는 제공하지 않습니다.

`synthetic_test` 및 공식/합성 혼합은 공개·Preview 입력에서 차단합니다. 자동 테스트의 공식 형태 fixture는 합성임을 테스트 파일에 명시하고 임시 디렉터리/브라우저 메모리에서만 사용합니다. 공개 출력은 허용 목록의 필드만 내보내 비공개 주석 등이 섞이지 않도록 합니다.

## 실제 원본 검증 범위

PR #36의 **2021-01~2026-09, 69개월** 원본 3개는 이 실행 환경에서 찾지 못했습니다. PR #36의 결과를 이번 신규 매핑 경로의 69개월 검증으로 재사용하지 않습니다.

대신 이전 작업공간에 남아 있던 **2021-01~2026-08, 68개월** 공식 XLS 3개와 같은 기간의 비공개 검증 원장을 발견했습니다. 그 자료를 별도로 사용했습니다.

| 검증 | 결과 |
| --- | --- |
| `xlrd==2.0.2` 실제 XLS 읽기 | 3/3 |
| 기존 비공개 원장의 원본 해시와 XLS 대조 | 3/3 일치 |
| XLS 재파싱 값과 기존 비공개 원장 대조 | 3계열 × 68개월 일치 |
| 새 어댑터→Macro 공개 변환의 수지 항등식 | 68/68 일치, 저장소 밖 격리 출력 |
| 실제 XLS 입력 CLI / 비공개 원장 입력 CLI | 각각 통과 |
| PR #36의 지정 해시·2026-09 포함 69개월 | **미실시: 해당 원본 미보유** |

[금액을 제외한 실데이터 검증 요약](official-validation-summary.json). 실제 원본·비공개 원장·실제 금액을 담은 Preview JSON/스크린샷은 커밋하지 않았습니다. 원본 3개가 확보되면 동일 CLI로 69개월 신규 매핑과 정정 검증을 다시 수행해야 합니다.

## 명시적인 수동 검증 명령

신뢰한 Python 환경에 `xlrd==2.0.2`를 설치합니다. 원본과 검증용 해시 목록은 저장소 밖에 둡니다. `hashes.json`은 검토한 원본의 `receipts`, `expenditure`, `balance`별 SHA-256을 가진 JSON 객체입니다. 출력은 **새 디렉터리**만 허용합니다.

```bash
python -m src.macro.tourgo_preview \
  --receipts /private/originals/receipts.xls \
  --expenditure /private/originals/expenditure.xls \
  --balance /private/originals/balance.xls \
  --hash-manifest /private/reviewed/hashes.json \
  --baseline-root /private/current-live-snapshot \
  --output /private/tourgo-preview-v1
```

`baseline-root`는 `site/data`와 `collector_state/macro_archive.json`을 가진 읽기 전용 로컬 스냅샷입니다. 생략하면 현재 checkout의 자료를 사용하므로 실제 최신 운영 스냅샷인지 별도 확인합니다. 기존 KTO 자료는 복사하여 보존하고 수집기를 호출하지 않습니다.

```bash
python -m src.macro.tourgo_preview \
  --ledger /private/validated/tourgo_balance_private.json \
  --ledger-sha256 '<independently-reviewed-ledger-sha256>' \
  --baseline-root /private/current-live-snapshot \
  --output /private/tourgo-ledger-preview-v1
```

Preview는 저장소 밖 새 디렉터리에만 생성됩니다. `site/`에는 “격리 미리보기 · 운영 게시 아님” 표시가 있고 `private/`에는 통합 원장이 있으며 최상단 `preview.json`에 격리 상태를 기록합니다. 임시 승인 설정은 메모리 안에서만 사용합니다. checkout·기존 파일·설정·Git ref를 바꾸거나 서버·업로드·배포를 자동 실행하지 않습니다. 사이트를 로컬에서 확인할 때도 출력 최상위나 `private/`가 아닌 **`site/`만** 제공해야 합니다. 기존 Actions는 이 디렉터리를 읽지 않습니다.

정정 파일은 기존 `balance_prepare`의 비공개 원장 병합을 거쳐 새 해시를 검토하고 다시 입력할 수 있습니다. 오래된 기준월 스냅샷은 거부하며, 빠진 과거 월은 이전 검증값으로 유지하고 상태를 기록합니다. 검증 실패 시 기존 공개 자료·원장 파일은 유지됩니다.

## 회귀 검증과 증빙

- Python 전체 **502개 통과**, 신규 TOURGO 18개 포함. 형식·단위·중복·기간·합계·항등식·해시·합성 혼입·음수·누락·정정·승인·출처 전환·오류 비노출·공개 필드 허용 목록을 검증했습니다. 기존 `balance.py` 테스트도 유지합니다.
- 브라우저 전체 **21개 스위트 통과**. 신규 스위트는 320/390/768/1440px에서 단위·소수점·음수 수지·절대 변화·증감률 색상·결측·공식 링크·미연동 기본 화면·모바일 넘침·잘못된 provenance 거부·기존 방문객/Scenario Lab 불변·외부 API 호출 없음 등을 확인합니다. [스위트별 결과](browser-results.json).
- 기본 운영 설정으로 같은 `data/live` 스냅샷을 main/변경 코드에 결합했을 때 **공개 JSON 12개와 원장 포함 총 30개 파일이 동일**합니다. [SHA-256 보존 검증](preservation.json).
- 기존 `balance.py`, ECOS·KTO 수집기, 비교 계산 모델, Percentage UI, 뉴스·리서치 설정, 정책, 파이프라인 설정, 9개 Actions workflow, 로고 원본은 그대로입니다. 운영 JSON·`data/live`를 변경하지 않았습니다.
- GitHub CI 최종 결과는 PR Checks에 제공합니다. PR에서는 기존 main 전용 조건에 따라 실제 수집·게시가 실행되지 않습니다.

| 화면 | PC 1440px | 모바일 390px |
| --- | --- | --- |
| 기본 운영 설정 · 관광수입/지출 미연동 | [보기](screenshots/default-unconnected-1440.png) | [보기](screenshots/default-unconnected-390.png) |
| 합성 데이터 UI 검증 · 실제 TOURGO 수치 아님 | [보기](screenshots/synthetic-tourgo-only-1440.png) | [보기](screenshots/synthetic-tourgo-only-390.png) |

자동 브라우저 검증은 Chromium 기준입니다. 실제 68개월 Preview는 저장소 밖에서만 생성했으며 위 공개 스크린샷에 사용하지 않았습니다.

## 운영 게시 전 남은 작업

1. PR #36 지정 해시와 일치하는 69개월 XLS 또는 그 원본으로 생성해 독립 검증한 비공개 원장을 안전하게 제공하고, 새 경로의 2026-09 포함 전체 재검증을 수행합니다.
2. 다운로드의 지표 선택 역할·공표 빈티지·잠정/확정 및 정정 상태를 검토합니다. 이용조건 확인 근거의 비공개 원본은 계속 별도로 보관합니다.
3. 사용자가 운영 활성화를 별도로 검토·승인한 뒤, source 선택·두 지표 활성화·collection/publication 승인 근거/유효기간을 별도 변경으로 적용합니다. 현재 PR의 기본 설정은 그대로 미연동입니다.
4. 기존 ECOS 금액 원장이 생긴 경우 보존·이관 정책을 별도로 검토합니다. 자동 혼합이나 삭제로 전환하지 않습니다.
5. 정기 자동 다운로드는 구현하지 않았습니다. 향후 공식 다운로드 경로·양식 변경 감시와 갱신 절차는 별도 개발 대상입니다. 이번 수동 XLS/원장 경로에는 API 키가 필요하지 않습니다.

main 자동 병합, 운영 수집 실행, Pages 배포는 하지 않습니다.
