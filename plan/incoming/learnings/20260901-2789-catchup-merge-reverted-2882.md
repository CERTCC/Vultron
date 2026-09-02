---
title: "A catch-up merge silently reverted PR #2882's BT wiring, and no test noticed"
type: learning
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-2789
signal: process-issue
---

## What happened

PR #2882 (ISSUE-2067) moved the procedural `add_activity_to_outbox` call out of
`OfferCaseOwnershipTransferReceivedUseCase.execute()` and into
`ForwardOfferToTransfereeNode`, wired via `create_offer_ownership_transfer_tree`.

`task/2490` was branched from a pre-#2882 `main`. Its catch-up merge
(`176154f63`, landing as PR #2909 / `ba8ea2ffa`) resolved the conflict in
`vultron/core/use_cases/received/actor/ownership.py` by keeping *its* side —
restoring the procedural forward verbatim, imports included. Nothing else from
that PR was lost — the node, the tree factory, the `__init__.py` export and the
unit tests all survived. Only the call site went back.

`notes/ownership-transfer.md` still asserted "Implemented by #2067. The use case
now calls `create_offer_ownership_transfer_tree()`", so the notes described a
state `main` no longer had.

## Why every test still passed

Both implementations queue the *same* activity id in the *same* outbox with the
*same* factory kwargs. `test_offer_cascade_forwards_to_transferee_via_case_actor_outbox`
asserts exactly those observable facts, so it passed against either shape. The
warning path (`test_offer_cascade_warns_when_trigger_activity_absent`) also
passes both ways, because the node and the procedural block log the same
"no trigger_activity" string.

The distinguishing fact is *which tree `execute()` builds* — a structural
property no behavioural assertion covered. The four tests #2882 added exercise
`create_offer_ownership_transfer_tree` directly, never through the use case, so
they kept passing on an unwired factory (same shape as the CLP-14 unwired-callsite
learning).

## How to apply

- When a refactor's whole point is *where* a side effect happens (CLP-10-005,
  ADR-0022), add an assertion on the structure, not only on the effect. A spy on
  the tree factory plus `assert not hasattr(module, "<retired helper>")` is
  cheap and names the contract. Added as
  `test_offer_cascade_forward_lives_in_the_bt_not_in_execute`.
- Testing a new tree factory in isolation does not prove anything calls it.
  Grep for callers of a new factory before closing the issue; a factory with
  only test callers is a red flag.
- This is the pitfall "A Conflict-Free Merge Is Not a Working Merge" with the
  polarity reversed: the semantic loss was in the *merged-in* branch's
  resolution, not in `main`'s new callers. Reviewing a catch-up merge means
  diffing the resolved file against **both** parents, not just running the suite.
