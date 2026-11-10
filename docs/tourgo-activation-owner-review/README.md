# TOURGO Activation Configuration — Owner Review Pack (NON-OPERATING DRAFT)

> **Review only. This PR is NOT collection approval, NOT publication approval, NOT a production configuration PR, and NOT permission to execute initial publication.**
>
> Deliberately leaves `macro_sources.json`, `operating_policy.json`, `data/live`, GitHub workflows, all source/indicator activation gates, and website publication unchanged.

## 1. Decision record (pending owner decision)

| Item | Recorded basis / proposed action | Status |
|---|---|---|
| Institutional terms | 2026-11-09 TOURGO/KCTI response summarized in `docs/tourgo-macro-integration-v1/README.md`: noncommercial use and explicit TOURGO attribution for monthly statistics; keep the original communication privately | **Terms documented; independently review exact scope** |
| Data scope | General-travel receipts, expenditure and balance; official 2021-01–2026-09 XLS, 69 months; original `천 US$` to internal `US$` to public `백만 US$` | Staging verified separately, NOT activated |
| Collection approval | Site operator's **separate, affirmative** decision to receive and manually import the official files | **NOT GRANTED** |
| Publication approval | Site operator's **separate, affirmative** decision to publish validated figures, provenance and source URL | **NOT GRANTED** |
| Approval dates | Proposed **90-day internal review cycle** from the owner's eventual approval date; a finite `valid_until` is mandatory. This is NOT an institutional license expiration date | **TBD, not approved** |
| Operator conditions | Noncommercial, free, no advertisements, source attribution; if these conditions change, stop using the applicable TOURGO publication gate | Confirm again before activation |
| Source choice | `tourgo_tourism_balance` with existing `kto_tourism_receipts`/`kto_tourism_expenditure` IDs. Do not enable either ECOS source | Planned, NOT switched in production |
| Actual publication | Only after private environment setup, fresh official XLS staging, a separate activation configuration PR, explicit owner approval and a verified 10-minute solo-owner Environment wait rule | **NOT AUTHORIZED** |

**Institutional terms are not an operator approval.** Keep an email/PDF copy of the 2026-11-09 response in the owner's private records. Public source control should store a **non-sensitive reference ID**, never sender names, email addresses, tokens, credentials or raw confidential correspondence.

## 2. Owner-controlled approval schema

`approval.DRAFT.json` in this folder is an **intentionally invalid illustration**. Its `YYYY-MM-DD` fields and `PENDING_*` IDs are not approvals. Never send it to the activation CLI as a completed authorization.

When—and only when—the owner makes **two affirmative decisions**, prepare a separate private file with:

- `terms_evidence_ref`: stable internal ID for the KCTI/TOURGO terms evidence;
- `collection.evidence_ref`, `publication.evidence_ref`: **different** owner decision IDs, each distinct from the terms ID;
- `valid_from`, finite `valid_until` for **each** decision, covering the eventual date of operation;
- exactly `noncommercial=true`, `free_access=true`, `no_ads=true`, `attribution=true`.

An internal 90-day cycle is only a proposed choice. If approved, use the **actual** decision date, not the 2026-11-09 institutional reply date, as the start of the operator's review period. Record the owner's decision securely. **Do not fabricate evidence_ref or approval dates.**

After explicit approval, generate a **new, separate** configuration review:
```sh
python -m src.macro.tourgo_activation \
  --approval /secure/owner-approval.json \
  --output /secure/new-tourgo-activation-review
```

Review `macro_sources.proposed.json` outside the checkout. The generator will not edit the active file. Submit a separate approval-specific PR against latest `main` **only after** confirming the terms and the two decisions. That subsequent configuration PR must not auto-merge.

## 3. Official data and staging boundaries

Prior independent staging with PR #39 read actual 3 official files at the pinned hashes and validated **69/69 identities**. In its snapshot it preserved KTO 483 observations while incorporating TOURGO receipts 69 + expenditure 69 = 621 non-balance observations. The official 2026-09 values were: receipts 2,460.8, expenditure 2,958.8, balance -498.0 million US$.

**These are historical verification facts, not evidence that today's newer `main` + `data/live` is already approved for publication.** PR #40 changed the implementation fingerprint; prior staging receipts cannot be replayed. After the activation configuration is finalized, create **fresh read-only staging** against latest `main` and `data/live` and validate all three original XLS hashes, 69/69 balance identities, current KTO archive preservation, public projection, metadata separation and staging UI. Do not commit the original files, private ledger or receipts to this public repo.

## 4. Handoff and production hard stops

The site owner handles the GitHub **solo-owner** protection (10-minute timer, no required reviewers, admin bypass off, main-only branch), private input secrets and final execution. A wait timer is not a substitute for independent review. See [PROTECTION-RUNBOOK.md](PROTECTION-RUNBOOK.md).

The following remain **OFF** in this review PR:
- `tourgo_tourism_balance.enabled=false`;
- `approval.collection.approved=false` and `approval.publication.approved=false`;
- `kto_tourism_receipts` and `kto_tourism_expenditure` remain disconnected;
- ECOS remains disabled;
- no `data/live` updates and no validated TOURGO financial values on Pages.

This PR may merge as **review documentation and fail-closed tests only**; it is **NOT** the later activation configuration PR. PR CI reports test success, not a real protected end-to-end production publication.
