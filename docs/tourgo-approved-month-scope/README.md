# TOURGO Monthly Automation Phase 1 — Step 1

이번 PR은 승인 기준월 강제만 구현합니다. 자동 다운로드/신규 월 승인/운영 데이터 갱신/수동 게시/Secrets·보호 환경 변경/자동 병합을 수행하지 않습니다. 기존 workflow와 배포 파이프라인도 변경하지 않았습니다.

## 설정과 공통 검사

`macro_sources.json`의 TOURGO `approval.collection`과 `approval.publication` 각각에 다음을 추가합니다.

```json
"period_from": "2021-01",
"period_through": "2026-09"
```

기존 approved/enabled·근거·`valid_from`·`valid_until=2027-02-08`·source/indicator 매핑은 변경하지 않았습니다. 승인 유효일과 통계 기준월은 독립적입니다. ECOS 비활성도 유지합니다.

`tourgo.py`의 `approved_range / require_range / require_periods / require_ledger_scope`를 모든 관련 경로에서 재사용합니다. 범위 누락·형식 오류는 `tourgo_period_scope_unverified`, 초과는 `tourgo_period_scope_exceeded`로 차단합니다. 오류에 파일 내용·금액·토큰을 포함하지 않습니다.

| 위치 | 적용 |
| --- | --- |
| private 초기/정정 전달 | manifest·receipt 메타데이터 범위를 먼저 검사. 범위 초과면 ledger/XLS blob 요청 안 함 |
| private 반복 전달 | 기존 owner 서명·main·10분 timer·bypass 금지 검사 후 manifest 범위 검사. 미확인/초과면 원본 다운로드·temp 파일 생성 안 함 |
| 원본/비공개 원장 디코더 | 기간을 확인할 수 있는 입력만 읽음. 이후 실제 period와 revision metadata를 재검사 |
| `OfficialFiles`, package/inspect CLI | 원본을 열기 전에 소유자가 검토한 범위를 검사. 실제 파싱 범위 불일치/초과는 파일 복사·원장 병합 전에 거부 |
| `stage`, `ReleaseRequest`, `fetch` | 입력·영수증·원장 범위와 현재 권한을 재검사. 공개용 영수증은 collection/publication 모두 만족해야 함 |
| `public_pair` | 기존 보관 자료의 승인된 month key만 선택한 후 그 값으로 공개/비교/관광수지 계산. 보관 원장/정정 이력 삭제 안 함 |
| legacy preview/prepare/download callback | 이전 도구로 우회하지 못하도록 같은 기간 검사를 적용. 범위 없는 callback은 호출하지 않음 |
| activation/Preview 설정 복사 | 실제 월 범위를 보존. 격리 Preview는 collection 범위 안에서만 생성하고 실제 publication 승인을 대체하지 않음 |

범위 초과 **입력을 받아 잘라 정상 자료로 승격하지 않습니다.** 입력 전체를 거부/검토 보류합니다. 기존 보관 자료의 공개 범위 제한은 원장 삭제와 구분됩니다.

## 사전 범위 확인과 호환성

- 고정 SHA 3개로 독립 검증한 기존 69개월 초기 XLS는 정확한 기간을 알고 있으므로 기존 6파일 계약을 유지합니다. legacy 초기 manifest에 새 필드가 없어도 핀이 일치하면 처리할 수 있습니다.
- 그 외 입력은 `period_range` 메타데이터가 필요합니다. **현재 승인 설정이나 오늘 날짜로 입력 기간을 자동 채우지 않습니다.** 서명된 소유자 입력/검토 영수증이 파일 해시와 기간 선언을 묶습니다. 기존 schema 1/2와 파일 개수는 유지합니다.
- 기존 CLI의 임의 원장/다른 빈티지 입력에는 `--period-from 2021-01 --period-through 2026-09`를 명시해야 합니다. source package의 manifest는 이 선언과 원본 해시를 프로그램이 함께 생성합니다.
- 메타데이터가 불명확한 오래된 업데이트 패키지는 원본을 먼저 다운로드/파싱하지 않고 보류합니다. 올바른 범위 메타데이터로 다시 준비해야 합니다.
- 원본을 검토했다고 주장하는 자동 manifest만으로 공식성을 인정하지 않습니다. 서명된 소유자의 원본/기간 검토라는 기존 신뢰 경계를 유지합니다. 이 PR은 안정적인 공식 HTTP 다운로드 경로를 추가하지 않습니다. 향후 HTTP 수집은 서버가 승인 기간만 반환한다는 근거가 없으면 요청해서는 안 됩니다.
- 코드 fingerprint가 바뀌므로 향후 수동 정정·갱신에 기존 영수증을 재사용할 수 없습니다. 최신 코드/원장으로 검토 패키지를 다시 생성해야 합니다. **이미 게시된 기존 69개월은 그대로 유지되며 initial 게시를 다시 실행할 필요가 없습니다.** 이 PR에서 private 패키지나 Secrets를 갱신하지 않았습니다.

[수정된 기존 운영 매뉴얼](../macro-data-pipeline-v2/OPERATOR-RUNBOOK.md).

## 검증

- Python 전체 573개 통과(기존 558 + 신규 범위 검사 15). 기존 v2의 70개월 성공 예제는 **로컬 bare Git 합성 fixture에만 명시적인 별도 10월 승인**을 설정해 확장 동작을 검증합니다. 실제 저장소는 9월 상한입니다.
- 9월 경계/10월 초과/범위 누락/유효일·철회/원본·원장 미열람/다운로드 callback·blob 미호출/공개 필터/69개월·정정 보존을 검사합니다.
- 실제 보유 승인 XLS 3종을 새 코드에서 읽기 전용 재검사: 고정 SHA 3/3, 69개월 항등식 69/69, 정수 US$ 환산 통과. 새 다운로드·private 원장/패키지 저장 없음.
- 운영 snapshot `ac41eab1cf36de9d858423920f393fba06d7628e`: News 86, Research 137, KTO 483 + TOURGO 금액 138 = 총 621개. 새 코드로 재투영한 **운영 파일 30개 SHA 전부 동일**, KTO·관광수지·정정·승인/가시성 이력 유지.
- 브라우저 전체 23개 스위트와 실제 69개월 UI의 320/390/768/1440px 검증을 수행합니다. 기존 합성 주입 스위트는 현재 News/Research + 미연동 Macro fixture, 실제 운영 Macro는 별도 69개월 검사로 검증합니다.
- main의 기존 ECOS 브라우저 fixture가 이관된 source_id를 TOURGO로 남겨 실패하는 것을 unchanged main에서 재현했습니다. **fixture만** `ecos_general_travel`로 명시했고 ECOS 엔진/활성화/앱 코드는 변경하지 않았습니다. 초기 동결 News 데이터에 없는 KPI/표제 가정은 현재 snapshot을 사용해 해결했습니다.
- GitHub CI 최종 결과는 PR Checks/설명에 기록합니다. 실제 source 수집·data/live push·Pages 배포 job은 PR에서 실행하지 않습니다.

[파일별 보존 SHA](preservation.json). 원본 파일·원장 금액·토큰은 보고서/공개 로그에 첨부하지 않습니다.
