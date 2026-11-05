# Tourism News Discovery Engine v0.1 — 통합 발견 계층

## 결과와 범위

**신규 실연동 공식 공급 경로 0곳, 신규 확인 발행기관 0곳, 신규 공개 가능 뉴스 0건이다.** 국내 새 기관·매체 2–3곳 확보 목표는 달성하지 못했다. 공통 발견 계층과 권리 분리·기존 게시 파이프라인 연결은 구현했으나, 실제 공공 API의 명세/이용조건 확인 및 인증·제휴 단계가 남았다. fixture 성공을 실연동으로 집계하지 않는다.

- 최신 main: PR #20 병합 커밋 `a1b8f43`에서 `feat/tourism-news-discovery-v01` 생성.
- 운영 기준: 읽기 전용 `data/live` `c32bcddd23f69c8047b7f34c5bb9ebdd79216585`.
- 동일 실응답·동일 평가시각 **2026-11-05 14:32:01 KST**으로 수정 전후를 비교했다. 원장 수는 코드 상수가 아니라 스냅샷에서 읽었다.
- **실제 운영 JSON/data-live 쓰기, main 병합, Pages 배포는 하지 않았다.** `pipeline.json`의 운영 JSON 허용 목록 30개도 바꾸지 않았다.

## 1. 기존 구조의 한계

기존 `src/discovery.py`의 RSS/API 파서는 제목·URL·발행일을 가져오고, `src/engine.py`가 관련성·날짜·권리·중복을 판정한 뒤 PublicationGate로 공개 6필드를 투영한다. PR #19는 운영 데이터를 data/live에 분리했고, PR #20은 발행처 식별자와 도메인 검증·다양성 지표를 추가했다.

현재 국내 공개 발행처는 전문매체 3곳과 공공 2곳이며 국내 뉴스의 88.89%가 상위 3곳에 집중된다. 일반 경제 RSS 한 페이지의 관광 후보가 적다는 점 외에도, **RSS를 읽을 수 있다는 사실이 공개 DB 이용허락을 뜻하지 않는 문제**가 있다. 통합 API도 공급 경로와 원 발행기관·권한을 별도로 확인해야 한다.

## 2. 공식 경로 실증 — 안내 페이지와 API 성공 구분

HTTP·robots·응답 크기/해시는 [http-evidence.json](http-evidence.json)에 있다. 원문/검색 화면 대량 수집, 차단 우회, 본문·사진 수집 및 AI 요약은 하지 않았다. 응답 원본은 검증 공간 `/tmp`에만 보관하고 저장소에는 넣지 않았다.

