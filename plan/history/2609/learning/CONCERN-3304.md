---
source: CONCERN-3304
timestamp: '2026-09-17T17:26:41.629768+00:00'
title: Direct-mint case creation must register CASE_OWNER and CASE_MANAGER at birth
type: learning
---

## Problem

`create_case_trigger_bt` (Path B: actor mints the case directly via
`trigger/create-case`) creates a `VulnerabilityCase` record but registers
no `CaseParticipant`. This left `resolve_case_manager_id` returning `None`
immediately after creation, violating the invariant that every case must
have both `CVDRole.CASE_OWNER` and `CVDRole.CASE_MANAGER` filled from birth.

The invite demo masked the breakage with `_get_case_actor_id`, which scans
for a Service actor whose `context` equals the case ID — the hosting-location
lookup ADR-0088 retired as an authority signal (ARCH-24-004, CM-02-013). The
fallback `vendor.id_` then silently papered over any `None` result, so the
demo passed while the role ledger was empty.

## Key Design Decisions

**Two creation paths are already separate code paths; no discriminator field is needed.**

- Path A (`Create(as_CaseProposal)` → `CreateCaseProposalReceivedUseCase` →
  `case_proposal_received_tree`): already registers the vendor as `CASE_OWNER`
  and the CaseActor as `COORDINATOR + CASE_MANAGER`. Correct; no change needed.

- Path B (`trigger/create-case` → `SvcCreateCaseUseCase` →
  `create_case_trigger_bt`): the creating actor IS both owner and manager from
  the start, holding both until they delegate `CASE_MANAGER` via `Offer(role)`
  → `Accept`. The fix is to add a participant-registration node to this BT.

There is no "on behalf of" situation in Path B. `CreateCaseTriggerRequest`
needs no new `owner_id` field — callers of `trigger/create-case` are always
minting their own case.

**The fallback must be removed, not just replaced.**

`case_actor_id if case_actor_id else vendor.id_` exists only because the
registration was missing. After the fix, the fallback becomes dead code
hiding a bug. If `resolve_case_manager_id` returns `None`, the correct
response is to raise — not to silently substitute a guess.

**The demo test must assert the invariant, not just "no ERROR in log".**

Because the fallback masked violations, the demo test must explicitly assert
that `resolve_case_manager_id` returns a non-`None` value after
`setup_initialized_case`. A test that passes silently when the role ledger is
empty provides no protection.

## Specs Added

- **CM-02-014** (`specs/case-management.yaml`): invariant — both
  `CVDRole.CASE_OWNER` and `CVDRole.CASE_MANAGER` must be filled from the
  moment of creation, regardless of creation path.
- **CM-02-015**: direct-mint path must atomically register the creating actor
  with `[CASE_OWNER, CASE_MANAGER]` as part of the same case-creation
  operation.

## Resolution

PR: <https://github.com/CERTCC/Vultron/pull/3334> (specs-notes)
Implementation: #3335 (blocked by #3304, sub-issue of epic #2685, milestone #15)
