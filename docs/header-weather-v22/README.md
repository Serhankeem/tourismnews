# Header Layout & Market Weather UI v2.2

기준: PR #15 병합 이후 최신 main `f46fbc2`. `git pull --ff-only origin main` 후 `feat/header-weather-layout-v22` 브랜치를 생성했습니다. UI 레이아웃·메뉴 동작·DOM 순서만 수정하며 main에는 병합하지 않습니다.

## 헤더 전후

기존에는 1080px 이하에서 로고 위/메뉴 아래, 550px 이하에서 2열 메뉴가 되었습니다. 기존 4개 CSS의 중복 헤더·로고·메뉴 선언과 반응형 덮어쓰기를 제거하고 **`navigation-research-v21.css`를 헤더 레이아웃의 단일 소유 파일**로 정리했습니다. Research 필터의 기존 반응형 규칙은 유지합니다.

이제 로고는 왼쪽, 메뉴는 오른쪽 한 줄이며 헤더 실측 높이는 81px입니다(기존 PC 96px). 로고 원본 비율 2:1, 클릭 시 홈 이동, 4개 상위 메뉴와 뉴스 하위 3개 경로를 보존합니다. 메뉴 영어 서브텍스트는 없습니다.

고정 breakpoint로 메뉴를 숨기지 않습니다. `ResizeObserver`와 resize/font-ready 시 실제 메뉴를 데스크톱 스타일로 동기 측정해 `로고 너비 + 간격 + 메뉴 너비 > 헤더 내부 가용 너비`인 경우에만 compact 메뉴로 전환합니다. 같은 768px에서도 글자가 커져 메뉴가 맞지 않으면 접히는 테스트를 통과했습니다. 기존 1080px/550px 헤더 규칙은 제거했습니다.

| 화면 폭 | 기본 글꼴의 결과 | 검증 |
|---|---|---|
| 320 / 390 | 왼쪽 로고 + 오른쪽 메뉴 버튼, 기본 접힘 | 메뉴·뉴스 하위 메뉴 펼침, 터치·키보드·화면 넘침 없음 |
| 768 / 1024 | 로고 + 메뉴 가로 한 줄 | 위아래 배치·줄바꿈 없음 |
| 1280 / 1440 | 로고 + 메뉴 가로 한 줄 | 불필요한 메뉴 접힘 없음 |

모바일 메뉴는 버튼의 `aria-expanded`/`aria-controls`를 사용합니다. 뉴스 하위 메뉴도 별도 disclosure입니다. Tab·Enter·Space와 ArrowDown을 지원하고, Escape는 열린 뉴스 하위 메뉴를 먼저 닫아 뉴스 버튼으로 포커스를 반환하며 다음 Escape는 전체 메뉴를 닫아 메뉴 버튼으로 반환합니다. 외부 클릭/포커스 이동·링크 선택·해시/브라우저 이력 이동 시 메뉴를 닫습니다. compact↔가로형 전환에서도 숨겨진 요소에 포커스를 남기지 않습니다. 헤더 높이를 CSS 변수로 동기화해 sticky 스크롤 여백을 유지하며, 펼침 패널은 작은 높이 화면에서 내부 스크롤이 가능합니다.

## Market Weather 순서

홈 `.market-home-card`의 실제 DOM을 다음 순서로 옮겼습니다.

1. `.weather-panel.scenario-preview`: 아이콘·상태·가상 점수·시나리오 실험실 링크
2. `#home-market-observation`: 공식 관광시장 관측 및 출처

상세 `#weather`의 실제 DOM은 다음 순서입니다.

1. 페이지 제목/설명
2. `.scenario-section`: 시나리오 결과와 3개 슬라이더, 초기화, 계산식 disclosure
3. `.market-observation-section`: 입출국 실측 카드·국적별 카드·12개월 추이·출처
4. 지표와 모델 안내

CSS `order`로 순서만 가장하지 않았습니다. 기존 ID·데이터 로딩·색상 체계는 그대로입니다. 홈과 상세에 **‘시뮬레이션 · 실제 관광시장 종합지수 아님’**을 표시하고 경계/레이블을 유지했습니다. 순서 변경에 맞춰 안내문의 ‘위 실제 관측’을 ‘아래 실제 관측’으로 정정했습니다. 홈의 경계선은 시나리오 아래로 옮겼습니다.

