# PR #18 main 자동 수집 충돌 해결

기존 `feat/korea-news-coverage-v05`에 `origin/main`의 `0357b30`를 병합했다. main/새 PR로 제출하지 않는다. 공통 조상 `54117f6`, 병합 전 PR HEAD `fa913562`이다.

## 원인과 기준

main의 실제 자동 수집(2026-11-04 **12:00:25 KST**)과 PR의 수집·편집 재투영이 같은 JSON을 각각 갱신했다. 동일 기사의 판정도 main의 기존 규칙과 PR의 v0.5 규칙에서 달라 텍스트 줄 단위 병합으로 해결할 수 없었다. 전체 파일 ours/theirs 선택은 사용하지 않았다.

최신 실제 실행과 현재 공개 투영을 구분했다. 수집 시간·출처별 상태·errors·시도/신규/중복의 **이번 실행 값**은 최신 main 기준이다. 병합은 수집 실행이 아니므로 PR의 7건을 main의 신규 수집 실적으로 다시 더하지 않았다. `merge_projection`에 이 구분을 기록했다. 이번 병합 중 새 뉴스 네트워크 수집은 하지 않았다.

## 항목별 병합

- **보관 원장:** 양쪽 ID·정규 URL 대응을 검사하고 합집합 71건을 보존했다. ID가 같으면서 URL/발행일이 다른 경우 자동으로 덮어쓰지 않도록 검증했다. 최신 main의 64건 + PR에서 이미 확보한 7건이다. 71개 ID·원 발행일·URL 유지, 기존 28개 한국 직접 관련 판정을 보존하고 새 main 기사까지 현행 editorial 함수로 재투영했다.
- **발견 기록:** 최신 main 2,351개와 PR 2,044개를 ID로 대조했다. PR의 ID는 모두 최신 main에도 있으므로 최종 합집합은 **2,351개**, main에만 있는 ID는 **307개**다. 최초 발견은 min, 마지막 관측은 max로 병합했다. 달랐던 시각과 원 판정은 감사 JSON에 양쪽 값을 남겼다. 등록·발견 시각을 기사 발행일로 사용하지 않았다.
- **7건의 판정 충돌:** main의 기존 규칙에서 exclude였던 실제 관측은 감사 기록으로 보존한다. 현재 정규 원장/발견 상태에는 PR에서 검증한 Direct 및 게시 상태를 반영했다. 세 정책 기사의 한국 등급 근거·중립 reference 설명·OTA 운영 기술 규칙은 그대로다. 과거 main 실행의 decisions를 현재 규칙으로 조작하지 않았다.
- **권리 이력:** 레코드별 transitions 합집합을 중복 제거 후 원 이벤트 시각으로 정렬했다. 최신 관측의 정책·상태를 사용하고 모든 과거 이벤트를 보존했다. PR에서 추가한 7개의 실제 기존 공개 전환도 남겼다. HNR 3개는 review/rights_hold, Newsroom·현재 브리핑 제외를 유지한다. 공개 hash manifest는 동일하다.
- **누적 source_metrics:** 공통 조상 이후 두 독립 실행을 모두 보존하도록 `base + (PR-base) + (main-base)`로 시도·성공·오류 카운터를 합쳤다. latest_checked는 최신 실제 값이다. main 실행의 상태·성공률 행은 해당 실행 당시 기록 그대로 health에 보존했다. 병합된 누적값과 latest-run 당시 비율은 서로 다른 시점의 지표다. 다음 실제 실행은 병합된 누적값을 이어받는다.
- **decisions/review_queue:** 최신 실행의 decisions는 main 원문 JSON과 동일하다. review_queue의 양쪽 articles가 완전히 동일함을 확인하고 최신 updated_at을 보존했다. PR의 판정 근거는 정규 원장과 Git 부모 커밋 및 감사 기록에 남는다.
- **공개 views/브리핑:** 최신 main의 실제 fetch 봉투와 병합된 정규 원장에 기존 PublicationGate·public_record·briefing 함수를 적용했다. PR의 공개 기사 54개 여섯 필드는 모두 동일하게 보존했다. main의 실제 신규 4건이 더해져 58건이고 봉투의 수집 시각은 최신 main이다. 현재 브리핑은 최신 수집 기준의 24시간 창으로 1건이다. 3개 정책 기사는 이 창 밖이므로 억지로 추가하지 않았다. main이 실제 생성한 11월 4일 확정 브리핑/selection을 포함하며, 기존 PR의 모든 확정 edition이 그대로 포함됨을 대조했다. 합친 뒤에는 최신 main 파일 바이트를 변경하지 않았다.

