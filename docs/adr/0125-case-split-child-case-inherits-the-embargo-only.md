---
status: proposed
date: 2026-10-08
created: 2026-10-08
updated: 2026-10-08
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Issue #4241, Idea #1229; ADR-0017, ADR-0023, ADR-0041,
  ADR-0105, ADR-0113, ADR-0114, ADR-0115, ADR-0117, ADR-0122;
  specs/vultron-protocol-spec.yaml VP-10; specs/case-management.yaml CM-05,
  CM-10, CM-14, CM-22
informed: CERT/CC Vultron protocol team
stakeholder_type: [project-contributor]
---

# A Case Splits by Its Owner Proposing a Child Case: the Child Links Its Parent and Inherits the Embargo Terms Only

## Context and Problem Statement

A Case sometimes covers more than its Participants can coordinate as one group.
A Coordinator learns that a vulnerability in Vendor1's product also affects Vendor2's codebase, and Vendor2 must not see Vendor1's details.
Or one vulnerability reaches two fix supply chains on very different timelines.
The protocol's answer is a case split: part of the coordination moves into a new Case, a *child* of the original.

The embargo rules for splits exist (VP-10, "Embargo Case Splits and Merges"), and `VulnerabilityCase` already carries `parent_cases`, `child_cases`, and `sibling_cases` fields.
Nothing else does.
No record says who may split a Case, how the child comes to exist, what it takes from the parent, or how sibling Cases learn of each other's embargo changes.
No code writes any of the three fields.

The question this record settles is: how does a Case Owner split a child Case off a parent Case, and what does the child carry?

## Decision Drivers

- A Participant invited to the child must learn nothing of the parent beyond the fact that its embargo came from one; the split exists to keep the two groups apart.
- Each Case has its own hash-chained ledger and genesis hash anchored to its Owner (CLP-08, ADR-0117); a split must not rewrite or share a ledger.
- Every Case has at least one report (CM-05-002), a CASE_MANAGER from creation (CM-24-006), and an Owner recorded in `attributed_to` (CM-02-008).
- Existing flows should be reused: case creation by `CaseProposal` (ADR-0023, ADR-0041), joining by stub Invite (ADR-0114), and embargo negotiation relayed through the CASE_MANAGER (ADR-0113).
- Participants address case messages only to the CASE_MANAGER (PCR-08-001), so a requirement that Participants of one Case tell Participants of another (VP-10-003) needs a defined route.
- The merge decision (ADR-0105) left the choice among `parent_cases`, `child_cases`, and `sibling_cases` to its spec; a split must not foreclose it.

## Considered Options

- The parent's Owner proposes a child Case to the parent's CASE_MANAGER
- The parent's CASE_MANAGER copies the parent and prunes the copy
- The Owner creates an unrelated Case by hand and links it afterwards

## Decision Outcome

Chosen option: "The parent's Owner proposes a child Case to the parent's CASE_MANAGER", because it reuses the creation flow that already gives a Case its CASE_MANAGER, ledger, and genesis hash, and because nothing reaches the child unless the splitter puts it there.

The decision has these parts.

1. **Only the parent's Case Owner splits, and it does so through the parent's CASE_MANAGER.**
   The Owner sends `Create(CaseProposal)` to the parent's CASE_MANAGER with the activity's `context` naming the parent Case.
   The parent `context` is what makes the proposal a split: it is a distinct message type with its own received use case, because its sender entitlement differs from a report-born proposal.
   The sender must hold `CASE_OWNER` on the parent (ADR-0115); any other sender is refused.
   The CASE_MANAGER answers as for any proposal (CP-05): `Accept(CaseProposal)` naming the child in `result`, then `Create(VulnerabilityCase)` for the child, or `Reject(CaseProposal)`.
   It reuses the proposal flow's admission decision, durable-delivery marker, and duplicate handling unchanged.
