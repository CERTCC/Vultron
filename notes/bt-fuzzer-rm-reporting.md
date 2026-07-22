---
title: "BT Fuzzer Nodes: RM Reporting to Other Parties"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for the Reporting to Other Parties
  sub-workflow (`ReportToOthersBt`): coordinator/finder notification,
  participant tracking, and outbound-report nodes used in simulation.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-fuzzer-nodes-report-management.md
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/bt-fuzzer-nodes.md
relevant_packages:
  - vultron/bt/report_management
---

## Reporting to Other Parties

These nodes belong to the `MaybeReportToOthers` sequence tree
(`vultron/bt/report_management/_behaviors/report_to_others.py`), which
models the process of identifying and notifying additional stakeholders
(vendors, coordinators, and other parties) who should be involved in the
coordinated disclosure.

### `HaveReportToOthersCapability`

- **Node name**: `HaveReportToOthersCapability`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether this participant has
  the capability and mandate to notify other parties
- **Input dependency**: Role/capability configuration; static metadata
  check on the participant's CVD role and organizational policy
- **Notes**: In production this is typically a static capability check,
  not a dynamic decision
- **Automation potential**: **High** — static capability and role configuration check; fully automatable as a metadata lookup.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.HaveReportToOthersCapability`
- **Call-out point shape**: TBD — role/eligibility check: "does this participant have the capability and mandate to notify other parties?" In the evolving architecture this may devolve to a `CVDRole.CASE_MANAGER` membership check (internal BT condition check, not a call-out point), or remain an Evaluator if notification-obligation reasoning beyond role membership is required. Revisit after the invite-participant-to-case protocol is finalized (see #1199, #1200).
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — top-level guard at the root of `MaybeReportToOthers`;
  exact shape (Evaluator vs. internal condition check) depends on
  invite-participant-to-case protocol design (#1199, #1200)

### `AllPartiesKnown`

- **Node name**: `AllPartiesKnown`
- **btz type**: `UniformSucceedFail` (p=0.50)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether all relevant parties
  that should receive notification have been identified
- **Input dependency**: Human analyst assessment; completion check on the
  party identification workflow
- **Notes**: Modeled as a coin flip in simulation because identification
  completeness is inherently uncertain
- **Automation potential**: **Low** — inherently requires human expert judgment about stakeholder completeness in a specific vulnerability context; hard to automate reliably.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.AllPartiesKnown`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.report_to_others_tree.create_report_to_others_tree`
  (`all_parties_known_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator Sentinel after `HaveReportToOthersCapability`;
  exits the outer party-identification loop once all parties are known

### `IdentifyVendors`

- **Node name**: `IdentifyVendors`
- **btz type**: `SuccessOrRunning` (p=0.50; never fails)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — identify the software vendors responsible
  for the affected product(s) so they can be notified
- **Input dependency**: Human analyst research; product/vendor databases
  (CPE, NVD product data, SBOM, asset inventory), supply chain data, or
  OSINT
- **Notes**: Uses `SuccessOrRunning` to model that vendor identification
  may be an ongoing (multi-tick) process; never hard-fails
- **Automation potential**: **Medium** — CPE/product database lookups, SBOM analysis, and NVD product data queries are automatable for known products; novel, multi-vendor, or open-source supply-chain cases benefit from human review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.IdentifyVendors`
- **Call-out point shape**: Retriever
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Retriever node in the party-identification Sequence;
  populates the vendor portion of the identified-parties queue using
  CPE/product database lookups, SBOM analysis, and NVD product data

### `IdentifyCoordinators`

- **Node name**: `IdentifyCoordinators`
- **btz type**: `SuccessOrRunning` (p=0.50; never fails)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — identify any coordinator organizations
  (e.g., CERT/CC, national CSIRTs) that should be involved in the
  disclosure
- **Input dependency**: Human analyst judgment; coordinator registry or
  directory (e.g., FIRST member directory, national CSIRT listings),
  or organizational policy on when to involve coordinators
- **Notes**: Uses `SuccessOrRunning` to model an ongoing identification
  process; never hard-fails
- **Automation potential**: **Medium** — FIRST member directory and national CSIRT registry lookups are automatable; routing policy (when to involve a coordinator) may require human judgment.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.IdentifyCoordinators`
- **Call-out point shape**: Retriever
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Retriever node in the party-identification Sequence;
  populates the coordinator portion of the identified-parties queue using
  FIRST member directory and national CSIRT registry lookups

