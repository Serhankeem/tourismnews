# ECOS STAT_NAME 안전성 수정 (2026-11-06 KST)

기준 main: `4c123f60b0047ac7059d8f64c97db54ff0af49b0`.
실패 실행: https://github.com/Serhankeem/tourismnews/actions/runs/42161984194

## 원인과 검증의 한계

실행 메타데이터에서 해당 SHA의 workflow_dispatch 실패를 확인했다. 사용자 제공 Summary는
STAT_NAME / unsafe_content다. 기존 함수는 역슬래시, %HH, HTML 엔터티, Unicode C 계열,
URL/HTML, 인증키 및 인코딩 키를 하나의 조건으로 묶어 같은 오류를 반환한다.
**어느 하위 조건이 실제 인증 응답에서 발동했는지는 이 Summary만으로 알 수 없다.**
Secret이나 전체 인증 응답을 Codex로 가져오지 않았다. 공식 공개 sample TableList 첫 10행을
메모리에서만 검사했다. URL/HTML/%HH/엔터티/역슬래시/Unicode C 조건은 각각 0건이었다.
수정 파서는 이 10행 모두 처리했다. 실제 Secret과의 일치 조건은 검사하지 않았다.
이 결과를 전체 인증 목록 파싱 성공으로 확대 해석하지 않는다.

독립 합성 테스트에서는 기존 검사가 정상 명칭의 `20%20`, `&amp;`, 일반 역슬래시,
숫자 비교 기호도 거절할 수 있음을 확인했다. 이것들이 실제 실패 명칭에 있었다는 증거는 없다.

## 변경

STAT_NAME에 한해 일반 텍스트와 코드 필드를 분리한다. 한글/영문/숫자/공백/괄호/연산 기호/
퍼센트/일반 역슬래시/무해한 엔터티·퍼센트 문자열은 출력 이스케이프를 거쳐 처리한다.
원문을 HTML로 해석하거나 decoded 값을 렌더링하지 않는다.

모든 디코딩 단계(NFKC, URL, HTML entity, Unicode escape)를 최대 8회까지 검사한다.
인증키 반사, URL/위험 스킴, HTML/스크립트 태그, 제어·서식 문자는 계속 거절한다.
과도한 중첩·Unicode escape 표현은 보류한다. 코드/항목 필드의 기존 엄격 검증은 유지한다.
오류 행을 건너뛰거나 부분 성공으로 바꾸지 않는다. P_STAT_CODE="*" 전용 처리와 전체 계층
탐색도 기존 회귀로 유지한다.

고정 하위 분류:

| 분류 | 의미 |
| --- | --- |
| credential_reflection | 원문/인코딩 인증키 반사 |
| forbidden_control_character | Unicode 제어·서식 문자 |
| forbidden_url_pattern | URL 또는 위험 스킴 |
| unsafe_markup | HTML/스크립트 형태 |
| encoded_pattern | 비허용 인코딩 표현/과도한 중첩 |

여러 조건이면 키 → 제어문자 → URL → 마크업 순으로 먼저 잡힌 고정 분류를 남긴다.
Summary의 표 제목에서도 STAT_NAME 표시를 제거했다. 오류에는 필드명·고정 분류만 남기며,
명칭·Secret·API 원문·인증 URL·값의 해시는 남기지 않는다. 출력 필드 허용 목록과
HTML/Markdown escaping, 최종 Secret 반사 검사를 유지한다.

## 테스트·보존

새 테스트 8개에서 정상 다국어·숫자·특수문자, 독립 차단 조건, 중첩 공격, 키 반사,
코드 필드 엄격성, 이름 미노출, 오류 행 거절, 출력 escaping을 확인한다.
기존 root/계층 테스트를 포함한 전체 Python 검사와 PR CI를 확인한다.

운영 JSON 30개, workflow 6개, macro_sources.json, pipeline.json은 main과 바이트 동일하다.
금액 수집·source 활성화·data/live 변경·Pages 배포·수동 workflow 실행은 하지 않는다.
사용자 병합 후 main에서 ECOS Preflight를 재실행해야 전체 인증 목록 파싱과 실제 하위 오류를
확인할 수 있다. 관광수입·지출 실측 확보는 이 작업의 성과가 아니다.
