# PR #17 — 기존 레코드 공개 권리 게이트 보완

현재 출처 설정을 신규 수집뿐 아니라 **기존 레코드의 모든 공개 projection**에도 적용했습니다. Hotel News Resource는 `publication.status=review`이므로 기존 3건을 Newsroom·홈 대표 뉴스·현재 Daily Briefing에서 제외했습니다. 세 기사의 원문 식별자·발행일·첫 발견/최초 게시 시각·관련성/편집 판정·수집 당시 정책은 원장에 그대로 보존합니다. 새 출처나 새 기사 수집은 하지 않았습니다.

## 현재 결과

| 항목 | 이전 검수 | 이번 보완 |
|---|---:|---:|
| 원장 보관 레코드 | 60 | 60 (파일 SHA-256 동일) |
| 공개 Newsroom | 50 | 47 |
| 실제 공개 뉴스 기여 출처 | 8 | 7 |
| Hotel News Resource 공개 뉴스 | 3 | 0 |
| Hospitality Net 공개 뉴스 | 3 | 3 |
| 현재 브리핑 후보 | 4 | 3 |
| 최근 24시간 발행 공개 뉴스 | 11 | 8 |
| 최근 7일 발행 공개 뉴스 | 37 | 34 |
| 상위 3개 출처 점유율 | 72.00% | 76.60% (36/47) |
| 공개 뉴스 Direct 비율 | — | 100% (47/47) |
| 권리 보류 뉴스 | — | 3 |

공개 출처별 기여는 여행신문 14 / 트래블데일리 13 / TTL 9 / 문체부 4 / 서울시 문화 2 / GOV.UK aviation 2 / Hospitality Net 3건입니다. HRN은 공개 기여 0건이며 수집 실패나 Irrelevant로 바꾸지 않았습니다. 기존 44건과 HN 3건의 공개 6필드는 이전 검수와 완전히 동일합니다.

공개 전체 record 합계(`total_published`/`public_record_count`)는 뉴스 47+공시 5+통계 3=55건, 원장 전체(`total_archived`)는 60건입니다. 원장에는 권리 보류 3건 및 기존 보관 전용 뉴스 2건도 있으므로 전체 원장 수를 공개 뉴스 수로 사용하지 않습니다. 기존 발견 단계의 Direct Ratio와 Duplicate Ratio는 전송 관측의 지표이며, 공개 뉴스 비율은 새 `public_news_direct_ratio`/`public_news_relevance_counts`로 분리했습니다.

실제 수집 시각은 이전 main 관측 그대로 유지하고, 공개 KPI 평가 시각은 `quality.public_metrics_as_of`에 따로 표시합니다. 이번 보완의 신규 네트워크 수집 건수는 0건입니다.

## 구현

- `src/visibility.py`의 `PublicationGate`가 현재 등록된 source ID·enabled·기존 permission()을 사용합니다. 저장된 과거 `publication_policy=approved`나 발견 원장의 과거 `publication_status=published`를 현재 허락으로 취급하지 않습니다.
- `src/engine.py`의 Newsroom/news.json, 현재 브리핑 입력, 공시/통계 projection 및 공개 KPI가 같은 허용된 뷰를 사용합니다. Research Library 보고서 엔진/DB는 이 대상이 아니며 변경하지 않았습니다.
- 네트워크 전부 실패 시에도 **명시적인 권리 보류/승인 변경**은 기존 데이터에 재투영합니다. 성공한 척 last_successful_fetch를 갱신하지 않습니다. 권리 변화가 없는 단순 수집 실패는 기존 공개 JSON·브리핑을 그대로 보존합니다.
- 권리 보류를 `archived_only`나 Irrelevant로 바꾸지 않았습니다. 별도 비공개 경로 `collector_state/publication_visibility.json`에 ID별 현재 상태와 public→rights_hold→public 전환 시각/사유/정책 상태를 저장합니다. 잘못된 이력 파일을 빈 상태로 초기화하지 않고 오류를 기록합니다.
- 공개 `site/data/publication_visibility.json`에는 보류 URL의 SHA-256만 포함하며 제목·원문 URL·본문이 없습니다. 확정 브리핑 원본 파일은 바이트 그대로 유지하고, Briefing UI가 현재 권리 해시 목록을 적용해 현재/과거 화면 및 복사에서 보류 항목을 제외합니다. 현재 후보 JSON 자체에서도 HRN 1건을 제거했습니다.
- 새 권리 정보가 로드되면 캐시된 브리핑도 즉시 다시 필터링합니다. 현재/아카이브 JSON 갱신이 실패해도 보류된 캐시 항목이 다시 나오지 않습니다. 권리 manifest를 확인할 수 없으면 브리핑 표시·복사를 보류합니다.

## 복구

이용조건이 확인되면 source의 근거/검토 기록과 publication.status를 정상 승인 상태로 수정합니다. 다음 엔진 실행은 같은 source ID·기사 ID·원문 날짜·최초 수집 이력으로 공개 뷰를 복원하고 상태 이력에 rights_hold→public을 추가합니다. 새 기사로 재집계하거나 오늘 발행한 기사로 바꾸지 않습니다. 기존 보존기간·날짜·관련성 조건도 계속 적용됩니다.

정상적인 승인 복구는 네트워크 장애 중에도 검증된 원장으로 재투영할 수 있습니다. 원본을 삭제하거나 보류 표시를 영구 보관 플래그로 바꾸지 않았으므로 재수집이 필수적이지 않습니다. 표시용 해시 목록도 승인에 따라 제거되어 원본 확정 기록을 수정하지 않고 표시를 복구할 수 있습니다.

## 보존 및 테스트

- Python **259/259 통과**(기존 253+권리 게이트 6개): 기존 review 기사와 브리핑 제거, 동일 원장 보존, 전부 수집 실패 중 보류 적용, 승인 시 원 ID/날짜/검증 값 복구, 이력 멱등성, 단순 장애의 공개 파일 바이트 보존, 비활성/미등록 출처 차단, 이력 손상 보존과 hash-only manifest 검증.
- 브라우저 **14/14 suite 통과**(기존 13+publication-visibility): 실제 HRN 3개 URL의 Newsroom/news fallback/현재 브리핑 제외, HN 키워드와 6필드 유지, 과거 브리핑 표시·복사 필터링, 원본 파일 불변, 실패 시 캐시 필터, 권리 정보 실패 시 표시 보류, 승인 복구를 390/1440px에서 검증했습니다. 기존 전체 UI/페이지네이션/검색/북마크/뉴스 최신순/리서치/Macro/Weather 회귀도 유지합니다.
- 원장 60건·수집 ID·검증 기록, 내부 확정 선정 이력·공개 확정 아카이브, Research 135건·Macro DB·Weather UI/계산식·로고·HTML·기존 내비게이션·GitHub Actions는 이전 커밋과 바이트 동일합니다. 현재 브리핑만 4→3건으로 재선정했습니다.
- 테스트의 임의 API 응답/과거 브리핑 복구 예시는 브라우저 격리 route와 임시 디렉터리에만 존재하며 운영 JSON에 추가하지 않았습니다.

[현재 데이터·권리 보류 ID·보존 SHA-256](publication-gate-final.json) · [Python](gate-python.txt) · [브라우저](gate-browsers.txt)

기존 PR #17에만 반영합니다. main 병합·운영 배포는 하지 않았으며, 검토·병합 후 실제 Actions와 Pages의 47건/보류 3건/브리핑 3건 반영을 확인해야 합니다. 이후 정상 수집에 따라 숫자는 바뀔 수 있지만 review source의 기존/신규 공개 차단은 동일하게 유지됩니다.
