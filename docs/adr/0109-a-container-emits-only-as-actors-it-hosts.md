---
status: accepted
date: 2026-09-28
deciders: Allen D. Householder
consulted: notes/case-ledger-authority.md, notes/case-communication-model.md, notes/ownership-transfer.md, notes/outbox.md, docs/adr/0021-caseactor-inbox-routing-canonical-ledger.md, docs/adr/0042-http-only-inter-actor-delivery.md, docs/adr/0073-per-actor-storage-isolation.md, docs/adr/0088-consolidate-case-authority-determination.md
informed: CERT/CC Vultron protocol team
stakeholder_type: [project-contributor]
---

# A Container Emits Only as Actors It Hosts; a Participant Asks the CaseActor to Act

## Context and Problem Statement

Concern #2996 asked that `cc:` stop being an addressing mechanism.
Its one surviving use is the CaseActor adding its own id to the `cc:` of an outbound `Invite(actor, case)` so that a copy loops back through its own inbox and mints the canonical `CaseLedgerEntry` (ADR-0021 § Clarification, CLP-10-001).
Investigating why that copy is needed exposed a larger defect that the copy compensates for.

The design places the CaseActor in a dedicated container.
CP-08-008 requires every case-creating actor's `case_actor_service_url` to name that container, and `docker/docker-compose-multi-actor.yml` deploys it.
The same compose file points every actor container's `case_actor_service_url` at *itself* instead, under a comment that says "until #1700 is resolved".
Issue #1700 closed in July 2026 and its demo follow-on, #1876, is open and unblocked.
So the deployed topology is a workaround that outlived its reason, and the CaseActor is co-hosted with whichever container created the case.

Several mechanisms were then built on top of that workaround as though it were the design:

- **Delegated emit from a foreign container.** When the case owner triggers `invite-actor-to-case` or `offer-case-ownership-transfer`, its container builds the activity with `actor` set to the CaseActor's id (PCR-08-007, CM-24-001) and runs the trigger tree locally as the CaseActor.
  With a dedicated CaseActor container that is *always* a container speaking with an identity another container hosts, not a handoff edge case.
- **The foreign-authority store fall-through.** The BT bridge lets a tree whose `actor_id` belongs to another authority keep the requester's store (BT-05-005 exception two), because cloning a store for a remote actor would run the tree against nothing.
- **The anti-fork decline guard.** `DeclineForeignLedgerCommitNode` makes the in-tree ledger commit silently decline in that fall-through, because otherwise the owner's replica would mint index N while the real CaseActor minted its own index N from the `cc:` copy (CLP-10-014, #2626).
- **The self-`cc:` copy itself.** Having sent an Invite it had no business sending, the owner's container mails the CaseActor a copy so the CaseActor can learn of it and commit it (CLP-10-001, OX-08-004's exemption, OX-12-004).

Two of those mechanisms and two docstrings justify themselves with the sentence "after an ownership handoff the CaseActor stays on the container that first received the report (CP-08-003)".
CP-08-003 says nothing of the kind; it requires the compose environment variable to be set.
The sentence describes the workaround.

