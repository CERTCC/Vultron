---
title: "notes/flaky-tests.md lists fv Demo Integration under closed issue #2422; the flake reproduced on PR #3029"
type: learning
timestamp: "2026-09-02T16:00:00Z"
source: ISSUE-3022
signal: process-issue
---

PR #3029 (a spec-text, spec-lint and docstring change with no runtime code in
its diff) saw `fv Demo Integration` and `fv Invariant Harness` fail, then pass
on an unchanged-in-substance re-push. Both jobs passed on the second run along
with all 25 checks, and `main` was green on `demo-integration.yml` across the
eight preceding runs. The failure was the flake, not the branch.

The failure mode is the documented FV async race:

```text
AssertionError: run_direct_path_rm_triage: no VulnerabilityCase replica for
offer '…' in http://vendor:7999/…'s store — the CaseActor's
Create(VulnerabilityCase) never arrived (ADR-0041, PCR-01-003)
GATE FAILED: case replica present in …'s own store before validate-report
```

**The tracking problem**: `notes/flaky-tests.md` lists both job names against
issue **#2422**, dated 2026-08-20. #2422 is **CLOSED** ("flaky: fv Demo
Integration — vendor RM.RECEIVED timeout / notify-fix-ready 422"). So the cache
points at a closed issue while the flake still reproduces.

The file's own convention says GitHub is ground truth and that `bugfix`/`build`
remove rows when the issue closes. Applying that rule mechanically here would be
wrong in the more expensive direction: it would delete the only record of a
flake that demonstrably still fires, and the next agent to hit it would spend a
full investigation cycle rediscovering that a spec-YAML diff cannot break Docker
delivery timing. The row needs **repointing**, not removal.

**How to apply**: when a `notes/flaky-tests.md` row points at a closed issue,
check whether the flake still reproduces before deleting the row. A closed
tracking issue plus an observed failure means the issue was closed prematurely
(or fixed only one of several races sharing a job name) — file a fresh Bug and
repoint the row. Only delete a row when the flake is actually gone.

Related: [[20260826-sibling-demo-async-race-not-fixed]] — the same race window
across sibling scenarios, and the reason a per-scenario job name is a coarse key
for "which race".

---

**Archived**: 2026-09-03 — already resolved. `notes/flaky-tests.md` rows for `fv Demo Integration` / `fv Invariant Harness` were repointed to #3033 (OPEN) on 2026-09-02. No further action.
