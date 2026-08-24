---
title: There is no "depth > 0" loopback delivery guard — the claim was folklore
type: learning
timestamp: 2026-08-21T00:00:00Z
source: ISSUE-2238
signal: concern
---

## Retraction

This file previously asserted that the CaseProposal round-trip fails in
`TestRunTwoActorDemo.test_full_workflow_succeeds` because "`_TestClientRouter`
loopback delivery is blocked when all actors share the same `api_app` TestClient
portal (depth > 0 guard prevents deadlock)".

**No such guard exists.** Checked directly while working #2238:

- Nothing in `test/demo/conftest.py`, `test/demo/_helpers.py` or the driven
  adapters implements a depth check. The only occurrences of "depth > 0" in the
  repo were this file and four comments in `test_fv_demo.py`, all citing each
  other rather than any code.
- `_TestClientRouter.emit` dispatches each POST through
  `anyio.to_thread.run_sync` **precisely so** a nested or loopback send cannot
  deadlock — the opposite of a guard that refuses one.
- Multi-hop deliveries are observably completing: logs show 202s to a CaseActor's
  inbox from *inside* another actor's inbox processing.

## Why it mattered

The claim was load-bearing in the wrong direction: it made a set of real defects
look like a fixed property of the test harness, so nobody examined them. Three
production defects were found within hours of discarding it:

- `ApplyNoteFromLedgerNode` appended a note id to a recipient's case without
  persisting the note, leaving a case referencing a note it could not read.
- `demo_sync_log_entry` committed as the case actor (BT-05-005) but read the entry
  back from the *requester's* store, reporting a successful commit as a 500.
- `_compute_report_addressees` dropped the recipient when the case manager was
  the sender, contradicting CLP-10-001 in as many words.

A fourth is tracked as #2456.

## Durable lesson

**A comment asserting a harness limitation is a claim, not evidence.** Before
building on one — especially before writing a workaround that a future reader will
treat as permanent — find the code that implements it. If several comments assert
it and none points at an implementation, suspect they are citing each other.

Corollary for the demo suite specifically: incomplete protocol round-trips there
are bugs until proven otherwise. Do not add "single-server mode can't do this"
comments without naming the mechanism.

## Related

- #2238 (per-actor DataLayer isolation; where this was found)
- #2456 (untyped report reaching the store — one of the real causes)
- `TestDeliveryIsolation` covers the real round-trip with isolated actor apps
