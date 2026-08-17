---
title: "The harness propagates the original exception and attaches accumulated failures as notes"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2239
signal: design-question
---

ISSUE-2239 specified the shape — "run phases, always dump ledgers, then assert.
The dump belongs in the `finally`" — but not what the failing path should raise.
Two behaviours are defensible and they differ in what a CI reader sees:

- Call `assert_demo_success()` unconditionally on the way out. Consistent, but
  on the failing path it replaces the exception that actually ended the run with
  a generic `DemoFailureError("N demo failure(s)")` — exactly the unusable
  reporting #2240 is about.
- Let the original exception propagate untouched and attach the accumulated
  `demo_check` failures via `exc.add_note()`.

`scenario_harness()` does the second. The traceback still points at the phase
that died; the soft failures that `demo_check` had recorded and would otherwise
be dropped ride along as `__notes__` (DEMOMA-23-004, SHOULD-level). Only the
succeeding path calls `assert_demo_success()`.

Two consequences worth knowing before touching this:

- **A dump error must not become the reported failure.** The dump runs inside
  `demo_step`, which records and continues, so a dump that dies still leaves the
  scenario's own exception in charge — and a scenario that otherwise succeeded
  but failed to dump does fail, as an accumulated failure rather than a raise.
- **The backstop manifest is written only when the dump raised.** Writing it
  from an unconditional `finally` looked equivalent and was not: `dump_case_ledgers`
  writes its own manifest, so the backstop only ever fires when the dump never
  got that far. Unconditionally, it stamped the "dump crashed" reason onto runs
  whose dump was fine — including unit tests that stub the dump out, which then
  wrote a spurious manifest into the repo-root `devlogs/` and turned the local
  invariant harness's skips into failures. Pinned by
  `test_no_crash_manifest_when_the_dump_succeeds`.

Unresolved and already tracked, noted here so it is not mistaken for settled:
AGENTS.md, DEMOCI-01-007 and ADR-0058 all describe `demo_gate` as the primitive
that stops dependent steps, and it still does not exist in code (#2201, #2203).
The harness makes an escaping assertion survivable; it does not make the ~20
unguarded `wait_for_case_participants` call sites causal.

**Promoted**: 2026-08-17 — captured in specs/demo-multi-actor.yaml DEMOMA-23; GitHub #2201, #2203 (already tracked).
Docs PR: TBD.
