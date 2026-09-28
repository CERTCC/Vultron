---
source: CONCERN-2996
timestamp: '2026-09-28T18:09:12.368208+00:00'
title: 'Remove the CaseActor self-cc: on Invite — a container emits only as actors
  it hosts'
type: learning
---

## Concern

`cc:` should not exist as an addressing mechanism in Vultron. Recipients go in
`to:`. There is exactly one surviving use of `cc:` in the codebase — the
CaseActor adding its own ID to the outbound `Invite(actor, case)` so a copy
loops back through its own inbox — and it should be removed.

## Where it lives

- `vultron/core/behaviors/case/nodes/actor.py:144` — `cc = [self.case_actor_id]
  if self.case_actor_id else None`, passed to the Invite emit at :160. The
  node docstring at :68 documents `to=[invitee_id]`, `cc=[case_actor_id]`.
- `vultron/core/use_cases/received/actor/invite.py:49-55` — documents the
  "CaseActor inbox (self-delivered `cc:` copy)" as one of two delivery paths
  for `InviteActorToCaseReceivedUseCase`.
- `vultron/core/models/activity.py:64` — `cc: list[str] | None` on
  `VultronActivity`.
- `vultron/core/use_cases/received/report.py:110-117` — already treats `cc:`
  addressing as unsupported and discards the activity with a WARNING.

## Why it is not a simple deletion

`cc:` here is load-bearing for the canonical ledger. CLP-10-001 requires every
protocol-significant trigger tree to emit to `case_manager_id`, and ADR-0021
makes the CaseActor's *own inbox delivery* the only path to a canonical
`CaseLedgerEntry`. The invite flow is the awkward case: the invitee is not yet
a participant, so the CaseActor cannot learn of the invite via its own
broadcast — the self-`cc:` is how it currently sees its own message.

Spec entries that encode this and would need to move together:

- `specs/case-ledger-processing.yaml` ~682-698 (the self-`cc:` clause and its
  rationale for preferring `cc:` over `to:` for the self-copy), ~933-938
- `specs/outbox.yaml` ~170-181 (the WARNING policy that exempts the CaseActor
  self-`cc:` from the "cc is suspect" rule), ~408
- `specs/behavior-tree-integration.yaml` ~163
- `specs/em-behavior.yaml` ~2024

## What needs deciding

How the CaseActor mints its canonical entry for `Invite(actor, case)` once the
self-`cc:` is gone. Candidate directions, none yet evaluated:

1. Commit the entry directly in the emitting (CASE_MANAGER-gated) trigger tree,
   since the executing actor already *is* the case manager and its store is
   already in scope (BT-05-006) — no loopback needed.
2. Keep the loopback but address it with `to:` alongside the invitee, and let
   the receiving use case discriminate by role rather than by `to`-vs-`cc`.
3. Something else that removes the special case without reintroducing the
   two-delivery-path shape in `InviteActorToCaseReceivedUseCase`.

Option 1 looks most consistent with ADR-0073 + ADR-0022 (one store, one BT
execution, role-gated commit) but needs checking against ADR-0021's reasoning
for why the loopback was introduced in the first place.

## Acceptance

- `cc:` is no longer set by any outbound emit path.
- The CaseActor still commits exactly one canonical `CaseLedgerEntry` per
  invite, with no duplicate/forked chain (CLP-09-001).
- `InviteActorToCaseReceivedUseCase` no longer has two delivery paths keyed on
  whether `receiving_actor_id` is set.
- Spec entries above are updated together; `cc:` handling in `report.py` and
  `outbox.yaml` collapses to a plain "unsupported" rule.
- Decide whether `VultronActivity.cc` / `as_Activity.cc` stay on the models as
  AS2-faithful-but-unused, or are removed.

## Provenance

Raised 2026-09-01 while fixing Bug #2762, during a check of whether an embargo
invitation could reach an actor other than its addressee. It cannot — embargo
proposals set no `cc:` — but the check surfaced that the invite path still
does, contrary to the intent that `cc:` be gone.

**Resolved**: 2026-09-28 — implementation tracked in #3821 (owner-direct invite goes through the CaseActor; retire the self-`cc:` emit path), #3822 (ownership-transfer offer goes through the CaseActor; retire the foreign-authority fall-through, decline guard and core `cc`), and the existing #1876 (wire the multi-container demo to the dedicated case-actor container), re-sequenced into the plan.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3820>.
ADR: `docs/adr/0108-a-container-emits-only-as-actors-it-hosts.md`.

**What planning found beyond the concern as written.** The trigger tree already committed the Invite in-tree (#1689), so with the CaseActor co-hosted the `cc:` loopback committed the same Invite a second time — two canonical entries, log indexes 0 and 1, one activity id (CLP-07-002 violated in every in-process scenario, invisible to a harness asserting `>= 2`). The CaseActor is designed to live in a dedicated container (CP-08-008); the demo compose points each container at itself as a workaround for the closed #1700. In that designed topology the owner's container emitting the Invite in the CaseActor's name is the normal path, and the self-`cc:` copy is the only canonical path — so the copy, the bridge's foreign-authority fall-through (BT-05-005), and the silent `DeclineForeignLedgerCommitNode` all compensate for a container speaking as an actor it does not host. Two docstrings and one spec rationale attributed "the CaseActor stays on the container that first received the report" to CP-08-003, which says no such thing. Decision (ADR-0108): the owner asks the CaseActor to act by sending its own `Offer(CaseParticipant)`; the CaseActor emits and commits in one tree; `cc:` is unsupported everywhere; the compensations are retired.
