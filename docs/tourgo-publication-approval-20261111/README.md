# TOURGO 69개월 홈페이지 공개 승인 — 2026-11-11

## 사용자 결정
- 여행기류(currentourism) 소유자가 2026-11-11 대화에서 TOURGO 관광수입·관광지출·관광수지 69개월 데이터의 **홈페이지 공개**를 명시적으로 승인함.
- 기존 수집 승인: `owner-collection-20261110-tourgo69m` (2026-11-10 ~ 2027-02-08).
- 이번 별도 홈페이지 게시 승인: `owner-publication-20261111-tourgo69m` (2026-11-11 ~ 2027-02-08).
- 두 기한은 프로젝트의 **내부 재검토 기한**이며 제3자 자료 이용 허가 만료일을 의미하지 않음.
- 기관 이용조건 근거: 기존 `docs/tourgo-macro-integration-v1/README.md` (2026-11-09 확인). 내부 추적 ID `institution-terms-20261109-tourgo`; 기관으로부터 새 허가를 받았다는 주장은 아님.
- 비영리·무료·무광고·TOURGO 출처 표시는 필수.

## 범위
- 초기 게시 대상은 공식 XLS에서 검증한 **2021-01 ~ 2026-09, 정확히 69개월**.
- 관광수입·관광지출은 원본 천 US$에서 정수 US$로 변환해 기존 Macro 지표 ID에 연결.
- 관광수지는 공식 원본과 수입−지출이 매월 같아야 하며, 음수 수지를 유지하고 수지 증감률(%)은 표시하지 않음.
- `macro_sources.json`은 기존 두 지표를 비활성 ECOS 매핑에서 TOURGO로 명시적으로 전환하고, ECOS 원천은 비활성으로 유지.
- **2026-10 이후 신규 월 업데이트는 이번 초기 게시 승인에 포함되지 않음.** 코드의 `scope=general_travel_monthly`만으로 추가 월이 기술적으로 차단되지는 않으므로 후속 신규 월을 승인 없이 수집·게시하지 않도록 운영 절차와 실행 조건을 별도로 확인할 것.
- 공식 TOURGO 원본 자동 다운로드는 구현돼 있지 않으며, 정기 자동 파일 게시를 승인하거나 활성화하지 않음.

## 최초 게시 실행과 PR 병합 구분
1. 이 PR은 **공개 승인·출처 매핑 설정**에 대한 변경과 테스트만 포함. 비공개 XLS, 원장, 검증 영수증, 토큰, 공개 Macro JSON, `data/live` 변경 없음.
2. 병합 시 보통의 Pages/기존 일일 Macro 작업이 호출될 수 있으나, 수동 TOURGO 원본이 없으면 숫자 등록을 하지 않아야 함. CI에서 이 조건과 권한 철회·정정 보존을 확인.
3. 처음 저장되는 실제 TOURGO 69개월 수치는 **별도의 보호된 `TOURGO initial publication (manual)` Actions**를 명시적으로 실행해야만 반영됨.
4. **기존 비공개 입력 패키지는 최초 게시 시 바로 재사용할 수 없음.** 현재 `main`, `data/live`와 코드 implementation fingerprint가 변경되면 `receipt.json`, `ledger.json`, `manifest.json`를 최신 원본과 새 baseline으로 재생성하고 비공개 루트 6개 파일만 포함한 고정 commit을 검토해야 함.
5. 보안 환경 `tourgo-production`의 Wait Timer >=10분, 관리자 bypass 금지, main-only 규칙, owner actor 1명과 읽기 전용 private token을 최종 확인.
6. 신규 private input commit과 manifest SHA를 지정하는 Environment Secrets 및 GitHub actor 권한은 별도 검증. 토큰은 PR, 채팅, public logs에 기록하지 않음.
7. 재생성 영수증의 `operating_approval:false`는 의도적으로 정상임. 승인 설정은 코드·protected environment에서 별도로 검증하며, 영수증은 격리 Staging 결과임.
8. 보호된 최초 게시 후 **data/live 원장 저장 성공과 GitHub Pages 배포 성공을 각각 확인**하고 홈페이지 최신 기준월·기존 KTO·News·Research 보존, 원본 비공개 여부 검증 후 완료 선언.

## 실행 전 게이트
- 공식 XLS SHA-256 핀 3/3, 69/69 수지 항등식, 기존 KTO 483개 보존, 신규 138개 → 총 621개 검증.
- 소스/매핑·기간 승인 유효, 저작권 이용조건 확인, 수집·게시 승인 구분.
- 구성 변경이 전체 일일 자동 수집을 실패시키거나, 사전 입력 없이 자동으로 금액을 공개한다면 병합/배포 중단.
- 현재 이 문서와 PR 자체는 최초 게시 성공의 증빙이 아님.

**이 PR을 검토·병합해도 최초 실데이터 게시 Actions까지 자동 실행하는 것은 아님.**
