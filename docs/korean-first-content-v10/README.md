# Korean-first Content Experience v1.0

최신 main `f07d27e`(PR #22 병합)에서 `feat/korean-first-content-v10`으로 작업했다. 검증 기준은 읽기 전용 data/live `37a2c4c` 스냅샷이며 실제 운영 data/live 쓰기·Pages 배포·main 병합은 하지 않았다. 정확한 전체 커밋과 수치는 [comparison.json](comparison.json)에 있다.

## 결과

- 뉴스 **전체/국내 발행처/해외 발행처** 탐색과 **국내 우선/전체 최신순** 선택을 구현했다. 원문·수집은 유지한다.
- Research **전체 기관/국내 기관/해외 기관** 빠른 필터를 기존 기관 구분 필터와 동기화했다.
- 한국어 안내 표제는 **Research 2건**, 뉴스 **0건**이다. 두 건도 원제 전체 번역이 아니라 기관·연도·관광 분야에 따른 **독립적인 서지 안내 표제**다. 공식 한국어 제목이나 연구 요약이라고 표시하지 않는다.
- 검토 보류는 **뉴스 9건 + Research 92건 = 101건**이다. 이들의 한국어 번역문을 생성·저장·공개하지 않았다.
- 원제·원문 링크·발행일·원장·권리 게이트·확정 브리핑·뉴스 6필드/Research 8필드는 보존했다.
- **Python 333개, 브라우저 18개 suite 통과**. 운영에 한국어 표제를 적용한 실적은 0이며, 위 2건은 PR의 격리 검증 화면/승인된 코드 자산 기준이다.

## 1. 국내 우선 탐색과 출처 검증

Newsroom의 기본값은 **전체 뉴스 + 국내 발행처 우선**이다. 국내 그룹 안에서 원문 발행일 최신순, 그다음 해외 그룹 안에서 최신순으로 정렬한다. 같은 시각은 기존 URL 기준으로 안정 정렬한다. 전체 최신순은 기존 발행일 비교 함수를 그대로 사용한다. 검색·카테고리·저장·출처 구분을 먼저 적용하고 페이지 수/현재 페이지를 계산하며, 구분·정렬 변경 시 1페이지로 돌아간다.

국내 발행처는 한국 시장 직접 관련성 등급이 아니다. 제목 언어·기사 속 국가명으로 발행처를 추정하지 않는다. 기존 sources.json의 검증된 KR 메타데이터를 사용했다. 기존 해외 3개 피드에는 국가 필드가 없었으므로 **공식 소개/법적 정보 확인 후 coverage 메타데이터만** 보완했다.

| 등록 피드 | 확인한 발행처/국가 | 근거 |
|---|---|---|
| govuk_tourism / govuk_aviation | GOV.UK / GB | [공식 소개](https://www.gov.uk/help/about-govuk), [공식 이용조건](https://www.gov.uk/help/terms-conditions) |
| hospitalitynet | Hospitality Net / NL | [이용약관](https://www.hospitalitynet.org/terms-conditions)의 Syndicate-Hospitality Net BV, Netherlands 등록/주소 명시 |

공급원·이름·URL·활성화·수집 주기·publication/discovery 정책은 바꾸지 않았다. 다른 출처의 국가가 확인되지 않거나 등록 이름·원문 호스트가 맞지 않으면 **구분 미확인**으로 남기고 별도 버튼을 표시한다. 언어로 해외 처리하지 않는다. 같은 GOV.UK의 두 피드도 새 발행처 확보로 계산하지 않는다.

홈의 대표 3건은 **전체 원문 발행일 최신순을 유지**한다. 오래된 국내 기사가 더 최근 해외 기사를 밀어내거나 ‘오늘의 뉴스’로 보이지 않게 하기 위한 선택이다. 홈에 발행처 구분과 전체 최신순 안내를 표시하며, 뉴스룸에서는 국내 우선 탐색을 바로 사용할 수 있다. 서버 공개 JSON과 내부 NEWS 원본 배열의 전체 최신순은 그대로다.

## 2. 한국어 표제 정책과 실제 사례

원장의 title을 바꾸거나 본문을 수집/요약/번역하지 않는다. 발행기관의 공식 한국어 제목, 명확한 제목 번역 허락, 독립적 사실 안내라는 세 경로를 구분하되 이번 실제 적용은 마지막 경로에 한정했다. 검증 없는 기계 번역은 없다.

### 게시 검토를 완료한 2건

| 원제 / 실제 발행일 | 표시용 한국어 안내 표제 | 검증 범위 |
|---|---|---|
| [OECD Tourism Trends and Policies 2026](https://www.oecd.org/en/publications/oecd-tourism-trends-and-policies-2026_3fd3cd75-en.html) / 2026-06-30 | **OECD 관광 보고서 · 2026년** | OECD 명칭·2026년·관광 분야·보고서라는 서지 사실만 사용 |
| [OECD Tourism Trends and Policies 2024](https://www.oecd.org/en/publications/oecd-tourism-trends-and-policies-2024_80885d8b-en.html) / 2024-07-08 | **OECD 관광 보고서 · 2024년** | 같은 기준으로 기관·연도·분야 대조 |

둘 다 한국어 안내 표제 배지와 **원제 전체**를 함께 표시한다. 접을 수 있는 근거 안내에는 “발행기관·연도·분야로 작성한 안내이며 원제의 공식 번역이나 연구 내용 요약이 아닙니다.”라고 명시하고 OECD/year/original title/URL 출처를 남긴다. 숫자·기관명·원문 발행일·링크를 대조했다. 연구 결과·주장·수치·결론은 작성하지 않았다.

[OECD 일반 이용조건](https://www.oecd.org/en/about/terms-conditions.html)은 2024-07-01 이후 다수 written content에 CC BY 4.0 및 번역/출처·면책 조건을 설명한다. 그러나 ‘다수’라는 일반 설명만으로 **개별 보고서 전체나 표현의 번역 허락을 확정하지 않았다**. 두 서지 페이지는 200으로 확인했지만 PDF/전문·표지·OECD 로고를 수집하지 않았다. 이 PR의 2건은 전체 원제 표현 번역이 아닌 사실 기반 탐색 안내로 검토했으며, 전체 번역 공개 건수는 **0건**이다. 기관의 별도 승인/공식 번역 인증을 받았다고 주장하지 않는다.

### 뉴스 대표 사례 — 원제 유지

| 사례 | 정확성·권리 검토 | 적용 |
|---|---|---|
| [New visitor levy powers to put money back into local communities](https://www.gov.uk/government/news/new-visitor-levy-powers-to-put-money-back-into-local-communities) | 기존 GOV.UK 메타데이터/OGL 근거는 유지. OGL 원문 호스트는 이번 robots 확인 403, GOV.UK의 대체 추정 경로는 404였다. 제목 변형 허락 확인과 개별 안내 표제 편집을 완료한 것으로 표시하지 않음 | 한국어 표제 미생성·보류 |
| [Phuket Enters a New Era of Growth as Billions in Investment Transform the Island's Property, Hospitality and Lifestyle Landscape](https://www.hospitalitynet.org/news/4135257/phuket-enters-a-new-era-of-growth-as-billions-in-investment-transform-the-islands-property-hospitality-and-lifestyle-landscape) | 기존 지정 RSS의 제한적 원제/링크 색인과 제목 변형·번역은 별개. 지역·투자 규모·성과 등을 확대 해석하지 않음 | 한국어 표제 미생성·보류 |

뉴스 9건 모두 원제를 유지한다. 국가 검증이 번역 허락을 의미하지 않는다.

### Research 보류 대표 사례

- [AI claims processing ranks last as a booking confidence driver](https://www.phocuswright.com/Travel-Research/Research-Updates/2026/ai-claims-processing-ranks-last-as-a-booking-confidence-driver): 공식 [Copyright](https://www.phocuswright.com/About-Us/Copyright/)에서 연구보고서 복제·수정·재게시의 사전 서면 허락 제한을 확인했다. 이것을 제목만의 법적 결론으로 확대하지 않되 서지 색인 허락을 자동 번역 허락으로 간주하지 않는다. 유료 본문을 읽거나 연구 결과를 추정하지 않았다.
- [Long-Haul Travel Barometer 3/2026](https://etc-corporate.org/reports/long-haul-travel-barometer-3-2026/): 제목의 회차/연도는 보존하며, 별도 한국어 표제·번역 공개 범위를 확인하지 못해 원제 유지. 시도한 약관 경로 404를 기관 전체의 이용불가나 포괄 허락으로 판정하지 않았다.
- Phocuswright 65건, ETC 27건은 모두 보류다. 자료 신뢰도 평가가 아니라 **추가 표제 편집/사용 범위 미완료**라는 뜻이다. 초안 한국어 번역문도 저장하지 않았다.

공식 법적/소개/서지 접근 결과는 [rights-evidence.json](rights-evidence.json)에 있다. 기사 본문·PDF·유료 보고서 내용·미승인 한국어 번역문을 문서 자산에 복제하지 않았다.

## 3. 표시 계층과 승인·철회

- `content_localization.json`: 코드 소유 검토 목록. 한글 없는 원제 103건을 URL·원제 SHA·출처·발행일로 추적한다. 승인 2건만 ko_title을 가진다. 보류/철회 항목에는 한국어 초안을 넣지 않는다. 편집 이력은 상태와 표제 해시를 남긴다.
- `tools/build_content_locale.py`: 승인/권리/정확성·숫자·기관 토큰·원제 SHA/날짜/출처 일치를 검증한다. 기존 PublicationGate/PR #21 공급 경로 권리 및 Research 현재 게시 정책도 **호출해 확인**하고, 원문이 공개될 수 없는 표제는 생성하지 않는다. 해당 게이트 구현은 변경하지 않았다.
- `site/assets/content-localization.json`: 위 검증을 통과한 **코드 소유 공개 표시 자산**. 현재 승인된 2건과 검증된 발행처 구분만 포함한다. 미승인 번역은 없다.
- `site/content-locale.js`: 원제와 정확히 결합되는 표제만 반환한다. 중복 키·잘못된 연도/기관/출처/날짜·미승인·철회·잘못된 근거 URL 등은 원제로 돌아간다. 원본 객체를 수정하지 않는다.

기존 pipeline.json의 운영 JSON **30개(공개 12+비공개 18)**를 늘리지 않았다. 새 자산은 site/data가 아니라 기존 코드/assets 복사 경로로 Pages에 포함되는 파일이다. 별도 운영 파일·data/live 스키마/마이그레이션·수집기·Actions 변경은 없다. JSON 형식이지만 **운영 원장이나 수집 결과 파일이 아니다**.

### 편집 절차·복구

1. 승인 전에는 한국어 초안을 Git 저장소/공개 자산에 기록하지 않는다. 원문 서지와 이용 범위·정확성을 검토한다.
2. 승인한 현재 표제만 검토 목록에 넣고 `python tools/build_content_locale.py`로 자산을 생성한다. 현재 기본 검증 입력은 기존 코드의 읽기 전용 bootstrap 원장/공개 뷰다. `--snapshot <읽기전용 복사본>`도 지원하며 운영 브랜치를 쓰지 않는다.
3. CI의 생성 일치 검사가 오래된 자산/권리 상태의 커밋을 차단한다. 새 원문이 bootstrap에 없는 추가 승인 사례는 검증 스냅샷·CI 입력 연계까지 함께 준비해야 한다. 현재 적용된 2건은 기본 입력과 실제 운영 복사본의 서지가 일치한다.
4. 철회는 `python tools/build_content_locale.py --withdraw '<원문 URL>' --kind research`로 ko_title을 제거하고 해시 기반 이력을 남긴 뒤 자산을 재생성한다. 코드/자산 변경을 같은 PR로 검토한다. 기존 site/** 배포 경로를 사용하므로 workflow를 바꾸지 않았다.
5. 런타임은 기존 뉴스/Research/브리핑 갱신 때 승인 자산도 갱신한다. 열린 화면/모달에도 상태를 반영하며, 자산 요청 실패·잘못된 JSON이면 **승인 표제를 캐시로 유지하지 않고 원제를 표시**한다. 기존에 검증한 발행처 정보만 유지할 수 있다.
6. 원제나 발행일이 정정되어 결합 조건이 달라지면 해당 표제를 적용하지 않는다. 검토 이력은 코드 소유여서 동일 URL 재수집으로 덮어쓰이지 않는다. 다시 검토해야 한다.
7. 이전 UI로 되돌려도 원제 데이터는 그대로다. 자산이 없으면 원문 메타데이터를 유지하는 방식으로 복구하며, 운영 원장 제목을 한국어로 되돌리는 마이그레이션은 필요하지 않다.

## 4. 검색과 화면 일관성

검색 대상은 원제 + 승인된 안내 표제 + 발행처 + 기존 카테고리/유형/키워드다. 자동 검색어 번역·추측 키워드 확장은 없다. 원제의 영문 검색은 안내 표제가 적용되어도 그대로 동작한다.

- `OECD Tourism Trends and Policies 2026`: 원제로 해당 1건 검색.
- `OECD 관광 보고서`: 두 승인 안내 표제로 2건 검색.
- Phocuswright 등 원제가 유지된 자료도 기존 한국어 분야/키워드로 탐색할 수 있으나, 승인하지 않은 번역어가 검색된다고 보장하지 않는다.
- 출처 구분·기존 필터·검색·10/20 페이지네이션을 합쳐도 범위·건수·페이지를 함께 계산한다. Research의 빠른 구분과 기존 기관 구분 select는 같은 상태를 쓴다.

홈/Newsroom/상세 모달/Research/현재 브리핑 후보는 같은 표시 함수를 사용한다. 실제 뉴스 한국어 표제는 현재 0건이지만, 격리 브라우저에서 기존 원문에 테스트 표제만 결합해 세 화면과 현재 후보의 일치·원제 표시를 확인했다. 이 테스트 표제는 운영 JSON/공개 자산/스크린샷에 넣지 않았다.

**확정 브리핑 날짜를 선택하면 안내 표제를 소급 적용하지 않고 원제를 표시·복사**한다. 원본 아카이브 자체도 수정하지 않았다. 현재 후보 복사 시 향후 안내 표제가 있는 경우 표시와 원제를 구분한다. 기존 PublicationGate/HNR 차단을 통과한 원문만 표시 대상으로 삼는다.

## 5. Before / After

[comparison.json](comparison.json)은 같은 운영 스냅샷과 기준시각의 값이다. ‘한글 없음’은 한글 포함 여부를 센 지표이지 발행처 국적 추론에 사용한 값이 아니다.

| 지표 | Before | After PR 검증 화면 |
|---|---:|---:|
| 전체 뉴스 | 63 | 63 |
| 기존 기사 구성: 국내 / 해외 발행처 | 54 / 9 | 54 / 9 |
| 한글 없는 뉴스 원제 | 9 | 9 |
| 승인 한국어 뉴스 표제 | 0 | 0 |
| 뉴스 표제 검토 보류 | 9 | 9 |
| Research 전체 / 국내 기관 / 해외 기관 | 135 / 41 / 94 | 동일 |
| 한글 없는 Research 원제 | 94 | 94 (원제 유지) |
| 승인 독립 서지 안내 표제 | 0 | 2 |
| 한국어 원제 또는 안내 표제가 우선 표시되는 Research | 41 | 43 |
| Research 표제 보류 | 94 | 92 |
| Research 전체 대비 안내 표제 제공률 | 0% | 2/135 = 1.48% |
| 영문 원제 대상 안내 표제 제공률 | 0% | 2/94 = 2.13% |
| 전체 원제 표현을 번역한 공개 표제 | 0 | 0 |
| 이 작업이 실제 운영에 반영한 표제 | 0 | 0 |

생성 2건·편집 검토 완료 2건·PR의 공개 표시 자산 2건을 구분한다. 기계 번역을 생성만 하고 승인됐다고 세지 않았다. 나머지 101건의 한국어 초안도 없다. 국가 정보 추가는 기존 9건의 구분 근거를 보완한 것으로, 새 기사/발행처 유입 성과가 아니다.

## 6. 데이터·UI 보존 및 검증

- **Python 전체 333개 통과**(기존 321 + 신규 12, Node 표시 로직 단위 검사 포함).
- **브라우저 전체 18개 suite 통과**(기존 17 + 신규 1). 320/390/768/1440px, 국내 우선/전체 최신순·구분·검색·페이지, 한/영 검색·철회/실패·원제·현재/확정 브리핑을 검증했다.
- 기존 OECD 목록 검사는 새 승인 표시 제목과 별도 원제·원문 링크가 함께 보존되는 계약으로 갱신했다. 원문 데이터 검증을 제거하지 않았다.
- 전후 합성한 **운영 JSON 30개 모두 바이트 동일**, 원본 control 포함 **31개 manifest 해시 동일**. 공개 뉴스 6필드/Research 8필드, 원장 ID·원 발행일·직접 URL, 확정 브리핑, HNR 보류 3건, Research/공식 통계가 보존됐다.
- sources.json은 기존 3개 해외 피드의 coverage 국가 정보만 추가했다. 공급원 목록·URL·이름·활성화·발견/게시 정책·주기는 동일하다.
- PR #21 Discovery Engine·PublicationGate 구현·Macro/Market Observation·Scenario 계산식·GitHub Actions/Pages는 Git 변경이 없다. PR #22의 130px 로고·세그먼트·모바일/키보드·hover/fade·SVG/Reduced Motion·sticky header 검사도 통과했다.
- API 키/번역 서비스/새 외부 런타임 호출은 없다. 발행처·표제 자산은 같은 사이트의 정적 파일이고 새 JS 타이머는 없다.
- **GitHub CI: 코드 커밋 `ab0bd54a`의 검사 3개 모두 SUCCESS** — [뉴스](https://github.com/Serhankeem/tourismnews/actions/runs/41987259190), [Research](https://github.com/Serhankeem/tourismnews/actions/runs/41987259410), [Macro](https://github.com/Serhankeem/tourismnews/actions/runs/41987259399). 운영 collect-and-publish 3개는 기존 main 전용 조건으로 SKIPPED. 후속 커밋은 결과 기록뿐이며 브라우저 18개는 별도 로컬 Chromium 검사다.

재현: `python -m unittest discover -s tests -v`, `node tests/korean-first.unit.cjs`, 격리 Pages에 `TOURISM_TEST_URL=<local URL> node tests/korean-first.smoke.cjs`. [tests.json](tests.json) 참조.

## 7. 화면 및 변경 파일

| 화면 | 이전 | 이후 |
|---|---|---|
| 뉴스 PC | [이전](screenshots/news-before-1440.png) | [국내 우선](screenshots/news-domestic-1440.png) / [해외](screenshots/news-foreign-1440.png) |
| 뉴스 모바일 | [이전](screenshots/news-before-390.png) | [국내 우선](screenshots/news-domestic-390.png) / [해외](screenshots/news-foreign-390.png) |
| Research PC | [원제](screenshots/research-before-1440.png) | [안내 표제+원제](screenshots/research-ko-1440.png) |
| Research 모바일 | [원제](screenshots/research-before-390.png) | [안내 표제+원제](screenshots/research-ko-390.png) |

[태블릿 국내 뉴스](screenshots/news-domestic-768.png) / [해외 뉴스](screenshots/news-foreign-768.png) / [Research](screenshots/research-ko-768.png). 스크린샷은 같은 원문 데이터의 UI 비교이며 운영 배포 화면이라고 표시하지 않는다.

주요 변경은 site/content-locale.js·assets/content-localization.json·기존 렌더러/필터/스타일, 코드 소유 content_localization.json·생성 도구, sources.json의 국가 메타데이터, 관련 테스트와 이 문서다. site/data·collector_state·src·workflow는 수정하지 않았다.

## 8. 남은 과제·사용자 조치

국내 우선 탐색과 원제 보존 계층은 완료했지만 **103건 전체 한국어화는 미완료**다. 나머지 뉴스 9건·연구자료 92건에는 공식 한국어 제목, 제목 변형/번역 허락, 또는 개별적으로 유용하고 정확한 독립 안내 표제 검토가 필요하다. 유사한 범용 안내 문구를 대량 생성해 수치를 채우지 않는다.

Phocuswright 등에는 서지정보와 보고서 내용의 권리를 구분해 확인해야 한다. OECD의 개별 번역/가공 범위를 더 확인한 경우에도 숫자·기관·시점과 요구된 출처/면책 조건을 검증한 후 별도 승인해야 한다. API 키는 필요하지 않으며 이번에 외부 문의·계약·유료 접근을 실행하지 않았다.

운영 반영은 사용자의 PR 승인/병합 이후 기존 배포 체계를 통해 별도 확인해야 한다. 현재 실제 Pages와 data/live에 이 작업을 반영하지 않았다.
