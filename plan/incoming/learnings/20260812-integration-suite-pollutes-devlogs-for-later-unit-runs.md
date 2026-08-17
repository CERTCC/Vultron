---
title: The integration suite writes repo-root devlogs/, so a later unit run fails the FV invariant harness
type: learning
timestamp: 2026-08-12
source: ISSUE-2266
signal: pre-existing-failure
---

## Observation

Phase 6 validation for #2266 was green in the documented order (unit, then
integration) but red when the unit suite was re-run afterwards:
four failures in `test/ci/invariants/test_fv_invariants.py`
(Invariant 1 for all three actors, and Invariant 5 for `validate_report`).

`test/demo/test_fv_demo.py::TestRunTwoActorDemo::test_full_workflow_succeeds`
drives `run_fv_demo()` in-process without setting `DEVLOGS_DIR`, so its final
dump phase writes real ledger files into the repo-root `devlogs/fv/`
(default `/app/devlogs`, `vultron/demo/scenario/fv_demo.py:898`). That makes
`load_devlogs("fv")` stop skipping, and the FV harness then evaluates the
in-process single-container ledger instead of the containerised artifact it was
written for. Because the dump is keyed by case URN, a second run adds a second
file to the same actor directory and `load_devlogs` concatenates both chains —
which is where the Invariant 1 `prevLogHash` mismatches come from.

Proven pre-existing: with the #2266 changes stashed, a pristine `origin/main`
worktree produces the same four failures against the same polluted `devlogs/`.
`devlogs/` is gitignored, so `git status` shows nothing and the failures read as
a broken branch.

## Why it matters

CI never sees this — the unit job and the demo job run in separate containers —
so it only bites locally, and it bites in the shape CONCERN-2243 warns about: a
red invariant harness that is not evidence about the artifact under test. Any
agent validating a branch after running the integration suite will attribute
these four failures to its own change.

Second, unrelated finding from the same evidence: a clean, "successful"
in-process FV run dumps only 9 ledger entries per actor, with **no**
`validate_report` and no `engage_case`. That is the in-process fidelity gap
already tracked in #2271 (no `CaseLedgerEntry` records are committed in the
single-container harness) and #2267 (the FV test can pass while accumulated
demo failures are non-empty) — not new, and not evidence about the containerised
FV demo. No issue filed for it.

## Status

Filed as **#2274** (Bug, parent Epic #2230, `size:S`). Until it lands, run
`rm -rf devlogs` before validating a branch if the integration suite has run in
that worktree.

**Promoted**: 2026-08-17 — captured in GitHub #2274 (open — already tracked).
Docs PR: TBD.
