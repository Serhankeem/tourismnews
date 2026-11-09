# KTO 월별 한국관광통계 공표 탐색 Hotfix

기준 main: `6e97cf30c12591a4be1ca4cb35a206e58f20fe42`. 브랜치: `fix/kto-monthly-release-discovery`.
PR #37의 `feat/tourgo-macro-integration-v1`은 수정·병합하지 않습니다.

## 확인한 장애 원인

2026-11-09 실제 HTTPS 응답과 기존 코드를 대조했습니다.

| 확인 대상 | 실제 결과 | 기존 코드와의 불일치 |
| --- | --- | --- |
| [홈페이지](https://datalab.visitkorea.or.kr/datalab/portal/main/getMainForm.do) | HTTP 200, 정상 한국관광 데이터랩 HTML, 약 592KB. 현재 노출된 발간자료 중 월별 `한국관광통계 공표` 링크 없음 | `latest_release()`가 홈페이지의 제한된 최신 목록에서만 제목을 찾으므로 `monthly_release_not_advertised_in_public_catalog` 발생 |
| [기존 9월 게시물](https://datalab.visitkorea.or.kr/site/portal/ex/bbs/View.do?cbIdx=1127&bcIdx=311425&pageIndex=1&cateCont=spt01) | HTTP 200. `2026년 9월 한국관광통계 공표`, 2026-10-28 10:10 KST, 공공누리 0유형, 공식 XLSX 첨부 유지 | 제목 정규식·게시물·첨부파일 자체의 소멸이 아님 |
| 홈페이지의 `방한 외래관광객` 메뉴 | 공개 HTML `/datalab/portal/ts/getEntcnyFrgnCust2Form.do`로 연결 | 기존 탐색은 이 공개 통계 페이지의 게시판 연결을 사용하지 않음 |
| 통계 페이지의 `a#bbsBtn` | `통계게시판`, `../../../site/portal/ex/bbs/List.do?cbIdx=1603&tgtTypeCd=CATE_CONT&searchKey2=spt01` | 허용된 공식 필터 게시판을 동적으로 따라갈 경로가 없었음 |
| 필터 게시판 | 익명 공개 세션 유지 시 HTTP 200. 연간 예정일/가이드북 고정글 다음에 9월·8월 등 월별 공표 목록 존재 | 직접 href가 `cbIdx=1603&cbIdx2=1127&...&cateCont=spt01` 형식. 기존 `cbIdx=1127` 단일 검사로는 거부됨 |
| 세션 없는 게시판 GET | HTTP 302 → `http://datalab.visitkorea.or.kr/`; 기존 전송기는 안전하게 중단 | 기존 opener에 CookieJar가 없어 공개 페이지가 발급한 세션을 유지하지 못함. 같은 공개 페이지를 익명 세션으로 순서대로 방문하면 HTTPS 200 |

이번 응답에서는 제목 형식이나 `goUrl()` 함수의 인자 형식이 변경된 증거는 없습니다. 홈페이지 응답은 정상 HTML이며 기존 파서는 해당 제목이 없는 페이지를 설계대로 거부했습니다. 문제는 홈페이지 노출 목록을 전체 공표 목록으로 취급한 탐색 범위와, 공개 세션/게시판 래퍼 URL 지원 부족입니다. 사이트가 과거 언제 변경됐는지는 단정하지 않습니다.

## 최소 변경과 안전성

- `src/macro/kto.py`: 기존 홈페이지 링크를 우선 처리하고, 월별 링크가 없을 때만 홈페이지에 실제 있는 공개 통계 메뉴 → 그 페이지의 실제 `통계게시판` 버튼 → 월별 공표 링크를 따라갑니다. 보관된 과거 URL을 fallback으로 사용하지 않습니다.
- 기존 제목·정정 제목 정규식은 유지합니다. 연간 공표 예정일·가이드북을 월별 실적으로 취급하지 않습니다.
- 기존 1127 직접 링크 외에는 **1603 래퍼 + 실제 게시판 1127 + spt01 + 공식 카테고리 필터**를 모두 만족하는 링크만 허용합니다. 다른 게시판·외부 도메인·HTTP·userinfo·fragment·중복 파라미터는 거부합니다.
- `src/macro/transport.py`: 익명 세션을 메모리 안에서만 유지합니다. 신규 공개 HTML 경로 2개와 정확한 게시판 필터 query만 허용 목록에 추가했습니다. robots, 응답 크기, 요청 간격, HTTPS, 리디렉션 목적지 검증은 유지합니다. 쿠키 값은 로그·파일로 내보내지 않습니다.
- `/portal/getChkShowYn.do` 등 내부 AJAX, `/datalab/portal/goUrl.do` 폼 호출, 로그인, 인증 우회, 브라우저 가장, HTTP 강제 추종은 구현하지 않았습니다. 공개 HTML에 들어 있는 링크 문자열만 해석합니다.
- 공표 게시물의 기준월·공표일·공공누리 0유형·첨부파일 다운로드 컨트롤 및 독립 XLSX 교차검증은 그대로입니다. 기존 engine의 이전 기준월/공표일 역행 차단·누락 보존·정정 이력도 유지합니다.
- 확인된 게시판 URL은 source snapshot의 `discovery_catalog_url`에 남깁니다. Macro engine, `macro_sources.json`, workflow, 공통 파이프라인 코드는 수정하지 않았습니다.

## 실제 수집 검증

실패 실행의 영속 저장 커밋과 일치하는 `data/live` 스냅샷 `5b4ee80b55b08da057575430b7b7481313be5d74`를 읽고, **저장소 밖 복사본에서만** 수집했습니다.

| 항목 | 결과 |
| --- | --- |
| robots / 홈페이지 / 공개 통계 페이지 / 필터 게시판 / 공표 게시물 / XLSX 2개 | 모두 실제 HTTPS HTTP 200 |
| 발견·검증한 최신 공표 | 2026-09, 게시물 311425 |
| 공표일 | 2026-10-28 10:10 KST 그대로 |
| 이용조건 | 공표 게시물의 KOGL-0 표시 확인 |
| 공식 원장·별도 통계월보 교차검증 | 방한·출국·5개 국적 및 전년/누적 비교 통과 |
| Macro 관측값 | 483 → 483, 신규 0, 동일 483, 값 정정 0 |
| 기준월·값·단위·최초 수집시각·정정 이력 | 기존 자료와 동일 |
| News / Research | 75 → 75 / 137 → 137, 파일 바이트 동일 |
| 변경된 격리 파일 | Macro 공개 JSON/health, Macro 원장/run summary 4개만. 실제 확인 시각과 검증된 게시물·탐색 링크 갱신 |
| 나머지 격리 파일 | 26개 SHA-256 동일 |
| 운영 JSON·원장·`data/live`·Pages | 변경·업로드 없음 |

[네트워크 검증 결과와 응답 해시](network-validation.json), [보존 증거](preservation.json). 전체 원문 HTML·다운로드 XLSX와 수집 결과 JSON은 커밋하지 않았습니다. fixture는 공개 제목·링크·날짜·권리 표식·다운로드 컨트롤의 축약본이며 통계 XLS 값은 포함하지 않습니다.

**정상적인 변경 없음**은 현재 게시판을 실제로 읽고 게시물·파일 검증을 통과한 뒤 `status=ok`, `new_observations=0`, `unchanged_observations=483`으로 확인합니다. 게시판 확인 실패·차단·필수 제어 부재·월별 링크 부재는 예외/failed이며 변경 없음으로 바꾸지 않습니다.

## 요청은 News였는데 Macro도 실행된 이유

[실패 실행 42566516540](https://github.com/Serhankeem/tourismnews/actions/runs/42566516540)의 진단 artifact에서 `requested=news`, News `partial`, Macro `failed`, `ready=true`, `collection_ok=false`, News 75 / Research 137 / Macro 483을 확인했습니다. Pages 단계는 성공했고 마지막 `Mark failed collection after preserving validated data` 단계가 실패했습니다.

`src/pipeline/schedule.py:pending()`은 요청한 엔진과 미완료·도래한 슬롯을 함께 선택합니다. news 요청은 다른 엔진을 배제하는 선택지가 아닙니다. Macro는 KST 12:20 일일 슬롯이 미완료였으므로 같은 공유 락 안에서 실행됐습니다. 실패 슬롯은 완료 처리되지 않아 이후 news 실행에서도 재시도됩니다.

`runner.transact()`는 엔진별 소유 파일·체크포인트·검증을 분리합니다. 검증된 자료와 실패 health를 영속 저장하고 Pages 조합이 안전하면 `ready=true`로 둡니다. 별도의 `collection_ok=false`와 workflow 마지막 실패 단계로 수집 장애를 숨기지 않습니다. 기존 `continue-on-error`는 저장·배포 보호 단계로 진행하기 위한 것이며, 마지막 실패 표시와 함께 작동합니다.

**이 정책은 변경하지 않습니다.** 수집 장애와 배포 성공을 별도로 알리는 현행 정책이 이번 사고에서도 자료를 보존했습니다. 이 hotfix는 수집 실패를 무시하거나 workflow를 강제 성공 처리하지 않습니다. 공통 정책 변경안을 별도 적용할 필요는 없다고 판단했습니다.

## 테스트와 기존 기능 보존

- Python 전체 **495개 통과**: 신규 KTO 10개, Due Engine 분리 시나리오 1개 포함.
- 새 테스트는 실제 확인한 제목·링크·세션 구조, 기존 goUrl/정정 제목, 최신월, 차단/오류 HTML, 잘못된 도메인/게시판/query, robots/HTTP 리디렉션, 공표일·권리·다운로드 검증, 483개 보존·재시도·역행 거부를 검사합니다. 합성 HTTP·XLSX는 네트워크를 사용하지 않습니다.
- 기존 pipeline harness에 News partial + 도래한 Macro failed 상태에서도 기존 Macro 원장과 Pages 파일을 보존하고, 전체 실패 및 재시도 상태를 유지하는 테스트를 추가했습니다. pipeline 실행 코드는 그대로입니다.
- 실제 수집 복사본을 기존 compose 검증으로 조합한 로컬 사이트에서 `macro.smoke.cjs`, `market-weather-v2.smoke.cjs` **2개 스위트 통과**. 320/390/768/1440px, 원문 링크·통계값·차트·실패 보존·시뮬레이션 분리를 확인했습니다. UI 수정은 없습니다.
- GitHub CI의 최종 결과는 이 PR의 Checks에 제공합니다. 실제 운영 수집·Pages 배포의 후속 확인은 사용자의 병합 후 별도 단계입니다.

변경 파일은 위 수집기 2개, KTO 테스트/축약 fixture, 기존 pipeline 테스트 1개, 본 문서·검증 증거입니다. `macro_sources.json`, Macro engine, TOURGO 원본·승인 게이트, ECOS 매핑, 뉴스 권리 게이트, Research 원장, Market Weather 계산식, 브랜드·디자인, GitHub Actions를 변경하지 않았습니다.

PR #37 HEAD `3a1cca987348a0b4a00c7e3b6bed2473e36c46c0`과 비교해 **직접 중복되는 변경 파일은 없습니다.** 공통 기반의 Loader 호출 시그니처도 유지하므로 TOURGO의 오프라인 통합 코드와 직접적인 충돌 요인은 없습니다. 향후 다른 수정과 함께 병합할 때는 각 PR CI를 다시 확인해야 합니다. PR #37은 기존 Draft 상태 그대로 유지합니다.
