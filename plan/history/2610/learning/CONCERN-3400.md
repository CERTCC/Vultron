---
source: CONCERN-3400
timestamp: '2026-10-01T19:46:58.017992+00:00'
title: CM-23-002 called case_fully_closed the last ledger entry, but bystander Leaves
  landed after it
type: learning
---

## Summary

`CM-23-002` step 3 requires the CASE_MANAGER to "emit a final `case_fully_closed`
CaseLedgerEntry **as the last ledger entry for the case**". Its rationale leans on
that: "making the CASE_MANAGER's own RM.CLOSED the penultimate step and
`case_fully_closed` the final entry gives all replicas an unambiguous terminal
anchor in the ledger chain."

That anchor is not achievable under the rest of CM-23:

- `CM-23-003` — a non-owner `Leave(VulnerabilityCase)` advances only that
  participant and **"the case MUST remain open for the remaining participants"**,
  committing its own `close_case` entry.
- `CM-23-012` — on owner Leave, **only** the Case Owner and the CASE_MANAGER
  advance to `RM.CLOSED`; "every other participant MUST retain its rung".
- `CM-23-004` — fan-out skips participants already at `RM.CLOSED`, which only
  matters because others are still open at that point.

So after `case_fully_closed` there may still be open participants, and each of
them may still `Leave`, producing a `close_case` entry *after* the entry the spec
calls last.

## Observed

Not hypothetical — this is the FV scenario's actual ledger. `_phase_case_closure`
(`vultron/demo/scenario/fv_demo.py`) closes the Vendor (the CASE_OWNER, per
CBT-01-003) first, then the Finder:

```text
17: close_case          actor=vendor   <- owner Leave
18: case_fully_closed   actor=vendor   <- "the last ledger entry"
19: close_case          actor=finder   <- lands after it
```

All eight other scenarios have the same owner-then-others shape.

## Why this is a landmine rather than a cosmetic wording issue

"`case_fully_closed` is the terminal anchor" is the kind of premise consumers get
built on. Anything that treats it as a chain terminator — a replica deciding it
has a complete log, a ledger consumer stopping there, a future invariant
asserting it is the highest `logIndex` — would be wrong on every current
scenario, and would look correct in review because the spec says so.

## Resolution options (not decided)

1. **Require owner Leave to be last.** Every non-owner must leave before the
   owner. Makes the clause true, but it is a new normative ordering constraint on
   all scenarios, and it is unclear what the CASE_MANAGER should do if a bystander
   never leaves.
2. **Refuse bystander Leave after full closure.** The case is closed, so a later
   `Leave` is declined (an `as:Reject`, per MSM-05-001). Makes the clause true but
   changes participant-facing behaviour and interacts with CM-23-012.
3. **Drop or qualify the "last entry" clause.** Amend CM-23-002 step 3 to say
   `case_fully_closed` records that the owner has left and the case is closed to
   new work, without claiming chain finality; state explicitly that later
   `close_case` entries are legal. Smallest change, but gives up the terminal
   anchor the rationale wanted, so anything relying on one needs another mechanism.

## Evidence

- `specs/case-management.yaml` — CM-23-002, CM-23-003, CM-23-004, CM-23-012
- `vultron/core/behaviors/case/receive_close_case_tree.py` — the owner-Leave arm
- `vultron/demo/scenario/fv_demo.py` `_phase_case_closure` — the ordering above
- ADR-0050, ADR-0051, ADR-0085

Surfaced while fixing #2505 (the CASE_MANAGER's own `RM.CLOSED` was never
recorded as a ledger entry). Deliberately **not** resolved in that PR: which of
the three options is right is a protocol decision, and picking one as a drive-by
would bury it.

**Resolved**: 2026-10-01 — ADR-0085 already settled it (refuse a bystander Leave after owner close); `case_fully_closed` now marks the write boundary, not chain finality (CM-23-002, new CM-23-013, CM-23-014). Implementation tracked in #4065, #4066.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4064>.

Spec: `specs/case-management.yaml`.