2. **The parent's CASE_MANAGER is the child's CASE_MANAGER, and the parent's Owner is the child's Owner.**
   The CASE_MANAGER creates the child natively in its own store, as it does any Case (CM-22-001, ADR-0041), with `attributed_to` set to the splitter.
   The child's genesis hash is derived from the child's own ID, creation time, and Owner (CLP-08-002), so its ledger shares nothing with the parent's.
   The Owner may later hand the child to another Owner through Case Ownership Transfer (ADR-0053), like any Case.
3. **The child records its parent, and the parent records the child; siblings are read from the parent.**
   The child is created with `parent_cases` holding exactly the parent's ID.
   The parent's CASE_MANAGER adds the child's ID to the parent's `child_cases` and commits that as an entry in the parent's ledger, after the child's own creation entry, so the parent never names a Case that does not exist.
   The split writes no `sibling_cases`, and only a split writes `child_cases`: a case merge records nothing there, so merged Cases never join a split family.
   A child's siblings are the other Cases in its parent's `child_cases`, which the CASE_MANAGER holds because it hosts the parent and every child.
   Storing them on each child would mean updating every existing sibling at each split, and `parent_cases` and `sibling_cases` stay free for the merge spec to choose between.
   The fields hold IDs, not embedded Cases, as ADR-0017 requires for related Cases.
4. **The child inherits the parent's embargo terms and nothing else.**
   When the parent has an active embargo, the child gets a new `EmbargoEvent` of its own, scoped to the child, with the active embargo's end time, active from creation, and the Owner's consent row for it written `AGREED`, so the Owner reads as its signatory.
   It is a new embargo, not the parent's object, so consent to it is recorded per Participant against the child's embargo (ADR-0122) and no parent consent row carries over.
   An open proposal or revision on the parent is not inherited.
   When the parent has no active embargo, the child has none, and the default embargo of case creation is not initialized either: the parent's state, not a default, decides.
   No report, note, ledger entry, Participant, case status, vulnerability record, or case reference is copied.
5. **The child's description is new, written by the splitter.**
   The proposal carries a new `VulnerabilityReport` attributed to the splitter, describing what the child is for.
   It satisfies CM-05-002 without handing the child any of the parent's reports.
   Writing it does not make the splitter the child's Finder or Reporter: the child is seated with its CASE_MANAGER and its Owner only.
   The proposal also carries the stub summary the child's stub Invites carry (CM-17-010), because the splitter decides how much an invitee not yet bound by the embargo may learn.
6. **A Participant joins the child by invitation and never touches the parent.**
   Participants join the child through the stub Invite flow (ADR-0114), addressed in the child's `context`.
   Nothing in the child adds a Participant to the parent's roster, and parent recipient selection reads only the parent's roster (CM-10-004), so a child Participant receives no parent ledger entry.
   A Participant in both Cases, such as the Owner, is a Participant of each separately.
7. **Embargo changes reach related Cases through their ledgers.**
   A parent and its children are treated as one family for VP-10-002 and VP-10-003, and the parent counts as a sibling, because in this design the parent stays open after the split.
   Every member of a family has the same CASE_MANAGER, so a notice is not a message between actors: the CASE_MANAGER commits a notice entry to each other member Case's ledger, which fans it out to that Case's active Participants.
   When an embargo change is proposed in one member that would end earlier than the terms it inherited, the CASE_MANAGER commits a notice carrying the end time and the proposer's rationale to every other member before the change can take effect (VP-10-002), and commits the rationale to the proposing Case's ledger.
   The rationale travels in the proposing activity's `content`, since embargo proposals have no field for it, and a proposal without one is refused.
   When any member's embargo changes, by an activated revision or a termination, the CASE_MANAGER commits a notice to every other member (VP-10-003).
   So Participants of one Case learn of another's change, but neither side ever addresses the other's Participants.
   A notice proposes nothing to the Case that receives it; each Case decides its own embargo.
   The notice carries the related Case's ID, the new end time or the fact of termination, and the rationale where one was given, and no other content of that Case.
