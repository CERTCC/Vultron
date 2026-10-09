---
description: >
  Decision records for the Vultron project.
stakeholder_type: [project-contributor]
---

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

An ADR is a historical record.
It answers what we decided and why, given what we knew at the time — a question whose answer cannot go stale, because the past does not change.
It is not a description of the current codebase.

That distinction decides most editing questions.
When an ADR names a function, a module path, or a class that was later renamed or deleted, the decision still stands and the record is still accurate about the decision; only its description of the code has aged.

**A refactor is never responsible for updating an ADR.**
Renaming a symbol or splitting a module does not oblige you to touch any ADR that mentions it.
If a decision has consequences that future code must obey, those belong in a spec requirement or a `notes/` file, which carry an obligation to stay current that an ADR does not.
Record them there and cite the ADR as provenance — see `notes/specs-vs-adrs.md` for the delineation and MS-11-004 for the bidirectional citation pattern.
A spec or note MUST NOT resolve its own meaning by pointing into an ADR body; cite the ADR for *why*, and state the rule where the reader already is.
The corpus does not satisfy that rule yet: the "ADR-0099 detail N" citations in `specs/` and `notes/` are the known exception, and converting them is tracked in #4389.

**How to edit an ADR**: follow the edit tiers in [ADR-0120](0120-adr-lifecycle-epochs-and-edit-tiers.md), which key off how long ago the ADR was last materially changed.
Editorial fixes and appended annotations are allowed at any time and change neither `updated` nor `revision`.
A clarification that does not alter what anything built on the ADR must do is appended as a dated note, rather than written over the original text.
A material change bumps `updated` and `revision`; on an `accepted-provisional` ADR, ask the human whether to edit in place or supersede.
On an `accepted` ADR, a material change to one detail with the chosen option intact is a dated Amendment that quotes the text it replaces.
A change of the chosen option is a new ADR that supersedes the old one; the old one is restored to its original text, marked `superseded`, and moved to `archived/` (MS-14-004).
Never rewrite an accepted ADR under its own number.
The `adr-lifecycle-check` pre-commit hook holds one part of this mechanically: on an `accepted` ADR last changed more than ten days ago, it refuses a changed `## Decision Outcome` or `## Considered Options` section that adds no new dated Amendment heading, and it refuses an `updated` bump that carries no `status_override` (MS-14-009).
It reads no other section, does not check that an Amendment quotes what it replaces, and does not fire on an `accepted-provisional` ADR, so the remaining tiers are yours to honour.

**What not to write into an ADR body.**
Implementation detail that drifts independently of the decision costs a future reader — including an agent with a limited context window — attention on claims that were true once and are not checkable now.

- A statement about a completed migration step — "X is deleted", a struck-through progress list, a renaming checklist — is project tracking, not a decision.
  Record it in the issue that does the work.
  Deleting it is an editorial edit wherever it sits outside `## Decision Outcome` and `## Considered Options`.
  Inside either of those, on an `accepted` ADR, the hook above refuses the deletion on its own, so leave it for the next material change or supersession to carry.
- A count, a metric, or a `file.py:line` citation goes stale on the next unrelated edit.
  State the rule and point at where the live answer lives.
  MS-16-001 and MS-16-002 in `specs/meta-specifications.yaml` set out the same principle for specs, notes and AGENTS.md; extending it to ADR bodies, with a check behind it, is tracked in #4389.
- A description of how the code looked when the decision was made is legitimate context, because it is part of why the decision was needed.
  Write it so it reads as of its time, and annotate anything since removed.
  [ADR-0063](0063-wire-rendering-port-for-core-objects.md) is the house style, noting inline that "that mechanism and that module were **deleted** in #2940".
  A reference marked that way is dead but not misleading.