### `IdentifyOthers`

- **Node name**: `IdentifyOthers`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — identify any other parties (beyond vendors
  and coordinators) that should be notified
- **Input dependency**: Human analyst judgment; case-specific stakeholder
  analysis
- **Notes**: Always succeeds in simulation (stub placeholder)
- **Automation potential**: **Low** — by definition a catch-all for non-vendor, non-coordinator parties; requires human expert assessment of the specific disclosure context.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.IdentifyOthers`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator node in the party-identification Sequence;
  catch-all for non-vendor, non-coordinator stakeholders requiring
  case-specific human expert assessment

### `NotificationsComplete`

- **Node name**: `NotificationsComplete`
- **btz type**: `UniformSucceedFail` (p=0.50)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether all identified parties
  have been successfully notified
- **Input dependency**: Notification tracking metadata; outbound message
  status records for each identified recipient
- **Notes**: Modeled as a coin flip; in production this is a status check
  against a notification queue
- **Automation potential**: **High** — notification status tracking against the identified-parties queue; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.NotificationsComplete`
- **Call-out point shape**: ProtocolInternal — reads notification-completion flags maintained in the
  local DataLayer / BT blackboard by the protocol's own `SetRcptQrmR` Actuator nodes (per-actor
  in-process). No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal condition check at the top of the per-recipient
  notification loop; exits the loop once the full notification queue
  is drained

### `ChooseRecipient`

- **Node name**: `ChooseRecipient`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — select the next recipient from the
  identified-parties list for notification
- **Input dependency**: Automated queue selection; priority ordering of
  the identified parties list
- **Notes**: Could be fully automated; always succeeds in simulation
- **Automation potential**: **High** — deterministic queue selection from the identified-parties list; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.ChooseRecipient`
- **Call-out point shape**: Retriever — reads the next recipient entry from the identified-parties queue according to the priority ordering and writes the selected recipient details to the blackboard for downstream nodes (FindContact, SetRcptQrmR, etc.); SUCCESS = next recipient selected and written.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Retriever node at the top of the per-recipient loop
  body; pops the next candidate from the queue and writes it to the
  blackboard

### `RemoveRecipient`

- **Node name**: `RemoveRecipient`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — remove a recipient from the pending
  notification queue (after successful notification or after effort
  limits are exceeded)
- **Input dependency**: Notification queue management; could be automated
- **Notes**: Always succeeds in simulation
- **Automation potential**: **High** — queue management operation; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.RemoveRecipient`
- **Call-out point shape**: Actuator — writes a queue-removal state change to the case management system, dequeuing the current recipient; the side effect in the external system is the seam, not a content artifact placed on the blackboard.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Actuator node appended at the end of the per-recipient
  notification Sequence (after `SetRcptQrmR`); removes the processed
  recipient from the pending queue

### `RecipientEffortExceeded`

- **Node name**: `RecipientEffortExceeded`
- **btz type**: `AlmostCertainlyFail` (p=0.07)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether the effort spent trying
  to notify a specific recipient has exceeded an organizational threshold
  (e.g., 3 contact attempts, 1 hour of effort)
- **Input dependency**: Effort tracking metadata per recipient; configurable
  policy threshold; may require human analyst judgment
- **Notes**: Rarely triggers in simulation; in production enforces
  reasonable limits on notification attempts