8. **A family stays at one CASE_MANAGER.**
   While a Case is a member of a split family, delegating its CASE_MANAGER role (CM-24-006) to a different actor is refused.
   Sibling lookup and notice delivery both rest on one CASE_MANAGER hosting the family; a family spread across CASE_MANAGERs is left to a later decision.

### Consequences

- Good, because the child's ledger, genesis hash, CASE_MANAGER, and Owner all come from the existing creation flow, so the split adds one message type, one parent ledger entry, and one notice entry rather than a parallel creation path.
- Good, because isolation holds by construction: the child starts with only what the splitter wrote and the parent's embargo end time, and its Participants join only through the child's own Invites.
- Good, because one write per split keeps the links consistent; no existing sibling changes when a new child appears.
- Bad, because a child Participant learns that a parent exists, through `parent_cases` and through embargo notices; the split hides the parent's content, not its existence.
  VP-10-003 needs that much.
- Bad, because the CASE_MANAGER role of a family member cannot be delegated away from the family's CASE_MANAGER; a design that lets a child move would have to store `sibling_cases`, keep them in step, and turn notices into messages between CASE_MANAGERs.
- Neutral, because the parent's Participants see the child's ID in the parent's ledger, and only that.

## Validation

The split requirements are written as a spec group derived from this record (CM-32 in `specs/case-management.yaml`), and each `kind: protocol` entry carries a marker test, strict `xfail` until the split is built.
Review confirms that the child is created with nothing from the parent but the embargo end time and the parent link, and that no parent recipient selection can return a child-only Participant.

## Pros and Cons of the Options

### The parent's Owner proposes a child Case to the parent's CASE_MANAGER

- Good, because it reuses case creation, admission, delivery retry, and duplicate handling.
- Good, because the child holds only what the splitter put in the proposal.
- Bad, because the proposal flow gains a second, Owner-only entry point that its received side must tell apart from a report-born proposal.

### The parent's CASE_MANAGER copies the parent and prunes the copy

- Good, because the child starts with full context.
- Bad, because every field the pruning misses leaks parent content to Participants who must not see it, and the safe default is inverted: forgetting to remove something discloses it.
- Bad, because a copied ledger cannot keep its hash chain under a new genesis hash, so the history must be dropped or rewritten anyway.

### The Owner creates an unrelated Case by hand and links it afterwards

- Good, because it needs no new message type for creation.
- Bad, because the link becomes an edit to two existing Cases with no single moment at which the split happened, and the inherited embargo must be set up by hand.
- Bad, because the CASE_MANAGER cannot tell a child from any other Case when routing VP-10 notices until the link arrives.

## More Information

- Source: Idea [#1229](https://github.com/CERTCC/Vultron/issues/1229); design task [#4241](https://github.com/CERTCC/Vultron/issues/4241); build [#4242](https://github.com/CERTCC/Vultron/issues/4242); demo [#4243](https://github.com/CERTCC/Vultron/issues/4243).
- Embargo split rules: VP-10 in `specs/vultron-protocol-spec.yaml`; reader-facing discussion in `docs/topics/process_models/em/split_merge.md`.
- Merge, the companion decision: [ADR-0105](0105-case-merge-freeze-and-redirect-by-owner-consent.md).
- Creation flow reused here: [ADR-0023](0023-case-proposal-protocol.md) and [ADR-0041](0041-caseactor-authoritative-case-initialization.md).
- Embargo relay through the CASE_MANAGER: [ADR-0113](0113-embargo-revision-negotiation-relays-through-the-case-manager.md); per-embargo consent: [ADR-0122](0122-per-embargo-participant-consent.md).
- Case cross-reference fields: `parent_cases`, `child_cases`, and `sibling_cases` in `vultron/core/models/case.py`.
