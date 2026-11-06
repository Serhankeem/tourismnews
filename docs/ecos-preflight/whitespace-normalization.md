# ECOS STAT_NAME 공백 정규화 — 3차 실패 후속

기준 main: `0dc062b0ab95c294aefe3bc5a127ffb595f29687`.
실패 실행: https://github.com/Serhankeem/tourismnews/actions/runs/42163870666

## 확인한 근거와 불확실성

지정 SHA의 main workflow_dispatch 실패를 실행 메타데이터로 확인했다.
사용자 제공 진단은 STAT_NAME / forbidden_control_character다.
이 오류는 기존 `unicodedata.category(c).startswith('C')`에서 발생한다.
이 코드는 CR/LF/TAB뿐 아니라 Cc/Cf/Cs/Co/Cn을 모두 같은 이유로 거절한다.
따라서 일반 공백형 제어문자가 포함된 정상 명칭도 실패할 수 있다는 코드상의 근거는 있다.
**실제 오류 문자가 CR/LF/TAB였는지는 아직 확인하지 못했다.**

실제 Repository Secret·인증 응답·명칭을 개발 환경으로 가져오지 않았다.
이 수정은 합성 응답으로 재현한 과도한 공백 거절과 후속 명칭 대조 문제를 해결한다.
전체 실제 목록이 이제 통과한다거나 관광수입·지출 실측을 확보했다고 보고하지 않는다.

## 허용·차단 기준

| 입력 | STAT_NAME | 코드·항목 등 다른 필드 |
| --- | --- | --- |
| raw CR/LF/TAB 및 연속 ASCII 공백 | 단일 공백으로 변환, 단어 경계 유지 | 기존대로 거절 |
| raw Cf (zero-width, BOM, 방향 제어 등) | format_control / raw | 거절 |
| raw 기타 C 범주 (NUL, 그 외 Cc, Cs, Co, Cn) | other_unicode_control / raw | 거절 |
| 디코딩으로 새롭게 등장한 모든 C 문자 | encoded_control / decoded | 거절 |
| 키 반사·URL·마크업 | 전·후 문자열 및 각 디코딩 단계에서 거절 | 거절 |

raw 공백형 문자만 제한적으로 허용하며 **encoded CR/LF/TAB는 허용하지 않는다**.
숫자 HTML 엔터티의 NUL/서러게이트 등은 `html.unescape`가 치환/삭제하기 전에 검사한다.
인코딩으로 위험 문자가 사라져 검사를 우회하지 못하도록 하기 위한 처리다.
키 원문·인코딩뿐 아니라 CR/LF/TAB/공백으로 분할된 키도 검사한다.
모든 C 범주를 허용하거나 오류 행을 건너뛰지 않는다.

## 식별·검색·대조

- 공식 통계표 코드는 기존 엄격 검증과 실제 요청 식별자로 유지한다.
- `raw_name`: 안전성 검사를 통과한 원본 명칭을 메모리에만 유지한다. 저장/로그/Summary 대상이 아니다.
- `name`: CR/LF/TAB 및 ASCII 공백만 접은 검색·대조용 명칭이다.
- TableList 최초 조회·재조회와 ItemList의 STAT_NAME 검증에 **같은 text()**를 적용한다.
  코드 일치 + 정규화 명칭 일치를 요구한다. 서로 다른 명칭을 같은 것으로 추정하지 않는다.
- `국제\n수지` → `국제 수지`처럼 단어 경계를 보존한다. 기존 키워드 탐색은 공백을 제거해
  비교하므로 국제수지/일반여행 탐색도 유지된다.
- raw/정규화 결과에 각각 비밀값·URL·마크업 검사를 적용한다. 출력은 HTML/Markdown escape를 유지한다.
- P_STAT_CODE="*"의 전용 처리, 숫자 분류 → 월간 표 탐색, 실제 코드·항목 매핑 정책은 그대로다.

## 다음 실패의 진단

고정 필드명·분류와 선택적인 stage enum **raw / decoded**만 Summary에 기록한다.
분류에는 whitespace_control(다른 필드의 공백형 제어문자), format_control,
other_unicode_control, encoded_control을 추가했다. 기존 키/URL/마크업 오류도 stage를 갖는다.

예: `STAT_NAME / format_control / raw` 또는 `STAT_NAME / encoded_control / decoded`.
이것으로 원문 단계의 서식 문자와 인코딩 뒤 등장한 제어문자를 구분할 수 있다.
문자·코드포인트·위치·원본 이름·인코딩된 키·원본 응답은 출력하지 않는다.
캡처/렌더링 양쪽에서 enum을 검사하고 임의 진단 속성을 공개하지 않는다.

사용자 병합 후 main의 기존 ECOS Preflight를 수동 재실행해야 한다.
계속 실패하면 이 고정 분류·단계로 다음 조사 범위를 정한다. 형식만 보고 특정 문자를 추측하거나
서식/사설/미할당 문자를 무조건 허용하지 않는다. 실제 문자 확인이 꼭 필요하면 기관 확인 등
별도 안전한 절차가 필요하며, Secret이나 raw 응답을 채팅에 붙여 넣지 않는다.

## 테스트·보존

신규 합성 테스트 14개: CR/LF/TAB 정상화, 원본/정규화 분리, 두 TableList 및 ItemList 일관성,
다른 명칭 거절, zero-width/BOM/방향제어/서러게이트/사설/미할당, 인코딩 제어문자,
URL/HTML 중첩, 키 분할·인코딩 반사, 전후 표면 검사, stage 출력 보호, 기존 root 계층.
기존 공격 테스트는 삭제하지 않고 새 분류·stage 계약을 확인하도록 갱신했다.

운영 JSON 30개·workflow 6개·macro_sources.json·pipeline.json이 main과 바이트 단위로 같다.
운영 수집·source 활성화·data/live 쓰기·실제 금액 수집·Pages 배포·실인증 workflow 실행은 없다.
로컬 전체 Python **435개 통과(기존 421 + 신규 14)**, compile / diff --check 통과. GitHub CI 결과는 PR 본문에 기록한다. 자동 병합하지 않는다.