`#weather` 직접 접근·상단 메뉴·홈 시나리오 링크 모두 최상단으로 이동해 제목 다음 시나리오부터 보입니다. 관측 데이터가 가상 점수나 슬라이더를 변경하지 않습니다.

## 회귀·불변 검증

- Python **236/236 통과**.
- 브라우저 **12/12 suite 통과**(기존 11 + 신규 `header-weather-v22.smoke.cjs`). 메뉴 접힘에 맞춰 기존 home/navigation/UI 테스트와 공통 실제 메뉴 클릭 helper만 갱신했습니다. Research 검색/필터·페이지네이션, 뉴스 최신순·브리핑 상태·아카이브, Macro, Data Observation, Weather v2, 로고·배너 회귀를 유지했습니다.
- 신규 검증: 320·390·768·1024·1280·1440px, 실제 한 줄 배치, 같은 폭에서 글자 확대에 따른 전환, 뉴스 3개 경로, 키보드/Tab/ArrowDown/Enter/Space/Escape, 외부 클릭, ARIA, 뒤로/앞으로, 직접 `#weather` 진입, 시나리오 DOM/화면 순서, 홈/상세 값 동기화, 슬라이더와 초기화, 실측 카드·차트 보존.
- 실제 3개 엔진·공개 JSON 11파일·내부 원장 17파일·Actions 3파일·출처/승인 설정 5파일은 기준 main과 바이트 동일합니다. 엔진 소스 전체 24파일도 동일합니다. Research 135건 유지.
- Market Weather `weather()` 함수 원문 SHA-256: `5091d7c5751cb44c1dd324f4bb55e35778f22206a4912b66db09063e5bd35754`, 변경 전후 동일. 가중치/등급/초기값·실측 시계열은 변경하지 않았습니다.
- 공식 비행기 로고 SHA-256: `7f92affea61c57197f2b015576cb7bcaf604defb0ac270894157d8e94d070b7f`, 원본 바이트 불변.
- PR #15의 뉴스 정렬 함수와 홈 최신 뉴스 렌더링, 배너 닫기 코드도 원문 동일합니다.

[브라우저 실행 결과](browser-results.txt) · [보존 검증 manifest](preservation.json)

## 화면 증빙

모든 화면은 기존 실제 공개 데이터로 캡처했습니다. 콘텐츠 증빙은 기존 배너 닫기 기능을 사용해 가림을 제거했습니다. 데이터나 계산값을 조작하지 않았습니다.

| 화면 | 변경 전 | 변경 후 |
|---|---|---|
| 1440px 헤더 | [전](screenshots/before-header-1440.png) | [후](screenshots/after-header-1440.png) |
| 1024px 헤더 | [전](screenshots/before-header-1024.png) | [후](screenshots/after-header-1024.png) |
| 390px 헤더 | [전](screenshots/before-header-390.png) | [후](screenshots/after-header-390.png) |
| 홈 오른쪽 Weather, 1440px | [전](screenshots/before-home-weather-1440.png) | [후](screenshots/after-home-weather-1440.png) |
| 홈 Weather, 390px | [전](screenshots/before-home-weather-390.png) | [후](screenshots/after-home-weather-390.png) |
| 상세 페이지, 1440px | [전](screenshots/before-weather-1440.png) | [후](screenshots/after-weather-1440.png) |
| 상세 페이지, 390px | [전](screenshots/before-weather-390.png) | [후](screenshots/after-weather-390.png) |

모바일 메뉴: [닫힘](screenshots/after-menu-closed-390.png) · [전체 메뉴+뉴스 하위 메뉴 열림](screenshots/after-menu-open-390.png)

## 배포

기존 Actions 및 Pages 배포 방식은 변경하지 않았습니다. PR은 검토용이며 운영 배포 완료를 뜻하지 않습니다. 사용자 검토·병합 이후 실제 main Pages 배포에서 반영을 확인해야 합니다. 새 API 키나 별도 서비스 설정은 필요 없습니다.
