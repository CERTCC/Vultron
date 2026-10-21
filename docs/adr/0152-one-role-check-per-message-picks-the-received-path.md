---
status: proposed
date: 2026-10-21
created: 2026-10-21
updated: 2026-10-21
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0088, ADR-0111, ADR-0115, ADR-0129, ADR-0135;
  specs/handler-protocol.yaml HP-01-005, HP-01-007, HP-01-008;
  specs/behavior-tree-integration.yaml BT-17-001, BT-17-008;
  specs/case-ledger-processing.yaml CLP-10-010;
  issues #5011, #5010, #4851, #4970
informed: []
stakeholder_type: [project-contributor]
---

# One Role Check per Message Picks the Received Path

## Context and Problem Statement

A received message is handled differently at the case's CASE_MANAGER, at a participant that holds a replica of the case, and at an actor that holds no case yet.
Received handlers decide which of these they are in about ten different ways.
The factory wraps `manager_effects` in a `CaseManagerGate`, and an inverse factory builds participant-replica-gated trees.
Node modules carry their own CASE_MANAGER-gated guards.
Sender rules branch on the receiver through `at_case_manager` and `at_participant` arms.
Two exemption registries, `ReplicaEmitExemption` and `AddresseeExemption`, record trees that step around a gate.
Diversions choose a `DiversionGate.CASE_MANAGER` or `DiversionGate.RECEIVER`.
A post-run helper, `not_case_manager(tree)`, reads "not the manager" from any failed `CheckIsCaseManagerNode` anywhere in the tree.
Some trees hand-roll a gate, some compare `resolve_case_manager_id(...)` to the actor id inline, and one reuses `SenderIsCaseOwnerNode` to ask about the invitee.