| 경로 | 실제 접근 결과 | 항목·인증·갱신·원문·이용조건 검증 | 결정 |
|---|---|---|---|
| [문체부 15개 기관 보도자료 API, 15105015](https://www.data.go.kr/data/15105015/openapi.do) | robots.txt HTTP 503에서 중단 | 현재 서비스 URL, 실제 응답 필드, 인증 방식, 갱신주기, 기관 식별자·직접 링크·이용허락 **미확인**. 등록명만으로 한국관광공사 자료 제공을 확정하지 않음 | 최우선 공공 API 실증 시도 실패. endpoint=null, 비활성·review. API 호출 성공 0 |
| [경기도 보도자료 현황 API, 15034926](https://www.data.go.kr/data/15034926/openapi.do) | robots.txt HTTP 503 | 같은 이유로 상세 계약/필드/KEY 파라미터/이용조건 미확인 | endpoint=null, 비활성·review |
| [경기데이터드림](https://data.gg.go.kr/), [공식 OpenAPI 호스트](https://openapi.gg.go.kr/) | 두 호스트 모두 robots.txt 503 | 검증된 보도자료 서비스 경로 확보 못함. API 이름이나 KEY 요청 형식을 추측하지 않음 | 대체 경로도 보류 |
| [문화공공데이터광장](https://www.culture.go.kr/data/main/main.do) | HTTP 503 | 문체부 통합 API 명세 대체 확보 실패 | 보류 |
| [한국관광공사 TourAPI](https://api.visitkorea.or.kr/) | 홈페이지 HTTP 200, 5,710바이트 앱 진입 HTML | 산업 보도자료 API/필드/실제 데이터 미검증. 관광지·행사 정보와 산업 뉴스를 동일시하지 않음 | API 실연동 아님 |
| [정책브리핑 공식 보도자료 RSS](https://www.korea.kr/rss/pressrelease.xml) | robots.txt 503 | 통합 공공 발표 대체 후보이나 현행 응답·기관/직접 링크·재사용 조건 미확인 | 우회하지 않고 보류 |
| [BIG KINDS](https://www.bigkinds.or.kr/) | 홈페이지 200, HTML 안내 링크 확인 | 공개 홈페이지는 외부 뉴스 공급 API 계약이 아님. 공식 외부 서비스용 엔드포인트·신청 승인·보관/재공개 범위·가격 미확인. 이용약관은 화면 내 팝업 링크 | 내부 검색/개발자 인터페이스를 역추적하거나 호출하지 않음. 비활성 |
| [네이버 기존 뉴스 검색 문서](https://developers.naver.com/docs/serviceapi/search/news/news.md) | 문서 200 | 기존 문서는 HTTPS GET `/v1/search/news.json`, title/originallink/link/pubDate, 클라이언트 ID·시크릿 헤더를 설명. 이는 **현재 신규 신청 가능/운영 중/저장·재공개 가능의 검증이 아님** | 기존 형식 파서 fixture만 구현 |
| [네이버 뉴스 API 무인증 점검](https://openapi.naver.com/v1/search/news.json?query=%EA%B4%80%EA%B4%91%EC%82%B0%EC%97%85&display=1) | robots_disallowed로 API 요청 전 중단 | 인증 오류 응답이나 성공 뉴스 응답을 받은 것이 아님 | robots 우회/헤더 위장 안 함 |
| [NAVER API HUB](https://apihub.naver.com/) 및 www 호스트 | robots 전송 확인 실패 | 현행 이관·신청·요금·보관·외부 공개 조건 미확인. 기존 문서로 현행 조건을 대체하지 않음 | 비활성·review |
| 네이버 공식 공지/약관 안내 경로 | 공지 경로는 HTTPS→HTTP 전환 차단, `/terms` 404 | 이관 공지·현행 약관 본문 확인 못함 | 성공·허용으로 표시 안 함 |
| [뉴스와이어 API](https://www.newswire.co.kr/coalition), [문서](https://www.newswire.co.kr/coalition/document), [API 약관](https://www.newswire.co.kr/coalition/policyterms) | 세 안내 모두 200 | 실제 공식 POST/HMAC 계약과 이용 승인 절차 확인. 인증된 API 데이터 응답은 **미수신** | 전용 수신 생명주기가 필요해 단순 GET 어댑터로 연결하지 않음 |

### 공공 API의 다음 검증 항목

문체부·경기도에 대해서는 현재 등록정보의 명세 파일/서비스 URL을 확보해야 한다. 서비스가 API 키를 요구하는지와 정확한 요청 키 이름도 현재 응답으로 확인하지 못했다. 문체부 자료를 전부 한국관광공사 발행으로 간주하거나 출처가 없는 결과를 공공 뉴스로 게시하지 않는다.

한국관광공사·지역관광조직의 홈페이지/RSS 제약은 PR #20 조사표도 참고했지만, 과거 관측을 이번 신규 API 성공으로 재집계하지 않았다. 관광·항공·숙박 정책을 다룰 수 있는 정책브리핑도 이번에는 robots 503으로 실패했다. 따라서 최소 1개 통합 공공 API의 **실데이터 성공 검증은 미완료**다.

### 뉴스와이어: 유망하지만 별도 승인·어댑터 필요

공식 문서는 `POST https://www.newswire.co.kr/api/v1/request`, 수신 `/api/v1/send`, 전송 결과 확인 등을 안내한다. partner_id, 발급 API Key를 이용한 SHA-256 HMAC, `X-HMAC`·`X-Timestamp`가 필요하다. 요청 생성은 이전 request_id를 무효화할 수 있으므로 승인·인증 없이 임의 POST를 하지 않았다.

- title/press_time/url/company 정보, 수정(update)/삭제(delete) 이벤트, 최대 100건/회, 장기 미수신 과거 자료 최대 1,000건 등의 문서 설명을 확인했다. 이 수치는 우리에게 수신된 기사 수가 아니다.
- company는 발표기관 정보이지 반드시 독립 취재 언론사가 아니다. url·press_time은 문서에서 선택 항목이므로 없으면 일반 뉴스 자동 게시를 보류해야 한다.
- 5–10분 간격 수신 권고와 수정·삭제 처리 계약이 있으므로 기존 2시간 배치에 단순 GET을 붙이는 것으로 완료할 수 없다. 현재 뉴스 스케줄은 바꾸지 않았다.
- 약관 제3조에 이용 신청·심사·승인이 명시돼 있다. 제6조는 승인 이용자의 자체 웹/앱/CMS 및 내부 모니터링 활용을 설명하지만, 유료 재판매/경쟁 서비스 제공·출처 은폐·권리 침해·호출 제한 우회를 제한한다. **우리 프로젝트의 승인·무료 여부·별도 보관 조건·메타데이터만 사용하는 범위는 미확인**이다.
- 본문/사진은 사용하지 않을 계획이며, 사진 다운로드/자체 호스팅 지침이 존재한다고 사진 수집을 추가하지 않았다. API의 수정·삭제 의무를 수용하는 별도 설계가 선행돼야 한다.

## 3. 산업별 발견 계획과 관련성

`QUERY_GROUPS`는 관광 정책·고용/예산, 인바운드·아웃바운드 수요/소비, 항공 노선/좌석/여객, 호텔 공급/투자/실적, OTA·여행기업 실적/M&A, MICE 국제회의, 관광수지/수입/지출 묶음을 제공한다. 일반 경제 전체 피드를 더 많이 긁는 방식 대신 경로별 검색 기능과 공식 분야 분류가 확인된 후 배치할 계획이다. **이번에는 실제 검색 API로 전송하지 않았다.** 요청 파라미터 이름을 추측해 자동 생성하지 않고 검증된 provider.queries만 사용할 수 있다.

Direct/Indirect/Irrelevant, 한국 직접 관련 editorial tier와 기존 승인 규칙은 바꾸지 않았다. 국내 발행처라는 이유로 승격하지 않는다. 할인·여행 팁·일반 기업 AI·지역 행사 일정 및 해외 세제/예산을 국내 핵심 뉴스로 올리지 않는 기존 테스트를 유지했다. 새 fixture도 국내 발행처가 다룬 해외 숙박정책을 reference로 유지한다. 통계/공시는 뉴스 계약과 구분하며 `record_type=news`가 확인되지 않은 새 공급 경로는 호출하지 않는다.

## 4. 구현 구조

```text
비활성/미승인 경로 → 호출 차단
승인 경로 → HTTPS/robots/인증/호출 예산 → Provider Adapter
→ 제목·원 발행일·직접 URL 정규화 → 발행기관 코드의 검증된 매핑
→ 기존 관광 관련성 판정 → URL/공식 ID 중복 검사 → 4개 권한 판정
→ 기존 engine.execute → 기존 Indirect 승인·PublicationGate → 공개 6필드
```

- `src/news_discovery.py`: RSS 재사용, 명시적 계약의 JSON/XML 목록, 기존 네이버 형식의 정규화 어댑터. JSON/XML 범용 fixture는 **문체부·경기도의 실제 필드 명세를 대신하지 않는다**. 해당 설정의 response.contract_verified는 false다.
- `discovery_providers.json`: 코드 소유 설정 파일. 문체부·경기도·네이버·빅카인즈·뉴스와이어 후보 5개 모두 enabled=false이며 모든 권한이 review다. 운영 등록/실연동 공급원 수에 포함하지 않는다. 뉴스와이어는 `unsupported_signed_delivery`로 별도 전용 구현이 필요함을 표시했다.
- `src/engine.py`: 기존 RSS 흐름을 보존하며 승인된 Batch만 기존 source_id별 피드에 결합한다. 원 RSS가 실패하고 승인된 API 자료가 있을 때도 fallback 사실을 남기고 partial로 구분한다. provider가 전부 비활성이면 API 호출도 없고 기존 실행 결과도 동일하다.
- `src/visibility.py`, `src/pipeline/policy.py`: 현재 공급 경로의 권한과 원 발행처 매핑을 수집뿐 아니라 코드 전용 Pages 재투영/검증 시에도 확인한다. 경로 삭제·비활성화·공개 승인 철회 후 기존 레코드도 숨기고 원장/권리 전환 이력은 보존한다.
- `.github/workflows/deploy.yml`: provider 설정만 변경해도 기존 main 전용 정책 재투영이 작동하도록 **push 경로 1줄만** 추가했다. 스케줄·권한·공유 큐·트랜잭션·배포 job은 그대로다. 이 PR에서 운영 배포는 실행하지 않았다.

### 공급 경로와 발행기관

API의 publisher_code는 검증된 publishers 매핑의 source_id/publisher_id로 연결해야 한다. source 등록과 매핑 모두의 원문 도메인 화이트리스트·근거가 일치해야 한다. 중계 도메인, 접미사 위장 도메인, 사용자정보/인증 쿼리가 있는 URL, 기관 코드 누락은 보류한다. 네이버 originallink도 발행기관 정보가 없는 한 자동 게시하지 않는다. 미확인 기관은 독립 발행처로 세지 않는다.

중복은 기존 정규화 URL과 원장 ID를 재사용한다. 공식 ID는 **발행처 + 검증된 ID namespace + 공식 ID**로 비교해, 다른 API에서 우연히 같은 숫자 ID를 사용한 것을 지우지 않는다. 동일 발행처의 여러 피드도 publisher_id로 묶는다. 이미 검증된 API 레코드가 RSS에 다시 등장해도 API의 권리 경로·식별자·원 발행일을 없애거나 다시 쓰지 않는다. 유사 제목만으로 다른 발행처의 기사를 삭제하지 않는 PR #20 정책도 유지한다.

## 5. 네 가지 권한과 저장 경계

각 capability는 status, evidence_url, basis, verified_at을 요구한다. API 수신/DB 이용허락과 발표기관·제3자 콘텐츠의 공개 권리는 별도로 확인해야 한다. 법적 자동 승인을 판정하는 기능이 아니다.

| 상태 | 접근·임시 처리 | 후보 제목·URL·기사 ID 영속 저장 | 공개 |
|---|---|---|---|
| blocked | 비활성 또는 접근/처리 미승인: 호출 안 함 | 새로 저장 안 함 | 불가 |
| discovery_only | 두 권한이 확인된 범위에서 메모리 처리 | **저장 안 함**, 숫자 집계·공급 경로 단위 시각만 | 불가 |
| manual_review | 접근/처리 및 저장 허락이 있으나 공개 review | 이번 버전은 여전히 후보 메타데이터를 저장하지 않음 | 불가 |
| publishable | 네 권한 모두 검증 + 원 발행처 기존 publication 승인 | 영구 메타데이터 보관 허락이 확인된 건만 기존 원장으로 전달 | 기존 관련성·날짜·Indirect 승인·PublicationGate까지 통과해야 가능 |

기간 제한 저장 허락을 무기한 저장으로 바꾸지 않는다. 이 버전은 TTL 삭제 스케줄러를 구현하지 않았으므로 store.retention=`permanent_metadata` 근거가 없으면 공개/영구 저장 경로에 진입하지 못한다. 본문·사진·요약·미승인 후보의 제목/URL/기사별 해시는 영구 저장·공개하지 않는다. 진단에는 고정 오류 코드와 집계만 남긴다.

## 6. 운영 효율과 보안

- 기존 뉴스 2시간 간격과 10:30 브리핑 스케줄 보존.
- 새 계층은 기본 전체 8회, 공급 경로별 기본 1회 시도로 제한한다. query plan이 예산에 다 들어오지 않으면 일부만 실행하고 성공 커서를 전진시키지 않고 전체를 defer한다.
- 확인된 갱신 간격 이전에는 not_due로 생략한다. since 파라미터는 실제 계약에 명시된 경우만 쓰고 1일 중첩 기간을 두어 중복을 검증한다.
- 요청 실패·스키마 오류/인증 오류 envelope와 정상 빈 결과를 구별한다. XML은 기대 루트/컨테이너, 계약에 있는 성공 코드를 확인한다. 실패한 multi-query는 해당 경로의 Batch와 성공 시각을 확정하지 않으며 다른 경로는 계속 실행한다.
- API 요청에는 숨은 자동 재시도를 추가하지 않았다. 429/503의 Retry-After를 최소 커서에 보존해 이후 실행도 defer한다. robots crawl-delay/request-rate도 지킨다.
- 키는 환경변수에서만 읽는다. HTTPS·허용 엔드포인트·robots를 확인한 후 인증을 붙이고, API 인증 요청은 리디렉션을 따라가지 않는다. 응답은 최대 2MiB, 예외 URL/키/응답 본문은 로그·공개 지표에 내보내지 않는다.
- calls는 loader 호출 시도 수다. 키 누락/robots 차단이면 실제 API HTTP 전송은 그보다 적을 수 있다. 이번 신규 경로의 실제 인증 API 요청은 0회다.
- 자동 페이지네이션, API별 삭제/정정 이벤트, ETag 캐시 및 외부 계약의 TTL 저장은 미구현이다. 완전한 아카이브/최종 운영 준비로 표시하지 않는다. 해당 기능이 필요한 API는 전용 계약/처리를 확인하기 전 활성화하면 안 된다.

## 7. 스키마·마이그레이션·복구

**새 운영 파일은 없다.** pipeline.json의 12개 공개 + 18개 비공개 JSON 허용 목록을 유지한다. 코드 설정 discovery_providers.json은 data/live에 복제하는 운영 JSON이 아니다.

| 기존 파일 | 선택적 추가 데이터 | 호환성/복구 |
|---|---|---|
| collector_state/archive.json, discovery.json | 승인 레코드의 discovery_origin: provider_id, publisher_code, publisher_id, official_id, official_namespace | 기존 필드/ID/URL/원 발행일 보존. 없는 레거시 레코드는 기존 출처 권리 규칙 그대로 |
| collector_state/source_metrics.json | discovery_providers: 공급 경로별 마지막 성공 시각·시도/성공/호출 누계·Retry-After 시각 | 원문·쿼리·후보 제목/URL/ID·응답 캐시 없음. 기존 sources 블록 보존 |
| collector_state/run_summary.json, site/data/health.json | 선택적 공급 경로 집계, 후보/보류/전달/실제 원장·공개 수의 구분 | 기사 공개 필드가 아님. 미승인 결과의 문자열은 넣지 않음 |
| publication_visibility 원장/manifest | 기존 상태 전환 구조에 provider approved/held 사유를 반영 | 원장 삭제 없이 공개 차단/정상 복구 |

신규 활성 경로가 없으므로 현재 운영 데이터에는 마이그레이션을 실행하지 않았다. 향후 승인 후 첫 실행이 선택적 필드를 붙일 수 있으며, 기존 pipeline 검증·manifest·일반 FF 영속 저장·복원 절차를 그대로 사용한다. 코드 전용 배포에서도 현재 provider 설정으로 재투영한다.

복구는 기존 data/live 스냅샷과 manifest로 수행하고 이력 필드를 제거하지 않는다. **discovery_origin이 생긴 뒤 구버전 게이트로 단순 롤백하면 권리 차단을 잃을 수 있다.** 그런 경우 provider 지원 게이트를 유지하거나, 영향받는 발행처의 기존 publication도 review로 내려 구버전에서도 차단한 뒤 복구해야 한다. 설정의 키만 지우거나 비활성화하고 구버전이 안전하다고 가정하지 않는다. 이 절차도 이번 실제 운영에는 실행하지 않았다.

## 8. Before / After와 실제 자료

[comparison.json](comparison.json)은 운영 스냅샷의 원장과 같은 실제 응답으로 계산했다. 새 API가 작동하지 않았으므로 그 API의 후보 발행량은 **미측정(null)**이며 성공한 빈 결과 0건이 아니다.

| 지표 | Before | After 격리 실행 |
|---|---:|---:|
| 기존 등록 공급원 | 26 | 26 |
| 같은 실응답 수집 성공 | 24/26 | 24/26 |
| 신규 실연동 공식 경로 / 새 원 발행기관 | 0 / 0 | 0 / 0 |
| 신규 API의 관광 후보량 | 미측정 | 미측정 |
| 신규 API에서 공개 권리 확인된 후보 / 새 공개 가능 뉴스 | 0 / 0 | 0 / 0 |
| 공개 뉴스 | 63 | 63 |
| 국내 발행처 / 국내 공개 뉴스 | 5 / 54 | 5 / 54 |
| 최근 7일 국내 뉴스 | 25 | 25 |
| 한국 직접 관련 뉴스 / 최근 7일 | 30 / 12 | 30 / 12 |
| 경제 / 종합 / 관광전문 / 공공 / 민간기업 (국내 54건 분모) | 0 / 0 / 48 / 6 / 0 | 동일 |
| 위 구성비 | 0 / 0 / 88.89% / 11.11% / 0 | 동일 |
| 국내 상위 3개 발행처 집중도 | 48/54 = 88.89% | 동일 |
| 원장 / 발견 기록 | 76 / 2774 | 77 / 2824 |

원장 +1은 Booking SEC 공시이며 국내 뉴스 성과가 아니다. 같은 기존 경로에서 918개 수신 관측, 신규 발견 50, 중복 관측 406으로 고유 발견 관측 456 중 중복률 89.04%였다. 뉴스 관련성 분류 451 관측 중 Direct 32 / Indirect 0 / Irrelevant 419(비관련률 92.90%). 이는 새 검색 API 성과가 아닌 기존 공급 경로의 재현 결과다. HNR 원장 뉴스 3건은 모두 권리 보류로 남는다. 재실행의 신규 발견·공개 뉴스·공시는 모두 0이었다.

수정 전후 **실행 summary 전체와 Newsroom 기사 배열 모두 동일**했다. API가 비활성일 때 기존 동작을 바꾸지 않는 것을 확인했다. 새 API의 중복/권리 보류율은 분모 자체가 없어 산출하지 않았다. fixture의 기관 2곳·후보 2건은 아래 기술 검증일 뿐 실제 KPI에 합산하지 않는다.

실제 원문 사례는 기존 승인 경로의 [에어부산 3분기 실적](https://www.traveldaily.co.kr/news/articleView.html?idxno=72573), [제주항공 3Q 영업이익](https://www.traveldaily.co.kr/news/articleView.html?idxno=72557), [MICE 예산과 국회·업계 투자 촉구](https://www.traveltimes.co.kr/news/articleView.html?idxno=500645)다. 새 API에서 확보한 사례라고 표시하지 않는다. 제목·발행일·직접 링크는 기존 공개 6필드로 유지하며 본문은 가져오지 않았다.

## 9. 검증과 보존 증거

- **Python 전체 321개 통과**, 그중 신규 Discovery 24개. 권한 4분리·저장 경계·복수 발행기관·원문 검증·고유 URL/공식 ID namespace·RSS 중복 시 provenance/원 발행일 보존·철회/복구·누락 키·HTTPS/robots/리디렉션·응답 크기·호출 예산·갱신 간격/증분·Retry-After·실패 계속 실행·인증/오류 응답과 정상 빈 결과 구분·통계 제외를 검증했다.
- **기존 브라우저 16개 suite 통과**. 임시 Pages 산출물에서 Newsroom/브리핑/Research/Macro/Weather/UI/모바일·PC·공개 6필드와 HNR 차단·PR #20 다양성 지표를 검증했다. API fixture를 공개 DB에 넣지 않았다.
- 기존 PR #19 전체 파이프라인 테스트 및 validate(after, before=baseline) 통과. 뉴스 63, 원장 77, 발견 2824, Research 135, Macro 483개 관측. 원 ID·URL·발행일·최초 발견/게시 시각·발견 기록·권리 전환·확정 브리핑·리서치/통계 이력을 보존했다.
- Research 공개/원장, Macro 공개/원장, 확정 브리핑 아카이브/선정 원장은 **바이트 동일**. 원본 운영 스냅샷 31개 manifest 해시(control 포함)도 그대로다. site/, collector_state/, sources.json, pipeline.json 및 모델/DB/로고는 Git 변경이 없다.
- 변경한 deploy.yml 단독 actionlint 통과. 전체 lint에서는 기존 actionlint 1.7.12가 기존 pipeline.yml의 신형 concurrency.queue 키를 인식하지 못했다. 해당 기존 큐를 변경하지 않았으며 실제 GitHub CI를 별도로 확인한다.
- GitHub CI는 PR 제출 후 확인 결과를 아래에 추가한다. 로컬 브라우저 검사와 GitHub Python CI는 구분한다. PR에서 운영 수집/배포는 실행하지 않는다.

재현: `python -m unittest discover -s tests -v`, 새 계층만 `python -m unittest discover -s tests -p test_news_discovery_v01.py -v`. 브라우저는 PR #19의 격리 Pages 합성 후 `TOURISM_TEST_URL=http://127.0.0.1:<port> node tests/<suite>.smoke.cjs`. 테스트 문서 [tests.json](tests.json) 참고. 실제 기사·API 응답 원본은 커밋하지 않았으므로 다른 시점의 실호출 결과는 달라질 수 있다.

## 10. 사용자 조치와 운영 전환 전제

1. 문체부/경기도 공식 API 명세·HTTPS 서비스 URL·응답 필드·최신 자료 기준·발행기관 코드·직접 링크·인증·갱신·이용허락을 확보해야 한다. robots/서버 오류가 해소된 뒤 제한을 준수해 다시 실증한다. 현재 등록정보 접근 실패를 API 서비스 폐지라고 단정하지 않는다.
2. 네이버는 현행 API HUB 이관·신규 신청·보관/외부 공개·제3자 권리 조건을 확인해야 한다. 기존 검색 문서나 단순 클라이언트 키 보유만으로 활성화하지 않는다. 빅카인즈는 외부 서비스용 정식 제공/제휴 범위를 확인해야 한다.
3. 뉴스와이어는 서비스 목적·메타데이터 6필드 사용·원문 링크·본문/사진/AI 미사용·보관/수정/삭제 정책으로 승인을 신청해야 한다. 비용·승인 가능 여부는 미확인이다. 이번에 신청/문의·계약 체결은 하지 않았다. HMAC 전용 요청/수신·수정/삭제 처리는 후속 구현이다.
4. 현재 **등록해야 할 필수 GitHub Secret은 없다**. 실제 계약 확정 뒤 사용할 제안 이름은 문체부 `TOURISM_MCST_PRESS_API_KEY`, 경기도 `TOURISM_GG_PRESS_API_KEY`, 네이버 `TOURISM_NAVER_CLIENT_ID`/`TOURISM_NAVER_CLIENT_SECRET`, 뉴스와이어 `TOURISM_NEWSWIRE_PARTNER_ID`/`TOURISM_NEWSWIRE_HMAC_SECRET`이다. 인증 방식이 미확인인 공공 API의 이름은 계획값이며 바인딩도 없다. 실제 키를 코드·PR·로그·공개 JSON에 기록하지 않는다.
5. Secret 등록만으로 동작하지 않는다. 공식 계약별 adapter/auth 바인딩·응답 스키마·다중 발행처 등록/도메인 검증·네 권한 근거를 채우고 격리 실호출을 통과한 뒤, 사용자 승인으로 설정 및 기존 workflow의 필요한 env 바인딩을 연결해야 한다. 이번에는 후보 키를 workflow에 노출시키지 않았다.
6. 승인된 기관부터 2–3곳의 실제 공급량·공개량을 검증하고, 호출 주기/페이지네이션/수정·삭제 의무를 계약에 맞춰 구현한다. 현재 단계는 **확장 가능한 기술 기반 구현, 실제 공급 확대 미완료**다. 이후 사용자가 병합·운영 전환을 승인한 뒤 운영 수집·data/live 영속 저장·Pages 지속 반영을 별도로 검증해야 한다.