## 결과

아래 최근 수치는 **마지막 실제 수집 시각인 2026-11-04 12:00:25 KST 기준 저장된 스냅샷**이다. 충돌 해결 시각을 새 수집일·발행일로 표시하지 않는다.

| 항목 | main | 병합 전 PR | 병합 후 |
|---|---:|---:|---:|
| 공개 뉴스 | 51 | 54 | **58** |
| 보관 원장 (전체 유형) | 64 | 67 | **71** |
| 한국 직접 관련 뉴스 | 23 | 28 | **29** |
| 발견 후보 | 2,351 | 2,044 | **2,351** |
| 현재 브리핑 후보 | 1 | 5 | **1** |
| 최근 7일 한국 직접 관련 | — | 20 | **17** |
| HNR 공개 / 권리 보류 | 0 / 3 | 0 / 3 | **0 / 3** |

최신 수집 시각: **2026-11-04 12:00:25 KST** (PR의 15:13:02에서 갱신). 최신 실제 출처 결과 **15 성공 / 11 실패** (PR의 과거 23/3으로 덮어쓰지 않음). main 대비 증가한 7건은 PR의 기존 기사 복원이며 새 공급원이 아니다. 작업 중 `c93444e` 이후 자동 수집이 더 진행돼 `40bba6f`, `3003303` 등을 거친 최신 `0357b30`까지 가져왔다. 최초 지시 시점보다 실제 기사 4건(제주항공 실적·호텔 기술·호텔 제휴·포항 관광/MICE)이 추가됐으며, 이 중 제주항공 실적만 한국 직접 관련으로 분류되어 28→29건이다. 최근 7일 20→17건 및 브리핑 5→1건은 기준 시각이 다음 날로 이동한 시간창 변화이며 기사 삭제가 아니다. 국내 실제 기여 출처 5개 / 신규 국내 공급원 0개는 그대로다.

## 파일 및 보존 검증

충돌 JSON 14개:

- `collector_state/`: `archive.json`, `briefing_latest_selection.json`, `decisions.json`, `discovery.json`, `publication_visibility.json`, `review_queue.json`, `run_summary.json`, `source_metrics.json`.
- `site/data/`: `briefing.json`, `filings.json`, `health.json`, `news.json`, `newsroom.json`, `research.json`.

main에서 정상적으로 추가된 `site/data/briefing_archive.json`, `collector_state/briefing_selection.json`도 병합에 포함한다. 추가 변경은 이 병합 문서와 감사·테스트 결과 및 README의 안내 링크다. 수집/편집 코드·출처 설정·PublicationGate·UI·Actions를 변경하지 않았다. Research Library 135건·Macro·Weather·TOURGO 게이트·로고·확정 아카이브 등을 포함해 **PR의 기존 보호 파일 40개와 최신 main 확정 파일 2개, 총 42개 SHA-256 동일**을 검사했다. source code도 병합 전 PR과 같다. `site/data/research.json`은 뉴스 엔진의 통계 views이며 Research Library `reports.json`과 구분한다.

재현 가능한 ID/관측 해시, 양쪽 수집 카운터, 최신 실제 source 행, 원 발행일/URL, 양쪽 권리 전환 및 보호 해시는 [MERGE-PRESERVATION.json](MERGE-PRESERVATION.json)에 있다. 특정 병합 스냅샷 검사는 `python docs/newsroom-source-expansion-v05/verify-merge.py`로 실행한다. 향후 정상 수집이 진행되면 시각·카운터가 바뀌는 것이 정상이므로 이 고정 스냅샷 검사는 정기 자동화 테스트에 추가하지 않았다.

Python 전체 **269개**, 병합 스냅샷 감사 **5개**, 브라우저 전체 **15개 suite**가 통과했다. GitHub CI 및 최종 mergeable 상태는 [MERGE-TESTS.json](MERGE-TESTS.json)과 기존 PR #18 Checks에 반영한다. 운영 수집/Pages 배포는 PR에서 실행하지 않는다.
