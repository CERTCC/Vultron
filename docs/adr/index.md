# Decisions

This section contains decision records for the Vultron project.

## What is an ADR?

An architectural decision record (ADR) is a document that captures an important architectural decision made along with its context and consequences.
We're using the expanded concept of an *Any Decision Record* (ADR) to capture any decision that is important to the project, not just architectural decisions.
We use [Markdown Any Decision Records (MADR)](https://adr.github.io/madr/) to document our architectural decisions.

### When to write an ADR

The primary signal for an ADR is **evaluated alternatives**: if you considered
more than one option and rejected at least one, document the decision. The
record preserves context for future maintainers who might otherwise re-open
a settled question.

Concretely, write an ADR when:

- You adopted a structural or architectural approach over one or more
  alternatives (e.g., hexagonal architecture over layered, SQLModel over
  TinyDB).
- You made a one-time process or tooling decision with lasting project-wide
  impact (e.g., CalVer over SemVer, pinning CI action SHAs).
- A decision will be hard or costly to reverse, so the rationale should be
  preserved explicitly.

**ADR vs. spec**: an ADR records *why* a choice was made; a spec entry records
*what* the system must do going forward. When a significant decision also
generates recurring testable requirements, create both — see
`notes/specs-vs-adrs.md` for the full delineation guidelines and worked
examples.

You do **not** need an ADR for:

- Uncontested conventions with no real alternatives (write a spec entry
  instead).
- Small tactical choices where the rationale is obvious from the code.

If you're unsure, err on the side of writing one — a brief ADR is better than
losing context.

### Revising vs. amending an ADR

An ADR records the decision that was made and why. Its value to a future reader
is that they can understand the current expectation in one pass.

**When to revise in-place**: If a recently-accepted ADR contains a statement
that its own implementation contradicted — e.g., an option label that says
"rejected" for something the chosen option actually requires, or a "what is
removed" list that conflicts with MUST-level spec entries — **revise the ADR
body directly** to make the current expectation accurate.

**When to write a new ADR**: If the decision itself changed (you adopted a
different option than originally chosen), write a new ADR that supersedes the
old one.

**Do not append `### Amendment` sections**: An append-only trail of amendments
forces future readers to reconcile the body against its own addenda to determine
which statement is currently authoritative. This defeats the primary purpose of
the record. The only exception is an ADR with `status: provisional` where the
amendment explicitly finalises that status.

Source: ISSUE-1777 / learning 2026-07-31

### How to write an ADR

For new ADRs, please use [adr-template.md](_adr-template.md) as basis.
More information on MADR is available at <https://adr.github.io/madr/>.
General information about architectural decision records is available at <https://adr.github.io/>.

## Accepted ADRs

- [ADR-0000 Record architecture decisions](0000-record-architecture-decisions.md)
- [ADR-0001 Use Markdown Any Decision Records](0001-use-markdown-any-decision-records.md)
- [ADR-0002 Model Processes with Behavior Trees](0002-model-processes-with-behavior-trees.md)
- [ADR-0003 Build our own Behavior Tree engine in Python](0003-build-custom-python-bt-engine.md)
- [ADR-0004 Use factory methods for common BT node types](0004-use-factory-methods-for-common-bt-node-types.md)
- [ADR-0005 Use ActivityStreams Vocabulary as the basis for Vultron Message Formats](0005-activitystreams-vocabulary-as-vultron-message-format.md)
- [ADR-0006 Vultron Project Versioning](0006-use-calver-for-project-versioning.md)
- [ADR-0007 Introduce a Behavior Dispatcher Between Inbox Handling and Behavior Execution](0007-use-behavior-dispatcher.md)
- [ADR-0008 Use py_trees for Behavior Tree Execution in Handler Integration](0008-use-py-trees-for-handler-bt-integration.md)
- [ADR-0009 Adopt Hexagonal Architecture (Ports and Adapters) for Vultron](0009-hexagonal-architecture.md)
- [ADR-0010 Standardize Object IDs to URI Form](0010-standardize-object-ids.md)
- [ADR-0011 Remove API v1 and consolidate vocabulary examples into API v2](0011-remove-api-v1.md)
- [ADR-0012 Per-Actor DataLayer Isolation](0012-per-actor-datalayer-isolation.md) — partially superseded by docs/adr/0073-per-actor-storage-isolation.md
- [ADR-0013 Unify RM State Tracking into Persisted VultronParticipantStatus Records](0013-unify-rm-state-tracking.md)
- [ADR-0014 Pin GitHub Actions to Full Commit SHAs with Version Comments](0014-sha-pin-github-actions.md)
- [ADR-0016 Replace TinyDB with SQLModel/SQLite DataLayer Adapter](0016-sqlmodel-sqlite-datalayer.md)
- [ADR-0017 Domain/Wire Object Separation: Shared-Base, Two-Branch Hierarchy](0017-domain-wire-object-separation.md)
- [ADR-0018 Canonical Case History Convergence on `CaseLogEntry`](0018-canonical-case-history-convergence.md)
- [ADR-0019 Separate the Case Ledger from the Per-Actor Process Log](0019-separate-case-ledger-from-process-log.md)
- [ADR-0021 CaseActor Inbox Routing as the Sole Path to Canonical Ledger Entries](0021-caseactor-inbox-routing-canonical-ledger.md)
- [ADR-0022 Single BT Execution Per Inbox Delivery for Received-Side CaseActor Routing](0022-single-bt-execution-for-received-side-case-actor-routing.md)
- [ADR-0023 Introduce `CaseProposal` for Distributed Case Actor Initialization](0023-case-proposal-protocol.md)
- [ADR-0024 Capability Shape Taxonomy](0024-coordination-agent-taxonomy.md)
- [ADR-0025 Call-Out Point Abstraction Layer: Factory-Based Injection with Typed Backends](0025-call-out-point-abstraction-layer.md)
- [ADR-0026 CaseActor-Routed Actor Suggestion and Invitation Flow](0026-caseactor-routed-actor-suggestion.md)
- [ADR-0027 Exploit-Strategy Subtree Collapse: Five Simulator Nodes → EvaluateExploitStrategy](0027-exploit-strategy-bt-collapse.md)
- [ADR-0028 Publication-Intent Subtree Collapse: Bypass Leaves → Intent-Record-Driven Arms](0028-publication-intent-bt-collapse.md)
- [ADR-0029 Notification Loop Collapse: InjectParticipant → suggest-actor-to-case Protocol](0029-notification-loop-suggest-actor.md)
- [ADR-0030 Publish Leaf Expansion: Single Actuator → Draft-Review-Submit Pipeline](0030-publish-leaf-draft-review-submit-pipeline.md)
- [ADR-0031 Introduce `vultron/enums/` as a Bottom-of-Stack Neutral Layer for Cross-Cutting Enumerations](0031-vultron-enums-neutral-layer.md)
- [ADR-0032 Validate at the Edge, Promote to Strict Core Types](0032-validate-at-edge-promote-to-core.md)
- [ADR-0033 Lifecycle-Staged Domain Types Anchored on Guaranteed-Field Changes](0033-lifecycle-staged-case-types.md)
- [ADR-0034 DataLayer Port Returns Core Domain Objects](0034-datalayer-returns-core-objects.md)
- [ADR-0035 Core Activity Representation and Envelope Reconstitution](0035-core-activity-representation-and-envelope-reconstitution.md)
- [ADR-0036 Per-Machine Dimension Objects for CaseStatus and ParticipantStatus](0036-status-dimension-objects.md)
- [ADR-0037 Buffer Out-of-Order `Announce(CaseLedgerEntry)` Instead of Dropping](0037-buffer-out-of-order-ledger-entries.md)
- [ADR-0038 Replace Six-Kind Spec Taxonomy with Four-Tier Portability Hierarchy](0038-four-tier-specification-taxonomy.md)
- [ADR-0039 Resolve Wire Ambiguity Between OFFER\_CASE\_MANAGER\_ROLE and OFFER\_CASE\_OWNERSHIP\_TRANSFER via Dedicated Object Type](0039-offer-case-participant-role-wire-type.md)
- [ADR-0040 Introduce UseCaseResult Envelope; Do Not Introduce UseCaseRequest](0040-use-case-result-envelope.md)
- [ADR-0041 CaseActor-Authoritative Case Initialization](0041-caseactor-authoritative-case-initialization.md)
- [ADR-0042 Deliver All Inter-Actor Communication over HTTP; Retire the In-Process ASGI Delivery Shortcut](0042-http-only-inter-actor-delivery.md)
- [ADR-0043 Use the ADR `status` Field as the Confidence Signal (Extend Its Vocabulary Rather Than Add a New Field)](0043-adr-status-as-confidence-signal.md)
- [ADR-0044 Adopt py_trees Typed Ports for BT Node Blackboard Contracts](0044-py-trees-typed-ports-adoption.md)
- [ADR-0045 Correct Field Assignment on `Create(VulnerabilityCase)` — `context` to Case URI, `inReplyTo` to Accept URI](0045-create-vulnerability-case-field-assignment.md)
- [ADR-0046 Two-Gate Authorization Model for Received-Side CaseStatus Canonicalization](0046-received-status-authorization.md) *(provisional)*
- [ADR-0047 Report-to-Others Party Discovery: Sentinel Over Inline BT Loop](0047-report-to-others-sentinel-over-inline-bt.md)
- [ADR-0048 PEC `NO_EMBARGO` Means Absence of Embargo, Not Pre-Consent](0048-pec-no-embargo-is-absence-not-pre-consent.md)
- [ADR-0049 Core Does Not Model Inbound Protocol Error Message Types; No `create_inbound_error_followup_tree`](0049-core-does-not-model-error-message-types.md)
- [ADR-0050 Leave(VulnerabilityCase) Is the Canonical RM Case Closure Mechanism](0050-leave-vul-case-canonical-rm-closure.md)
- [ADR-0051 CaseActor Has Its Own RM Lifecycle Tracked via CaseParticipant](0051-caseactor-rm-lifecycle.md)
- [ADR-0052 Demo CI Job Structure: Accept Barrier + Concurrency Group Over Job Consolidation](0052-demo-ci-job-structure-barrier-accepted.md) *(provisional)*
- [ADR-0053 Route Ownership-Transfer Offer and Accept Through the CaseActor](0053-ownership-transfer-routed-via-caseactor.md)
- [ADR-0054 Retain plan/incoming/learnings/ as a File Queue; Do Not Migrate to GitHub Issues](0054-learnings-queue-as-files-not-issues.md)
- [ADR-0055 CI Failure Alerting via GitHub Issues on Main-Branch and Scheduled Workflows](0055-ci-failure-alerting-via-github-issues.md)
- [ADR-0056 `embargo_adherence` Is a Computed Property Derived from PEC State](0056-embargo-adherence-computed-field.md)
- [ADR-0057 Rename `CVDRole.OTHER` to `CVDRole.OBSERVER` and Define Observer Participant Semantics](0057-observer-participant-role.md)
- [ADR-0058 Gate Demo Scenario Steps on Causal Preconditions, Not Temporal Order](0058-causal-gating-in-demo-scenarios.md)
- [ADR-0059 Buffer Pre-Genesis `Announce(CaseLedgerEntry)` and Drain on Case Seed](0059-buffer-pre-genesis-ledger-entries.md)
- [ADR-0060 Re-express the Legacy Case-State Invariants and Keep the Hypercube as Reference](0060-re-express-legacy-cs-invariants.md)
- [ADR-0061 Adjudicate Received `ParticipantStatus` Per Dimension, Not as a Unit](0061-per-dimension-partial-accept.md)
- [ADR-0062 Normalise Wire → Core at Ingress, and Enforce It Again at the Persistence Boundary](0062-normalise-wire-to-core-at-both-ingress-and-persistence.md) — partially superseded by docs/adr/0082-wire-core-boundary-pairing-registry.md
- [ADR-0063 Render Core Objects to Wire JSON Through a Driven Port; Remove `alias_generator` From All Core-Branch Types](0063-wire-rendering-port-for-core-objects.md) — partially superseded by docs/adr/0082-wire-core-boundary-pairing-registry.md
- [ADR-0064 Enforce Post-Construction Type Safety on the Core Branch Only, in Three Ratcheted Steps](0064-core-branch-validate-assignment.md)
- [ADR-0065 Carry the Embargo Invite RSVP Deadline on `Invite.end_time`](0065-embargo-invite-rsvp-deadline.md)
- [ADR-0066 Outbox Terminal State: Per-Activity Attempt Counter, 4xx Classification, and Dead-Letter Store](0066-outbox-terminal-state.md)
- [ADR-0067 Accept Non-Adjacent Forward RM Jumps and Notify; Refuse Backward Regressions Non-Silently](0067-rm-nonadj-accept-and-notify.md)
- [ADR-0068 Refuse Misaddressed Activities at the Inbox with a Synchronous 4xx](0068-inbox-refuse-misaddressed-activities.md)
- [ADR-0069 Adopt certcc.github.io/Vultron as the Initial Vultron Vocabulary Namespace Host](0069-vultron-namespace-uri.md) *(provisional)*
- [ADR-0070 Reuse `validate-report` for Invited Actors; Derive `VultronOfferRecord` from Ledger Backfill](0070-invited-actor-rm-triage-via-ledger-backfill.md)
- [ADR-0071 CVE Eligibility: Reference Baseline over Normative Citation or Implementation-Defined](0071-cna-eligibility-reference-baseline.md)
- [ADR-0072 Use a Dedicated `stories:` Field for Spec-to-Story Traceability (Not `relationships:`)](0072-stories-field-for-spec-to-story-traceability.md)
- [ADR-0073 Give Each Actor Its Own Store; Delete the Unscoped DataLayer](0073-per-actor-storage-isolation.md)
- [ADR-0074 Treat Wire Activities as Immutable Artifacts; Freeze at Receipt and at Factory Seal](0074-wire-activity-artifact-immutability.md)
- [ADR-0075 Split Per-Participant VFD Tracking into Separate Vendor-Path and Deployer-Path Sub-Machines](0075-split-vfd-state-machine.md) *(provisional)*
- [ADR-0076 Security-Significant Call-Out Gates Default to `RequireCaseOwnerApproval`](0076-security-significant-gates-default-require-case-owner-approval.md)
- [ADR-0077 Scope Ledger Replication Mechanics to a Companion Spec; Single-Hub Fan-Out Is Normative](0077-ledger-replication-companion-spec.md)
- [ADR-0078 Retire `CVDRole.FINDER` — Reporter Is the Protocol-Salient Role](0078-retire-finder-role.md)
- [ADR-0079 CaseLedger Causal Ordering: CaseActor Observation Order Is the Canonical Causal Order](0079-case-ledger-causal-ordering.md)
- [ADR-0080 Asking Permission Is a Protocol Message, Not a Suspended Behavior](0080-protocol-asks-not-suspended-behaviors.md)
- [ADR-0081 Peer Knowledge Lives in the Hosted Actor's Own Store, Not as a Hosted Actor](0081-peer-knowledge-in-hosted-actor-store.md)
- [ADR-0082 Wire/Core Boundary: One Declarative Pairing Registry, One Translator, and Reject Unknown Keys](0082-wire-core-boundary-pairing-registry.md)
- [ADR-0083 The Formal Message Set and the AS2 Wire Vocabulary Are Deliberately Different Shapes; the Mapping Is the Reconciling Artifact](0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)

## Proposed ADRs

- [ADR-0020 Move Inbox Orchestration into a Core BT Module with a Typed `process_payload` Seam](0020-inbox-bt-orchestration.md)

## Rejected ADRs

- none

## Superseded / Archived ADRs

Retired ADRs (`status: deprecated` or `superseded`) are moved to
`docs/adr/archived/` so they stay out of the default `docs/adr/` context sweep.
Each is listed here with a forward link to its replacement.

- [ADR-0015 Create VulnerabilityCase at Report Receipt (RM.RECEIVED)](archived/0015-create-case-at-report-receipt.md) — superseded by 0041-caseactor-authoritative-case-initialization.md
