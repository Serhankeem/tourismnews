# Macro Monitor v0.6 — ECOS 관광수입·관광지출 연동 준비

2026-11-05 확인. 기준 main: `8728c169281b9ec4e7741e4afcbafffd28723e54` (PR #23 병합).
브랜치: `feat/macro-ecos-financial-v06`.

**관광수입·지출 실연동은 아직 완료되지 않았다.** 현재 실행 환경에 `ECOS_API_KEY`가 없어
일반여행의 공식 표·항목·단위 및 실제 월별 수치를 검증하지 못했다. 검증되지 않은 코드를
설정하지 않았으며, 수입·지출은 기존대로 disabled / 미연동이다. 아래 구현과 fixture 통과를
실측 통계 확보로 계산하지 않는다. main 병합, data/live 쓰기, Pages 배포는 수행하지 않았다.

## 1. 완료 판정과 실제 확보량

| 단계 | 판정 | 근거 / 남은 조건 |
| --- | --- | --- |
| A. 일반여행 API 코드 검증 | 미완료 | 공통 API 명세는 확인. 일반여행 표·수입/지급 항목·계층·단위·수록 기간은 인증 조회로 확인 필요 |
| B. 실수집 | 미완료 · **0건 / 0개월** | 인증된 ECOS 일반여행 `StatisticSearch` 요청 0회. 최신 기준월·수입·지출·수지 값 모두 미확인 |
| C. 공개 준비 | 미완료 | 실제 응답, 통계정보 이용지침/계열 조건, KTO 동일 월·단위·공표 시점 교차검증 필요 |
| D. 운영 연동 | 미수행 | 이번 작업에서 금지. 병합 후 data/live 저장·Pages 게시의 별도 검증 필요 |

| 구분 | 이번 검증 결과 | 성과에 포함하는 범위 |
| --- | --- | --- |
| ECOS 공식 안내 / robots | HTTPS 200, robots 접근 허용 | 공식 서비스 접근 가능성 |
| 명세의 공개 샘플 | `StatisticTableList/sample/json/kr/1/10/102Y004` → JSON 1행 | **본원통화** 목록 예제. 관광수지 실측값 0건 |
| ECOS 관광수입 / 지출 실측 | 0 / 0 | 최신 월·금액·원본 단위 미확인 |
| 기존 KTO 입·출국 / 국적 통계 | 공식 XLSX 실제 다운로드 검증, **7계열 × 69개월 = 483건** | 기존 관광수요 회귀 검증. 신규 금융 지표 성과 아님 |
| 합성 금융 fixture | 기본 2계열 × 13개월 = 26개 인공 관측값 | 파서·원장·UI 테스트 전용. 변형 fixture 포함 총 테스트 수와도 별개 |

네트워크 허용 정책은 unrestricted/enforced였고 ECOS 공식 HTTPS 안내 및 공개 예제는
정상 응답했다. 따라서 환경 전체의 네트워크 차단으로 보고하지 않는다. 현재 차단점은
실행 환경의 인증키 부재와 미검증 계열 매핑이다. GitHub Secret **이름만** 조회하려 했으나
HTTP 403 `Resource not accessible by integration`으로 거절되어 저장소의 등록 여부는 미확인이다.
Secret 값을 읽거나 인증을 우회하지 않았다. 접근 증거는 [source-access.json](source-access.json).

## 2. 공식 경로·정의·공표 상태

공식 ECOS [개발 명세서](https://ecos.bok.or.kr/api/#/DevGuide/DevSpeciflcation)의 정상 브라우저 UI에서
다음 서비스를 확인했다. 비공개 웹 API를 직접 호출하지 않았다.

| 서비스 | 확인한 항목 | 이번 일반여행 실증 |
| --- | --- | --- |
| `StatisticTableList` | 표 코드·이름, 상위 표, 주기, 검색 가능 여부, 작성 기관 | 일반여행 표 코드 미확인 |
| `StatisticItemList` | 그룹, 항목 코드·이름, 상위 항목, 주기, 수록 시작/종료, 단위 | 일반여행 항목 코드·전체 경로·원본 단위 미확인 |
| `StatisticSearch` | 항목 1~4, 단위, 시점, 문자열 DATA_VALUE | 일반여행 실인증 호출 없음 |
| `StatisticMeta` | 통계메타DB 검색과 설명 필드 | 서비스 명세 확인. 특정 일반여행 계열의 설명 응답 미확보 |

코드 검색 공개 UI도 열었으나 일반여행의 전체 매핑을 재현 가능한 증거로 확보하지 못했다.
`102Y004`는 문서에 공개된 **본원통화** 예제일 뿐 일반여행 설정에 사용하지 않는다.
테스트의 `999Y999`와 `GR`/`GP` 등은 **인공 식별자**이며 실제 코드가 아니다.

정의는 다음과 같이 유지한다.

- `kto_tourism_receipts`: 관광수입 = **일반여행수입**.
- `kto_tourism_expenditure`: 관광지출 = **일반여행지급**.
- 관광수지 = 일반여행수입 − 일반여행지급. 이번 공개 카드에 추가하지 않는다.
- 유학연수를 포함하는 `bok_travel_credit` / `bok_travel_debit` 전체 여행 항목은 비활성 유지.

KTO [공식 관광수지 안내](https://datalab.visitkorea.or.kr/datalab/portal/ts/getKorTursmBalcForm.do)는
HTTPS 200이며, 일반여행만 관광수치로 제공한다고 설명한다. 페이지는 2025·2026년을 잠정치로
안내하지만 이를 ECOS 개별 응답의 확정 상태로 전용하지 않았다. ECOS 명세의 DATA_VALUE
응답에는 공표일·개별 최종 확정 여부가 없으므로 기본 `not_stated`, 공표일 null로 보존한다.
API를 조회한 날이나 오래된 기준월이라는 이유로 공표일·확정치를 만들지 않는다.

기존 KTO 방문객 자료의 이번 확인 기준월은 **2026-09**, 공표문 시각은
**2026-10-28 10:10 KST**다. 2021-01~2026-09의 483개 관측값은 별도 임시 경로에서 검증했으며
운영 원장을 다시 쓰지 않았다. 이 기준월을 미확보 금융 지표의 최신 월로 표시하지 않는다.

## 3. 이용조건과 교차검증

ECOS 공식 페이지 하단의 **경제통계 Open API 이용약관**을 정상 UI로 확인했다.

- 제2조: ECOS의 통계데이터·설명자료 활용과 재가공 배포 이용자를 규정.
- 제4조: 약관 동의 등 요건을 갖춰 인증키 신청, 키 관리, 기본 이용기간 2년과 연장.
- 제5조: 통계정보 상업적 이용이 가능하되 작성기관이 제한한 통계는 해당 승인 필요.
- 제6조: 과다 호출·접근 범위 위반·키 양도 등의 제한.
- 제7조: ECOS 제공 정보임을 표시하고 ECOS의 통계정보 이용지침도 준수.

일반 API 제공 취지를 특정 미확인 계열의 권리 검증 완료로 처리하지 않았다.
`rights_review.status=review`를 유지한다. 사용자 대신 약관 동의·신청을 제출하지 않았다.

KTO의 2026-09 한국관광통계 공표문과 공식 제공 XLSX 2개는 정상 다운로드됐다.
그 게시물의 KOGL 0과 파일의 입·출국 / 국적별 수치를 검증했다. 이 파일들은 방문객 통계이며
관광수입·지출 대조표가 없으므로 **금융 수치 교차검증 완료가 아니다**.

KTO 관광수지 페이지에는 공식 다운로드 버튼과 다운로드 외 수집 금지 안내가 있다.
자료별 이용·다운로드 조건 및 실제 파일을 확인하기 전 CSV나 내부 조회 API를 호출하지 않았다.
공통 메타데이터 모달의 KOGL 표시를 별도 다운로드 파일 승인으로 간주하지 않았다.
TOURGO 페이지·기존 승인 대기 XLS는 다운로드·읽기·게시하지 않았다.

`ecos.crosscheck()`는 운영자가 정식으로 확보하고 검증한 KTO 원문 근거에 대해 동일 월·동일
US$ 단위로 수입/지급 각각을 비교한다. 차이는 공표 시점/정정 차이 가능성을 기록하며 자동으로
같게 맞추지 않는다. 허용 오차를 전달하면 US$ 기준 오차도 결과에 기록한다.
**이번 교차검증은 합성 fixture로만 통과했으며 실자료 결과는 없다.**

## 4. 기존 구조와 최소 통합

기존 Macro 원장 `collector_state/macro_archive.json`은 indicator별 observations(월 → 정수 값)와
revisions(이전/이후 값), source별 확인 이력을 보존한다. `public_view()`가 `site/data/macro.json`을
만들고 `macro.js`가 홈과 관광지표 페이지를 함께 표시한다. 정수 인원 규칙을 금액의 소수점에
그대로 적용하지 않도록 ECOS 전용 모듈을 분리했다.

- **`src/macro/ecos.py`**: 공개 API 전용 HTTPS 클라이언트, 메타데이터·전체 항목 계층·월간 주기·수입/지급 방향의 이중 검증, 월별 정규화, 정확한 단위 변환, 비공개 사전검증 CLI.
- **`engine.py`**: `method`로 기존 `kto.fetch()`와 ECOS를 분기. KTO 파서/전송 코드는 변경하지 않음.
- **`model.py`**: 금융성 지표의 비교만 `exact=True`로 Decimal 계산. 기존 인원 지표 계산 결과 유지.
- **`macro_sources.json`**: 기존 ECOS 후보에 비활성 어댑터와 `pending_verification` 매핑·권리·교차검증 상태 추가. 표·단위는 null, 항목은 빈 설정. 기존 지표 정의·단위·enabled는 그대로.
- **`macro.js`**: 승인 후 검증된 금융 payload가 들어오는 경우에만 카드·축·툴팁 단위 전환. 현재는 미연동 유지.
- **`report.py`**: Actions 운영 요약에 source별 상세 collection_state 병기.

뉴스·리서치 공개 6/8필드, PR #23 한국어 표시/검색, 해시 라우팅, UI #22, 통계 승인 게이트,
운영 데이터 허용 목록, 스케줄·GitHub Actions는 변경하지 않았다.

## 5. 정확한 단위·날짜·정정 모델

**실제 ECOS 일반여행 원본 단위는 아직 미확인**이다. 코드는 공식 메타데이터의 UNIT_NAME과
검토된 설정의 unit_name이 정확히 일치해야만 처리한다. 테스트에서 쓰는 백만달러를 실제
단위라고 주장하지 않는다. 지원 변환은 수학적 단위 대응일 뿐 특정 계열의 단위 확정이 아니다.

| 항목 | 처리 |
| --- | --- |
| 저장 값 | 정수 **US$**, 비음수 수입/지급만. 원장 정수 제약 유지 |
| 원본 보존 | DATA_VALUE 문자열·UNIT_NAME·표 코드/명·항목 코드/명·응답 SHA-256 |
| 변환 | Decimal × 1 / 1,000 / 1,000,000. US$ 미만 잔여 또는 JS 안전 정수 범위 초과는 반올림하지 않고 거절 |
| 화면 | 백만 US$, 원장 US$ 별도 표기. 카드/툴팁은 정수 문자열 분할로 US$ 마지막 자리까지 정확히 표시 |
| 차트 축 | 금융: 백만 US$; 인원: 만 명; 증감률: %. 한 차트는 선택 지표 한 단위만 표시 |
| 비교 | 전월·전년 같은 월, 누락/0 분모는 null. 금융 비율은 Decimal 반올림 후 숫자로 전달 |
| 연초 누적 | 해당 연도 1월~기준월이 모두 있어야 함. 안전 정수 범위를 벗어난 금융 누적값도 null |
| 미공표/결측 | 조회 범위의 빠진 월은 별도 기록, 0·보간값으로 채우지 않음 |
| 최초/최근 확인 | first_collected_at 유지, 검증 재조회 시 last_collected_at 갱신 |
| 원 공표일 | API에 없으면 null. 확인일과 분리 |
| 정정 | 같은 월의 값 변경은 before/after와 탐지시각을 revisions에 추가, 최초 수집일 보존 |
| 이전 월 누락/실패 | 기존 검증 레코드 전체 유지. 누락/실패 이유 별도 기록 |
| 수지 | 별도 내부 signed 계산만 지원. 수입/지급 관측값의 음수 불가 규칙 유지, 수지 퍼센트 해석 없음 |

공개 뷰는 현재 권리·매핑·교차검증 승인을 다시 확인하고, 원장 각 레코드의 표/항목/단위/
원본 값 변환·검증 표시도 재검증한다. 승인이 보류되거나 저장 provenance가 잘못된 경우 원장은
보존하고 공개 대상에서 제외한다. 신규 수집 성공 여부만으로 이전 레코드를 자동 게시하지 않는다.

## 6. 인증·오류·갱신 상태

기존 `pipeline.yml`의 `ECOS_API_KEY: ${{ secrets.ECOS_API_KEY }}` 전달 구조를 그대로 쓴다.
별도 인증 시스템이나 클라이언트 API 호출은 없다. 원본 key URL·provider MESSAGE·예외 traceback을
로그/JSON에 저장하지 않고 고정된 오류 ID만 기록한다. 성공 응답에 키가 반사되어도 저장 거절한다.

- HTTPS ECOS `/api/`의 명시적 3개 서비스만 호출. robots 확인, 리디렉션 전부 거절.
- 기본 호출 간격 1초 이상 및 robots 지연 준수. 5xx 중 502/503/504만 최대 1회 재시도.
- 인증 오류·403·429·API 과다 호출(ERROR-602)은 재시도하지 않음. 최대 5,000행, 응답 크기 제한,
  페이지 총수/행수 검증. sample 키는 production client에서 거절.
- 매일 기존 Macro 12:20 KST 일정과 source의 같은 KST 날짜 재조회 방지 유지.
  미래 월 차단, 2021-01 이후 수록/공표된 범위만 재조회할 준비. 실제 시작/종료는 API 확인 필요.
- 원장은 복사본에서 검증 후 기존 atomic write 사용. 손상된 원장을 공개 JSON만으로 재생성하지 않음.
- ECOS 실패와 KTO 성공을 분리. 카드도 다른 source의 실패를 정상 KTO에 전파하지 않음.

기존 `status`는 유지하고 ECOS source에 상세 `collection_state`를 추가한다.

| 상세 상태 | 의미 |
| --- | --- |
| `not_configured` | 소스 비활성/운영 활성화 전 |
| `authentication_required` | 현재 키 미설정 또는 인증 실패. 성공 건수에 포함하지 않음 |
| `mapping_pending` | 공식 코드 검증 전. API 데이터 수집 안 함 |
| `not_due` | 같은 KST 일자에 이미 정상 확인 |
| `new_data` | 검증된 신규 관측값/정정/상태 변경 확보 |
| `no_new_data` | 정상 재조회했으나 신규·정정 없음 |
| `partial_missing` | 일부 월 미수신. 이전 값 유지, 빠진 월 별도 기록 |
| `no_data` | 해당 조회의 실수치가 없어 수집 미완료. 이전 검증값 유지 |
| `failed_retained` | 네트워크·구조·단위 등 오류. 기존 데이터 보존 |

`status=not_connected` 후보는 정상 source 성공 건수에 포함하지 않는다. 전체 실패로 표시하는
경우와 한 source만 실패한 partial은 구분한다. 현재 실검증은 KTO ok, ECOS not_connected다.

## 7. 보존 검증과 파이프라인

읽기 전용 운영 참조: `37a2c4c911f5337c62db49a3010d9a219d718ee5`.
동일 스냅샷·동일 시각으로 main/수정 코드의 기존 정책 투영과 Pages 로컬 조합을 비교했다.

- 운영 공개/비공개 JSON **30개 전후 SHA-256 동일**, 운영 JSON 수정 파일 0개.
- Newsroom 63건, Research 135건, 기존 Macro 7계열 483개 관측값·정정 이력 보존.
- HNR 보류 3건 원장 보존, 공개 0건. 확정 브리핑·뉴스 ID/발행일/URL·권리 이력 보존.
- `kto.py`, `transport.py`, TOURGO `balance.py` / `balance_prepare.py` 불변.
- `market-observation.js`, Scenario Lab 입력·계산식·점수/경계·SVG 모션 불변.
- 모든 workflow, `pipeline.json`, PR #19 runner/store/검증·allowlist·복구 구조 불변.
- Python 회귀에서 data/live 로컬 bare 저장소 복원·동시성·데이터 손상·PR 배포 차단도 검사.
- 원격 main/data/live push, 운영 workflow_dispatch, Pages 업로드/배포 없음.

[전체 보존 수치와 파일 해시](preservation.json).

## 8. 테스트와 화면

로컬 최종 결과: **Python 370개 통과(기존 333 + 신규 37), 브라우저 19개 스위트 통과(기존 18 + 신규 1)**. 상세 결과는 [tests.json](tests.json)에 기록한다. 테스트용 금융 데이터는 tests 파일과
임시 브라우저 메모리에서만 사용한다. **실측 금융 통계 0건과 혼합하지 않는다.**

- Python: 기존 전체 회귀 + 인증 부재/오류·표/계층/방향·일반/전체 혼동·단위·소수점·미래/중복 월·
  0/결측·정정·재실행·정밀도·복구·7개 실제 방문객 계열 보존·기존 공개 게이트·비공개 출력 테스트.
- 브라우저: 기존 18개 스위트 + 금융 UI 1개. 320/390/768/1440px, 홈/Macro 공통 표시, 개별 기준월,
  금액 축/툴팁, US$ 정수 경계값의 정확한 표시, 부분 실패/이전값 보존, PR #22·23 회귀.
- GitHub CI: PR 검사만 실행. PR 컨텍스트의 collect-and-publish는 skip되어야 함.
  CI의 Python 통과를 인증된 ECOS 수집 또는 실제 배포 통과라고 보고하지 않는다.

실제 데이터 스냅샷의 금융 카드는 미연동이다:

| 화면 | PC | 모바일 |
| --- | --- | --- |
| 홈 · 실제 스냅샷 | [1440px](screenshots/real-home-1440.png) | [390px](screenshots/real-home-390.png) |
| Macro · 실제 스냅샷 | [1440px](screenshots/real-macro-1440.png) | [390px](screenshots/real-macro-390.png) |
| **합성 금융 UI 검증 전용** · 노란 경고 표시 | [1440px](screenshots/synthetic-ui-only-macro-1440.png) | [390px](screenshots/synthetic-ui-only-macro-390.png) |

마지막 행은 운영 연결 화면이 아니다. 인공 응답을 브라우저에서 가로채 화면 표시만 검증했다.

## 9. 사용자 작업과 운영 전환 순서

1. [ECOS Open API](https://ecos.bok.or.kr/api/)의 **인증키 신청 → 약관동의 → 정보입력 → 신청완료**를
   사용자 명의로 진행한다. 홈페이지 서비스 이용 목적과 현행 통계정보 이용지침을 확인한다.
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 이름을
   정확히 **`ECOS_API_KEY`**로 등록한다. 기존 항목이 있으면 등록 여부/유효기간을 확인한다.
   키는 채팅·PR·코드·명령행 URL·브라우저·공개 JSON에 넣지 않는다.
3. **GitHub Secret 등록만으로 이 PR의 실증이 완료되지는 않는다.** PR test에는 Secret을 전달하지
   않는다. 병합 전 실증을 원하면 관리형 개발 환경의 안전한 Secret 연결로 동일 환경변수를
   제공해야 한다. 현재 환경 바인딩은 없음. 키를 GitHub에서 읽어 가져오지 않는다.
4. 안전하게 키가 주입된 환경에서 아래 private preflight로 공식 메타데이터를 받는다.

   ```sh
   python -m src.macro.ecos metadata --private-dir /tmp/currentourism-ecos-private
   # 공식 목록에서 실제 표를 확인한 뒤에만 실행 (실제 코드로 교체):
   python -m src.macro.ecos metadata --table-code OFFICIAL_CODE --private-dir /tmp/currentourism-ecos-private
   ```

   `OFFICIAL_CODE`는 실행 가능한 실제 코드가 아닌 자리 표시자다. 형식/코드를 추측하지 않는다.
   출력은 저장소 밖 mode 0600 파일이고 stdout에는 성공 여부만 남는다.
5. 공식 표명·일반여행 수입/지급 전체 항목 계층·선택 차원·주기 M·원본 단위·수록 기간을 확인한다.
   `mapping`을 근거와 함께 검토하고, 금융 지표의 저장 unit을 `US$`, value_kind를
   `money_nonnegative`로 설정하고, 검증된 정의·미연동 사유·출처표시도 정리한 뒤 **비활성 상태에서** private validation을 수행할 수 있다.

   ```sh
   python -m src.macro.ecos validate --private-dir /tmp/currentourism-ecos-private
   ```

6. 실제 자료 수·최신 월·원 단위/금액·결측·정정 상태를 기록하고 KTO 공식 제공 자료를 동일 월/
   단위로 교차검증한다. 다른 공표 시점의 차이는 원인을 확인한다. 이용조건도 확인한 뒤에만
   `rights_review` / `crosscheck`를 verified로 변경하는 승인 PR을 준비한다. 테스트 통과만으로
   이 플래그를 바꾸지 않는다. 자동 KTO 금융 다운로드·자동 crosscheck 승인 기능은 이번에 없음.
7. 사용자 코드 검토 후 수입·지급 및 ECOS source의 enabled를 활성화한다. 기존 전체 회귀 통과 후
   사용자가 main 병합 여부를 결정한다. Secret만 넣어도 현재 disabled 소스가 자동 활성화되지는 않는다.
8. 병합 이후 승인된 운영 실행에서 data/live 저장, macro.json 실제 금액·단위·기준월과 Pages 화면,
   실패 시 보존·다음 재조회·정정 반영을 확인한 뒤에만 **D 운영 연동 완료**로 표시한다.

이번 에이전트는 1~3의 사용자 인증/신청, 5~7의 미확인 코드 승인/활성화, 8의 운영 실행을 대신
수행하지 않았다. 준비 코드는 검토할 수 있지만 **필수 목표인 실제 관광수입·지출 확보는 남아 있다.**

## 10. PR #25 인터페이스 제안 (이번 PR에서는 미연결)

Market Observation은 기존 `MacroMonitor.database`의 읽기 전용 객체를 사용한다.
추후 `kto_tourism_receipts` / `kto_tourism_expenditure` 중 `connected`,
`verification_status=official_api_validated`, unit `US$`, 최신 period와 출처가 검증된 계열만 별도
**관광경제 관측** 카드/단일 단위 차트로 받을 수 있다. 방한객과 다른 기준월을 별도로 표시하고
상호간 결측을 채우지 않는다. 이를 Scenario Lab의 입력·가중치에 연결하지 않는다.
금액 증가율만으로 시장 호황이나 종합 날씨를 판정하는 기능은 제안 범위에도 포함하지 않는다.

## GitHub CI 최종 기록

[PR #24](https://github.com/Serhankeem/tourismnews/pull/24), 기능 커밋 `738ae4e2928242ab08788b40eaa3ac35f5640650`: **3개 test job 모두 SUCCESS**.

- [Macro Monitor official statistics](https://github.com/Serhankeem/tourismnews/actions/runs/41992999378/job/127129446991): 통과.
- [Research Library weekly collector](https://github.com/Serhankeem/tourismnews/actions/runs/41992999728/job/127129447942): 통과.
- [Tourism Pulse RSS collector](https://github.com/Serhankeem/tourismnews/actions/runs/41992999546/job/127129447234): 통과.

3개 `collect-and-publish`는 모두 SKIPPED. 실제 ECOS 금융 API 호출·운영 저장·Pages 배포 검증을 뜻하지 않는다. 후속 문서 커밋은 이 결과만 기록하며 코드·테스트 변경이 없다.