- **Automation potential**: **High** — effort counter check against a configurable policy threshold; fully automatable once the threshold policy is defined.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.RecipientEffortExceeded`
- **Call-out point shape**: Evaluator — evaluates whether the notification-attempt budget for this recipient has been exhausted by comparing the per-recipient attempt counter against a configurable policy threshold; a process-gate judgment about whether continued effort is warranted.
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.report_to_others_tree.create_report_to_others_tree`
  (`recipient_effort_exceeded_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator guard in the per-recipient effort-limit
  Sequence; triggers `RemoveRecipient` when the per-recipient attempt
  budget is exhausted

### `TotalEffortLimitMet`

- **Node name**: `TotalEffortLimitMet`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether the total effort across
  all notification attempts has exceeded an organizational ceiling
- **Input dependency**: Aggregate effort tracking; configurable policy
  threshold; may require human analyst review
- **Notes**: Rarely triggers in simulation; provides a global stop
  condition to prevent unbounded notification effort
- **Automation potential**: **High** — aggregate effort counter check against a configurable policy ceiling; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.TotalEffortLimitMet`
- **Call-out point shape**: Evaluator — evaluates whether the global notification budget has been exhausted by comparing the total effort counter against a configurable policy ceiling; a process-gate judgment about whether any further notification attempts are warranted across all recipients.
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.report_to_others_tree.create_report_to_others_tree`
  (`total_effort_limit_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator guard checked at the outer loop level;
  terminates all further notification attempts when the global effort
  ceiling is reached

### `PolicyCompatible`

- **Node name**: `PolicyCompatible`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether the potential recipient's
  disclosure/embargo policy is compatible with the case's current embargo
  expectations before notifying them
- **Input dependency**: Policy comparison between recipient's published
  CVD policy and the case embargo terms; could be automated via a
  policy registry, or require human analyst judgment
- **Notes**: In production may involve structured policy comparison tooling
- **Automation potential**: **Medium** — comparison between the recipient's published CVD policy and the case embargo terms is automatable for machine-readable policies (e.g., OpenVEX, structured security.txt); human review needed for ambiguous or informal policies.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.PolicyCompatible`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.report_to_others_tree.create_report_to_others_tree`
  (`policy_compatible_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Evaluator precondition guard before `FindContact` and
  `RcptNotInQrmS`; gates notification on policy compatibility check
  against the recipient's published CVD/embargo policy

### `FindContact`

- **Node name**: `FindContact`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — look up contact information for the
  chosen recipient (security email, bug bounty platform, disclosure portal)
- **Input dependency**: Contact directory lookup (e.g., security.txt,
  vendor security contacts, FIRST member database, PSIRT directory);
  could be automated for well-known organizations
- **Notes**: Succeeds most of the time; may fail for lesser-known vendors
  with no published security contact
- **Automation potential**: **High** — security.txt lookup, PSIRT directory queries, FIRST member database, and NVD contact data are all automatable for well-known organizations; obscure vendors may require manual research.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.FindContact`
- **Call-out point shape**: Retriever
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — Retriever node after `PolicyCompatible`; resolves contact
  details for the current recipient and writes them to the blackboard
  for downstream use by `SetRcptQrmR` and outbound message nodes

### `RcptNotInQrmS`

- **Node name**: `RcptNotInQrmS`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — verify that the recipient has not
  already been notified (i.e., their RM state is still START / not yet
  RECEIVED)
- **Input dependency**: Case state lookup; RM state record for the
  recipient participant; automatable
- **Notes**: Succeeds almost always; guards against duplicate notifications
- **Automation potential**: **High** — RM state query against the case participant record; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.RcptNotInQrmS`
- **Call-out point shape**: ProtocolInternal — reads a per-recipient RM-state flag maintained in the
  local DataLayer / BT blackboard; the flag is written by `SetRcptQrmR` (protocol-internal Actuator)
  after each notification. No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal idempotency check after `FindContact`; skips
  re-notification if the recipient's RM state is already past START

### `SetRcptQrmR`

- **Node name**: `SetRcptQrmR`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — record that the recipient has been
  notified by transitioning their RM state from START to RECEIVED
- **Input dependency**: State write to case management system; automatable
  state transition
- **Notes**: Always succeeds in simulation; in production performs
  a state update
- **Automation potential**: **High** — RM state write on the case participant record; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.SetRcptQrmR`
- **Call-out point shape**: Actuator — writes a recipient RM-state transition (START → RECEIVED) to the case management system; the side-effect state write is the seam, not a content artifact placed on the blackboard.
- **Factory-fn placement**: `vultron.core.behaviors.report.create_report_to_others_tree`
  (collapsed in #1311) — eliminated from the production tree; RM-state
  transition to RECEIVED is handled by the `AcceptInviteToCase` cascade
  triggered by `suggest-actor-to-case` (Production Collapse 3, ADR-0029).

### `MoreVendors`

- **Node name**: `MoreVendors`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — return SUCCESS iff the
  `identified_vendors` blackboard list is non-empty; falls back to
  probabilistic behaviour (`UsuallyFail`, p=0.25) when the key is absent
  or the list is empty.  Drives exhaustion-based loop iteration.
- **Blackboard contract**: Input keys: `identified_vendors: list`
  (READ; key may be absent). Output keys: none.
  Implemented via `setup()`/`update()` overrides that call
  `attach_blackboard_client()` with `Access.READ`.
- **Input dependency**: Query to the `identified_vendors` blackboard key;
  written by `IdentifyVendors` upstream.
- **Notes**: Returns SUCCESS deterministically when `identified_vendors`
  is non-empty; falls back to `UsuallyFail` (25%) when absent or empty.
- **Automation potential**: **High** — queue-emptiness check; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.MoreVendors`
- **Call-out point shape**: ProtocolInternal — checks the local `identified_vendors`
  blackboard list (BT blackboard, per-actor in-process); this is a BT for-loop
  iteration guard, not an external query. No external agent seam — the list is
  local and actor-scoped.
  (Category 3 per issue #1199 triage — reads from the protocol's own BT blackboard.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal iteration guard at the head of the vendor sub-loop;
  drives the vendor-notification iteration until the vendor queue is empty

### `MoreCoordinators`

- **Node name**: `MoreCoordinators`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — return SUCCESS iff the
  `identified_coordinators` blackboard list is non-empty; falls back to
  probabilistic behaviour (`AlmostAlwaysFail`, p=0.10) when the key is
  absent or the list is empty.  Mirrors `MoreVendors` for the coordinator
  sub-list.
- **Blackboard contract**: Input keys: `identified_coordinators: list`
  (READ; key may be absent). Output keys: none.
  Implemented via `setup()`/`update()` overrides that call
  `attach_blackboard_client()` with `Access.READ`.
- **Input dependency**: Query to the `identified_coordinators` blackboard
  key; written by `IdentifyCoordinators` upstream.
- **Notes**: Returns SUCCESS deterministically when
  `identified_coordinators` is non-empty; falls back to `AlmostAlwaysFail`
  (10%) when absent or empty.
- **Automation potential**: **High** — queue-emptiness check; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.MoreCoordinators`
- **Call-out point shape**: ProtocolInternal — checks the local `identified_coordinators`
  blackboard list (BT blackboard, per-actor in-process); this is a BT for-loop iteration guard,
  not an external query. No external agent seam — the list is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads from the protocol's own BT blackboard.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal iteration guard at the head of the coordinator sub-loop;
  drives coordinator-notification iteration until the coordinator queue is
  empty

### `MoreOthers`

- **Node name**: `MoreOthers`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Condition — check whether there are more "other"
  parties pending notification
- **Input dependency**: Query to the other-parties notification queue;
  automatable
- **Notes**: Fails almost always; catch-all category is usually empty
- **Automation potential**: **High** — query against the other-parties notification queue; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.MoreOthers`
- **Call-out point shape**: ProtocolInternal — checks the local `bb.case.potential_participants`
  other-parties sub-list (BT blackboard, per-actor in-process); this is a BT for-loop iteration guard,
  not an external query. No external agent seam — the list is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads from the protocol's own BT blackboard.)
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_report_to_others_tree`
  (issue #1252) — ProtocolInternal iteration guard at the head of the other-parties sub-loop;
  drives other-party notification iteration until the other-parties queue
  is empty

### `InjectParticipant`

- **Node name**: `InjectParticipant`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — add a new participant to the case (generic
  form; specialized by `InjectVendor`, `InjectCoordinator`, `InjectOther`)
- **Input dependency**: Case management system write; triggered after a
  recipient is successfully notified and agrees to participate
- **Notes**: Always succeeds in simulation; base class for the three
  role-specific inject nodes below. In production, these simulator leaf nodes
  would be replaced by subtrees that invoke the InviteParticipantToCase
  protocol; the call-out point lives at the boundary with that protocol, not
  at this leaf.
- **Automation potential**: **High** — case management system write; fully automatable once participant details are known.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectParticipant`
- **Call-out point shape**: Actuator — writes a new participant record to the case management system; the side-effect state write is the seam. Production replacement: InviteParticipantToCase protocol subtree (not yet implemented).
- **Factory-fn placement**: `vultron.core.behaviors.report.create_report_to_others_tree`
  (implemented in #1311) — collapsed; the base `InjectParticipant` family is
  replaced by `WriteRolesNode` + `suggest_*_factory` in each typed sub-loop.
  Role-specific sub-classes (`InjectVendor`, `InjectCoordinator`, `InjectOther`)
  serve as the default fuzzer backends for their respective `suggest_*_factory`
  parameters (Production Collapse 3, ADR-0029).

### `InjectVendor`

- **Node name**: `InjectVendor`
- **btz type**: `InjectParticipant` (AlwaysSucceed, p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — pop the first entry from the
  `identified_vendors` blackboard list and append it to
  `potential_participants`.  When the list is absent or empty, succeeds
  as a no-op.  Specialization of `InjectParticipant` via `source_key =
  "identified_vendors"`.
- **Blackboard contract**: Input keys: `identified_vendors: list`
  (READ/WRITE; key may be absent). Output keys: `potential_participants:
  list` (WRITE; key may be absent).
  Implemented through the shared `InjectParticipant.setup()`/`update()`
  logic keyed by `source_key`; uses `attach_blackboard_client()` with
  `Access.WRITE`.
- **Input dependency**: Reads `identified_vendors` written by
  `IdentifyVendors`; writes to `potential_participants`.
- **Notes**: Specialization of `InjectParticipant` for vendor role. See
  `InjectParticipant` for production-replacement note.
- **Automation potential**: **High** — case management system write for vendor role; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectVendor`
- **Call-out point shape**: Actuator — pops from `identified_vendors` and appends to
  `potential_participants`; the side-effect state write is the seam. Production
  replacement: InviteParticipantToCase protocol subtree.
- **Factory-fn placement**: `vultron.core.behaviors.report.create_report_to_others_tree`
  (implemented in #1311) — default fuzzer backend for `suggest_vendor_factory`
  parameter; the production trigger replaces it with `suggest-actor-to-case`
  with `CVDRole.VENDOR` (Production Collapse 3, ADR-0029).

### `InjectCoordinator`

- **Node name**: `InjectCoordinator`
- **btz type**: `InjectParticipant` (AlwaysSucceed, p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — pop the first entry from the
  `identified_coordinators` blackboard list and append it to
  `potential_participants`.  When the list is absent or empty, succeeds
  as a no-op.  Specialization of `InjectParticipant` via `source_key =
  "identified_coordinators"`.
- **Blackboard contract**: Input keys: `identified_coordinators: list`
  (READ/WRITE; key may be absent). Output keys: `potential_participants:
  list` (WRITE; key may be absent).
  Implemented through the shared `InjectParticipant.setup()`/`update()`
  logic keyed by `source_key`; uses `attach_blackboard_client()` with
  `Access.WRITE`.
- **Input dependency**: Reads `identified_coordinators` written by
  `IdentifyCoordinators`; writes to `potential_participants`.
- **Notes**: Specialization of `InjectParticipant` for coordinator role. See
  `InjectParticipant` for production-replacement note.
- **Automation potential**: **High** — case management system write for coordinator role; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectCoordinator`
- **Call-out point shape**: Actuator — pops from `identified_coordinators` and appends to
  `potential_participants`; the side-effect state write is the seam. Production
  replacement: InviteParticipantToCase protocol subtree.
- **Factory-fn placement**: `vultron.core.behaviors.report.create_report_to_others_tree`
  (implemented in #1311) — default fuzzer backend for `suggest_coordinator_factory`
  parameter; the production trigger replaces it with `suggest-actor-to-case`
  with `CVDRole.COORDINATOR` (Production Collapse 3, ADR-0029).

### `InjectOther`

- **Node name**: `InjectOther`
- **btz type**: `InjectParticipant` (AlwaysSucceed, p=1.00)
- **Source file**: `report_management/fuzzer/report_to_others.py`
- **Parent tree**: `MaybeReportToOthers`
- **Semantic function**: Action — add any other identified party as a
  participant in the coordinated disclosure case
- **Input dependency**: Case management system write; stakeholder contact
  and acceptance of participation
- **Notes**: Specialization of `InjectParticipant` for other-party role. See
  `InjectParticipant` for production-replacement note.
- **Automation potential**: **High** — case management system write for other-party role; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.report_to_others.InjectOther`
- **Call-out point shape**: Actuator — inherits InjectParticipant; writes an other-party participant record to the case management system; the side-effect state write is the seam. Production replacement: InviteParticipantToCase protocol subtree.
- **Factory-fn placement**: `vultron.core.behaviors.report.create_report_to_others_tree`
  (implemented in #1311) — default fuzzer backend for `suggest_other_factory`
  parameter; the production trigger replaces it with `suggest-actor-to-case`
  with `CVDRole.OTHER` (Production Collapse 3, ADR-0029).

---