The verdicts disagree as a result.
Four handlers report `APPLIED` when a participant receives a CASE_MANAGER-addressed message it could not act on, where HP-01-005 requires `REFUSED` (#5010), and #4851 and #4970 were role refusals that fired wrongly.
Each tree also carries its own "not my job" arms.
All of this follows from asking the role question late, and in many places.

How should a received tree learn which role the receiver holds in the case, and what should it do with the answer?

## Decision Drivers

- HP-01-005: a message the receiver holds no role to act on is `REFUSED`, with a reason naming the role, never `APPLIED` or `SKIPPED`.
- CM-02-011 and ADR-0088: authority is the CASE_MANAGER role in the case's roster, never a name, a URL or where the actor is hosted.
- A role belongs to an (actor, case) pair. An actor can manage one case and be a plain participant in another, and roles change during a case, so the answer cannot be fixed at actor startup.
- HP-01-007 and ADR-0115: a general received-side check is declared once per use case and composed by the factory, never copied into each tree.
- ADR-0135: one tree per delivery; alternatives are branches inside it, never Python control flow choosing between trees.

## Considered Options

1. **One path stage, one shared predicate.** The factory asks the role question once per message, in the door stage, and the answer picks one path. Each message type declares the paths it handles.
2. **Keep the gates and make the verdicts agree.** Keep every mechanism, and give each handler a shared helper that maps a gate failure to the right `REFUSED` reason.
3. **Fix the path at actor startup.** Configure an actor as a manager or a participant and route accordingly.

## Decision Outcome

Chosen option: **"One path stage, one shared predicate"**, because it is the only option that asks the question once, gives one verdict for one cause, and lets the role-based alternatives that grew up around the gates retire.

### Decision details

1. **One role predicate.** `has_role(actor, case, role) -> bool` is the one sanctioned way to ask whether an actor holds a role in a case.
   It reads the actor's own replica of the case fresh for each message, a cheap read like today's `CheckIsCaseManagerNode`.
   It wraps `CaseParticipant.has_role`; it does not replace it.
   Inline `resolve_case_manager_id(...) == actor_id` comparisons and a sender check reused to ask about some other actor are replaced by it.
2. **Three paths, chosen by the CASE_MANAGER role alone.** The path is *manager* when the receiver holds `CVDRole.CASE_MANAGER` in the case, *participant replica* when it holds a replica of the case without that role, and *no case yet* when it holds no replica.
   No other role is a path.
   The Case Owner, like every participant, holds a replica and sends its changes through the CASE_MANAGER (PCR-08-001).
   Owner, vendor, deployer and every other role are permission rules inside a path, checked with the same predicate, so a new role adds permission rules and never a new path.
3. **The path stage is a door stage.** It runs after the addressee check (HP-01-005) and before the sender guard (HP-01-006), so the sender guard reads the path the stage chose rather than asking again.
   A sender rule's `at_case_manager` and `at_participant` arms are selected by that path.
4. **Each message type declares the paths it handles.** The declaration is made once, to the factory.
   A message type that does real work on both the manager and the participant path declares a branch for each, and the factory forks once, after the door stages.
   Today that covers the embargo Invite and Remove, the role and ownership offers, `Add(CaseStatus)`, `Announce` and `Reject` of a `CaseLedgerEntry`, and the case invites.
5. **An undeclared path is refused once, by the factory.** A message whose type declares no branch for the receiver's path is `REFUSED` with the reason "not the CASE_MANAGER of case …", composed by the factory and identical for every message type.
   No handler maps a gate failure to a verdict after the run, so `not_case_manager(tree)` retires.
6. **No case yet either waits or proceeds.** A case-scoped message type waits for its case, as the defer check does today.
   A message type that starts a case, such as a report, a case proposal or the first `Create(VulnerabilityCase)`, declares a no-case branch and takes it.
7. **The role-based alternatives become declared branches.** The `CaseManagerGate` around `manager_effects`, the participant-replica-gated factory, the `ReplicaEmitExemption` registry and the `DiversionGate.CASE_MANAGER` and `DiversionGate.RECEIVER` choices are each expressed as a path branch, and their separate mechanisms retire.
   `AddresseeExemption` is about addressing, not role, and is not changed by this record.
8. **Intake is unchanged.** This record does not move intake or change what it stores; ADR-0153 does.

### Consequences

- Good, because one cause gets one verdict and one reason, so the class of defect behind #5010, #4851 and #4970 is closed by construction rather than handler by handler.
- Good, because the role question is answered from the roster once per message, which is what CM-02-011 requires and what a role that changes mid-case needs.
- Good, because a reader learns which paths a message type handles from one declaration instead of from the gates scattered through its tree.
- Bad, because every received tree changes shape: about sixty factory call sites migrate, and the ratchets that pin the old gates and registries have to move with them.
- Bad, because a message type that handled both paths implicitly, by leaving some effects ungated, must now declare both branches explicitly, and finding those cases is part of the migration.
- Neutral, because BT-17-001 still holds: the manager path is still a role-guarded subtree composed at tree-composition time, and it is still acquired only through `create_receive_activity_tree` (BT-17-008).

### Confirmation

- An architecture test fails when received-side code under `vultron/core/behaviors/` or `vultron/core/use_cases/received/` asks the CASE_MANAGER question other than through `has_role` or the path stage.
- A test per path drives a message type with no branch for that path and asserts `REFUSED` with the shared reason.
- The tests that pin the corrected dispositions of #5010 stay green through the migration.

## Pros and Cons of the Options

### One path stage, one shared predicate

- Good, because the question is asked once, in one place, with one answer.
- Good, because the exemption registries and post-run inference retire instead of growing.
- Bad, because it is a migration of every received tree.

### Keep the gates and make the verdicts agree

- Good, because no tree changes shape.
- Bad, because the ten mechanisms stay, and a new handler can still pick the wrong one or forget the helper.
- Bad, because the post-run inference still reads "not the manager" from any failed check in the tree, which is how a wrong refusal fires.

### Fix the path at actor startup

- Good, because routing is trivially cheap.
- Bad, because a role belongs to an (actor, case) pair and changes during a case, so a startup choice is wrong for every actor that manages one case and participates in another.
- Bad, because anyone can receive a report that starts a new case, so no actor is only a participant.

## More Information

- Source: #5011. The storage half of that Idea is ADR-0153, which builds on this record.
- Related: ADR-0088 (authority is the CASE_MANAGER role), ADR-0115 and ADR-0129 (declared sender entitlement), ADR-0135 (compose, never chain).
