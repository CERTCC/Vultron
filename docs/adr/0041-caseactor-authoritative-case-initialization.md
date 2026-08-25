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

   The guard has two distinct failure modes, and they need separate fixes.
   It only rejects when the snapshot's `actor` **equals** the CaseActor's own
   ID. In a multi-actor deployment the vendor URI is the snapshot actor, so the
   guard never fires and removing the back-fill is sufficient. In a single-actor
   deployment (the `fvv` scenario, where the vendor *is* the CaseActor) the
   snapshot actor equals `case_actor_id`, the guard does fire, and the
   `("Add", "CaseStatus")` signature must additionally be authorized.

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
- Remove `WritePrologueLedgerEntriesNode`, and remove `Offer(CaseManagerRole)`
  from the initialization path, as both become unnecessary there

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

3. **Authorize `("Add", "CaseStatus")` and stop there**: add the signature to
   `_CASE_AUTHORED_SIGNATURES` as the *whole* response to Issue #1767, leaving
   the two-init-path architecture intact. Rejected: it silences the guard while
   the vendor continues to author and back-fill initialization entries it has no
   authority over. Attempted in commit `256ef3e1` and reverted in `f6578c22`.

   Note that authorizing the signature is **not** rejected in itself — Option 1
   requires it, because the CaseActor authors that entry natively and must be
   permitted to. What is rejected is treating it as a substitute for removing
   the back-fill. See "Signature authorization" under Decision Outcome.

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
- `SendOfferCaseManagerRoleNode` from `receive_report_case_tree.py`, and the
  prologue node from `offer_case_manager_role_received_tree.py` — the CaseActor
  adds itself as `CASE_MANAGER` when creating the case natively, so the
  `Offer(CaseManagerRole)` handshake is no longer part of case initialization.

  **Scope limit:** what is removed is the handshake's role in *initialization*,
  not the handshake. `Offer(CaseManagerRole)` remains a protocol operation in
  its own right — explicit CASE_MANAGER delegation to a service actor while the
  vendor retains CASE_OWNER — required by DEMOMA-08-002, DEMOMA-08-003, and
  DEMOMA-08-006 through DEMOMA-08-009, and reachable via the manual trigger
  `offer_case_manager_role_trigger_bt`. `create_offer_case_manager_role_received_tree`
  therefore keeps its accept/reject path fully functional, which also means
  traffic from pre-ADR-0041 actors is answered rather than silently dropped.
- `CreateCaseActorNode` from the vendor's `receive_report_case_tree.py` — the
  CaseActor is a pre-existing service; the vendor does not spawn it at report
  receipt. The node itself is **retained**: `create_tree.py` still uses it for
  standalone case construction outside the report-receipt flow.

### Signature authorization

Because the CaseActor now authors the four initialization entries itself,
`_CASE_AUTHORED_SIGNATURES` MUST authorize every signature it emits during
initialization: `("Create", "VulnerabilityCase")`, `("Add", "VulnerabilityReport")`,
`("Add", "ParticipantStatus")`, and `("Add", "CaseStatus")`. The last of these
was previously absent, which is the mechanical half of Issue #1767. Normative in
CLP-12-001 (the specific entry) and CLP-12-002 (the general completeness rule).

This is a consequence of Option 1, not an alternative to it — see Option 3.

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
- **Good**: Single initialization path; `WritePrologueLedgerEntriesNode` is
  removed entirely and `Offer(CaseManagerRole)` no longer participates in
  initialization.
- **Good**: Issue #1767 is resolved by the two halves together — removing the
  back-fill eliminates the vendor-authored snapshot in multi-actor deployments,
  and authorizing `("Add", "CaseStatus")` covers the single-actor deployment
  where the guard still fires. Neither half is sufficient alone.
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

3. **Remove prologue and decouple `Offer(CaseManagerRole)` from init** (Issue C,
   blocked by Issue A): delete `WritePrologueLedgerEntriesNode`, remove the
   prologue node from `offer_case_manager_role_received_tree.py` while keeping
   its accept/reject path functional, remove `SendOfferCaseManagerRoleNode` and
   `CreateCaseActorNode` from the vendor's report-receipt tree, and authorize
   `("Add", "CaseStatus")`. Closes Issue #1767.

4. **Spec and notes updates** (Issue D, parallel with B/C): update CP, CM, CLP
   specs and `notes/case-proposal.md`, `notes/case-bootstrap-trust.md`.

## More Information

- Supersedes: `docs/adr/0015-create-case-at-report-receipt.md`
- Refines: `docs/adr/0023-case-proposal-protocol.md`
- Source concern: Issue #1771
- Symptom issue resolved: Issue #1767
- Workaround removed: Issue #1688 (`WritePrologueLedgerEntriesNode`)
- Generated spec requirements: `specs/case-proposal.yaml` CP-09,
  `specs/case-management.yaml` CM-22 (CaseActor-authoritative init),
  `specs/case-ledger-processing.yaml` CLP-12
- Retained by scope limit: DEMOMA-08-002, DEMOMA-08-003, DEMOMA-08-006 through
  DEMOMA-08-009 (`Offer(CaseManagerRole)` as a standalone delegation operation)

### Revision history

Revised 2026-07-31 during Issue #1777 (PR #1851), the implementation of step 3.
The decision is unchanged; three statements that misdescribed it were corrected
in place rather than appended to, so the document reads as the decision now
stands:

- Option 3 previously read as rejecting the `("Add", "CaseStatus")`
  authorization outright, which the chosen option in fact requires. It now
  rejects only *substituting* that authorization for removal of the back-fill.
- "What is removed" listed the `Offer(CaseManagerRole)` accept path and
  `CreateCaseActorNode` without qualification, conflicting with MUST-level
  DEMOMA-08 specs and with `create_tree.py`'s live use of the node. Both entries
  are now scoped to the report-receipt path.
- The Issue #1767 consequence claimed removal of the back-fill was sufficient on
  its own. It is sufficient only for multi-actor deployments.