**On the former guidance in this section.**
Until 2026-10-09 this section asked authors to revise an accepted ADR body in place so that a reader would meet only currently-accurate statements (ISSUE-1777), and discouraged appended amendments for the same reason.
That pursued the goal above — keeping stale detail out of a reader's way — through the only mechanism available while every ADR body was read as routine context: keeping the bodies current.
Keeping implementation detail out of the body in the first place serves the same goal without asking a historical record to change, and without conflicting with the lifecycle rules that ADR-0120 and MS-14-009 now set.
Records revised in place under the former guidance, such as [ADR-0098](0098-demo-scenarios-self-register.md), are left as they are.

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
- [ADR-0006 Vultron Release Versioning](0006-use-calver-for-project-versioning.md)
- [ADR-0007 Introduce a Behavior Dispatcher Between Inbox Handling and Behavior Execution](0007-use-behavior-dispatcher.md)
- [ADR-0008 Use py_trees for Behavior Tree Execution in Handler Integration](0008-use-py-trees-for-handler-bt-integration.md)
- [ADR-0009 Adopt Hexagonal Architecture (Ports and Adapters) for Vultron](0009-hexagonal-architecture.md)
- [ADR-0010 Standardize Object IDs to URI Form](0010-standardize-object-ids.md)
- [ADR-0011 Remove API v1 and consolidate vocabulary examples into API v2](0011-remove-api-v1.md)
- [ADR-0012 Per-Actor DataLayer Isolation](0012-per-actor-datalayer-isolation.md) — partially superseded by docs/adr/0073-per-actor-storage-isolation.md
- [ADR-0013 Unify RM State Tracking into Persisted VultronParticipantStatus Records](0013-unify-rm-state-tracking.md)
- [ADR-0014 Pin GitHub Actions to Full Commit SHAs with Version Comments](0014-sha-pin-github-actions.md)
- [ADR-0016 Replace TinyDB with SQLModel/SQLite DataLayer Adapter](0016-sqlmodel-sqlite-datalayer.md)
- [ADR-0018 Canonical Case History Convergence on `CaseLogEntry`](0018-canonical-case-history-convergence.md)
- [ADR-0019 Separate the Case Ledger from the Per-Actor Process Log](0019-separate-case-ledger-from-process-log.md)
- [ADR-0021 CaseActor Inbox Routing as the Sole Path to Canonical Ledger Entries](0021-caseactor-inbox-routing-canonical-ledger.md) — partially superseded by 0109-a-container-emits-only-as-actors-it-hosts.md
- [ADR-0022 Single BT Execution Per Inbox Delivery for Received-Side CaseActor Routing](0022-single-bt-execution-for-received-side-case-actor-routing.md)
- [ADR-0023 Introduce `CaseProposal` for Distributed Case Actor Initialization](0023-case-proposal-protocol.md)
- [ADR-0024 Capability Shape Taxonomy](0024-coordination-agent-taxonomy.md) — partially superseded by docs/adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md
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
- [ADR-0041 CASE_MANAGER-Authoritative Case Initialization](0041-caseactor-authoritative-case-initialization.md) *(revision 2)*
- [ADR-0042 Deliver All Inter-Actor Communication over HTTP; Retire the In-Process ASGI Delivery Shortcut](0042-http-only-inter-actor-delivery.md) — partially superseded by 0109-a-container-emits-only-as-actors-it-hosts.md
- [ADR-0043 Use the ADR `status` Field as the Confidence Signal (Extend Its Vocabulary Rather Than Add a New Field)](0043-adr-status-as-confidence-signal.md)
- [ADR-0044 Adopt py_trees Typed Ports for BT Node Blackboard Contracts](0044-py-trees-typed-ports-adoption.md)
- [ADR-0045 Correct Field Assignment on `Create(VulnerabilityCase)` — `context` to Case URI, `inReplyTo` to Accept URI](0045-create-vulnerability-case-field-assignment.md)
- [ADR-0046 Two-Gate Authorization Model for Received-Side CaseStatus Canonicalization](0046-received-status-authorization.md) *(provisional)*
- [ADR-0047 Report-to-Others Party Discovery: Sentinel Over Inline BT Loop](0047-report-to-others-sentinel-over-inline-bt.md)
- [ADR-0048 PEC `NO_EMBARGO` Means Absence of Embargo, Not Pre-Consent](0048-pec-no-embargo-is-absence-not-pre-consent.md) — partially superseded by docs/adr/0122-per-embargo-participant-consent.md
- [ADR-0049 Core Does Not Model Inbound Protocol Error Message Types; No `create_inbound_error_followup_tree`](0049-core-does-not-model-error-message-types.md)
- [ADR-0050 Leave(VulnerabilityCase) Is the Canonical RM Case Closure Mechanism](0050-leave-vul-case-canonical-rm-closure.md)
- [ADR-0051 CaseActor Has Its Own RM Lifecycle Tracked via CaseParticipant](0051-caseactor-rm-lifecycle.md)
- [ADR-0052 Demo CI Job Structure: Accept Barrier + Concurrency Group Over Job Consolidation](0052-demo-ci-job-structure-barrier-accepted.md) *(provisional)*
- [ADR-0053 Route Ownership-Transfer Offer and Accept Through the CaseActor](0053-ownership-transfer-routed-via-caseactor.md)
- [ADR-0054 Retain plan/incoming/learnings/ as a File Queue; Do Not Migrate to GitHub Issues](0054-learnings-queue-as-files-not-issues.md)
- [ADR-0055 CI Failure Alerting via GitHub Issues on Main-Branch and Scheduled Workflows](0055-ci-failure-alerting-via-github-issues.md)
- [ADR-0057 Rename `CVDRole.OTHER` to `CVDRole.OBSERVER` and Define Observer Participant Semantics](0057-observer-participant-role.md)
- [ADR-0058 Gate Demo Scenario Steps on Causal Preconditions, Not Temporal Order](0058-causal-gating-in-demo-scenarios.md)
- [ADR-0059 Buffer Pre-Genesis `Announce(CaseLedgerEntry)` and Drain on Case Seed](0059-buffer-pre-genesis-ledger-entries.md)
- [ADR-0060 Re-express the Legacy Case-State Invariants and Keep the Hypercube as Reference](0060-re-express-legacy-cs-invariants.md)
- [ADR-0061 Adjudicate Received `ParticipantStatus` Per Dimension, Not as a Unit](0061-per-dimension-partial-accept.md)
- [ADR-0063 Render Core Objects to Wire JSON Through a Driven Port; Remove `alias_generator` From All Core-Branch Types](0063-wire-rendering-port-for-core-objects.md) — partially superseded by 0099-one-object-model-as2-is-a-serialization.md
- [ADR-0064 Enforce Post-Construction Type Safety on the Core Branch Only, in Three Ratcheted Steps](0064-core-branch-validate-assignment.md)
- [ADR-0065 Carry the Embargo Invite RSVP Deadline on `Invite.end_time`](0065-embargo-invite-rsvp-deadline.md)
- [ADR-0066 Outbox Terminal State: Per-Activity Attempt Counter, 4xx Classification, and Dead-Letter Store](0066-outbox-terminal-state.md)
- [ADR-0067 Accept Non-Adjacent Forward RM Jumps and Notify; Refuse Backward Regressions Non-Silently](0067-rm-nonadj-accept-and-notify.md)
- [ADR-0068 Refuse Misaddressed Activities at the Inbox with a Synchronous 4xx](0068-inbox-refuse-misaddressed-activities.md)
- [ADR-0069 Adopt certcc.github.io/Vultron as the Initial Vultron Vocabulary Namespace Host](0069-vultron-namespace-uri.md) *(provisional)* — partially superseded by 0106-versioning-machine-facing-interfaces.md
- [ADR-0071 CVE Eligibility: Reference Baseline over Normative Citation or Implementation-Defined](0071-cna-eligibility-reference-baseline.md)
- [ADR-0072 Use a Dedicated `stories:` Field for Spec-to-Story Traceability (Not `relationships:`)](0072-stories-field-for-spec-to-story-traceability.md)
- [ADR-0073 Give Each Actor Its Own Store; Delete the Unscoped DataLayer](0073-per-actor-storage-isolation.md) — partially superseded by 0109-a-container-emits-only-as-actors-it-hosts.md
- [ADR-0074 Treat Wire Activities as Immutable Artifacts; Freeze at Receipt and at Factory Seal](0074-wire-activity-artifact-immutability.md) — partially superseded by 0099-one-object-model-as2-is-a-serialization.md
- [ADR-0075 Split Per-Participant VFD Tracking into Separate Vendor-Path and Deployer-Path Sub-Machines](0075-split-vfd-state-machine.md)
- [ADR-0076 Security-Significant Call-Out Gates Default to `RequireCaseOwnerApproval`](0076-security-significant-gates-default-require-case-owner-approval.md)
- [ADR-0077 Scope Ledger Replication Mechanics to a Companion Spec; Single-Hub Fan-Out Is Normative](0077-ledger-replication-companion-spec.md)
- [ADR-0078 Retire `CVDRole.FINDER` — Reporter Is the Protocol-Salient Role](0078-retire-finder-role.md)
- [ADR-0079 CaseLedger Causal Ordering: CaseActor Observation Order Is the Canonical Causal Order](0079-case-ledger-causal-ordering.md)
- [ADR-0080 Asking Permission Is a Protocol Message, Not a Suspended Behavior](0080-protocol-asks-not-suspended-behaviors.md)
- [ADR-0081 Peer Knowledge Lives in the Hosted Actor's Own Store, Not as a Hosted Actor](0081-peer-knowledge-in-hosted-actor-store.md)
- [ADR-0083 The Formal Message Set and the AS2 Wire Vocabulary Are Deliberately Different Shapes; the Mapping Is the Reconciling Artifact](0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)
- [ADR-0085 Owner-Close Is a Hard Write Boundary; RM.CLOSED Is Terminal and Rejoin Is Unsupported](0085-case-lifecycle-boundaries.md)
- [ADR-0086 Report Every Violation, Reject the Batch — and the Emit/Receive Dispositions Are Postel's Maxim](0086-report-every-violation-reject-the-batch.md)
- [ADR-0087 Case-Resolution Disposition for BT Nodes Is Chosen by Role, Not Re-Decided Per Call Site](0087-case-resolution-disposition-policy.md)
- [ADR-0088 Authority Is the CASE_MANAGER Role; "Case Actor" Names the Prototype Actor That Enacts It, Not the Authority](0088-consolidate-case-authority-determination.md)
- [ADR-0089 One `ParticipantStatus` Writer, and Pre-Case RM State Belongs to `ReportCaseLink`](0089-one-participant-status-writer.md)
- [ADR-0090 A Blank Required Field Is Absence, and a Recognised Inline Object That Fails Validation Is Refused](0090-blank-is-absent-and-inline-faults-are-refused.md)
- [ADR-0091 Rename PEC `NO_EMBARGO` to `UNBOUND`; Drop `EM.NO_EMBARGO` Alias](0091-rename-pec-no-embargo-to-unbound.md) — partially superseded by docs/adr/0122-per-embargo-participant-consent.md
- [ADR-0092 Lint Fragments as Source, and Evaluate Page-Scoped Style Rules on the Rendered Page](0092-lint-fragments-as-source-page-rules-on-rendered-page.md)
- [ADR-0093 `DECLINE` Is Legal from `SIGNATORY` — Consent Withdrawal Is a First-Class PEC Action](0093-signatory-declined-pec-transition.md) — partially superseded by docs/adr/0122-per-embargo-participant-consent.md
- [ADR-0094 Replace flake8, isort and black with ruff, and declare lint exclusions instead of discovering them](0094-ruff-replaces-flake8-isort-black.md)
- [ADR-0095 Received-Side `HandlerResult` Carries a Handler Disposition Across the Dispatcher Boundary](0095-received-side-handler-result.md)
- [ADR-0096 A Protocol Default Embargo Replaces the Pre-Case Phase](0096-protocol-default-embargo.md) *(revision 2)*
- [ADR-0097 The Capability Layer: Four Call-Out Shapes, Core-Declared Typed-Port Contracts, and Sentinel as a Call-In Pattern](0097-capability-layer-four-shapes-and-core-declared-contracts.md)
- [ADR-0098 Demo scenarios self-register at import time; every scenario table and the CI matrix become derived artifacts](0098-demo-scenarios-self-register.md)
- [ADR-0099 One Object Model: AS2 Is a Serialization of the Core Model, Not a Parallel Hierarchy](0099-one-object-model-as2-is-a-serialization.md)
- [ADR-0100 There Is No Multi-Candidate Embargo Poll; Open Proposals Resolve in Earliest-Expiration Order](0100-no-multi-candidate-embargo-poll.md)
- [ADR-0101 Spec Item Format Is Field Presence, Not a Class Choice; a Bare Item Cannot Be a `BehavioralSpec`](0101-spec-item-format-is-field-presence.md)
- [ADR-0102 Organize reader-facing documentation by stakeholder type and invisible prerequisite level](0102-docs-stakeholder-types-and-invisible-prerequisite-levels.md) *(provisional)*
- [ADR-0103 An Object's Time Is Carried, Never Minted by the Receiver](0103-object-time-is-carried-never-minted.md)
- [ADR-0104 The Interactive Demo UI Is a React/ReactFlow Operator-Side Ledger Watcher, Fed by a Prototype-Only SSE Stream](0104-interactive-demo-ui-live-ledger-watcher.md)
- [ADR-0106 Version Each Machine-Facing Interface Independently of the Release Tag](0106-versioning-machine-facing-interfaces.md) *(provisional)*
- [ADR-0108 One Move, One Mover: Case State Flows Through the Case Manager and the Ledger, Whatever Message Carried It](0108-one-move-one-mover-case-state-flows-through-the-case-manager-and-the-ledger.md)
- [ADR-0109 A Container Emits Only as Actors It Hosts; a Participant Asks the CaseActor to Act](0109-a-container-emits-only-as-actors-it-hosts.md)
- [ADR-0110 The Trigger Driving Port Is One `trigger()` Method over a Verb Registry, Returning a Typed Result Bound to the Request](0110-trigger-dispatcher-port-over-verb-registry.md)
- [ADR-0111 Intake Is the First Stage of a Received-Side Tree: Record What Arrived Before Judging It](0111-intake-is-the-first-received-side-stage.md)
- [ADR-0112 Per-Recipient Ordered Outbox Delivery: One Drain per Actor, One In-Flight Row per Recipient](0112-per-recipient-ordered-outbox-delivery.md)
- [ADR-0113 Embargo Negotiation Relays Through the CASE_MANAGER; the Ledger Carries State but Never Asks](0113-embargo-revision-negotiation-relays-through-the-case-manager.md)
- [ADR-0114 Joining a Case: The Invite Creates an Inert Participant, the Stub Is Its Own Type, and RM Closes from *Received*](0114-joining-a-case-stub-invite-inert-participant.md)
- [ADR-0117 The Per-Case Genesis Hash Is Anchored to the Case Owner, Not the CaseActor](0117-genesis-hash-is-anchored-to-the-case-owner.md)
- [ADR-0118 An Expired Invite Is Not a Decline, and a Terminated Embargo Is Not the Start State](0118-pec-expired-and-unbound-exited-states.md) — partially superseded by docs/adr/0122-per-embargo-participant-consent.md
- [ADR-0120 ADR Lifecycle: Three Epochs and Tiered Edits](0120-adr-lifecycle-epochs-and-edit-tiers.md) *(provisional)*
- [ADR-0121 A Joined Participant Judges the Case by Answering a Full-Case Invite; Status Is Self-Declared and Asserted Only for Existing Participants](0121-joined-participant-judges-the-case-by-full-case-invite.md) *(provisional)*
- [ADR-0123 An Embargo Invite May Name Its Terms by URI](0123-embargo-invite-may-name-its-terms-by-uri.md) *(provisional)*

## Proposed ADRs

- [ADR-0020 Move Inbox Orchestration into a Core BT Module with a Typed `process_payload` Seam](0020-inbox-bt-orchestration.md)
- [ADR-0105 Two Cases for One Vulnerability Merge by Owner Consent: the Offered Case Freezes and Redirects](0105-case-merge-freeze-and-redirect-by-owner-consent.md)
- [ADR-0107 A Case Ledger Entry Is a Postmark on the Received Envelope; References Resolve by Dereference](0107-case-ledger-entry-is-a-postmark-on-the-received-envelope.md)
- [ADR-0115 Received Handlers Check the Sender's Entitlement, Declared Once per Use Case and Composed by the Receive-Tree Factory](0115-received-handlers-check-sender-entitlement.md)
- [ADR-0116 Removing a Participant Withdraws Entitlement, Not Membership](0116-removing-a-participant-withdraws-entitlement-not-membership.md)
- [ADR-0119 The Case Ledger Records Completed Acts](0119-case-ledger-records-completed-acts.md)
- [ADR-0122 Participant Embargo Consent Is Recorded per (Participant, Embargo), Against an Embargo Register on the Case](0122-per-embargo-participant-consent.md) *(revision 3)*
- [ADR-0124 The Case Is a Projection of Its Ledger: One Replay Function for the CASE_MANAGER and Every Replica](0124-case-is-a-projection-of-its-ledger.md)
- [ADR-0125 A Case Splits by Its Owner Proposing a Child Case: the Child Links Its Parent and Inherits the Embargo Terms Only](0125-case-split-child-case-inherits-the-embargo-only.md)
- [ADR-0126 CI Is the Full-Suite Authority After a Pull Request's First Push](0126-ci-is-the-full-suite-authority-after-the-first-push.md)
- [ADR-0128 Message Vocabulary Docs Are Projections of the Semantic Registry](0128-message-vocabulary-docs-are-projections-of-the-semantic-registry.md)

## Rejected ADRs

- none

## Superseded / Archived ADRs

Retired ADRs (`status: deprecated` or `superseded`) are moved to
[`docs/adr/archived/`](archived/README.md) so they stay out of the default `docs/adr/` context sweep.
Each is listed here with a forward link to its replacement.

- [ADR-0015 Create VulnerabilityCase at Report Receipt (RM.RECEIVED)](archived/0015-create-case-at-report-receipt.md) — superseded by 0041-caseactor-authoritative-case-initialization.md
- [ADR-0017 Domain/Wire Object Separation: Shared-Base, Two-Branch Hierarchy](archived/0017-domain-wire-object-separation.md) — superseded by 0099-one-object-model-as2-is-a-serialization.md
- [ADR-0056 `embargo_adherence` Is a Computed Property Derived from PEC State](archived/0056-embargo-adherence-computed-field.md) — superseded by 0122-per-embargo-participant-consent.md
- [ADR-0062 Normalise Wire → Core at Ingress, and Enforce It Again at the Persistence Boundary](archived/0062-normalise-wire-to-core-at-both-ingress-and-persistence.md) — superseded by 0082-wire-core-boundary-pairing-registry.md
- [ADR-0070 Reuse `validate-report` for Invited Actors; Derive `VultronOfferRecord` from Ledger Backfill](archived/0070-invited-actor-rm-triage-via-ledger-backfill.md) — superseded by 0121-joined-participant-judges-the-case-by-full-case-invite.md
- [ADR-0082 Wire/Core Boundary: One Declarative Pairing Registry, One Translator, and Reject Unknown Keys](archived/0082-wire-core-boundary-pairing-registry.md) — superseded by 0099-one-object-model-as2-is-a-serialization.md
- [ADR-0084 Participant Status Is Self-Declaratory, With Narrow Externally-Evidenced On-Behalf Exceptions](archived/0084-participant-assertion-authority.md) — superseded by 0121-joined-participant-judges-the-case-by-full-case-invite.md
