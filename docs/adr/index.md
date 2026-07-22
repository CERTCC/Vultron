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

### How to write an ADR

For new ADRs, please use [adr-template.md](_adr-template.md) as basis.
More information on MADR is available at <https://adr.github.io/madr/>.
General information about architectural decision records is available at <https://adr.github.io/>.

## Accepted ADRs

- [ADR-0000 Record architecture decisions](0000-record-architecture-decisions.md)
- [ADR-0001 Use Markdown Any Decision Records](0001-use-markdown-any-decision-records.md)
- [ADR-0002 Model Vultron Processes as Behavior Trees](0002-model-processes-with-behavior-trees.md)
- [ADR-0003 Build Our Own Behavior Tree Engine](0003-build-custom-python-bt-engine.md)
- [ADR-0004 Use Factory Pattern to Create Behavior Tree Nodes](0004-use-factory-methods-for-common-bt-node-types.md)
- [ADR-0005 Use ActivityStreams Vocabulary as Vultron Message Format](0005-activitystreams-vocabulary-as-vultron-message-format.md)
- [ADR-0006 Use CalVer for Project Versioning](0006-use-calver-for-project-versioning.md)
- [ADR-0007 Introduce a Behavior Dispatcher](0007-use-behavior-dispatcher.md)
- [ADR-0008 Use py_trees for Handler BT Integration](0008-use-py-trees-for-handler-bt-integration.md)
- [ADR-0009 Adopt Hexagonal Architecture (Ports and Adapters)](0009-hexagonal-architecture.md)
- [ADR-0010 Standardize Object IDs to URI Form](0010-standardize-object-ids.md)
- [ADR-0011 Remove API v1 and consolidate vocabulary examples into API v2](0011-remove-api-v1.md)
- [ADR-0012 Per-Actor DataLayer Isolation](0012-per-actor-datalayer-isolation.md)
- [ADR-0013 Unify RM State Tracking](0013-unify-rm-state-tracking.md)
- [ADR-0014 Pin GitHub Actions to Full Commit SHAs with Version
  Comments](0014-sha-pin-github-actions.md)
- [ADR-0015 Create VulnerabilityCase at Report Receipt
  (RM.RECEIVED)](0015-create-case-at-report-receipt.md)
- [ADR-0016 Replace TinyDB with SQLModel/SQLite DataLayer
  Adapter](0016-sqlmodel-sqlite-datalayer.md)
- [ADR-0017 Domain/Wire Object Separation: Shared-Base, Two-Branch
  Hierarchy](0017-domain-wire-object-separation.md)
- [ADR-0018 Canonical Case History Convergence on
  `CaseLogEntry`](0018-canonical-case-history-convergence.md)
- [ADR-0019 Separate the Case Ledger from the Per-Actor Process
  Log](0019-separate-case-ledger-from-process-log.md)
- [ADR-0021 CaseActor Inbox Routing as the Sole Path to Canonical Ledger
  Entries](0021-caseactor-inbox-routing-canonical-ledger.md)
- [ADR-0022 Single BT Execution Per Inbox Delivery for Received-Side
  CaseActor Routing](0022-single-bt-execution-for-received-side-case-actor-routing.md)
- [ADR-0023 Introduce `CaseProposal` for Distributed Case Actor
  Initialization](0023-case-proposal-protocol.md)
- [ADR-0024 Coordination Agent Taxonomy](0024-coordination-agent-taxonomy.md)
- [ADR-0025 Call-Out Point Abstraction Layer: Factory-Based Injection with
  Typed Backends](0025-call-out-point-abstraction-layer.md)
- [ADR-0031 Introduce `vultron/enums/` as a Bottom-of-Stack Neutral Layer for
  Cross-Cutting Enumerations](0031-vultron-enums-neutral-layer.md)
- [ADR-0032 Validate at the Edge, Promote to Strict Core
  Types](0032-validate-at-edge-promote-to-core.md)
- [ADR-0026 CaseActor-Routed Actor Suggestion and Invitation
  Flow](0026-caseactor-routed-actor-suggestion.md)
- [ADR-0034 DataLayer Port Returns Core Domain
  Objects](0034-datalayer-returns-core-objects.md)
- [ADR-0035 Core Activity Representation and Envelope
  Reconstitution](0035-core-activity-representation-and-envelope-reconstitution.md)
- [ADR-0036 Per-Machine Dimension Objects for CaseStatus and
  ParticipantStatus](0036-status-dimension-objects.md)
- [ADR-0037 Buffer Out-of-Order `Announce(CaseLedgerEntry)` Instead of
  Dropping](0037-buffer-out-of-order-ledger-entries.md)
- [ADR-0038 Replace Six-Kind Spec Taxonomy with Four-Tier Portability
  Hierarchy](0038-four-tier-specification-taxonomy.md)
- [ADR-0028 Publication-Intent Subtree Collapse: Bypass Leaves →
  Intent-Record-Driven Arms](0028-publication-intent-bt-collapse.md)
- [ADR-0029 Notification Loop Collapse: InjectParticipant →
  suggest-actor-to-case Protocol](0029-notification-loop-suggest-actor.md)

## Proposed ADRs

- [ADR-0020 Move Inbox Orchestration into a Core BT Module with a Typed
  `process_payload` Seam](0020-inbox-bt-orchestration.md)
- [ADR-0027 Exploit-Strategy Subtree Collapse: Five Simulator Nodes →
  EvaluateExploitStrategy](0027-exploit-strategy-bt-collapse.md) *(provisional)*
- [ADR-0030 Publish Leaf Expansion: Single Actuator →
  Draft-Review-Submit Pipeline](0030-publish-leaf-draft-review-submit-pipeline.md)
  *(provisional)*
- [ADR-0033 Lifecycle-Staged Domain Types Anchored on Guaranteed-Field
  Changes](0033-lifecycle-staged-case-types.md)

## Rejected ADRs

- none

## Superseded ADRs

- none
