# Owner Handoff — GitHub tourgo-production (NO EXECUTION UNTIL APPROVED)

## Purpose

The manual TOURGO workflow must be unable to publish when the input, operator authority, environment protection or approvals are missing. GitHub Environment protection is separate from the institution's data reuse terms.

## A. Protect the publication environment

Open `https://github.com/Serhankeem/tourismnews/settings/environments`, create **`tourgo-production`** and set:

1. **Required reviewers**: a trusted independent GitHub reviewer, different from the workflow initiator. Enable **Prevent self-review**. If there is no separate reviewer, **STOP**; do not weaken protection to bypass the gate.
2. Disable administrator bypass: `can_admins_bypass=false`.
3. Deployment branches/tags: **selected branch main only**, with no tag exemptions.
4. Verify these controls actually save and are supported by the repo plan/visibility.

Do not use existing `github-pages` as the protected TOURGO environment.

## B. Prepare the private inputs (owner-managed, not this PR)

Use a separate **private** GitHub repository whose pinned, independently reviewed commit root contains exactly six regular blob files:

```
manifest.json
ledger.json
receipt.json
receipts.xls
expenditure.xls
balance.xls
```

- `ledger.json` must be the raw bytes from fresh PR #40 staging `validated-input.json`.
- `receipt.json` must be the raw bytes from that same staging `readiness.json`.
- XLS must be the actual, pinned official files; the GitHub delivery code reparses and compares their values to the ledger.
- `manifest.json` supplies SHA-256 for the 5 other files and has `schema_version=1,profile=initial`.
- Do not include README, symbolic links, unreviewed commits, private correspondence, tokens or extra root files in this *input* repository at the pinned commit.
- Staging must be **regenerated after the activation code/config and baseline Macro archive are final**, as the code and baseline fingerprints are checked during actual execution.
- Verify the private repository, pinned 40-character commit SHA, manifest SHA and file hashes independently. No public artifacts or public Git source copies.

## C. Five **Environment Secrets** (not Repository Secrets)

| Secret | What the owner must supply |
|---|---|
| `TOURGO_INPUT_TOKEN` | Expiring, fine-grained, read-only token scoped to the private input repo and permitted environment-check scope; never paste into chat or public PR |
| `TOURGO_INPUT_REPOSITORY` | `owner/private-repository` |
| `TOURGO_INPUT_COMMIT` | Reviewed exact 40-character private commit SHA, no floating branch |
| `TOURGO_MANIFEST_SHA256` | Independently reviewed manifest byte SHA-256 |
| `TOURGO_ALLOWED_ACTOR_IDS` | Authorized numeric GitHub actor IDs, comma-separated |

Verify token permissions and environment API accessibility before attempting a real publication. Never share secret values in this conversation.

## D. Separate configuration and final publishing procedure

1. Owner approves **collection AND publication** separately with distinct references and finite review windows.
2. Generate review-only activation plan, submit and validate a separate `macro_sources.json` configuration PR, merge only when the owner explicitly authorizes the production configuration.
3. Recreate official 69-month staging from latest actual XLS + final `main` and `data/live`; verify hashes, identities, preservation, fields, and Pages preview. Regenerate private ledger/receipt if the implementation or Macro archive changes.
4. Populate the private input repo and five environment secrets; independently confirm configured protections and non-self reviewer.
5. Only on explicit final go-ahead, run GitHub Actions → **TOURGO initial publication (manual)** on `main`, `confirm_reviewed_initial_publication=true`, obtain independent environment review.
6. Validate transaction, latest `data/live` and deployed Overview/Macro pages before declaring success. Distinguish successful storage from successful Pages deployment.
7. On fail: do not force-push or paste a staging public JSON into production. Diagnose/re-stage via existing validation workflow. Existing KTO/News/Research must remain intact.

**Nothing in the present PR is an operational grant or instructions to execute the workflow now.**
