---
status: accepted
date: 2026-07-28
deciders: [adh, Claude Sonnet 4.6]
supersedes: 0015-create-case-at-report-receipt.md
---

# ADR-0041: CaseActor-Authoritative Case Initialization

## Context and Problem Statement

ADR-0015 established that the receiver (vendor) creates the `VulnerabilityCase`
object in its own DataLayer at report receipt (`RM.RECEIVED`), then
retroactively introduces the CaseActor via the `CaseProposal` protocol
(ADR-0023). This produces an architecture gap: the vendor is not the
authoritative creator of the canonical case, yet it creates the case object
before the CaseActor exists.

The concrete problems this gap causes:

1. **AS2 authorship violation**: the vendor creates a `VulnerabilityCase` with
   itself as `attributed_to`, but per ADR-0023 the CaseActor is the
   authoritative case creator and the only correct `actor` on
   `Create(VulnerabilityCase)`.

2. **Prologue back-fill**: `WritePrologueLedgerEntriesNode` (Issue #1688) was
   introduced as a workaround to stamp vendor-authored initialization entries
   into the CaseActor's canonical ledger when the CaseActor accepts the
   `Offer(CaseManagerRole)`. Its own docstring acknowledges "the vendor actor
   is not the CaseActor and MUST NOT commit canonical case-ledger entries."

3. **Two overlapping init mechanisms**: the `CaseProposal` accept path
   (ADR-0023) and the prologue back-fill path (#1688) both attempt to establish
   the initial case at the CaseActor. Their overlap is the direct cause of
   Issue #1767: `add_case_status_to_case` is rejected by the
   `_validate_canonical_entry` guard because the CaseActor is stamping a
   vendor-authored snapshot.

4. **Latent scenario-dependent breakage**: the prologue `add_case_status_to_case`
   entry is silently skipped in passing runs (the genesis `CaseStatus` is
   already inlined in the `create_case` entry), so the ledger "works" while
   quietly dropping an entry. Attempting to commit it (PR #1746, reverted)
   shifted ledger indices and broke `fvcv-extension` VFD replication timing —
   evidence that the back-fill is load-bearing scar tissue, not a clean layer.

The question is: **when and by whom should the `VulnerabilityCase` be
created, and what does the receiver hold locally during the proposal window?**

## Decision Drivers

- Preserve AS2 "I created this" semantics end-to-end (ADR-0023)
- Single authoritative init path: no back-fill workarounds
- Receiver needs no local `VulnerabilityCase` before the CaseActor responds
- Remove `WritePrologueLedgerEntriesNode` and the `Offer(CaseManagerRole)` path
  as they become unnecessary

## Considered Options

1. **CaseActor-authoritative initialization** (chosen): receiver stores the
   report and sends `Create(CaseProposal)`, then waits. CaseActor creates the
   case, adds participants, initializes embargo, and commits canonical ledger
   entries natively when accepting the proposal. Receiver creates no
   `VulnerabilityCase` until `Create(VulnerabilityCase)` arrives from the
   CaseActor.

2. **Keep vendor-created case, fix back-fill signing**: allow the vendor to
   create the case but have it authored correctly as a vendor-local copy, with
   the CaseActor superseding it on `Create(VulnerabilityCase)` arrival.
   Requires complex merge/supersession logic and still violates AS2 `actor`
   semantics on the vendor-side copy.

3. **Add `("Add", "CaseStatus")` to `_CASE_AUTHORED_SIGNATURES`** (symptom
   fix only): addresses Issue #1767 but leaves the underlying two-init-path
   architecture intact. Rejected: treats the symptom without removing the
   cause.

## Decision Outcome

**Chosen option: CaseActor-authoritative initialization (Option 1).**

### New protocol flow

```text
Reporter → Offer(VulnerabilityReport) → Receiver inbox
Receiver: store report + write VultronReportCaseLink(status=PENDING_PROPOSAL)
Receiver → Create(as_CaseProposal) → CaseActor inbox

CaseActor (on Accept(CaseProposal)):
  - Create VulnerabilityCase (attributed_to=CaseActor)
  - Add receiver as CASE_OWNER participant (RM.RECEIVED)
  - Add reporter as participant (RM.ACCEPTED)
  - Initialize default embargo
  - Commit canonical ledger entries natively (no back-fill)
  - Emit Accept(as_CaseProposal) → Receiver inbox
  - Emit Create(VulnerabilityCase, actor=CaseActor) → Receiver inbox

Receiver (on Create(VulnerabilityCase)):
  - Seed local replica via CreateCaseReceivedUseCase (already exists)
  - Record trust anchors in VultronReportCaseLink
  - CaseActor is now the comms hub for the case
```

### What is removed

- `CreateCaseNode`, `CreateCaseOwnerParticipant`, `InitializeDefaultEmbargoNode`,
  `CreateCaseActivity`/`UpdateActorOutbox` from the vendor's
  `receive_report_case_tree.py`. The vendor tree becomes: store report →
  write pending link → `ProposeCaseToActorNode` → done.
- `WritePrologueLedgerEntriesNode` (Issue #1688) — the back-fill is no longer
  needed when the CaseActor commits init entries natively.
- `SendOfferCaseManagerRoleNode` and the `Offer(CaseManagerRole)` / accept
  path from the vendor tree — the CaseActor adds itself as `CASE_MANAGER` when
  creating the case natively.
- `CreateCaseActorNode` from the vendor tree — the CaseActor is a pre-existing
  service; the vendor does not spawn it.

### What stays

- `ProposeCaseToActorNode` — still needed; the vendor sends
  `Create(as_CaseProposal)` to initiate the CaseActor-authoritative flow.
- `CreateCaseReceivedUseCase` — already handles `Create(VulnerabilityCase)`
  arriving at the vendor inbox; now actually seeds the case rather than hitting
  the idempotency skip.
- `VultronReportCaseLink` — vendor's interim record during the proposal window
  (`status=PENDING_PROPOSAL`). No `VulnerabilityCase` exists vendor-side until
  the CaseActor's `Create(VulnerabilityCase)` arrives.
- All of `case_proposal_received_tree.py` structure — enriched with native
  participant, embargo, and ledger initialization.

### Consequences

- **Good**: AS2 `actor` semantics are correct end-to-end — only the CaseActor
  bears `actor` on `Create(VulnerabilityCase)`.
- **Good**: Single initialization path; `WritePrologueLedgerEntriesNode` and
  the `Offer(CaseManagerRole)` path are removed entirely.
- **Good**: Issue #1767 is resolved as a consequence — the
  `add_case_status_to_case` signature conflict disappears because the back-fill
  is gone.
- **Good**: `receive_report_case_tree.py` becomes significantly simpler.
- **Neutral**: `case_proposal_received_tree.py` gains participant creation,
  embargo initialization, and ledger commit responsibility. This is the correct
  place for it.
- **Bad**: The embedded participant payload in `Create(VulnerabilityCase)` must
  be rich enough for `_store_embedded_participants` and
  `EnsureReporterParticipantAtAcceptedNode` to seed the vendor's replica
  correctly. This is an implementation constraint on the CaseActor-side tree.

### Implementation order

Issues must be implemented in this order to keep each step independently
testable:

1. **Enrich CaseActor tree** (Issue B, blocked by #1771 docs PR): add native
   participant creation, embargo init, and ledger commits to
   `case_proposal_received_tree.py`. Additive; vendor tree is untouched.
   Demo still passes.

2. **Slim vendor tree** (Issue A, blocked by Issue B): remove case-creation
   nodes from `receive_report_case_tree.py`. Depends on Issue B being merged
   so the CaseActor's `Create(VulnerabilityCase)` carries full participant
   data.

3. **Remove prologue and `Offer(CaseManagerRole)` path** (Issue C, blocked by
   Issue A): delete `WritePrologueLedgerEntriesNode`, gut
   `offer_case_manager_role_received_tree.py`, remove `SendOfferCaseManagerRoleNode`
   and `CreateCaseActorNode` from vendor tree. Closes Issue #1767.

4. **Spec and notes updates** (Issue D, parallel with B/C): update CP, CM, CLP
   specs and `notes/case-proposal.md`, `notes/case-bootstrap-trust.md`.

## More Information

- Supersedes: `docs/adr/0015-create-case-at-report-receipt.md`
- Refines: `docs/adr/0023-case-proposal-protocol.md`
- Source concern: Issue #1771
- Symptom issue resolved: Issue #1767
- Workaround removed: Issue #1688 (`WritePrologueLedgerEntriesNode`)
- Generated spec requirements: `specs/case-proposal.yaml` CP-09,
  `specs/case-management.yaml` CM-16 (CaseActor-authoritative init)
