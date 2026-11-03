# News Engine v0.4 — 출처 확대 결과

> **병합 전 최종 검수 반영:** 신규 6건의 영문 키워드를 보완했습니다. Hotel News Resource의 실제 일반 이용약관을 추가 확인한 결과 공개 색인 범위가 불명확하여 **신규 자동 게시를 review 게이트로 보류**했습니다. 기존 50건·해당 출처 3건은 보존합니다. 아래 2개 출처/6건 및 20개 게시 승인 대상 수치는 최초 실증 시점의 기록이며 현재 승인 상태와 구별해야 합니다. Hospitality Net은 지정 RSS 범위의 로컬 판단이며 별도 서면 승인 완료가 아닙니다. [최종 검수 보고](PR17-final-review.md)

기준: 최신 main `7926c71`(PR #16 병합 포함)을 pull한 `feat/newsroom-source-expansion-v04`. 본문·사진·RSS 설명문·AI 요약을 수집/게시 대상으로 추가하지 않았습니다. 공개 기사는 기존 6필드만 제공합니다.

## 결론과 미달 목표

실제 신규 연동 및 공개 뉴스 기여 출처는 **Hospitality Net / Hotel News Resource 2곳**, 신규 뉴스 **6건**, 전체 뉴스 **44 → 50건**, 게시 기여 출처 **6 → 8곳**입니다. 기존 뉴스 44건의 URL별 6필드 값과 내부 49개 원장 ID를 모두 보존했습니다.

**목표인 신규 기여 출처 최소 3곳에는 미달했습니다. 신규 국내 언론·OTA 출처는 0곳이며 국내 일일 공급 부족은 해결되지 않았습니다.** 국내 RSS가 있다고 공개 플랫폼 이용 허용으로 간주하지 않았으며, 해외 숙박/항공 기사나 SEC 공시로 국내 뉴스 문제를 해결한 것처럼 표시하지 않습니다. 추가 6건은 모두 항공·숙박 분야이고 다른 분야의 공급 증가는 아직 없습니다.

## ① 기존 구조와 실제 실행 대상 차이

작업 시작 시점의 main 데이터는 2026-11-03 12:00:20 KST에 생성되었습니다. 설정 24곳, 발견(discovery) 실행 기록 24곳 중 성공 13곳, 게시 승인 대상 18곳 중 성공 9곳, 실제 Newsroom 기여 6곳이었습니다.

`health.json` 상위 `sources`/`source_count`는 기존 collector가 승인된 출처의 게시용 피드를 처리한 결과입니다. `health.discovery.sources`는 발견 단계의 24곳 전체입니다. 차이 6곳은 Korea.net, 대한항공, Trip.com IR, Hilton Stories, Skift, 연합뉴스의 `publication.status=review` 때문이며 비활성화나 누락이 아닙니다. 발견 성공과 공개 게시 승인은 별개입니다.

SEC는 `regulatory_filing`, KOSIS는 통계 자료로 분리되어 뉴스 기여 수에 포함되지 않습니다. Research Library 보고서 수집은 별도 엔진입니다. 정상 수신하였으나 관련 기사/신규 URL이 없는 경우도 성공으로 기록합니다.

### 기존+신규 출처별 이번 결과

실제 응답은 기존 24곳을 robots-aware HTTPS Loader로 읽고, 추가 2곳은 공식 안내에 실린 RSS로 검증했습니다. 응답을 `/tmp`에 고정해 **한 번 전체 엔진에 재생**하여 데이터/지표를 산출했습니다. 원문 기사는 호출하지 않았고, 설명문을 관련성 분석이나 공개 출력에 사용하지 않았습니다. 미승인 원문 제목은 발견 원장에서 계속 해시로 보류합니다.

- 최종 엔진 평가 시각: 2026-11-03 **13:36:40 KST**.
- 서로 다른 실제 출처 경로 26곳의 응답/오류 확인, 성공 23곳.
- 게시 승인 대상 20곳 중 성공 18곳(`health.json` 상위); Newsroom 기여는 8곳.
- 즉시 네트워크 실행과 응답 고정 재생을 구별합니다. 이 결과는 PR 코드의 운영 Actions 연속 성공을 뜻하지 않습니다.

아래 D/I/I는 원래 발견 단계 분류 수입니다. SEC 행의 Direct는 공시 대상 판정이며 **뉴스 Direct 수가 아닙니다**. KPI의 Direct Ratio는 이와 달리 공시·통계를 제외한 `news_classifications`만 사용합니다.

| 출처 | 게시 권리 상태 | 실행 | 수신 항목 | Direct/Indirect/Irrelevant | 신규 뉴스 | 누적 뉴스 | 발행 7일 뉴스 | 오류/미게시 사유 |
|---|---|---|---:|---|---:|---:|---:|---|
| 문화체육관광부 보도자료 | approved | error | 0 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 0} | 0 | 4 | 3 | robots_unverified:http_503 |
| Korea.net Food/Travel | review | error | 0 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | redirect_loop |
| KOSIS 최근수록자료 | approved | error | 0 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | robots_unverified:http_503 |
| 서울시 내 손안에 서울 문화 | approved | ok | 20 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 20} | 0 | 2 | 0 | 정상(관련 0건은 실패 아님) |
| 서울시 내 손안에 서울 경제 | approved | ok | 20 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 20} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| 서울시 내 손안에 서울 교통 | approved | ok | 20 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 20} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| 서울시 내 손안에 서울 환경 | approved | ok | 20 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 20} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| SEC EDGAR · Booking Holdings | approved | ok | 47 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| SEC EDGAR · Expedia Group | approved | ok | 38 | {'Direct': 1, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| SEC EDGAR · Marriott International | approved | ok | 35 | {'Direct': 1, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| SEC EDGAR · Hilton Worldwide | approved | ok | 46 | {'Direct': 1, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| SEC EDGAR · Delta Air Lines | approved | ok | 40 | {'Direct': 1, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| SEC EDGAR · United Airlines | approved | ok | 38 | {'Direct': 1, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| SEC EDGAR · Trip.com Group | approved | ok | 23 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| GOV.UK · tourism | approved | ok | 100 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 10} | 0 | 0 | 0 | 정상(관련 0건은 실패 아님) |
| GOV.UK · aviation | approved | ok | 100 | {'Direct': 2, 'Indirect': 0, 'Irrelevant': 7} | 0 | 2 | 0 | 정상(관련 0건은 실패 아님) |
| 대한항공 뉴스룸 | review | ok | 10 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 10} | 0 | 0 | 0 | 권리 보류 |
| Trip.com Group IR | review | ok | 10 | {'Direct': 2, 'Indirect': 0, 'Irrelevant': 0} | 0 | 0 | 0 | 권리 보류 |
| Hilton Stories | review | ok | 10 | {'Direct': 5, 'Indirect': 0, 'Irrelevant': 5} | 0 | 0 | 0 | 권리 보류 |
| Skift | review | ok | 10 | {'Direct': 1, 'Indirect': 0, 'Irrelevant': 9} | 0 | 0 | 0 | 권리 보류 |
| 연합뉴스 경제 | review | ok | 120 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 120} | 0 | 0 | 0 | 권리 보류 |
| 여행신문 | approved | ok | 50 | {'Direct': 8, 'Indirect': 0, 'Irrelevant': 26} | 0 | 14 | 8 | 정상(관련 0건은 실패 아님) |
| 트래블데일리 | approved | ok | 50 | {'Direct': 6, 'Indirect': 0, 'Irrelevant': 44} | 0 | 13 | 11 | 정상(관련 0건은 실패 아님) |
| 퍼블릭뉴스통신(TTL) | approved | ok | 50 | {'Direct': 0, 'Indirect': 0, 'Irrelevant': 50} | 0 | 9 | 9 | 정상(관련 0건은 실패 아님) |
| Hospitality Net | approved | ok | 20 | {'Direct': 3, 'Indirect': 0, 'Irrelevant': 17} | 3 | 3 | 3 | 정상(관련 0건은 실패 아님) |
| Hotel News Resource | approved | ok | 20 | {'Direct': 3, 'Indirect': 0, 'Irrelevant': 17} | 3 | 3 | 3 | 정상(관련 0건은 실패 아님) |

구조화된 전체 필드(활성화·발견 허용·방식·URL·이용조건·날짜 보류 포함): [source-audit.json](source-audit.json).

### 오류 분류 및 안전한 처리

이번 실제 재검증에서 실패한 3곳은 문체부 robots HTTP 503, KOSIS robots HTTP 503, Korea.net redirect_loop입니다. robots를 검증하지 못하면 본 피드 접근을 중단합니다. 503 응답 주체가 원본인지 중간 프록시인지 확인되지 않았으며 단순히 사이트 폐쇄·HTTPS 미지원이라고 결론내리지 않습니다. 런타임 네트워크 정책은 unrestricted/enforced로 확인했고 명시적 도메인 허용목록 차단은 관측하지 않았습니다.

기존 GitHub 실행에서 SEC 7곳의 robots 403, 서울 교통 TLS timeout, Trip.com robots 403은 이번 환경에서 재현되지 않았습니다. 원본과 중간망 중 과거 403 발생 주체는 확정할 수 없고, robots 규칙 위반/영구 폐기 피드라고 추정하지 않습니다. 기존 KOSIS의 `https_public_endpoint_required`도 보호 로더가 비 HTTPS 대상/리디렉션을 거부한 기록이며 이번에는 robots 503에서 먼저 중단했습니다.

신규 조사에서는 아시아경제·공항·한국은행 robots 금지, Booking Holdings의 긴 crawl-delay, 일부 기관 robots 전송 오류, 이데일리 406 등을 각각 별도로 기록했습니다. 우회·UA 위장·HTTP 다운그레이드는 없습니다. 폐기 확정 피드는 없습니다.

Loader는 HTTP 500/502/503/504에만 최대 1회 제한 재시도하며 기존 crawl-delay와 짧은 Retry-After를 지킵니다. 긴/날짜형 Retry-After는 다음 예약 실행으로 연기하고, 403/429/robots 금지/인증·TLS 오류를 반복 호출하지 않습니다. 실패는 출처별로 격리하며 다음 기존 2시간 예약 실행에서 다시 확인합니다.

## ② 신규 조사 결과

공식 홈페이지·RSS 가이드·약관 등 접근 관측은 [access-observations.json](access-observations.json)에 기록했습니다. 후보 46곳/매체군의 상세 항목(Access/Rights/Coverage/Date/Reliability/Result)은 [candidate-review.json](candidate-review.json)에 있습니다. '미확인'과 실제 0건은 구분했습니다. 공식 URL조차 확인되지 않은 한국호텔업협회는 추정 주소를 호출하지 않았습니다.

| 출처 | 유형 | 수집 경로 또는 공식 홈페이지 | 접근 결과 | 최종 판단과 근거 |
|---|---|---|---|---|
| Hospitality Net | 글로벌 | https://www.hospitalitynet.org/rss/news.xml | 수신 20 | 연동 — 공식 RSS 안내가 웹사이트 통합을 명시. Terms 5.2/6.2의 일반 무단 봇·대량 재사용 금지를 유지하며 지정 RSS 제목·출처·날짜·링크만 제공. 일반 How-to 1건 제외. |
| Hotel News Resource | 글로벌 | https://www.hotelnewsresource.com/feeds/latest.xml | 수신 20 | 연동 — 공식 가이드가 indexing/research/content discovery 용도 XML 제공을 명시. 현재 피드의 선별된 메타데이터 색인만 연결. |
| 투어코리아 | 국내 전문 | https://cdn.tournews21.com/rss/gn_rss_allArticle.xml | 수신 50 | 보류 — 공식 홈페이지 RSS 링크 확인. 저작권정책/약관은 사전 승낙 없는 재배포 금지, 별도 외부 제목·링크 게시 허용 미확인. 현재 50건 중 엄격한 산업 Direct 후보 0건. |
| 호텔앤레스토랑 | 국내 전문 | https://cdn.hotelrestaurant.co.kr/rss/gn_rss_allArticle.xml | 수신 50 | 보류 — 최근 7일 피드 항목 24건 중 Direct 후보 3건이나 일반 저작권정책/약관 외 공개 제목·링크 색인 허용 미확인. 허락 확인 전 게시 0건. |
| 여행정보신문 | 국내 전문 | https://www.travelinfo.co.kr/ | 홈 공식 JS 리디렉션 목적지 확인 성공 | 보류 — 공식 홈페이지/안내 링크 확인. RSS/API 제공 경로와 자동 공개 색인 허용 확인 못함. 기사 목록 크롤러를 임의 추가하지 않음. |
| 디스커버리뉴스 | 국내 전문 | https://www.discoverynews.kr/ | 홈 접근 성공 | 보류 — RSS 안내가 HTML 주석으로 비노출이며 무단 전재·복사·배포 금지 표시. 비활성 경로를 임의 활성화/호출하지 않음. |
| 트래블바이크뉴스 | 국내 전문 | https://www.travelnbike.com/ | robots 503 | 보류 — 피드·권리 검증 전에 중단. 접근 정상화 후 공식 경로 확인 필요. |
| 연합뉴스 | 종합·경제 | https://www.yna.co.kr/rss/economy.xml | 수신 120 (기존 발견만) | 보류 — 공식 피드/가이드 제공은 확인하되 외부 플랫폼 공개 재사용 허용을 별도로 확인해야 함. |
| 한국경제 | 종합·경제 | https://www.hankyung.com/feed/economy | 공식 RSS 경로 안내 확인; 권리 보류로 피드 미호출 | 보류 — 공식 RSS 안내·이용약관·콘텐츠 구매/제휴 경로 확인. 공개 서비스의 자동 제목·링크 이용 범위는 별도 확인 필요. |
| 매일경제 | 종합·경제 | https://www.mk.co.kr/rss/50100032/ | 공식 RSS 경로 안내 확인; 권리 보류로 피드 미호출 | 보류 — 공식 피드/가이드 제공은 확인하되 외부 플랫폼 공개 재사용 허용을 별도로 확인해야 함. |
| 서울경제 | 종합·경제 | https://www.sedaily.com/rss/economy | 공식 RSS 경로 안내 확인; 권리 보류로 피드 미호출 | 보류 — RSS 안내가 개인 이용자의 비상업적 사용에 한정. 무료 공개 플랫폼이 개인용 리더와 같다고 간주하지 않음. |
| 뉴시스 | 종합·경제 | https://www.newsis.com/RSS/industry.xml | 공식 RSS 경로 안내 확인; 권리 보류로 피드 미호출 | 보류 — 공식 피드/가이드 제공은 확인하되 외부 플랫폼 공개 재사용 허용을 별도로 확인해야 함. |
| 세계일보 | 종합·경제 | https://www.segye.com/Articles/RSSList/segye_economy.xml | 공식 RSS 경로 안내 확인; 권리 보류로 피드 미호출 | 보류 — 공식 피드/가이드 제공은 확인하되 외부 플랫폼 공개 재사용 허용을 별도로 확인해야 함. |
| 아시아경제 | 종합·경제 | https://www.asiae.co.kr/ | robots_disallowed | 보류 — 자동 접근 금지에서 중단 |
| 동아닷컴 | 종합·경제 | https://www.donga.com/ | HTTP 503 | 보류 — 정상 공개 피드/조건 확인 전 중단 |
| 이데일리 | 종합·경제 | https://www.edaily.co.kr/ | HTTP 406 | 보류 — 원본 거부 응답; UA 위장 등 우회하지 않음 |
| 뉴스1 | 종합·경제 | https://www.news1.kr/ | 홈 성공 | 보류 — 공식 피드/공개 색인 허용을 확인 못함 |
| TV조선 | 종합·경제 | https://www.tvchosun.com/ | robots 전송 오류 | 보류 — robots 확인 불가, 중단 |
| 대한항공 | OTA·민간 | https://news.koreanair.com/feed/ | 수신 10 (기존 발견만) | 보류 — 기업 뉴스룸 RSS 정상이나 공개 플랫폼 메타데이터 표시 조건 확인 미완료. |
| Trip.com Group | OTA·민간 | https://investors.trip.com/rss/news-releases.xml?items=15 | 공식 RSS 안내 및 피드 수신 확인 | 보류 — 기존 발견용 RSS와 별개로 공개 재사용 조건 확인 필요. SEC 공시와 구분. |
| Hilton Stories | OTA·민간 | https://stories.hilton.com/feed | 수신 10 (기존 발견만) | 보류 — 공개 재사용 조건 확인 필요; 피드가 있다고 승인하지 않음. |
| 야놀자 | OTA·민간 | https://www.yanolja.com/ | 기업 홈 성공 / news룸 robots 전송 오류 | 보류 — 공식 기업 보도자료 RSS·제목 링크 재사용 승인 확인 필요. 소비자 상품 feed를 뉴스로 연결하지 않음. |
| 여기어때 | OTA·민간 | https://www.yeogi.com/ | 홈 성공 | 보류 — 소비자 서비스 약관은 기업 보도자료 수신·재사용 권한이 아님. |
| Booking Holdings / Booking.com | OTA·민간 | https://www.bookingholdings.com/ | Holdings crawl-delay 초과 / news.booking.com 홈 성공 | 보류 — 긴 crawl-delay를 무시하지 않음. 별도 뉴스룸 RSS/재사용 경로 미확인. |
| Expedia Group | OTA·민간 | https://www.expediagroup.com/ | 홈 성공 | 보류 — 공식 뉴스룸 경로·외부 메타데이터 이용 허용 추가 확인 필요. |
| Klook | OTA·민간 | https://www.klook.com/newsroom/ | 공식 뉴스룸 홈 성공 | 보류 — RSS/API 및 공개 색인 허용 미확인. 개별 보도자료 본문 접근 안 함. |
| KKday | OTA·민간 | https://www.kkday.com/ | 공식 홈 성공 | 보류 — 소비자 상품 페이지를 산업 뉴스 피드로 간주하지 않음. |
| Airbnb | OTA·민간 | https://news.airbnb.com/ | 뉴스룸 홈 성공 | 보류 — 공식 RSS/API·메타데이터 공개 범위 확인 미완료. |
| Skift | 글로벌 | https://skift.com/feed/ | 수신 10 (기존 발견만) | 보류 — 공개 재사용 허용 확인 전 기존 review 게이트 유지. |
| PhocusWire | 글로벌 | https://www.phocuswire.com/RSS/All-News | 공식 RSS 수신 성공 | 보류 — 약관이 HTTP 외부 문서를 안내하며 공개 플랫폼 이용 허용 확인 미완료. RSS만으로 승인하지 않음. |
| Travel Weekly | 글로벌 | https://www.travelweekly.com/ | 홈 성공 | 보류 — 재사용 요청 창구는 확인했으나 공개 RSS/사용 허용 미확인. 개별 기사 호출 안 함. |
| Travel Daily News | 글로벌 | https://www.traveldailynews.com/feed/ | 공식 RSS 링크 확인; 권리 보류로 미호출 | 보류 — Editorial policy와 Terms of Sale은 외부 뉴스 재사용 라이선스가 아님. |
| Travel And Tour World | 글로벌 | https://www.travelandtourworld.com/feed/ | 공식 RSS 링크 확인 | 보류 — 공개 재사용 허용 확인 미완료. |
| 뉴스와이어 | 배포 서비스 | https://www.newswire.co.kr/?md=A31 | 공식 API·RSS 안내/약관 확인 | 보류 — API 신청 심사·키 발급 필요. 비용 미확인. 관광/여행/호텔·숙박/항공사 카테고리 안내 확인. RSS 리더 구독 안내를 공개 서비스 이용 승인으로 대체하지 않음. |
| PR Newswire | 배포 서비스 | https://www.prnewswire.com/rss/ | 공식 RSS·약관 접근 성공 | 보류 — 공개 웹사이트 배포는 제휴/명시적 동의 필요. 개인 비상업적 사용을 공개 재게시와 혼동하지 않음. |
| Business Wire | 배포 서비스 | https://www.businesswire.com/ | 홈 성공; 약관 링크 확인(본문 미호출) | 보류 — 공개 이용 가능한 RSS/메타데이터 이용 허용 미확인. |
| 한국관광공사 | 공공·협회 | https://www.knto.or.kr/ | robots 전송 오류 | 보류 — 공식 보도자료 피드·이용조건 확인 전 보류. |
| 한국여행업협회 | 공공·협회 | https://www.kata.or.kr/ | 홈 742바이트 (메뉴 목록 미확인) | 보류 — RSS/API·공개 자동 색인 조건 확인 미완료. |
| 한국호텔업협회 | 공공·협회 | 미확인 | 공식 URL/피드 미확인 | 보류 — 주소를 추정해 API/RSS를 호출하지 않음. 공식 제공 경로 문의 필요. |
| 한국MICE협회 | 공공·협회 | https://www.koreamice.or.kr/ | robots 전송 오류 | 보류 — robots 확인 불가, 자동 목록 수집 안 함. |
| IATA | 공공·협회 | https://www.iata.org/api/rss/pressrelease | 공식 RSS 수신 성공 | 보류 — 약관은 타 웹사이트 이용에 사전 서면 동의 요구. 승인 전 게시하지 않음. |
| WTTC | 공공·협회 | https://www.wttc.org/ | 홈 성공 / 약관 링크 확인 | 보류 — 연구보고서·통계를 뉴스로 이동하지 않음. 뉴스 제공 범위 미확인. |
| 인천국제공항 | 공공·협회 | https://www.airport.kr/ | robots_disallowed | 보류 — 차단 준수, 경로 변경 우회 안 함. |
| 한국은행 | 공공·협회 | https://www.bok.or.kr/ | robots_disallowed | 보류 — 뉴스 접근 제한 준수. 기존 Macro 통계 엔진과 별개. |
| 국토교통부 | 공공·협회 | https://www.molit.go.kr/ | robots 503 | 보류 — 보도자료 RSS/권리 확인 전에 중단. |
| 대한민국 정책브리핑 | 공공·협회 | https://www.korea.kr/ | robots 503 | 보류 — 피드 주소를 임의 생성하지 않음. 자동 게시 없음. |

### 신규 2곳의 이용 범위

- Hospitality Net [공식 RSS 안내](https://www.hospitalitynet.org/rss): “RSS feeds allow you ... to integrate Hospitality Net content on your website.” 해당 **지정 RSS 인터페이스**의 사용 안내를 근거로 선택적 제목·링크 색인에만 연결했습니다. [일반 약관](https://www.hospitalitynet.org/terms-conditions)의 무단 자동 접근/대량 콘텐츠 재사용 금지를 해제한 것이 아닙니다. 일반 웹페이지/본문/이미지·설명문 수집은 하지 않습니다.
- Hotel News Resource [공식 XML 안내](https://www.hotelnewsresource.com/Info-Newsfeeds.html): 피드가 “intended for indexing, research, and content discovery”라고 명시합니다. 선별된 제목·출처·발행일·직접 링크 색인으로 한정했고 본문·이미지·AI 가공 허가로 확대하지 않았습니다.
- 이는 공식 서비스 안내에 따른 범위 판단이며 **새로 별도 서면 회신이나 재사용 계약을 취득했다는 뜻은 아닙니다.** 기존 무료·광고 없는 비상업 운영 조건을 승인 게이트로 유지합니다. 데이터베이스 전체/과거 아카이브를 추출하지 않고 현재 반환 피드만 사용합니다.

투어코리아는 최근 피드 50건 모두 7일 이내지만 기존 엄격한 관련성 규칙상 Direct 후보가 0건이었습니다. 호텔앤레스토랑은 최근 7일 항목 24건 중 Direct 후보 3건을 발견했으나 공개 재사용 조건이 미확인이므로 **자동 게시 가능 수는 0건**입니다. 매체의 존재나 피드 수신을 신규 연동·게시 성과로 계산하지 않았습니다.

### 뉴스와이어: 사용자 신청이 필요한 별도 과제

[API 안내](https://www.newswire.co.kr/coalition)와 [API 이용약관](https://www.newswire.co.kr/coalition/policyterms)을 실제 확인했습니다.

- 신청 → 회사 내부 심사 → 승인 시 API Key 발급 → 호출/수신 절차입니다. 목적·운영 주체·활용 방식·안정성 등을 검토하며 추가 정보를 요청할 수 있습니다. 자동 승인으로 표시하지 않습니다.
- 약관의 이용자는 법인·기관·단체로 정의됩니다. 개인 비상업 프로젝트의 신청 자격/승인 가능성은 문의가 필요합니다.
- **요금·무료 여부·쿼터는 확인한 안내/약관에서 확인되지 않았으므로 미확인**입니다. '유료 재판매 금지' 문구는 API 요금이 무료라는 근거가 아닙니다.
- API는 제목·발표시각·회사정보·분류 등 메타데이터와 본문/사진도 제공하나 여행기류에서는 승인되더라도 6필드 메타데이터만 요청/출력해야 합니다. 원출처 표시 및 계약 목적 준수, 호출 제한 우회 금지, 무단 재판매/경쟁 서비스 제공 금지 등이 있습니다.
- 공식 RSS 카테고리 안내에는 여행·관광명소·호텔/숙박·항공사 등 분야가 있습니다. 실제 승인될 API의 필터 ID/수신 범위는 별도 확인해야 합니다. RSS 리더 구독 안내를 공개 Newsroom 서비스 승인으로 대체하지 않았습니다.
- 사용자가 해야 할 일: 무료·무광고 링크 큐레이션 목적, 공개 6필드, 본문/사진/AI 미사용, 보관·호출 빈도를 명시해 공식 API 수신 신청. 비용·쿼터·공개 제목/링크 색인·저장/정정 조건을 확인하고 승인 문서를 제공해야 합니다. 키는 채팅/PR에 보내지 말고 **향후 연동 시 GitHub Secret `NEWSWIRE_API_KEY`**로 등록합니다. 이번 PR은 해당 키를 읽거나 API를 활성화하지 않습니다.

## ③ 실제 개발 결과

- `sources.json`: 고유 ID `hospitalitynet`, `hotelnewsresource`, 공식 URL/가이드/조건/비상업 제한/90일 상한/본문 불허 기록. 기존 24곳은 그대로 유지.
- `src/discovery.py`: 기존 RSS/Atom 어댑터 재사용. 새 API 어댑터는 추가하지 않음. robots·HTTPS 보호 유지, 제한된 5xx 재시도만 추가.
- `src/collector.py`: 동일 URL은 계속 제거. 유사 제목 병합은 **동일 발행 출처 안에서만** 허용. 서로 다른 매체의 독립 URL은 같은 사건·제목이라는 이유로 삭제하지 않음. 기존 숫자 사실이 다른 기사 보존도 유지.
- `src/relevance.py`: 제목의 `hospitality` 단어만으로 일반 글을 Direct로 만드는 fallback을 제한. 일반 `How to ...` 안내도 실제 운영 변화 뉴스로 보지 않음. Direct/Indirect/Irrelevant·6카테고리와 승인 규칙은 그대로이며 기준을 느슨하게 만들지 않음.
- `src/engine.py`: 기존 health 구조를 유지하며 `health.discovery.quality`에 소스·뉴스 품질 KPI를 추가. 공시/통계를 제외한 Direct Ratio, 정확한 분모, source gates 및 뉴스 기여 출처를 기록.
- `src/report.py`: 기존 Actions job summary에 품질 KPI 표시. workflow 파일 수정 없음.
- `tests/test_source_expansion_v04.py`: 신규 10개 검증. `tests/newsroom-freshness.smoke.cjs`는 새 11월 3일 실제 기사가 들어와도 11월 2일이 10월 29일보다 앞서는지를 검증하도록 조정.
- `collector_state/*`, 뉴스용 `site/data/*`: 실제 응답을 처리한 원장·발견/선정·실패 기록·6필드 공개 projection. 테스트 데이터는 일절 반영하지 않음.

### 신규 공개 기사 6건

원문 제목·직접 URL·발행일·카테고리·키워드는 [comparison.json](comparison.json)의 `new_articles`로 확인할 수 있습니다. Hospitality Net 3건은 숙박 운영 기술·기업 제휴·비즈니스 여행 플랫폼 변화, Hotel News Resource 3건은 글로벌 항공수요·호텔 2곳 개관입니다. 한국 시장 관련성을 임의로 부여하지 않았습니다. 글로벌 항공수요 기사만 기존 정량적 세계 산업 변화 규칙에 해당하며, 나머지 한국 연계 미입증 자료는 기존 reference 편집 등급을 유지합니다.

## ④ 개발 전후 비교

| 지표 | Before (main 저장 기록) | After (이번 실제 응답 처리) |
|---|---:|---:|
| Configured Sources | 24 | 26 |
| Attempted Sources (발견 경로) | 24 | 26 |
| Successful Sources (발견 경로) | 13 | 23 |
| 게시 승인 대상 / 그중 성공 | 18 / 9 | 20 / 18 |
| Publishing Sources | 6 | 8 |
| New Sources / 실제 신규 기여 | — | 2 / 2 |
| Published Articles | 44 | 50 |
| 실제 신규 Newsroom 기사 | — | 6 |
| 최근 7일 발행 뉴스 | 31 | 37 |
| 최근 24시간 (동일 13:36:40 평가 시각) | 5 | 11 |
| Top 3 Source Share | 81.82% (36/44) | 72.00% (36/50) |
| Direct Ratio (공시/통계 제외 발견 뉴스 관측) | 새 지표 없음 | 7.06% (30/425) |
| Duplicate Ratio (유효 발견 관측 중 이미 본 URL) | 90.35% (337/373) | 86.98% (374/430) |

Before의 12:00 저장 health에는 최근 24시간 6건이 기록돼 있지만, After와 동일한 13:36 시점으로 재평가하면 기존 5건입니다(시간 경과로 한 건이 창에서 빠짐). 서로 다른 수집 시점/환경의 성공률 증가를 신규 2곳의 도입 효과나 운영 오류 전부 해결로 해석하지 않습니다. 출처 확대의 순수 신규 기사 기여는 위 6건입니다.

`Duplicate Ratio`는 반복 관측 비율이지 뉴스 삭제 비율이 아닙니다. 서로 다른 매체의 동일 사건 보도는 각 독립 URL 기사로 보존하며 6건이 서로 다른 사건 6개라는 주장을 하지 않습니다. 같은 실제 응답을 임시 원장에서 두 번째 실행한 결과 **신규 뉴스 0·신규 공시 0**, 중복 관측 430건, 공개 뉴스 50건 유지: [repeat-run.json](repeat-run.json).

전체 보관 원장 60건에는 뉴스 외 SEC 신규 공시 5건과 기존 통계가 포함됩니다. 공시 신규 5건은 `filings.json`, 통계 3건은 별도 `research.json`이며 Newsroom/브리핑의 뉴스 수로 계산하지 않습니다. Research Library `reports.json` 135건과는 다른 데이터입니다.

분야별 공개 뉴스는 관광정책 3 / 인바운드 9 / 여행산업 7 / 항공·숙박 15 / 문화·트렌드 15 / 경제·시장 1건입니다. 이번 신규 6건은 항공·숙박에 집중되어 분야 다양성 개선은 추가 과제입니다.

## ⑤ 테스트 및 보존

- Python: **246/246 통과** (기존 236 + 신규 10). RSS GMT/Atom 오프셋, 정상 빈 피드, 세 관련성 등급, 같은 URL/독립 매체/상이한 수치, 오류 격리·기존 기사 보존, 재실행 0건, KPI 분모·권리 게이트, 재시도 제한·crawl-delay 검증.
- Playwright: **기존 12/12 suite 통과**. 실제 50건으로 검색·6카테고리·북마크·10/20/전 페이지 링크·최신순·홈 대표 3건·브리핑 상태/아카이브·Research 135건·Macro·Weather·4메뉴/320~1440px 회귀 확인.
- 전송 검증과 공급 범위: 1회 네트워크 응답 검증이지 최근 7일간 2시간 자동 수집을 이미 관측했다는 뜻은 아닙니다. ‘7일 기여’는 원 발행일 기준 현재 확보된 기사 수입니다.
- 기존 44개 공개 레코드는 6필드 값까지 동일. 내부 기존 49개 ID 보존. 이미 확정한 브리핑 아카이브 및 내부 확정 이력은 바이트 동일. 현재 브리핑 후보만 기존 최대 5건/10:30 이후 정책에 맞춰 갱신(4건).
- Research 135건·해당 엔진/DB, Macro 원장·엔진/관측 UI, Weather 시나리오/순서/계산식·Data Observation, TOURGO 게이트·로고, HTML/JS/CSS, Actions는 수정하지 않음. [comparison.json](comparison.json)에 보호 파일 SHA-256을 기록했습니다.
- 키/개인정보 추가 없음. 원문 기사·사진·RSS 설명문·AI 요약 공개 없음. 테스트용 XML·mock은 임시 디렉터리에서만 사용.

[Python 결과](python-results.txt) · [브라우저 결과](browser-results.txt) · [최신성 브라우저 추가 확인](freshness-browser.txt)

## ⑥ 미완료 및 운영 확인

1. 국내 신규 언론·민간기업 공급원은 아직 0곳. 투어코리아/호텔앤레스토랑 등 메타데이터 공개 이용 허락, 뉴스와이어 신청·비용/쿼터/키 승인 확인이 우선입니다.
2. PhocusWire/Skift/민간 뉴스룸은 RSS 존재와 공개 재사용 권한을 구별해 보류했습니다. 원문/이미지 사용 허락도 자동으로 확보되지 않습니다.
3. 문체부·KOSIS robots 503, Korea.net 리디렉션 문제는 운영 환경의 후속 확인이 필요합니다. 접근 우회나 임의 피드 대체는 하지 않았습니다.
4. 신규 2곳의 장기간 안정성·일일 공급량은 병합 이후 실제 Actions 실행에서 확인해야 합니다. 해당 매체가 매일 산업 Direct 기사를 제공한다고 보장할 근거는 아직 1회 응답뿐입니다.
5. CI는 고정 mock/fixture 기반 회귀와 기존 workflow 호환성을 확인합니다. 외부 사이트의 실시간 접근·권리는 로컬 실증 결과와 별도로 표시합니다. 실제 main의 2시간 예약, KST 10:30 확정, 데이터 Git 커밋/Pages 배포는 PR에서 활성화하거나 새로 변경하지 않았습니다.
6. 사용자는 PR의 6건·2곳 범위와 보류 판단을 검토한 뒤 병합 여부를 결정합니다. 병합 이후 새 출처별 `new_newsroom_items`, `quality.publishing_sources`, 오류 기록과 Pages 원문 링크 반영을 확인해야 합니다. 이번 PR에 필요한 새 API 키는 없고, 뉴스와이어는 별도 승인 과제입니다.
