# TOURGO Excel Importer v1.0 — PR #36

## Scope and status

**Preparation-only.** Fix the official TOURGO XLS BIFF formatting-only 15th column and provide a read-only validation mode. No approved publication or automated downloads, no `data/live` or `site/data` updates, no Macro indicator enablement, no changes to ECOS.

The authority replied on 2026-11-09 that metadata/statistical numbers from TOURGO can be automatically collected, processed into charts and percentages, and reproduced on a **noncommercial project with clear TOURGO source attribution** without prior permission. The full original reply is held outside the public repository. This acknowledgement does **not** approve ECOS's independent API terms or override future changes to TOURGO's export route/format.

## Official sample and provenance (offline)

Official 2026-11-09 operator-provided XLS exports were inspected separately in a private workspace, **not committed**. Source: https://know.tour.go.kr/stat/koreaTourIncomeDis19Re.do

| Export | SHA-256 | Scope |
| --- | --- | --- |
| 관광수입 | `780465a3e72886e94643dd6da5f2fa03d3f5d0a991200ce29313e969eae51f7d` | 2021-01–2026-09 |
| 관광지출 | `c21d857270a37d29251f3f3c0d2314c50b49c1b73259c7fbab50f7eb72e96ff1` | same |
| 관광수지 | `c2a3bd7ba225db9117fcb5535c0f8957ff80f0440801c18080080a74a3f2f721` | same |

- 69 monthly observations for each of 3 series, unit `1,000 US$` (thousand USD).
- The preflight staging ledger's original-file hashes were independently reproduced from the attached XLS binaries, and all 69 arithmetic identities `receipts - expenditure = balance` matched.
- Previous offline cross-check: 18/18 annual series totals and 6/6 annual balance identities matched, with unpublished 2026-10–12 blank.
- The displayed XLS grid contains 14 business columns, while BIFF declares 15 columns with a wholly empty, formatting-only trailing column. The new parser accepts such trailing columns **only when all trailing cells are truly empty** (empty string or None); any value, whitespace, or unexpected extra header/data causes a hard failure.
- Publisher subject/category of each XLS was identified by cross-series numerical relationships and filenames. A future import operator should additionally retain the selected label from the official download UI; numerical consistency alone does not independently prove publisher provenance or statistical definition.
- Final/provisional status: not stated by the supplied sheets; do not infer finality.
- The current execution environment does not have `xlrd` and cannot install packages from the network. Therefore the runtime read of the raw XLS via the updated `read_xls()` is **not yet independently executed**. Synthetic parser regression tests and raw hashes/arithmetic checks are separate evidence, not a claim of live XLS parsing success.

## Local read-only validation (no writes)

Install pinned `xlrd==2.0.2` in your own trusted Python environment, keeping the three raw XLS files outside this repository.

```bash
python -m pip install xlrd==2.0.2
python -m src.macro.balance_prepare \
  --receipts "/absolute/private/path/관광수입.xls" \
  --expenditure "/absolute/private/path/관광지출.xls" \
  --balance "/absolute/private/path/관광수지.xls" \
  --private-dir "/absolute/private/tourgo-validated" \
  --verify-only
```

The read-only mode validates strict sheet count, headers, individual rows, year totals, equal monthly period sets and receipt − expenditure = balance. It rejects accidentally supplying the same path under multiple kinds and prints only count/latest month/validation status, not statistical values. It **never creates an output ledger**.

For offline private import, omit `--verify-only` **after** successful validation; importer writes `tourgo_balance_private.json` only under `--private-dir` outside the repository, with SHA-256 provenance and revision history. Existing collection/publication gates stay inactive.

## Release gates, next PR

1. Run the real XLS parse against the exact SHA-256 matched originals using installed `xlrd`, and document results without committing raw files or private full correspondence.
2. Confirm official selector labels and release vintage/finality; retain noncommercial policy and mandatory source attribution evidence in a reviewed private record.
3. Independently review the target Macro schema, USD amount scale (thousand USD raw versus million USD UI), visualization and revisions; adapt only through a separate integration PR.
4. Explicitly review `collection` and `publication` approval states, rights constraints, permission revocation/policy drift, and update About/source credit only when actually published.
5. No automatic source fetching or public indicator enablement in this PR. ECOS-related approval stays separate.

## Regression tests

`python -m unittest discover -s tests -v`

New tests cover BIFF-style trailing blank cells, rejected populated/whitespace tails, header/data shape errors, signed balance rows, and zero-write `--verify-only` execution via synthetic mocks. Existing negative-path and approval-gate tests remain intact.
