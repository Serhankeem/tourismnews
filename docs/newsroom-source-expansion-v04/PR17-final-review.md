# PR #17 병합 전 최종 검수

> 이후 재검수에 따라 기존 HRN 3건도 공개 대상에서 제외했습니다. 이 문서는 이전 검수 이력이며, 현재 상태(공개 47건/브리핑 3건)는 [PUBLICATION-GATE.md](PUBLICATION-GATE.md)를 확인하세요.

기존 PR 브랜치 `feat/newsroom-source-expansion-v04`에서만 수정했습니다. 새 PR·main 병합·신규 수집원 발굴·기사 추가 수집은 하지 않았습니다.

## 1. 영문 키워드

기존 `matches()`는 용어 패턴을 소문자로 만들지만 `public_record()`가 영문 원문 제목을 그대로 넘겨 대소문자가 맞지 않았고, 용어 사전에도 신생 기사에 필요한 산업 구문/기업명이 부족했습니다.

`src/publication.py`에 제목만을 읽는 전용 추출을 추가했습니다. 기존 영문 산업 구문과 검토한 관광기업명 사전을 대소문자 구분 없이 **단어 경계**로 찾고, 겹치는 구문은 긴 구문을 우선합니다. 출력은 실제 제목의 철자·대소문자를 그대로 사용합니다. 일반 단어 Global/Growth/Revenue/AI/Platform/Opens, 제품명 추측, 번역 태그, 국가·출처·카테고리 기반 추론은 하지 않습니다. 애매한 단독 Booking은 제외하고 Booking Holdings 등 확인 가능한 기업명을 사용합니다.

한국어가 포함된 제목은 이전 추출 방식을 그대로 사용하여 기존 한국어 뉴스 **42건의 keywords가 완전히 동일**합니다. 기존 44건의 제목·출처·발행일·URL·카테고리는 모두 동일합니다. 기존 영문 GOV.UK 1건도 제목의 `air passengers` 키워드만 보강됐습니다.

| 신규 기사 | 최종 keywords | editorial tier |
|---|---|---|
| Global Air Passenger Demand Falls 0.5% in September | Air Passenger Demand | global_major |
| IHG Opens Kimpton Al Rowda Doha Hotel in Qatar | Kimpton · Hotel · IHG | reference |
| Grand Hyatt The Red Sea Opens on Shura Island | Grand Hyatt | reference |
| IDS Next Launches Pomolabs, New AI-Native Intelligence Platform for Hospitality Operations | Hospitality Operations | reference |
| Accor & Corinthia Group launch strategic collaboration to bring Verdi Hotels to Handwritten Collection | Corinthia Group · Hotels · Accor | reference |
| Hyatt Introduces Enhanced Hyatt Leverage Platform for Small-and-Midsize Business Travel | Business Travel · Hyatt | reference |

공개 `news.json`/`newsroom.json`과 현재 `briefing.json`의 파생 키워드만 갱신했습니다. 키워드 보완 자체로 수집 시각·발행일·정렬·선정·기사 수를 바꾸지 않았으며 공개 필드는 6개 그대로입니다. 날짜별 확정 아카이브는 빈 키워드가 있더라도 변경하지 않았습니다.

## 2. 산업 관련성과 중요도 구분

실제 신규 6건은 relevance_label이 모두 Direct이지만 이는 관광산업 대상이 명확하다는 뜻이며, 한국 핵심 뉴스나 세계 시장 전체의 주요 변화라는 뜻이 아닙니다.

기존 `exposure()`를 그대로 적용하면 1건(global air passenger demand의 세계 범위·정량적 변화)만 global_major이고, 단일 호텔 개관 2건 및 기업 기술/제휴 발표 3건은 reference입니다. 한국 관련성을 입증하는 제목 근거가 없으므로 korea_direct는 0건입니다. 기존 브리핑 선정기에 이 6건만 입력하면 해당 세계 수요 변화 1건만 후보가 됩니다. 호텔 개관·일반 기업 실적에 숫자나 Worldwide/Global이 있다는 이유로 승격되지 않는 회귀도 통과했습니다.

