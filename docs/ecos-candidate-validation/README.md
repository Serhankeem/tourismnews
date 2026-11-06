# ECOS 301Y013 / 301Y014 — 원천 선정·월별 수치 교차검증 준비

2026-11-06 KST. 기준 main `8ab39858bb03e145f1b07556feb1c3de278d1795`.
브랜치 `feat/ecos-candidate-crosscheck`.

**301Y013은 우선 검증 후보이며 운영 매핑 승인 상태가 아니다.**
이 PR은 Secret을 Actions 안에서만 사용하여 월별 값을 읽고 대조할 수 있는 별도 수동 작업을
준비한다. 개발 환경의 실제 StatisticSearch 호출 0회, 확보한 금융 실측값 0건이다.
새 workflow는 기본 브랜치에 파일이 있어야 실행할 수 있으므로 사용자 병합 전 실인증 검증은 하지 않는다.

## 1. 기존 Preflight의 성공과 검토 상태 구분

[사용자 검증 실행](https://github.com/Serhankeem/tourismnews/actions/runs/42165343790)은 사용자 제공
Summary 기준 verified_catalogue / inspection_complete, 전체 844표 중 월간 후보 6표 검사 완료,
일반여행 후보 2쌍, review_required다. GitHub job 결론 failure는 기존 코드의 단일 후보 쌍
선택 가드에 따른 것이다. **메타데이터 수집 실패라고 해석하지 않는다.**
기존 preflight와 assessment()/review_required 가드는 바이트 단위로 보존한다.

| 역할 | 통계표 | 확인할 공식 명칭 | 수입 Group1 | 지급 Group1 | 단위 |
| --- | --- | --- | --- | --- | --- |
| 우선 검증 | 301Y013 | 국제수지 | 2C1Y00 | 2C2Y00 | 백만달러 |
| 비교 | 301Y014 | 서비스무역세분류통계 | SDA200 | SDB200 | 백만달러 |

코드는 사용자가 실제 Preflight에서 확인한 후보 식별자다. 일반여행 전체 부모 계층과 수입/지급
방향, 주기 M, 원 단위, 수록 시작/종료는 **매 실행의 공식 metadata로 다시 검증**한다.
추가 Group2~4 등 선택 차원이 있으면 임의로 조합하지 않고 거절한다. 표명은 번호 접두사·공백을
제외한 공식 명칭을 검증하고 각 ItemList/Search 응답의 STAT_NAME도 대조한다. 이름/코드를 추정하지 않는다.

## 2. KTO 작성 기준·다운로드 조사

[공식 관광수지 안내](https://datalab.visitkorea.or.kr/datalab/portal/ts/getKorTursmBalcForm.do)에
국제수지 여행수지 중 **일반여행**을 관광수치로 제공한다는 정의가 있다. 유학연수 포함 전체
여행수입/지급과 구분한다. 이 정의 때문에 국제수지 표 301Y013을 먼저 검증하지만,
정의 문구만으로 KTO가 실제로 사용하는 코드와 월별 금액까지 일치한다고 확정하지 않는다.

이번 정상 브라우저 UI 검증에서 공식 다운로드 버튼은 **로그인 안내/로그인 화면**으로 연결됐다.
다운로드 이벤트는 없었고 공식 금융 파일을 확보하지 못했다. 공개 안내 HTML 접근 성공과 파일
이용·확보는 다르다. 제한 우회, 내부 조회 API 호출, 로그인 대행, TOURGO 자료 다운로드는 하지 않았다.
개별 공식 파일의 이용조건·원 단위·공표시점도 미검증이므로 **KTO 실측 교차검증은 미완료**다.
확인한 최소 접근 결과는 [evidence.json](evidence.json)에 기록했다. 원본 화면/응답/금액은 저장하지 않았다.

## 3. 수동 Actions 실행

사용자가 PR을 검토·병합한 후:

1. Actions → **ECOS Candidate Comparison** → Run workflow → **main**.
2. start_month / end_month는 선택적 `YYYY-MM`이다. 둘 다 비우면 네 계열 metadata의 공통 수록
   종료월과 현재 월 직전 월 중 이른 월까지 최근 최대 12개월(2021-01 이후)을 검증한다.
3. 예를 들어 확인하고 싶은 공식 기준월 하나만 있으면 시작·종료를 같은 월로 지정한다.
   명시 기간은 최대 24개월이며 미래/공통 수록 범위 밖은 거절한다.
4. Summary의 두 표 비교와 KTO 상태를 각각 확인한다. 비교가 끝나도 301Y013 적합성은 검토중이며
   source/운영 매핑을 승인하지 않는다.

`ECOS_API_KEY`는 기존 Repository Secret을 단일 실행 step에만 전달한다.
main-only, dispatch SHA checkout, contents:read, persist-credentials:false,
독립 concurrency, 15분 제한이다. schedule/PR trigger/운영 collector/pipeline/Pages 권한/배포/
artifact 업로드/Git push는 없다. 코드/날짜가 검증된 고정 두 후보만 공식 HTTPS API로 조회한다.
클라이언트의 기존 robots·리디렉션 차단·호출 간격·재시도·응답/페이지 상한을 재사용한다.

## 4. 정확한 수치 비교와 Summary

수입/지급을 각각 StatisticSearch로 요청한다. 원본 DATA_VALUE 문자열을 Decimal로 읽어
백만달러 단위로 정확히 비교한다. KTO 천 US$ 근거는 1,000으로 나눈다. 반올림·float·0 채움은 없다.
이번 읽기 전용 비교는 운영 원장의 정수 US$ 저장/수집 승인과 독립적이다.

Search 응답의 표·공식 명칭·항목 코드/명·불필요한 추가 차원·단위·월·수치 형식을 다시 검증한다.
미래/중복/범위 밖 월을 거절하고 결측은 missing으로 표시한다. 한 계열이 통째로 없으면 검증 실패다.

Summary에 공개하는 것은 고정 출처 링크·표 코드·검증 상태·기간·단위·비교 결과뿐이다.
원본 DATA_VALUE/금액 표·통계표 이름·원본 응답·응답 해시·인증 URL·키·provider 예외는 공개하지 않는다.
메타데이터 오류는 기존 고정 필드/분류/stage를 안전하게 표시하고 나머지는 알려진 오류 ID만 남긴다.
원본과 수치는 프로세스 메모리에서만 처리하며 쓰기는 저장소 밖 step Summary 파일뿐이다.

| 결과 | 해석 |
| --- | --- |
| comparison_completed | 요청 범위의 ECOS 두 후보 수치 검증·비교 완료. 원천 선정/운영 연동 완료 아님 |
| equal_at_current_query | 이번 조회에서 같은 월·단위의 두 표 값이 같음. 작성 기준·빈티지 동일성 증거 아님 |
| difference_requires_definition_or_vintage_review | 실제 값 차이. 정의/계상 범위/정정/공표 시점을 추가 확인. 차이 원인을 임의로 정정이라 단정하지 않음 |
| partial_missing / missing | 월별 값 부족. 0으로 대체하지 않으며 job 실패로 표시 |
| reference_missing | KTO 공식 파일 근거 없음. KTO 교차검증 미완료 |
| reference_periods_unavailable / partial_reference_coverage | KTO 파일은 있으나 비교 기간의 근거가 없거나 일부만 있음 |
| value_equal_vintage_not_equivalent | KTO와 숫자는 같지만 공표 빈티지/잠정·확정 상태의 동등성을 확인한 것은 아님 |
| value_difference_vintage_review_required | KTO와 값이 다름. 원문 정정/공표 시점·정의를 별도 검토해야 함 |
| validation_failed | API 인증/접근/metadata/단위/수치 등의 고정 오류. 결과를 성공으로 대체하지 않음 |

job은 ECOS 비교 자체가 끝났으면 성공할 수 있으나 **KTO 근거가 없을 때 원천 적합성은 여전히
review_required**다. 차이가 발견되어도 비교 실행 자체의 실패와 분리한다.
API 조회일을 공식 공표일로 쓰지 않으며, API가 주지 않는 잠정/확정/정정 시점을 추론하지 않는다.

## 5. KTO 근거를 안전하게 추가하는 후속 절차

현재 `kto-reference.json` 파일은 **존재하지 않는다**. 운영자가 정상 제공 경로에서 확보한 공식
금융 통계 파일을 확인한 뒤 별도 근거 검토 PR로 이 디렉터리에 추가할 수 있게 parser만 준비했다.
워크플로에 임의 URL·파일 경로를 입력하거나 파일을 런타임 다운로드하는 기능은 없다.

필수 구조(아래는 형식 설명이며 실제 금액/증거가 아니다):

- data_origin: `official_kto_export`, definition: `general_travel`
- reference_review: `official_file_verified` — 코드 검토자가 원문/이용조건을 확인한 자료에만 사용
- unit: 원문 그대로 `백만달러` 또는 `천 US$`
- source_url: KTO 공식 HTTPS View.do / Download.do URL, source_sha256: 실제 원본 파일 해시
- published_at / verified_at: 시간대가 있는 실제 공표·검증 시각, finality: provisional/final/not_stated
- observations: period(YYYY-MM), receipts, expenditure(각각 원문의 숫자 **문자열**)

파일·근거 검토는 실제 공식 파일의 SHA/정의/단위/기준월/잠정·확정/출처 및 이용조건을 확인해야 한다.
단지 형식 검사를 통과했다고 공식 자료가 되는 것은 아니다. 인공 fixture를 근거 파일로 승격하지 않는다.
다른 출처·전체 여행수지·비HTTPs·결측 공표일·잘못된 해시·중복/미래 월·float 수치는 거절한다.
원문을 받지 못한 현 단계에서는 파일을 만들어 수치를 채우지 않았다.
근거 파일을 검토해도 Macro 운영 게이트/수집 승인과는 별도이며 이번 PR에서 변경하지 않는다.

## 6. 테스트·운영 보호와 남은 과제

로컬 전체 Python **456개 통과(기존 435 + 신규 합성 21)**, actionlint / compile / diff --check 통과. GitHub CI 근거는 PR 본문에 기록한다. Fake 값은 테스트 메모리에만 있고 실제 확보량에
포함하지 않는다. 두 표의 코드/방향/단위/계층, 기간 범위·결측·중복·정밀도, KTO 빈티지·단위 환산,
Summary/로그 보호, Secret 부재, 수동 main-only 및 쓰기 범위, 기존 가드 보존을 검증한다.
UI·운영 코드 변경이 없어 브라우저 회귀용 제품 변경은 없다.

운영 JSON 30개·기존 workflow 6개·ECOS Preflight·Macro source/승인·pipeline·홈페이지 불변.
추가한 workflow 하나만 수동 읽기 검증용이다. data/live push, source 활성화, 운영 저장·Pages 배포는 없다.

남은 작업은 사용자 병합 후 Actions 실인증 실행 → 실제 두 후보 차이 확인 → KTO 공식 파일 확보·
이용조건/동일 월·단위·공표 시점 확인 → 원천 적합성 판단이다. 조건이 충족된 후에도 실제 운영
활성화는 별도 PR과 검증이 필요하다. 이번 PR에 자동 병합은 설정하지 않는다.
