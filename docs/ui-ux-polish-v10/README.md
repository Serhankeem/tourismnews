# UI/UX Polish v1.0 — 헤더·내비게이션·마이크로 인터랙션

최신 main `68f28bb`(PR #21 병합)에서 `feat/ui-ux-polish-v10`을 생성했다. **UI 파일·브라우저 테스트·이 문서만 변경했고 main 병합·운영 JSON 수정·data/live 쓰기·실제 Pages 배포는 하지 않았다.** 데이터 검증은 읽기 전용 운영 스냅샷 `95b197d786a40bfcc4bc906988d03f16c312c3f6`을 임시 공간에 복사해 진행했다.

## 기존 문제와 개선

| 항목 | 이전 | 변경 |
|---|---|---|
| 헤더 로고 | CSS 너비 112px | **130px**, 높이 65px, 원본 비율 2:1 유지 |
| 뉴스 ↔ 리서치 | 비활성 링크와 배경의 구별 부족 | 파란 테두리의 Segmented Navigation, 선택 딥블루/흰 글자/체크 표시, 비선택 흰 배경 |
| 날씨 | 정적 이모지 | 두 화면에서 재사용하는 인라인 SVG·CSS 모션 4종 |
| 페이지 전환 | 즉시 전환 | 다른 페이지로 이동할 때만 200ms ease-out, opacity 0→1·Y 6px→0 |
| 카드 | 일관되지 않은 피드백 | 링크를 포함한 주요 카드만 2px 상승·약한 그림자, 키보드 focus-within도 강조 |
| 일반 KPI | 클릭 기능 없는 정보 | pointer 커서/상승 효과 없이 미세한 테두리 강조만 |
| 버튼·입력 | 일부 선택/누름/포커스 구분 부족 | 순간 active와 지속 selected를 분리, 선명한 focus-visible, 필터 aria-pressed, 주요 버튼/슬라이더/페이지 번호 44px 확보 |
| Sticky Header | 고정 blur | 같은 헤더 규칙 안에서 스크롤 상태에 따라 배경·그림자 180ms 전환·blur 10→12px |
| Research 접근조건 | `미확인` | **`열람 조건 미확인`**, 짧은 원문 열람 안내 추가 |

### 로고와 헤더

기존 비행기 로고 `currentourism-new-airplane-logo.png`의 픽셀·색·투명도는 바꾸지 않았다. SHA-256은 `7f92affea61c57197f2b015576cb7bcaf604defb0ac270894157d8e94d070b7f`, 원본은 1774×887px이다. 112→130px로 약 16.1% 확대했다. 원본 자체의 투명 여백도 유지해, 알파 영역 기준 실제 그림 너비는 약 98.9→114.8px이다. 이미지를 자르거나 여백을 새로 가공하지 않았다.

헤더 높이는 약 80→82px이다. `navigation-research-v21.css`의 기존 헤더 소유 규칙을 수정했고 중복된 scroll-padding 규칙 하나를 정리했다. 기존 실제 폭 측정 JS를 그대로 사용해 메뉴가 한 줄에 들어갈 때는 가로형, 안 들어갈 때는 접힘 메뉴를 유지한다. 로고 클릭 홈 이동, 하위 메뉴, 외부 클릭/Escape, 키보드 포커스 및 ARIA는 보존했다. 스크롤 리스너는 passive이며 임계 상태가 바뀔 때만 class를 변경한다. 새 sticky 레이어를 추가하지 않았다.

### 탭과 컨트롤

탭은 role=tab으로 바꾸지 않고 `href=#news/#research` 링크를 유지했다. 선택 탭은 `aria-current=page`와 체크 표시로 색상 이외에도 상태를 알린다. 모바일에서는 두 링크가 같은 너비다. 키보드로 전환하면 새 화면의 선택 링크에 포커스를 옮겨, 숨겨진 이전 페이지에 포커스가 남지 않게 했다. 뒤로가기/앞으로가기·직접 해시와 기존 헤더 라우팅도 유지한다.

새 hover 효과는 hover 가능한 정밀 포인터에만 적용한다. active는 순간적인 밝기 변화이며, selected/aria-current/aria-pressed는 선택이 유지된다. Disabled는 native disabled와 낮은 강조·not-allowed 커서로 표시한다. 페이지네이션의 기존 뒤/앞 화살표와 10/20개 선택은 보존하고 버튼 최소 크기만 44×44px로 보완했다. 카드 내부 링크는 그대로이며 카드 전체 클릭 기능을 새로 만들지 않았다.

### Research 열람 조건

원장의 `access_type` 값과 스키마는 그대로다. 프런트엔드의 카드 표시에서만 `미확인`을 `열람 조건 미확인`으로 변환하고 아래 안내를 덧붙였다.

> 해당 자료의 무료 열람·회원 접근·구매 여부는 원문에서 확인해야 합니다.

무료/회원/구매 조건을 추측하지 않았다. `발행일 미확인`은 기존 별도 날짜 정보로 유지한다. 검색·기관/분야/유형 필터·정렬·초기화·결과 수·기관별 현황·페이지네이션은 그대로다.

## 날씨·모션 기준

| 상태 | 표현 | 모션 |
|---|---|---|
| 맑음 | 오렌지 태양 | 광선 24초 회전, 5초 부드러운 빛 변화 |
| 구름 조금 | 태양 + 딥블루 윤곽 구름 | 구름 ±2px 이동, 6초 왕복 |
| 흐림 | 겹친 두 구름 | 전·후면 구름이 6/7초로 미세 이동 |
| 비 | 구름 + 빗방울 3개 | 시차를 둔 1.5초 낙하 |

날씨 배경/등급 색상은 기존 UI 2.0 것을 유지한다. SVG에는 기존 딥블루 `#173B73`, 오렌지 `#F47735`와 블루그레이만 사용하고 그라데이션·외부 패키지·영상·새 이미지 요청을 추가하지 않았다. 태양/구름/비는 모두 같은 렌더러를 사용하며 홈과 상세 화면의 SVG 내용·상태·점수가 일치한다. 상태가 바뀌지 않는 슬라이더 입력은 기존 SVG DOM을 재사용한다.

첫 측정에서 SVG로 교체되는 순간의 높이 변화가 CLS를 늘리는 것을 확인했다. **98×78px 아이콘 슬롯을 최초 CSS부터 확보**해 이를 보완했다. 움직임은 작은 SVG 내부의 transform/opacity로 한정한다. 분모 `/100`의 상속된 음수 자간도 정리해 숫자 겹침을 없앴다.

`시나리오 · 가상 실험`, `시뮬레이션 · 실제 관광시장 종합지수 아님` 안내를 함께 유지한다. 아이콘의 role=img/aria-label에도 가상 실험임을 명시한다. 공식 시장 관측값이나 실제 날씨로 표현하지 않는다.

- 기본 가정값: 방한객 +21%, 관광소비 +8%, 항공 공급 +6% 그대로.
- 계산식: `clamp(round(50 + 0.65×방한 + 0.4×소비 + 0.25×항공), 0, 100)` 그대로.
- 등급 경계: 75/60/45 그대로. 기본 실제 계산 점수 68도 동일하다.
- 페이지가 숨겨지거나 브라우저 탭이 숨겨지면 SVG 모션을 pause한다.
- `prefers-reduced-motion: reduce`는 SVG를 정적으로 만들고 페이지 등장/카드 이동/전환 모션을 끈다. 설정이 실행 중 바뀌어도 적용한다.
- 페이지 등장 효과는 실제 route가 바뀔 때만 실행한다. 데이터 갱신에는 실행하지 않고, 연속 이동 시 이전 등장 효과를 취소한다. 프레임 반복 JS 타이머는 없다.

## 화면 증빙

모두 같은 공개 운영 스냅샷을 합성한 로컬 페이지다. 정지 스크린샷은 애니메이션 프레임을 고정했으며, 모션 실행/중단 여부는 별도 브라우저 테스트로 확인했다. 아래 외에도 768px의 네 화면과 네 가지 날씨 결과를 screenshots/에 보관했다.

| 화면 | 이전 | 이후 |
|---|---|---|
| 홈 PC 1440px | [이전](screenshots/before-overview-1440.png) | [이후](screenshots/after-overview-1440.png) |
| 홈 모바일 390px | [이전](screenshots/before-overview-390.png) | [이후](screenshots/after-overview-390.png) |
| 뉴스 PC | [이전](screenshots/before-news-1440.png) | [이후](screenshots/after-news-1440.png) |
| 뉴스 모바일 | [이전](screenshots/before-news-390.png) | [이후](screenshots/after-news-390.png) |
| 리서치 PC | [이전](screenshots/before-research-1440.png) | [이후](screenshots/after-research-1440.png) |
| 리서치 모바일 | [이전](screenshots/before-research-390.png) | [이후](screenshots/after-research-390.png) |
| Weather PC | [이전](screenshots/before-weather-1440.png) | [이후](screenshots/after-weather-1440.png) |
| Weather 모바일 | [이전](screenshots/before-weather-390.png) | [이후](screenshots/after-weather-390.png) |

[768px 헤더/홈](screenshots/after-overview-768.png) · [모바일 메뉴 열림](screenshots/after-menu-open-390.png) · [맑음](screenshots/weather-sunny.png) · [구름 조금](screenshots/weather-partly.png) · [흐림](screenshots/weather-cloudy.png) · [비](screenshots/weather-rain.png)

## 접근성·기능 검증

신규 `tests/ui-ux-polish-v10.smoke.cjs`는 **320/390/768/1024/1440px**를 검사한다. 320/390은 터치/모바일 에뮬레이션도 활성화했다.

- 원본 로고 SHA·130×65px 표시·82px 이하 헤더·모바일 메뉴 열기/Escape 및 겹침 없음.
- 링크 탭의 키보드 포커스·Enter·선택 상태·뒤/앞 이동·모바일 동일 너비.
- 데스크톱 hover/active 및 카드 2px 상승, 터치에서 hover 미의존, 일반 KPI의 pointer 커서 부재.
- 날씨 4종과 홈/상세 SVG·점수 일치, 같은 등급의 DOM 재사용, 입력/계산/초기화 유지.
- 숨겨진 페이지/문서의 모션 pause, Reduced Motion 정적 표현과 등장 효과 취소.
- 페이지 진입 200ms와 데이터 갱신 시 재등장하지 않음 구분.
- Research 원장값 `미확인` 유지와 표시/안내 변경, 검색·초기화 유지.
- 페이지네이션 disabled/44px, 필터 aria-pressed, 수평 넘침·JS 오류 없음.

기존 브라우저 검사는 6개 폭과 글자 확대 시 헤더 자동 접힘, 모든 route·해시/뒤/앞 이동, 뉴스 최신순·검색·필터·10/20 페이지네이션, 브리핑/확정 아카이브, Research 복합 필터, Macro 실측과 공식 시장 관측, 모델 분리, HNR 공개 차단, 배너 닫기·원문 링크를 함께 검증한다.

완전한 WCAG 적합성 인증이나 실기기 Safari 전체 검사라고 표시하지 않는다. 비활성 컨트롤과 작은 보조 닫기 버튼 등 기존 UI의 모든 요소를 전면 재설계하지 않았으며, 주요 조작 영역의 44px 확보에 집중했다.

## 성능 영향

로컬 Chromium에서 같은 데이터·뷰포트마다 fresh context 3회, 초기 데이터/폰트 로딩 후 400ms 관찰했다. CPU/네트워크 제한 없는 로컬 HTTP 결과이며 **운영 사용자 Core Web Vitals나 Lighthouse 점수가 아니다**. 원자료는 [performance.json](performance.json).

| 뷰포트 | LCP 중앙값 이전→이후 | CLS 중앙값 이전→이후 |
|---|---:|---:|
| 390px | 116→108ms | 0→0 |
| 1440px | 120→112ms | 0.0478→0.0456 |

이 조건에서는 악화가 관측되지 않았다. 수 ms 차이를 의미 있는 속도 개선으로 단정하지 않는다. 기존 비동기 뉴스/시장 관측 로딩의 초기 shift는 남아 있고 CLS=0을 달성했다고 하지 않는다. 이후 운영 환경의 실제 측정이 필요하다.

새 외부 요청·라이브러리는 없고 관측 리소스 수는 전후 모두 30개다. 프런트엔드 파일 전체 증가분은 압축 전 7,229바이트다. SVG/ARIA 등의 DOM은 초기 약 26개 늘었지만 JS 반복 타이머는 추가하지 않았다. 페이지 모션은 200ms로 제한하고 hover는 정밀 포인터에만 적용한다.

## 데이터·엔진 보존

[보존 증거](preservation.json)에 원본 manifest와 전후 해시·모델/로고 검증을 기록했다.

- 같은 기준시각에 합성한 전후 **공개 12개 + 비공개 18개 JSON 모두 바이트 동일**.
- 읽기 전용 원본 스냅샷의 control 포함 31개 manifest 해시도 동일.
- 공개 뉴스 63건의 기존 6필드와 HNR 보류 3건, Research 135건을 보존했다.
- PR #21 Discovery Engine, 뉴스/리서치/Macro 엔진·원장·권리 게이트, 확정 브리핑·공식 관측·TOURGO 승인 설정·Actions·Pages 방식은 변경하지 않았다.
- `src/`, `collector_state/`, `site/data/`, 설정 JSON과 `.github/workflows/`는 이번 Git diff에 없다. 새 로고 자산도 Git 변경이 없다.
- Scenario 입력 min/max/step/default, 계산식과 경계값은 이전 main의 문자열과 대조했다.

## 변경 파일

| 파일 | 변경 |
|---|---|
| site/navigation-research-v21.css | 로고 130px·기존 헤더의 스크롤 강조·터치 hover 정리·중복 규칙 제거 |
| site/currentourism.polish.css | 세그먼트·컨트롤·카드 상태, SVG/고정 슬롯·모션 및 reduced-motion |
| site/ui-2.css | 페이지네이션 최소 44px, 점수 분모 자간 |
| site/currentourism.js | 공유 SVG 렌더러·route 등장 효과·숨김/설정 변화 처리·passive 스크롤 상태 |
| site/index.html | 전환 호출·시나리오 표시·필터 ARIA·세그먼트 포커스·이모지 표시 경로만 조정 |
| site/research.js | 원장값을 바꾸지 않는 열람 조건 표시/안내 |
| tests/ui-ux-polish-v10.smoke.cjs | 새 UI·모션·키보드/터치·실제 공개 데이터 회귀 |
| docs/ui-ux-polish-v10/ | 보고서·25개 스크린샷·측정/보존/테스트 증거 |

## 테스트·CI·남은 작업

- **Python 전체 321개 통과**.
- **브라우저 전체 17개 suite 통과**(기존 16 + 신규 1). JS 오류 없음.
- **GitHub CI: 코드 커밋 `6f57f29d`의 검사 3개 모두 SUCCESS** — [뉴스](https://github.com/Serhankeem/tourismnews/actions/runs/41980132846), [Research](https://github.com/Serhankeem/tourismnews/actions/runs/41980133040), [Macro](https://github.com/Serhankeem/tourismnews/actions/runs/41980132851). 운영 collect-and-publish 3개는 기존 main 전용 조건으로 SKIPPED. 후속 커밋은 CI 기록뿐이며 브라우저 17개는 별도 로컬 Chromium 검사다.
- main에 병합하지 않았으며 운영 data/live에 쓰거나 실제 Pages 배포를 실행하지 않았다.

남은 UI 과제는 실기기 Safari/Android 및 운영 환경의 접근성·필드 성능 확인, 기존 비동기 데이터 영역의 추가 CLS 축소다. 뉴스 공급 확대·승인·모델 고도화는 이번 UI 범위에 포함하지 않았다.