따라서 editorial/Direct·Indirect·Irrelevant 코드나 브리핑 기준은 변경하지 않았고 산업뉴스를 대량 제외하는 필터도 추가하지 않았습니다. Newsroom/홈 대표 3건의 **발행일 최신순**은 중요도 순서가 아니며 PR #15 정렬을 유지합니다. 키워드는 중요도·국가 연계·브리핑 승인 근거로 사용하지 않습니다.

## 3. 권리 조건 재검토 — 현재 설정

### Hospitality Net: 지정 RSS 범위의 제한적 로컬 판단 유지

- [RSS 안내](https://www.hospitalitynet.org/rss)는 피드를 RSS 리더로 읽거나 외부 웹사이트에 통합할 수 있다고 명시합니다.
- [일반 이용약관](https://www.hospitalitynet.org/terms-conditions) **5.2**는 허락 없는 자동 접근을 금지하고 **6.2**는 허락 없는 복제·배포 및 자동 대량 추출을 제한합니다. 이전 보고서의 ‘4.3’ 표기는 잘못된 조항 번호여서 바로잡았습니다.
- 허용 근거는 이 지정 RSS 인터페이스의 명시적인 웹사이트 통합 안내입니다. 이를 선택적인 제목·날짜·출처·직접 링크 색인에 한정하고, 일반 사이트 크롤링·본문/사진/설명문 재사용·대량 아카이브 추출 권한으로 확대하지 않습니다.
- **RSS 안내와 일반약관의 우선순위/예외 조항은 명시돼 있지 않고 별도 서면 확인도 없습니다.** `status=approved`는 기존 엔진의 로컬 범위 판단용 게이트이며 제공자의 서면 허가/포괄적 라이선스 인증을 뜻하지 않습니다. 이를 `approval_authority`, `publisher_written_permission_obtained=false`, `rights_review.remaining_uncertainty`에 명시했습니다.
- 현재 무료·무광고·비상업 및 지정 피드 6필드 색인에 한해서만 유지하며, 일반 콘텐츠 사용은 여전히 불허입니다.

### Hotel News Resource: 신규 자동 게시 보류로 정정

- [XML 안내](https://www.hotelnewsresource.com/Info-Newsfeeds.html)는 indexing/research/content discovery를 명시하지만 **공개 웹사이트 재배포**의 범위를 직접 설명하지 않습니다.
- 이전 검토에서는 [개인정보 정책](https://www.hotelnewsresource.com/legal-privacy.html)을 확인했으나, 이 페이지에서 연결하는 [실제 일반 이용약관 Info-legal.html](https://www.hotelnewsresource.com/Info-legal.html)을 누락했습니다. 이번에 해당 공식 링크를 따라 읽어 보완했습니다.
- 실제 약관 **1조**는 특정 서비스의 지침도 편입한다고 하지만, **12조**는 권리를 유보하고 서비스 제공 자체가 묵시적/명시적 라이선스를 부여하는 것은 아니라고 명시합니다. XML 색인 안내가 이 공개 서비스의 메타데이터 게시를 허용하는지 명확히 해결되지 않습니다.
- 따라서 `sources.json`의 publication.status를 **review**로 바꿨습니다. 기존 permission()이 false를 반환하므로 **앞으로의 새 자동 게시가 중단**됩니다. RSS 연결은 발견용으로 남기고, 기관의 공개 6필드 색인 허용 확인이 필요합니다. 추가 출처/대체 API는 만들지 않았습니다.
- 요청하신 기존 3건은 삭제/재분류하지 않았으며, 원장에 남은 최초 수집 당시의 정책 기록은 현재 승인 증명으로 해석하지 않습니다. 기존 전체 50건을 보존했습니다.

현재 자동 신규 게시가 가능한 신규 출처는 **Hospitality Net 1곳**, 보류 중인 신규 출처는 Hotel News Resource 1곳입니다. 최초 실증의 ‘2곳/6건’은 역사적 수신·선별 결과이며 현행 권리 승인을 뜻하지 않습니다. source-audit.json의 13:36 수집 성과도 재실행한 수치가 아니며 현재 상태는 sources.json 및 review-final.json을 봐야 합니다.

## 4. 최종 검증

- Python **253/253 통과**: 기존 246 + 최종 검수 7개. 실제 6건의 리터럴 키워드/5필드 보존, 대소문자·단어 경계·중첩·한국어 회귀, 실제 tier, 기업/호텔 과대승격 방지, 서면 승인 미취득 표시 및 review 게이트의 신규 차단/기존 자료 보존.
- 브라우저 **13/13 suite 통과**: 기존 12 + `pr17-review.smoke.cjs`. 실제 신규 6건의 표시·키워드·50건·6필드·현재 브리핑·호텔 개관 미선정, PC 1440px/모바일 390px 및 기존 전체 UI/기능 회귀.
- 기존 44건과 신규 6건의 제목·출처·발행일·URL·카테고리 동일, 전체 50건 유지. 한국어 키워드 42건 동일. 추가 기사/본문/가상 데이터 없음.
- 내부 전체 기사 원장의 레코드 배열·editorial 기록, 확정 브리핑/내부 이력, Research 135건·Macro DB·Weather 코드/표시 순서·UI·Actions·로고 원본은 변경하지 않았습니다. 현재 브리핑 4건의 구성은 동일하며 파생 키워드 1개만 보강했습니다. 아래 main 자동 갱신 반영 과정에서 현재 후보의 평가 시각은 갱신했지만 확정 아카이브는 그대로입니다.
- 이번 보완에 새 키는 필요 없고 신규 네트워크 확인은 기존 두 출처의 공식 안내/약관 5개 페이지만 대상으로 했습니다. PR에서는 운영 수집/Pages 배포를 하지 않습니다.

[기록/보존 SHA-256/현재 6건 메타데이터](review-final.json) · [Python](review-python.txt) · [브라우저](review-browsers.txt)


## main 자동 갱신 충돌 해소

검수 중 main에 `7e6322a` 자동 수집 커밋(2026-11-03 14:04:58 KST)이 추가되어 같은 PR 브랜치로 받아 충돌을 해소했습니다. main으로 PR을 병합한 것이 아닙니다.

- 최신 main의 44건과 PR의 신규 6건을 모두 유지해 50건이며, 검수 직후와 비교해 50건의 레코드 배열(키워드 포함)이 동일합니다. 내부 원장의 60개 레코드 배열도 동일합니다.
- main의 실제 전송 상태/새 발견 기록을 보존하고, 원장 발견 시각·소스 계수는 두 관측 기록을 합쳐 보존했습니다. 새 네트워크 수집 실행이나 새 기사 게시를 한 것은 아닙니다.
- health의 review_context에 최신 실제 main 수집 시각, 초기 확장 실증 시각, 현재 투영 검토 시각을 각각 기록했습니다. latest transport는 main의 24곳 관측이며 configured는 26곳입니다. 현재 권리 게이트가 통과하는 출처 19곳과 최초 실증 당시 20곳을 구별합니다.
- 현재 DB의 50건을 기준으로 기사 수/카테고리/기여 출처 지표를 맞췄으며, 최초 26곳 전송 검증·6건 추가라는 실증 이력은 comparison.json에 그대로 보존했습니다. 서로 다른 실행을 하나의 성공률로 합치지 않았습니다.
- 현재 브리핑 후보만 원 발행일과 기존 선정 규칙으로 재평가했고 URL/제목/키워드/순서가 이전 4건과 동일함을 확인했습니다. 생성/마지막 수집 시각은 실제 main 갱신·이번 재평가에 맞춰 구분합니다. 당일 확정본·내부 확정 이력은 바이트 동일합니다.
- 충돌 해소 뒤 Python 253개와 브라우저 13개 전체 회귀를 다시 통과했습니다.