The compensation is also wrong in the co-hosted configuration it was built for.
`EmitInviteActorToCaseNode` commits an `invite_actor_to_case` entry in the trigger tree (#1689) *and* the loopback copy commits it again through `GuardedCommitCaseLedgerEntryBT`, because nothing deduplicates on activity id.
A probe on 2026-09-28 with the CaseActor co-hosted produced two canonical entries at log indexes 0 and 1 for the same Invite activity id, with different bytes (the trigger-side snapshot carries `name`, the wire copy does not).
That violates CLP-07-002 in every in-process demo scenario, and the invariant harness cannot see it because it asserts only `invite_actor_to_case >= 2`.

Finally, `InviteActorToCaseReceivedUseCase` keeps two delivery paths keyed on `receiving_actor_id is None`, but the FastAPI inbox pipeline always sets that field from the addressed inbox, so the "invitee path" is reachable only from direct test invocation.

## Decision Drivers

- Single-writer canonical ledger: exactly one commit per protocol act, minted where the log lives (ADR-0018, CLP-07-002, CLP-09).
- Per-actor storage: a tree runs in its actor's own store, and only there (ADR-0073, BT-05-005, BT-05-006).
- Uniform HTTP delivery with no in-process shortcut (ADR-0042, OX-12).
- Identity integrity: a container can only ever sign or speak as actors it hosts.
  Signed delivery (OX-10) is unimplemented today; a design that needs one container to speak as another cannot survive it.
- Authority is the `CASE_MANAGER` role, enacted by the CaseActor; hosting location carries no authority signal (ADR-0088).
- `cc:`, `bto:` and `bcc:` have no handler semantics in Vultron (HP-10-001); Vultron direct messages use `to:` (OX-08).

## Considered Options

- **A. Keep the foreign-container emit; move the CaseActor from `cc:` to `to:` when it is remote; add a dedup guard.**
- **B. A container emits only as actors it hosts.
  A participant on another container asks the CaseActor to act by sending it the participant's own activity; the CaseActor emits from its own store and commits in the emitting tree.**
- **C. Move the CaseActor's id from `cc:` to `to:` unconditionally and keep the loopback.**

## Decision Outcome

Chosen option: **B**, because it is the only option under which the invite path has one emitter, one store and one commit end to end, and the only one that removes the compensations rather than re-addressing them.
A and C both keep a container emitting under an identity it does not host, keep the loopback as the canonical path in the intended topology, and keep the store fall-through and the decline guard alive to make that survive.

Concretely:

1. **No trigger tree executes as an actor its container does not host.**
   `SvcInviteActorToCaseUseCase` and `SvcOfferCaseOwnershipTransferUseCase` stop running the tree as the CaseActor.
   The bridge's foreign-authority fall-through is removed; a tree whose `actor_id` is not hosted by the store's authority is a programming error and raises.
   `DeclineForeignLedgerCommitNode` becomes a fail-fast invariant rather than a silent decline.
2. **The owner reaches the CaseActor by message.**
   The owner's `invite-actor-to-case` trigger sends the owner's own `Offer(CaseParticipant)` to the CaseActor, reusing the suggest-actor flow (CM-16).
   The CaseActor's recommend-actor tree gains one branch: when the recommender holds `CASE_OWNER`, it emits the Invite directly with the offered roles instead of forwarding the Offer to the owner.
   The ownership-transfer offer follows the same shape.
   This is one path for every topology, including a single-container deployment where the owner hosts the CaseActor: the message loops back over HTTP as OX-12 already requires.
3. **The CaseActor commits in the emitting tree and never addresses itself.**
   The in-tree commit already present in `EmitInviteActorToCaseNode` is the only commit.
   The `cc` parameter is removed from the emit node, the trigger tree, `TriggerActivityPort.invite_actor_to_case` and its adapter.
   `InviteActorToCaseReceivedUseCase` collapses to one receive tree; the `CASE_MANAGER` role gate is what separates the invitee's storage from the manager's commit, and the manager never receives its own Invite.
   The rule forbids a *copy* of an activity the CaseActor authors as `CASE_MANAGER`.
   It does not touch a participant-role activity addressed to the case manager whose recipient happens to be the same actor, such as a vendor that also manages its case validating a report; that activity is addressed to the `CASE_MANAGER` in `to:` like any participant's and arrives over ordinary HTTP delivery (CLP-10-001, OX-12-001).
4. **`cc:` is unsupported everywhere.**
   OX-08-004 warns on any `cc`/`bto`/`bcc` with no exemption.
   OX-12-004 is retired.
   `VultronActivity.cc` leaves the core model and the extractor stops mapping it.
   The wire `as_Object.cc` stays: it is AS2 vocabulary and inbound activities from other implementations may carry it, and IE-11 continues to refuse only on provable exclusion.
5. **The demo runs the designed topology.** #1876 wires every actor container's `case_actor_service_url` to the dedicated `case-actor` container.
   The retired compensations are verified in that topology, so any surviving foreign emit fails loudly instead of being mailed a copy of itself.
6. **CM-17-006 is reconciled with the enforced order.** The invite tree builds the activity, commits the entry, then appends to the outbox (`vultron/core/behaviors/case/AGENTS.md`, CLP-10-006), so a failed commit cannot orphan an outbox item.
   CM-17-006 previously said the commit must follow the queueing; it now states the order the code enforces.

### Consequences

- Good, because every protocol act has exactly one emitter and one commit, and the measured CLP-07-002 duplicate becomes structurally impossible.
- Good, because no container ever speaks as an actor it does not host, which is the precondition for signed delivery.
- Good, because four compensating mechanisms (self-`cc:`, OX-08-004's exemption, the foreign-authority store fall-through, the silent decline guard) and the two-path invite use case are deleted rather than maintained.
- Good, because the owner's invite reuses the suggest-actor machinery instead of adding a message type.
- Bad, because the owner's direct invite becomes asynchronous: the trigger's `202` means "the request reached the CaseActor's outbox path", not "the Invite was sent".
  Demo scenarios that read the Invite id off the trigger response must instead observe the CaseActor's ledger.
- Bad, because the change lands as three sequenced pull requests and the intermediate state after the first still carries the `cc:` copy for the ownership-transfer offer until the second lands.

## Validation

- The invariant harness asserts that no replica holds two `CaseLedgerEntry` records whose `payloadSnapshot.id` names the same activity (CLP-07-002 verification).
- An architecture ratchet asserts that no trigger use case executes a BT with an `actor_id` under an authority its DataLayer does not host.
- `test/core/behaviors/test_bridge.py` asserts that a foreign-authority `actor_id` raises rather than falling through.
- `test/demo/test_remote_case_actor_invite.py` is rewritten: an owner on one container invites an actor on another, and the Invite is emitted from and committed on the CaseActor's container with no `cc:`.
- Demo integration scenarios pass with the dedicated `case-actor` container active (#1876 AC-6).

## Pros and Cons of the Options

### A. Keep the foreign-container emit; `to:` when remote; dedup guard

- Good, because it is the smallest diff and fixes the measured duplicate.
- Bad, because the owner's container still emits under the CaseActor's identity, which breaks under signed delivery.
- Bad, because the store fall-through and the decline guard remain load-bearing.
- Bad, because in the intended topology the "copy" is still the only canonical path, so the CaseActor can only refuse to record an invite the invitee has already seen.

### B. A container emits only as actors it hosts (chosen)

- Good, because one emitter, one store, one commit.
- Good, because it removes mechanisms instead of adding one.
- Neutral, because it depends on #1876 to be exercised in the real topology.
- Bad, because the owner's direct invite becomes asynchronous.

### C. `to:` unconditionally, keep the loopback

- Good, because it is a one-line addressing change.
- Bad, because it still needs the dedup guard, and it puts the CaseActor in `to:` of its own co-hosted Invite, which ADR-0021 rejected as misrepresenting the recipient.
- Bad, because everything A leaves in place, C leaves in place too.

## More Information

- Supersedes ADR-0021 § "Clarification: CaseActor-Originated Activities (Issue #1287)".
  The rest of ADR-0021 (participants address the CASE_MANAGER in `to:`; pre-flight guard by receiving actor) stands.
- Removes the second exception of BT-05-005 (ADR-0073) and the "decline" semantics of CLP-10-014.
- Retires OX-12-004 (ADR-0042); OX-12-001 through OX-12-003 stand.
- Source concern: #2996. Demo topology: #1876 (successor to #1700 and #1872).
- Stale statements corrected by this decision: `vultron/core/behaviors/sync/nodes/ledger_authority.py`, `vultron/core/behaviors/bridge.py`, `vultron/demo/scenario/fvcv_handoff_demo.py`, `test/demo/test_remote_case_actor_invite.py`, and the BT-05-005 exception text, each of which attributed "the CaseActor stays where the report was first received" to CP-08-003.

Generated spec requirements: `case-ledger-processing.yaml` CLP-10-001, CLP-10-014, CLP-07-002 (verification); `outbox.yaml` OX-08-004; `behavior-tree-integration.yaml` BT-05-005; `case-management.yaml` CM-17-006, CM-17-007, CM-24-004; `inbox-endpoint.yaml` IE-11-003 (rationale); `em-behavior.yaml` EMB-19-001 (note).
