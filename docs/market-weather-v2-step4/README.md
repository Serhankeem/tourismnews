# Market Weather v2 Step 4 — private decimal collection foundation

Related: [Issue #49, Step 1–3](https://github.com/Serhankeem/tourismnews/issues/49).
This change implements collection plumbing, not operational activation or publication approval.
All three new ECOS sources and nine indicators default to `enabled: false`.
Collection reviews and rights remain pending. There is no decimal public projection.

## Design and scope

- Reuse the existing `ecos.Client`: authenticated official API, pagination, robots,
  throttling/retry, TLS, redirect/response limits and credential-safe errors. No new
  database, workflow, collector command, admin page, UI or composite score.
- `src/macro/ecos_decimal.py`: independent monthly index/FX adapter; table and all
  selectors checked against metadata and each observation. Group 1 must declare
  the expected unit; secondary classification selectors may have a null unit,
  as the official production-index Group 2 does. Actual observations must always
  declare the expected unit. Only complete monthly ranges are accepted.
- `src/macro/model.py`: canonical decimal **strings**, not floats or JSON numbers.
  Up to 30 integer and 18 fractional digits; reject nonfinite/exponent/negative,
  float/bool inputs. Decimal arithmetic uses precision 80; rates are strings
  rounded half-up to six decimal places. Normalization removes insignificant
  trailing zeros while preserving the original `source_value`. No YTD index or
  exchange-rate sums. Scaled integers were considered but would require
  per-series scale migrations and could truncate future reported precision.
- `src/macro/decimal_series.py`: optional `decimal_indicators` and `decimal_sources`
  inside the **existing private** `macro_archive.json`. Existing integer
  `indicators`, KTO/TOURGO approvals, source identities and revisions are unchanged.
  Identity changes (unit/base year/definition/selectors/publisher/provider/source)
  require separate review; they do not overwrite an existing series.
- `src/macro/engine.py`: existing collector dispatches the new method after explicit
  source activation + dated collection review + indicator activation. Default
  configuration never requests the new API. Per-source staging is atomic:
  reject gaps, duplicates, future/latest-month errors and metadata/unit drift,
  preserving the last validated data. A failed source cannot erase another.
- `src/pipeline/validation.py`: durable snapshot validation checks optional decimal
  records, immutable first collection time, retained months and previous revisions;
  changed values/finality require an exact before/after revision.

No public export exists for these types, even if enabled or rights flags are
changed. `release_published_at` / `original_publication_at` stay null because ECOS
observation responses do not provide an exact publication timestamp. Never use
collection time as publication time. Finality stays `not_stated`; official
provisional notes are not silently converted into per-observation final status.
Every private record retains original selected row fields/value, response SHA-256,
collection times, definition, provider, crosscheck state and collection mode.
Value/finality changes retain full previous/current records and detection time.
Replays update last checked time but create no duplicate observation or revision.

## Registered monthly series

Provider/collection path: 한국은행 ECOS / official `StatisticTableList`,
`StatisticItemList`, `StatisticSearch` with `ECOS_API_KEY`. Index originator:
국가데이터처; FX originator: 한국은행. All begin 2021-01.

| Indicator | Table / item selectors | Unit/base | Step 3 latest month | Observations / YoY |
|---|---|---|---|---|
| 숙박업 생산지수 | 901Y038 / I51ADA / 2 (불변지수) | 2020=100 | 2026-09 | 69 / 57 |
| 예술·스포츠·여가관련 서비스업 생산지수 | 901Y038 / I51AL / 2 | 2020=100 | 2026-09 | 69 / 57 |
| 원·달러 월평균 환율 | 731Y004 / 0000001 / 0000100 (평균자료) | 원, no base year | 2026-10 | 70 / 58 |
| 숙박 서비스 CPI | 901Y009 / K02 | 2020=100 | 2026-10 | 70 / 58 |
| 호텔숙박료 CPI | 901Y009 / K02101 | 2020=100 | 2026-10 | 70 / 58 |
| 여관숙박료 CPI | 901Y009 / K02102 | 2020=100 | 2026-10 | 70 / 58 |
| 콘도이용료 CPI | 901Y009 / K02103 | 2020=100 | 2026-10 | 70 / 58 |
| 국내단체여행비 CPI | 901Y009 / I06101 | 2020=100 | 2026-10 | 70 / 58 |
| 해외단체여행비 CPI | 901Y009 / I06102 | 2020=100 | 2026-10 | 70 / 58 |

Monthly average FX selector excludes month-end `0000200`. Production indices are
unadjusted constant indices, not nominal or seasonally adjusted indices. These
are auxiliary environment/proxy series; aggregate accommodation CPI and its
components overlap. No summation, arbitrary weighting or weather classification.

## Isolated verification

`python -m unittest discover -s tests -v` passed all **594 tests**, including
KTO/TOURGO, existing ECOS, news, research and transactional pipeline regressions.
`tests/test_macro_decimal.py` adds 13 focused tests using synthetic observations and injected metadata;
no network or real keys. It covers exact decimals, comparisons, default-off and
review/auth gates, all selectors, units, duplicates, gaps, future metadata,
identity drift, repeated collection, correction/finality vintages, history-loss
rejection, failed-source atomicity, legacy preservation and secret-safe errors.

The actual Step 3 originals remain outside the checkout at
`/workspace/work/weather49-step3`. Real raw values were **not** added to Git or
public fixtures. Reproduce with a fresh output directory outside the repository:

```sh
python -m tools.validate_market_weather_foundation \
  --evidence-dir /workspace/work/weather49-step3 \
  --work /workspace/work/weather49-step4/new-offline-replay
```

The tool validates 63 original response hashes against their acquisition metadata
and Step 3 manifest; verifies aggregated rows equal the original pages; then
runs the **existing engine** against original observations. Metadata transport is
simulated, not a new authenticated metadata/API test. It reproduces 628 exact
observations and 520 YoY results against the independent Step 3 research rates,
checks repeat collection, injects one correction, and verifies a failed fetch
leaves the archive/public files byte-identical. Retained output includes private
raw fields, vintages, metadata/hashes and a report; no real data enters the site.
[Replay results](replay-verification.json) list counts and original response hashes.

A second isolated replay used the latest fetched `data/live` commit
`4e7f2f2923773b2d6f4533e9be241e1012cd0768`. Existing Macro 621 observations and
source/revision ledgers remained equal; the existing public projection remained
equal; 26 other data files stayed byte-identical. Pipeline validation accepted
628 additional private records alongside news 97/archive 110/discovery 8,823 and
reports 137. [Preservation results](live-preservation.json). Production `data/live`
was only read/fetched, never written.

## Conditions still required before any activation

1. Configure an authorized ECOS key through the existing secret mechanism and
   verify authenticated metadata/observation access, pagination, operational
   limits, latest release availability and safe error handling in isolation.
   No key is configured here. Only original public-sample observation replay and
   synthetic metadata tests passed; authenticated operation is **unverified**.
2. Complete ECOS and originator reuse/attribution/redistribution review for each
   series. Step 3 production publication carried KOGL Type 2 restrictions; CPI
   publication Type 1 does not automatically resolve all API reuse conditions.
   No new series is publishable or approved by this PR.
3. Complete KOSIS original-table comparison with matching month, industry, index
   type and base year. Leisure's nine level checks and hotel/overseas-tour rate
   comparisons are partial evidence only; all full-period checks remain pending.
4. Explicitly review source collection enablement separately from rights/public
   enablement. Public projection and homepage exposure need a later reviewed
   implementation; flipping these flags alone cannot publish the new series.

Aviation, tourism card consumption, employment, annual structural statistics and
TOURGO approval expansion are outside this change. No operational Actions,
merging, deployment, Scenario Lab or UI changes are part of this work.
