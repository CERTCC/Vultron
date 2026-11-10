---
title: "No requirement says what Log Replay does with a ledger line of the wrong shape"
type: learning
timestamp: "2026-11-10T17:00:00Z"
source: ISSUE-4729
signal: spec-gap
---

**Trigger.** You are changing how `ui/` loads a case ledger
(`parseCaseLedger`, `ui/src/utils/ledgerShape.ts`), or adding a reader of the
ledger outside `vultron/`, and you look for the requirement that says how a
replay tool treats a line it cannot read.

**Claim.** The DRPT group covers the Python report tool's naming and timeline
(DRPT-02, DRPT-03), and SYNC-03 covers a *replica* refusing an entry whose hash
does not match. No requirement says what a replay or visualization tool does
with a line that is not JSON, or that is JSON of the wrong shape. Such a line
could be dropped, replayed with defaults, or refused and shown. `learn` should
settle whether this is a requirement (one rule for the UI and the Python report
tool) and what it says. Questions to decide:

- Is a malformed line refused whole (the PR's choice), or replayed for its
  well-formed fields?
- Must it be shown to the user, and where?
- Which fields does a reader require: everything the model always writes for
  the envelope, but only what the parse edge requires for the received
  statuses inside `payloadSnapshot` (MV-11-003)?

**Evidence.** PR #6217 (part 1 of #4729) chose the following. The envelope
must carry every field the model always writes and no undeclared key. Nested
statuses follow the parse edge. A failing line is not replayed, and it is
listed in the replay header and the event log. The choice rests on the issue's
"visible, never silently dropped" wording and on the "falls back to" testing
pitfall, not on a spec.

**How to apply.** Until a requirement exists, keep the reader's behaviour
matching `ledgerShape.ts` and its tests. Do not add a second reader with
different rules. Cite this file if you need the behaviour pinned in `specs/`.
