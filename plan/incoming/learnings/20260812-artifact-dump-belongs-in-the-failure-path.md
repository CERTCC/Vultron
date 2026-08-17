---
title: "No spec required forensic artifacts to survive the failure they document"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2239
signal: spec-gap
---

DEMOCI-04 requires the demo job to upload `devlogs/` as an artifact and the
invariant harness to run as a separate `if: always()` job. Both were implemented
correctly. Nothing anywhere required the *producer* of that artifact to run on
the failing path, so all nine scenarios ended `run_<name>_demo()` with a plain
call to `_phase_dump_case_ledgers()` — code that by construction runs only when
nothing went wrong. The workflow-side requirement (`if: always()`) and the
application-side placement (after the last phase) were each locally reasonable
and jointly guaranteed that the run most in need of forensics produced none.

The gap is a shape, not a line: **an artifact whose only purpose is diagnosing
failures must be produced from a path that failure cannot skip.** Filled as
DEMOCI-10-001/-002 (dump from a path that runs on failure; always write a
manifest) and DEMOMA-23-001/-003 (`scenario_harness()` owns the ordering;
register the dump as soon as a case exists).

The related trap, worth stating separately because it survived the first fix
attempt: the invariant harness treated a missing/empty `devlogs/` as "no test
data" and called `pytest.skip`. A skip that means *"the thing I was going to
assert on is absent"* is a false green whenever the absence **is** the failure.
Distinguishing the two needs evidence from the producer, which is why the dump
now always writes `dump-manifest.json` — the manifest is what turns "nothing to
check" into "the demo ran, dumped, and had no ledgers, and here is why per
actor" (DEMOCI-10-003).

Generalisable check for any future skip-on-missing-input fixture: can the input
be missing *because* the system under test broke? If yes, the fixture needs a
positive signal that the producer ran, and it must fail — not skip — when that
signal is present and the data is not.

**Promoted**: 2026-08-17 — captured in specs/demo-ci.yaml DEMOCI-10 (already written in prior session).
Docs PR: TBD.
