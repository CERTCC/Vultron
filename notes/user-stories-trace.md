# User Story Traceability Matrix

This document maps user stories from `docs/topics/user_stories/` to formal
requirements in `specs/`. It is a **traceability reference**, not a
requirements document. User stories capture stakeholder intent; the
requirements in `specs/` specify system behaviour.

Stories are grouped by theme. Each story entry lists the mapped spec
requirements with a brief traceability note. Stories with no clear mapping
to an existing requirement are marked *No mapped requirements*.

Source user stories: `docs/topics/user_stories/story_2022_NNN.md`
Source specifications: `specs/*.md`

---

## Table of Contents

| Section | Line | Stories | Theme |
|---------|------|---------|-------|
| [1. Vulnerability Reporting](#1-vulnerability-reporting) | ~17 | 001–020 | Report submission, reception, validation, tracking |
| [2. Policy Discovery and Management](#2-policy-discovery-and-management) | ~109 | 021–030 | Disclosure policies, policy publication and lookup |
| [3. Embargo Management](#3-embargo-management) | ~215 | 031–050 | Embargo proposals, negotiation, termination |
| [4. Case Management and Participant Roles](#4-case-management-and-participant-roles) | ~323 | 051–080 | Case creation, participants, coordinators, roles |
| [5. Actor Identity, Privacy, and Security](#5-actor-identity-privacy-and-security) | ~570 | 081–090 | Actor registration, identity, privacy constraints |
| [6. Communication and Messaging](#6-communication-and-messaging) | ~686 | 091–100 | Inbox/outbox, notifications, acknowledgements |
| [7. Publication and Disclosure](#7-publication-and-disclosure) | ~837 | 101–106 | Coordinated publication, advisories, disclosure timing |
| [8. Bug Bounty and Incentives](#8-bug-bounty-and-incentives) | ~991 | 107–109 | Bug bounty programs and incentives |
| [9. Prioritization, Assessment, and Fix Verification](#9-prioritization-assessment-and-fix-verification) | ~1022 | 110–111 | SSVC scoring, fix readiness |

---

## 1. Vulnerability Reporting

- **story_2022_001** — "As a Finder, discover how to report a vulnerability"
  - *Mapped requirements:*
    - **VP-02-001** (`vultron-protocol-spec.md`): Coordinators MUST have a
      clearly defined and publicly available policy — intake discovery.
    - **VP-02-005** (`vultron-protocol-spec.md`): Vendors SHOULD have a
      clearly defined and publicly available policy — intake discovery.
    - **IE-02-001** (`inbox-endpoint.md`): The endpoint URL MUST be
      discoverable from actor profile — system support for finding intake.
    - **EP-01-001** (`embargo-policy.md`): An Actor profile MAY include an
      `embargo_policy` field — policy discovery mechanism.

- **story_2022_002** — "As a Participant, receive reports submitted via platform"
  - *Mapped requirements:*
    - **VP-03-001** (`vultron-protocol-spec.md`): Participants MUST be in
      RM Accepted to send a Report Submission — pre-condition for receipt.
    - **VP-03-002** (`vultron-protocol-spec.md`): Vendor Recipients receiving a
      new Report Submission MUST process it — receiving obligation.
    - **IE-02-002** (`inbox-endpoint.md`): The endpoint MUST accept POST
      requests only — HTTP intake for report submission.
    - **HP-00-001** (`handler-protocol.md`): Handlers MUST interpret received
      activities as assertions about the sender's state — semantics of receipt.

- **story_2022_012** — "As a Participant, report a new vulnerability"
  - *Mapped requirements:*
    - **VP-02-015** (`vultron-protocol-spec.md`): Participants SHOULD create a
      case from reports entering the Valid state — report-to-case transition.
    - **VP-03-001** (`vultron-protocol-spec.md`): Participants MUST be in RM
      Accepted to send a Report Submission — submission precondition.
    - **MV-01-001** (`message-validation.md`): Incoming payloads MUST conform
      to ActivityStreams 2.0 structure — message format for report submission.
    - **IE-02-002** (`inbox-endpoint.md`): The endpoint MUST accept POST
      requests only — HTTP entry point for report.

- **story_2022_038** — "As a vendor or coordinator, receive vulnerability reports"
  - *Mapped requirements:*
    - **VP-03-002** (`vultron-protocol-spec.md`): Vendor Recipients receiving a
      new Report Submission MUST process it — receiving obligation.
    - **IE-02-002** (`inbox-endpoint.md`): The endpoint MUST accept POST
      requests only — HTTP intake.
    - **MV-01-001** (`message-validation.md`): Incoming payloads MUST conform
      to ActivityStreams 2.0 structure — validation on receipt.
    - **VP-02-001** (`vultron-protocol-spec.md`): Coordinators MUST have a
      clearly defined and publicly available policy — intake advertised.

- **story_2022_077** — "As a Participant, ask further questions about a report"
  - *Mapped requirements:*
    - **VP-02-025** (`vultron-protocol-spec.md`): Participants MAY perform a
      more technical report validation process — allows follow-up inquiry.
    - **VP-03-008** (`vultron-protocol-spec.md`): Participants SHOULD send RE
      regardless of state when any error occurs — error/inquiry path.
    - **VP-03-011** (`vultron-protocol-spec.md`): Recipients SHOULD acknowledge
      RE messages and inquire about the error — bidirectional inquiry.

- **story_2022_101** — "As a Coordinator, validate the report before engaging"
  - *Mapped requirements:*
    - **VP-02-006** (`vultron-protocol-spec.md`): Participants SHOULD subject
      each Received report to a validation process — validation obligation.
    - **VP-02-007** (`vultron-protocol-spec.md`): Participants SHOULD have a
      clearly defined process for validating reports — process definition.
    - **VP-02-009** (`vultron-protocol-spec.md`): Participants SHOULD proceed
      only after validating the reports they receive — gating.
    - **VP-02-025** (`vultron-protocol-spec.md`): Participants MAY perform a
      more technical report validation process — technical validation.
    - **VP-03-003** (`vultron-protocol-spec.md`): Participants SHOULD send RI
      when the report validation process determines invalid — send result.
    - **VP-03-004** (`vultron-protocol-spec.md`): Participants SHOULD send RV
      when the report validation process determines valid — send result.

- **story_2022_102** — "As a Coordinator, collect artifacts (PoC, analysis)"
  - *Mapped requirements:*
    - **VP-02-025** (`vultron-protocol-spec.md`): Participants MAY perform a
      more technical report validation process — artifact collection.
    - **VP-02-028** (`vultron-protocol-spec.md`): Participants MAY choose to
      perform a shallow technical analysis on the reported vulnerability.
    - **CM-05-002** (`case-management.md`): A VulnerabilityCase MUST reference
      at least one VulnerabilityReport — case ties to report artifacts.

- **story_2022_111** — "As a Vendor, identify which products are affected"
  - *Mapped requirements:*
    - **VP-02-011** (`vultron-protocol-spec.md`): Once a Vendor confirms that a
      reported vulnerability affects one or more products — acknowledgment.
    - **VP-02-015** (`vultron-protocol-spec.md`): Participants SHOULD create a
      case from reports entering the Valid state — per-product case creation.
    - **VP-02-025** (`vultron-protocol-spec.md`): Participants MAY perform more
      technical report validation — scope analysis.
    - **CM-05-006** (`case-management.md`): One report MAY describe multiple
      vulnerabilities; one case MAY cover multiple reports — model support.

---

## 2. Policy Discovery and Management

- **story_2022_003** — "As a Participant, discover others' policies"
  - *Mapped requirements:*
    - **VP-02-001** (`vultron-protocol-spec.md`): Coordinators MUST have a
      clearly defined and publicly available policy — policy discoverability.
    - **VP-02-005** (`vultron-protocol-spec.md`): Vendors SHOULD have a clearly
      defined and publicly available policy — policy discoverability.
    - **EP-01-001** (`embargo-policy.md`): An Actor profile MAY include an
      `embargo_policy` field — machine-readable policy on actor profile.
    - **EP-02-001** (`embargo-policy.md`): Each Actor SHOULD expose its embargo
      policy at a well-known endpoint (`PROD_ONLY`) — policy endpoint.

- **story_2022_004** — "As a Participant, parse and evaluate others' policies"
  - *Mapped requirements:*
    - **EP-01-002** (`embargo-policy.md`): The embargo policy record MUST
      include specified fields — machine-parseable structure.
    - **EP-01-003** (`embargo-policy.md`): The embargo policy record SHOULD
      include additional fields — richer parseable structure.
    - **EP-01-004** (`embargo-policy.md`): The embargo policy record MUST be
      serializable as a Pydantic model — programmatic parsing support.
    - **VP-07-001** (`vultron-protocol-spec.md`): If neither Sender nor
      Receiver proposes an embargo and no policy — default policy evaluation.

- **story_2022_005** — "As a Participant, optimize all of the policies involved"
  - *Mapped requirements:*
    - **VP-07-003** (`vultron-protocol-spec.md`): If the Receiver has declared
      a default embargo, use it — policy reconciliation.
    - **VP-07-004** (`vultron-protocol-spec.md`): If the Sender proposes an
      embargo longer than the Receiver's default — negotiation rule.
    - **VP-07-005** (`vultron-protocol-spec.md`): If the Sender proposes an
      embargo shorter than the Receiver's default — negotiation rule.
    - **EP-03-001** (`embargo-policy.md`): Before proposing an embargo,
      retrieve potential Participant's policy (`PROD_ONLY`) — pre-proposal.
    - **EP-03-002** (`embargo-policy.md`): Compatibility evaluation MUST check
      that policy fields are compatible (`PROD_ONLY`) — compatibility check.

- **story_2022_006** — "As a Participant, decide if I will/can engage"
  - *Mapped requirements:*
    - **VP-02-006** (`vultron-protocol-spec.md`): Participants SHOULD subject
      each Received report to a validation process — engagement gating.
    - **VP-02-014** (`vultron-protocol-spec.md`): For Valid reports, the
      Participant SHOULD perform a prioritization step — engagement decision.
    - **VP-02-016** (`vultron-protocol-spec.md`): Participants SHOULD have a
      bias toward accepting rather than deferring — acceptance policy.
    - **VP-02-021** (`vultron-protocol-spec.md`): Participants SHOULD act in
      accordance with their own policy and the policies of others.

- **story_2022_007** — "As a Participant, flag when policy trouble is detected"
  - *Mapped requirements:*
    - **VP-03-008** (`vultron-protocol-spec.md`): Participants SHOULD send RE
      regardless of state when any error occurs — error signal.
    - **VP-11-002** (`vultron-protocol-spec.md`): If information about the
      vulnerability has been made public, initiate embargo termination.
    - **VP-06-001** (`vultron-protocol-spec.md`): CVD Participants MUST NOT
      propose or accept a new embargo in specific states — constraint flag.

- **story_2022_008** — "As a Participant, warn Participants, invoke other channels"
  - *Mapped requirements:*
    - **VP-03-008** (`vultron-protocol-spec.md`): Participants SHOULD send RE
      when any error occurs — error notification.
    - **VP-11-003** (`vultron-protocol-spec.md`): Participants SHALL initiate
      embargo termination upon becoming aware of exploitation — escalation.
    - **VP-11-005** (`vultron-protocol-spec.md`): Participants SHOULD
      acknowledge and inquire about unexpected embargo state changes.

- **story_2022_009** — "As a Participant, post/advertise my policy"
  - *Mapped requirements:*
    - **VP-02-001** (`vultron-protocol-spec.md`): Coordinators MUST have a
      clearly defined and publicly available policy — publication obligation.
    - **VP-02-005** (`vultron-protocol-spec.md`): Vendors SHOULD have a clearly
      defined and publicly available policy — publication recommendation.
    - **VP-07-006** (`vultron-protocol-spec.md`): Report Recipients SHOULD post
      a default embargo period as part of their policy — embargo policy post.
    - **EP-01-001** (`embargo-policy.md`): An Actor profile MAY include an
      `embargo_policy` field — machine-readable policy on profile.
    - **EP-02-001** (`embargo-policy.md`): Each Actor SHOULD expose its embargo
      policy at a well-known endpoint (`PROD_ONLY`) — policy endpoint.

- **story_2022_021** — "As a Participant, advertise locale aspects of policy"
  - *Mapped requirements:*
    - **EP-01-002** (`embargo-policy.md`): The embargo policy record MUST
      include specified fields — locale/scope fields in policy.
    - **EP-01-003** (`embargo-policy.md`): The embargo policy record SHOULD
      include additional optional fields — extended locale fields.
    - **VP-02-001** (`vultron-protocol-spec.md`): Coordinators MUST have a
      clearly defined and publicly available policy — policy publication.

- **story_2022_022** — "As a Participant, advertise scope of CVD capability"
  - *Mapped requirements:*
    - **VP-02-001** (`vultron-protocol-spec.md`): Coordinators MUST have a
      clearly defined and publicly available policy — scope in policy.
    - **VP-02-005** (`vultron-protocol-spec.md`): Vendors SHOULD have a clearly
      defined and publicly available policy — scope in policy.
    - **EP-01-002** (`embargo-policy.md`): The embargo policy record MUST
      include required fields — structured scope definition.

- **story_2022_076** — "As a VDP operator, want protocol to support VDP"
  - *Mapped requirements:*
    - **VP-02-001** (`vultron-protocol-spec.md`): Coordinators MUST have a
      clearly defined and publicly available policy — VDP policy expression.
    - **EP-01-001** (`embargo-policy.md`): An Actor profile MAY include an
      `embargo_policy` field — policy field applicable to VDP operators.

---

## 3. Embargo Management

- **story_2022_010** — "As a Participant, publish/share embargo dates"
  - *Mapped requirements:*
    - **VP-04-003** (`vultron-protocol-spec.md`): An embargo MAY be proposed —
      initial proposal mechanism.
    - **VP-04-004** (`vultron-protocol-spec.md`): Once proposed, an embargo MAY
      be accepted or rejected — acceptance/rejection workflow.
    - **VP-05-001** (`vultron-protocol-spec.md`): An embargo SHALL specify an
      unambiguous date and time — date specification requirement.
    - **VP-07-006** (`vultron-protocol-spec.md`): Report Recipients SHOULD post
      a default embargo period as part of their policy — default sharing.
    - **EP-01-002** (`embargo-policy.md`): The embargo policy record MUST
      include specified fields — structured date fields.

- **story_2022_014** — "As a Participant, negotiate and renegotiate embargo schedules"
  - *Mapped requirements:*
    - **VP-04-001** (`vultron-protocol-spec.md`): Accepted embargoes MUST
      eventually terminate — termination requirement.
    - **VP-04-003** (`vultron-protocol-spec.md`): An embargo MAY be proposed —
      initial proposal.
    - **VP-04-005** (`vultron-protocol-spec.md`): Once accepted, revisions MAY
      be proposed — renegotiation mechanism.
    - **VP-06-004** (`vultron-protocol-spec.md`): Participants SHOULD explicitly
      accept or reject embargo proposals — explicit negotiation.
    - **VP-06-005** (`vultron-protocol-spec.md`): Participants SHOULD make
      reasonable attempts to retry embargo negotiations.

- **story_2022_023** — "As a Participant, constrain communication to enforce embargo"
  - *Mapped requirements:*
    - **VP-05-006** (`vultron-protocol-spec.md`): Embargo Participants SHOULD
      NOT knowingly release embargo information — information restriction.
    - **VP-05-007** (`vultron-protocol-spec.md`): Embargo participation SHOULD
      be limited to the smallest possible set — access restriction.
    - **VP-08-006** (`vultron-protocol-spec.md`): The inviting Participant
      SHOULD NOT share the vulnerability report without embargo — need-to-know.
    - **VP-16-001** (`vultron-protocol-spec.md`): Vulnerability details MUST
      NOT appear in embargo representation — separation of concerns.

- **story_2022_024** — "As a Finder/Reporter, constrain communication for anonymity"
  - *Mapped requirements:*
    - **VP-08-017** (`vultron-protocol-spec.md`): Participants in an MPCVD case
      MAY delay notifying potential Participants — controlled disclosure.
  - *No further mapped requirements* (reporter anonymity has no direct
    requirement in current specs).

- **story_2022_025** — "As a Vendor/Deployer, constrain until patch published"
  - *Mapped requirements:*
    - **VP-05-006** (`vultron-protocol-spec.md`): Embargo Participants SHOULD
      NOT knowingly release information — pre-patch restriction.
    - **VP-05-014** (`vultron-protocol-spec.md`): Participants SHOULD NOT
      publish information before embargo terminates.
    - **VP-14-007** (`vultron-protocol-spec.md`): Once Fix Ready, new embargoes
      have reduced scope — fix-ready transition.

- **story_2022_026** — "As a Coordinator, constrain communication within embargo"
  - *Mapped requirements:*
    - **VP-05-006** (`vultron-protocol-spec.md`): Embargo Participants SHOULD
      NOT knowingly release information — coordinator obligation.
    - **VP-08-006** (`vultron-protocol-spec.md`): The inviting Participant
      SHOULD NOT share the vulnerability report — need-to-know enforcement.
    - **VP-05-007** (`vultron-protocol-spec.md`): Embargo participation SHOULD
      be limited to the smallest possible set — minimal disclosure.

- **story_2022_027** — "As a Participant, address Participants constraints/entity lists"
  - *Mapped requirements:*
    - **VP-05-013** (`vultron-protocol-spec.md`): Participants SHOULD consider
      other Participants' history of embargo compliance — reputation check.
    - **VP-08-010** (`vultron-protocol-spec.md`): Participants known to leak
      information SHOULD be excluded from embargoes — exclusion mechanism.
    - **VP-08-021** (`vultron-protocol-spec.md`): Participants MAY decline to
      participate in future CVD cases with known leakers.

- **story_2022_078** — "As a coordinator, drive better/shorter embargo timelines"
  - *Mapped requirements:*
    - **VP-05-008** (`vultron-protocol-spec.md`): Embargo duration SHOULD be
      limited to the shortest duration feasible — coordinator goal.
    - **VP-05-009** (`vultron-protocol-spec.md`): Embargoes SHOULD be of short
      duration, from a few days to a few months — target range.
    - **VP-08-003** (`vultron-protocol-spec.md`): Participants SHOULD follow
      consensus agreement to decide embargo terms — coordinator drives.

- **story_2022_079** — "As a coordinator, collect and optimize embargo timelines"
  - *Mapped requirements:*
    - **VP-07-001** (`vultron-protocol-spec.md`): If no embargo policy and no
      proposal — default determination rule.
    - **VP-07-003** (`vultron-protocol-spec.md`): If Receiver has a default
      embargo, use it as the starting point.
    - **VP-07-004** (`vultron-protocol-spec.md`): If Sender proposes longer
      than Receiver's default — negotiation.
    - **VP-07-005** (`vultron-protocol-spec.md`): If Sender proposes shorter
      than Receiver's default — negotiation.
    - **VP-08-003** (`vultron-protocol-spec.md`): Participants SHOULD follow
      consensus agreement to decide embargo terms.

- **story_2022_080** — "As a Participant, disclose sooner but minimize others' risk"
  - *Mapped requirements:*
    - **VP-05-020** (`vultron-protocol-spec.md`): Participants MAY publish
      information when embargo terminates — publish timing.
    - **VP-14-011** (`vultron-protocol-spec.md`): Exploit Publishers who are
      Participants in pre-public CVD cases MUST notify others.
    - **VP-14-012** (`vultron-protocol-spec.md`): Exploit Publishers SHOULD NOT
      release exploit code while an embargo is active.
    - **VP-14-014** (`vultron-protocol-spec.md`): In MPCVD cases where some
      Vendors reach Fix Ready before others — staggered disclosure.

---

## 4. Case Management and Participant Roles

- **story_2022_013** — "As a Participant, add a Participant (de-duplicate)"
  - *Mapped requirements:*
    - **VP-08-001** (`vultron-protocol-spec.md`): When inviting a new
      Participant to a case with an existing embargo — invite protocol.
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors of affected
      software SHOULD be included — inclusion obligation.
    - **VP-08-013** (`vultron-protocol-spec.md`): Third-party Coordinators MAY
      be included as Participants — multi-party inclusion.
    - **ID-01-001** (`idempotency.md`): All activities MUST have globally
      unique `id` fields — de-duplication via unique IDs.

- **story_2022_029** — "As a Vendor/Deployer/Other, assign own ID to a case"
  - *Mapped requirements:*
    - **OID-01-001** (`object-ids.md`): All ActivityStreams object IDs MUST use
      full URI form — ID format requirement.
    - **OID-01-002** (`object-ids.md`): IDs MUST be globally unique within the
      system — uniqueness enforcement.
    - **OID-01-003** (`object-ids.md`): The canonical base URI for locally
      created objects MUST be configurable — local ID namespace.
    - **CM-02-001** (`case-management.md`): Each VulnerabilityCase MUST have
      exactly one associated CaseActor — case ownership and identity.

- **story_2022_030** — "As a Participant, discover and map to global/shared case ID"
  - *Mapped requirements:*
    - **OID-01-001** (`object-ids.md`): All ActivityStreams object IDs MUST use
      full URI form — global ID format.
    - **OID-01-002** (`object-ids.md`): IDs MUST be globally unique within the
      system — global uniqueness.
    - **VP-16-002** (`vultron-protocol-spec.md`): A case or vulnerability
      identifier SHOULD appear in embargo representation — case ID in embargo.
    - **VP-16-003** (`vultron-protocol-spec.md`): Case or vulnerability
      identifiers SHOULD NOT carry sensitive information — ID privacy.

- **story_2022_031** — "As a Participant, get list of cases I am involved in"
  - *Mapped requirements:*
    - **VP-01-001** (`vultron-protocol-spec.md`): Participants SHOULD track the
      state of other Participants in a case — state tracking.
    - **CM-02-001** (`case-management.md`): Each VulnerabilityCase MUST have
      exactly one associated CaseActor — case listing support.
    - **CM-07-001** (`case-management.md`): The system SHOULD expose an
      endpoint returning the set of valid next actions — case API.

- **story_2022_032** — "As a Participant, ask if another Participant is in a case"
  - *Mapped requirements:*
    - **VP-01-001** (`vultron-protocol-spec.md`): Participants SHOULD track the
      state of other Participants — participant tracking.
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors SHOULD be
      included — participation list.
    - **VP-08-009** (`vultron-protocol-spec.md`): Participants in a case SHOULD
      notify when a new Participant is added — membership events.

- **story_2022_033** — "As a Participant, request anonymity in a case"
  - *Mapped requirements:*
    - **VP-08-017** (`vultron-protocol-spec.md`): Participants in an MPCVD case
      MAY delay notifying potential Participants — controlled disclosure.
  - *No further mapped requirements* (anonymity policy has limited current
    spec coverage).

- **story_2022_045** — "As a Participant, produce a shared verified public record"
  - *Mapped requirements:*
    - **VP-16-002** (`vultron-protocol-spec.md`): A case or vulnerability
      identifier SHOULD appear in embargo representation — shared case ID.
    - **OID-01-001** (`object-ids.md`): All object IDs MUST use full URI form —
      stable record identifiers.
    - **SL-01-001** (`structured-logging.md`): All log entries MUST include
      `timestamp` field (`PROD_ONLY`) — auditable timeline.

- **story_2022_046** — "As a Participant, want the case to have a leader"
  - *Mapped requirements:*
    - **CM-02-004** (`case-management.md`): CaseActor MUST know the case owner —
      leadership/ownership model.
    - **VP-08-003** (`vultron-protocol-spec.md`): Participants SHOULD follow
      consensus agreement to decide embargo terms — leader-driven consensus.

- **story_2022_047** — "As a Participant, propose a case leader, possibly myself"
  - *Mapped requirements:*
    - **CM-02-004** (`case-management.md`): CaseActor MUST know the case owner —
      ownership field populated by leader proposal.
    - **VP-08-012** (`vultron-protocol-spec.md`): Participants MAY engage a
      third-party Coordinator to act as mediator — coordinator as leader.
    - **RF-02-001** (`response-format.md`): Accept responses MUST use `Accept`
      activity type — accepting a leader proposal uses Accept activity.

- **story_2022_048** — "As a Participant, vote/accept a proposed case leader"
  - *Mapped requirements:*
    - **RF-02-001** (`response-format.md`): Accept responses MUST use `Accept`
      activity type — acceptance mechanism.
    - **RF-03-001** (`response-format.md`): Reject responses MUST use `Reject`
      activity type — rejection mechanism.
    - **CM-02-005** (`case-management.md`): CaseActor MUST restrict certain
      activities to the case owner (`PROD_ONLY`) — ownership enforcement.

- **story_2022_049** — "As a Participant, announce the case leader to all Participants"
  - *Mapped requirements:*
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to other Participants — announcement mechanism.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      delivery mechanism for announcement.

- **story_2022_050** — "As a Participant, transfer case leadership to another"
  - *Mapped requirements:*
    - **CM-02-004** (`case-management.md`): CaseActor MUST know the case owner —
      ownership transfer.
    - **CM-02-005** (`case-management.md`): CaseActor MUST restrict certain
      activities to the case owner (`PROD_ONLY`) — ownership change restriction.
    - **RF-02-001** (`response-format.md`): Accept responses MUST use `Accept`
      activity type — new leader accepts the transfer.

- **story_2022_051** — "As a Participant, depose or step down as case leader"
  - *Mapped requirements:*
    - **CM-02-004** (`case-management.md`): CaseActor MUST know the case owner —
      leader identity tracked.
    - **VP-08-011** (`vultron-protocol-spec.md`): When consensus fails to reach
      agreement on embargo terms — fallback when no leader.
    - **RF-02-001** (`response-format.md`): Accept responses MUST use `Accept`
      activity type — replacement leader acceptance.

- **story_2022_052** — "As a Participant, add/notify others of new Participants"
  - *Mapped requirements:*
    - **VP-08-001** (`vultron-protocol-spec.md`): When inviting a new
      Participant to a case with an existing embargo — invitation protocol.
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors of affected
      software SHOULD be included — obligation to include.
    - **VP-08-005** (`vultron-protocol-spec.md`): A newly invited Participant
      SHOULD be informed about the existing embargo — notification duty.
    - **VP-08-009** (`vultron-protocol-spec.md`): Participants SHOULD notify
      when a new Participant is added to a case.

- **story_2022_053** — "As a Participant, propose new Participants to a case"
  - *Mapped requirements:*
    - **VP-08-001** (`vultron-protocol-spec.md`): When inviting a new
      Participant to a case with an existing embargo — invitation process.
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors SHOULD be
      included — who to propose.
    - **VP-08-012** (`vultron-protocol-spec.md`): Participants MAY engage a
      third-party Coordinator — coordinator as proposed participant.

- **story_2022_054** — "As a Participant, vote/accept new Participants to a case"
  - *Mapped requirements:*
    - **RF-02-001** (`response-format.md`): Accept responses MUST use `Accept`
      activity type — acceptance of invitation.
    - **RF-03-001** (`response-format.md`): Reject responses MUST use `Reject`
      activity type — rejection of invitation.
    - **VP-08-015** (`vultron-protocol-spec.md`): The inviting Participant MAY
      interpret a non-response as non-participation.

- **story_2022_063** — "As a Participant, include a non-vendor role Participant"
  - *Mapped requirements:*
    - **VP-08-014** (`vultron-protocol-spec.md`): Other parties MAY be included
      as Participants when necessary and appropriate — non-vendor inclusion.
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors of affected
      software SHOULD be included — vendor coverage before others.

- **story_2022_064** — "As a Participant, include the Government in the case"
  - *Mapped requirements:*
    - **VP-08-014** (`vultron-protocol-spec.md`): Other parties MAY be included
      as Participants when necessary and appropriate — government inclusion.

- **story_2022_065** — "As a Participant, include Industry/trade group in case"
  - *Mapped requirements:*
    - **VP-08-014** (`vultron-protocol-spec.md`): Other parties MAY be included
      as Participants when necessary and appropriate — industry group inclusion.

- **story_2022_066** — "As a Participant, stop participating in the case"
  - *Mapped requirements:*
    - **VP-05-010** (`vultron-protocol-spec.md`): Participants stopping work
      SHOULD notify remaining Participants.
    - **VP-05-011** (`vultron-protocol-spec.md`): Participants SHOULD continue
      to comply with any active embargoes even after stopping.
    - **VP-05-012** (`vultron-protocol-spec.md`): Participants who leave an
      Active embargo SHOULD be removed by the remaining Participants.

- **story_2022_067** — "As a Participant, stop participating and inform others"
  - *Mapped requirements:*
    - **VP-05-010** (`vultron-protocol-spec.md`): Participants stopping work
      SHOULD notify remaining Participants — notification obligation.
    - **VP-05-011** (`vultron-protocol-spec.md`): Participants SHOULD continue
      to comply with active embargoes — compliance after stopping.
    - **VP-13-009** (`vultron-protocol-spec.md`): A Participant's closure or
      deferral of a report has implications for the embargo state.

- **story_2022_068** — "As a Participant, stop and no longer receive forwarded queries"
  - *Mapped requirements:*
    - **VP-05-010** (`vultron-protocol-spec.md`): Participants stopping work
      SHOULD notify remaining Participants — departure notification.
    - **VP-05-012** (`vultron-protocol-spec.md`): Participants who leave SHOULD
      be removed from the active embargo — removal from distribution.

- **story_2022_074** — "As a Participant, keep track of events and timelines"
  - *Mapped requirements:*
    - **VP-01-001** (`vultron-protocol-spec.md`): Participants SHOULD track the
      state of other Participants — state tracking.
    - **VP-01-002** (`vultron-protocol-spec.md`): Participants SHOULD track the
      RM states of the other Participants — RM state tracking.
    - **VP-05-001** (`vultron-protocol-spec.md`): An embargo SHALL specify an
      unambiguous date and time — timeline anchor.
    - **SL-04-001** (`structured-logging.md`): Log entries MUST include
      structured state-transition format (`PROD_ONLY`) — event log for tracking.

- **story_2022_088** — "As a Participant, maintain knowledge of case state"
  - *Mapped requirements:*
    - **VP-01-001** (`vultron-protocol-spec.md`): Participants SHOULD track the
      state of other Participants — state awareness.
    - **VP-01-002** (`vultron-protocol-spec.md`): Participants SHOULD track the
      RM states of other Participants — RM awareness.
    - **CM-01-001** (`case-management.md`): Each actor MUST have an isolated
      protocol state domain — state isolation per actor.
    - **CM-01-002** (`case-management.md`): Each actor's RM state MUST be
      maintained independently per case — per-case state.
    - **CM-07-001** (`case-management.md`): The system SHOULD expose an
      endpoint returning valid next actions — state-aware API.

- **story_2022_104** — "As a Participant, address multiple vulnerabilities across vendors"
  - *Mapped requirements:*
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors of affected
      software SHOULD be included — multi-vendor inclusion.
    - **VP-10-004** (`vultron-protocol-spec.md`): A new embargo SHOULD be
      proposed when any two or more CVD cases are merged.
    - **VP-10-001** (`vultron-protocol-spec.md`): If no new embargo has been
      proposed after a case split — split/merge embargo handling.
    - **CM-05-006** (`case-management.md`): One report MAY describe multiple
      vulnerabilities; one case MAY cover multiple reports — data model.

- **story_2022_105** — "As a Vendor, address same vulnerability across products"
  - *Mapped requirements:*
    - **VP-10-004** (`vultron-protocol-spec.md`): A new embargo SHOULD be
      proposed when any two or more CVD cases are merged.
    - **VP-10-001** (`vultron-protocol-spec.md`): If no new embargo proposed
      after case split — per-product split embargo handling.
    - **VP-14-014** (`vultron-protocol-spec.md`): In MPCVD cases where some
      Vendors reach Fix Ready before others — staggered timelines.
    - **CM-05-006** (`case-management.md`): One report MAY describe multiple
      vulnerabilities; one case MAY cover multiple reports — multi-product.

- **story_2022_106** — "As a Participant, want decentralized coordination process"
  - *Mapped requirements:*
    - **VP-01-003** (`vultron-protocol-spec.md`): Adequate operation of the
      protocol MUST NOT depend on perfect knowledge of all Participants.
    - **VP-15-001** (`vultron-protocol-spec.md`): Vultron Protocol messages
      SHOULD use well-defined format — interoperable, decentralized messaging.
    - **VP-15-002** (`vultron-protocol-spec.md`): Implementations SHOULD use
      common identity mechanisms (`PROD_ONLY`) — federated identity.

---

## 5. Actor Identity, Privacy, and Security

- **story_2022_034** — "As a Participant, use global/federated user ID"
  - *Mapped requirements:*
    - **OID-01-001** (`object-ids.md`): All ActivityStreams object IDs MUST use
      full URI form — global ID format.
    - **VP-15-002** (`vultron-protocol-spec.md`): Implementations SHOULD use
      common identity mechanisms (`PROD_ONLY`) — federated identity.
    - **VP-15-003** (`vultron-protocol-spec.md`): Implementations SHOULD use
      common messaging protocols (`PROD_ONLY`) — interoperable identity use.

- **story_2022_035** — "As a Participant, have confidence in identity/group membership"
  - *Mapped requirements:*
    - **ENC-01-001** (`encryption.md`): Each CaseActor MUST generate an
      asymmetric key (`PROD_ONLY`) — identity key material.
    - **ENC-01-002** (`encryption.md`): The CaseActor MUST publish its public
      key in its actor profile (`PROD_ONLY`) — verifiable identity.
    - **VP-15-002** (`vultron-protocol-spec.md`): Implementations SHOULD use
      common identity mechanisms (`PROD_ONLY`) — federated identity.

- **story_2022_036** — "As a non-vendor, determine integration of auth/authz"
  - *Mapped requirements:*
    - **ENC-01-001** (`encryption.md`): Each CaseActor MUST generate an
      asymmetric key (`PROD_ONLY`) — auth model via keys.
    - **VP-15-002** (`vultron-protocol-spec.md`): Implementations SHOULD use
      common identity mechanisms (`PROD_ONLY`) — auth/authz integration.
    - **CM-02-006** (`case-management.md`): CaseActor MUST enforce case-level
      authorization for all activities (`PROD_ONLY`) — authz enforcement.

- **story_2022_089** — "As a Participant, mechanism for message authentication/integrity"
  - *Mapped requirements:*
    - **ENC-01-001** (`encryption.md`): Each CaseActor MUST generate an
      asymmetric key (`PROD_ONLY`) — signing key for integrity.
    - **ENC-01-002** (`encryption.md`): CaseActor MUST publish its public key
      (`PROD_ONLY`) — verifiable signatures.
    - **VP-15-004** (`vultron-protocol-spec.md`): Implementations MAY use
      end-to-end encryption (`PROD_ONLY`) — integrity mechanism.
    - **VP-15-005** (`vultron-protocol-spec.md`): Implementations MAY use
      encryption for messages (`PROD_ONLY`) — transport integrity.

- **story_2022_090** — "As a Participant, mechanism for all Participants' authentication"
  - *Mapped requirements:*
    - **ENC-01-001** (`encryption.md`): Each CaseActor MUST generate an
      asymmetric key (`PROD_ONLY`) — participant authentication.
    - **ENC-01-003** (`encryption.md`): CaseActor MUST share its public key
      with Participants (`PROD_ONLY`) — key exchange for auth.
    - **VP-15-002** (`vultron-protocol-spec.md`): Implementations SHOULD use
      common identity mechanisms (`PROD_ONLY`) — identity framework.

- **story_2022_091** — "As a Participant, mechanism for confidential transport/storage"
  - *Mapped requirements:*
    - **ENC-02-001** (`encryption.md`): Case Participants MAY encrypt messages
      (`PROD_ONLY`) — confidential transport.
    - **ENC-02-002** (`encryption.md`): When sending messages, encrypt using
      recipient's public key (`PROD_ONLY`) — encryption mechanism.
    - **ENC-01-004** (`encryption.md`): Private keys MUST be stored securely
      (`PROD_ONLY`) — confidential storage.
    - **VP-15-004** (`vultron-protocol-spec.md`): Implementations MAY use
      end-to-end encryption (`PROD_ONLY`) — end-to-end confidentiality.

- **story_2022_092** — "As a Participant, know who else is participating in a case"
  - *Mapped requirements:*
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors of affected
      software SHOULD be included — full participant list.
    - **VP-08-009** (`vultron-protocol-spec.md`): Participants SHOULD notify
      others when a new Participant is added to a case.
    - **VP-01-001** (`vultron-protocol-spec.md`): Participants SHOULD track the
      state of other Participants — state tracking implies membership.

- **story_2022_093** — "As a Participant, ensure Participant list is complete"
  - *Mapped requirements:*
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors of affected
      software SHOULD be included — completeness obligation.
    - **VP-08-009** (`vultron-protocol-spec.md`): Participants SHOULD notify
      others when a new Participant is added.
    - **VP-01-001** (`vultron-protocol-spec.md`): Participants SHOULD track the
      state of other Participants — tracking supports list integrity.

- **story_2022_094** — "As a Participant, assess reputation of others to decide to engage"
  - *Mapped requirements:*
    - **VP-05-013** (`vultron-protocol-spec.md`): Participants SHOULD consider
      others' history of embargo compliance — reputation as input.
    - **VP-08-010** (`vultron-protocol-spec.md`): Participants known to leak
      information SHOULD be excluded from embargoes.
    - **VP-08-021** (`vultron-protocol-spec.md`): Participants MAY decline to
      participate in future CVD cases — reputation-driven decisions.

- **story_2022_095** — "As a Participant, provide evidence of reputation to others"
  - *Mapped requirements:*
    - **VP-05-013** (`vultron-protocol-spec.md`): Participants SHOULD consider
      others' history of embargo compliance — reputation-based trust.
    - **EP-01-001** (`embargo-policy.md`): An Actor profile MAY include an
      `embargo_policy` field — policy as proxy for reputation.
  - *No further mapped requirements* (reputation attestation has no direct
    current spec requirement beyond policy publication).

- **story_2022_096** — "As a Participant, record/log trust/reputation of others"
  - *Mapped requirements:*
    - **VP-05-013** (`vultron-protocol-spec.md`): Participants SHOULD consider
      others' history of embargo compliance — basis for reputation log.
    - **VP-08-010** (`vultron-protocol-spec.md`): Participants known to leak
      information SHOULD be excluded — outcome of reputation tracking.
  - *No further mapped requirements* (reputation logging is not specified
    in current specs).

- **story_2022_097** — "As a Participant, organize own groups of other Participants"
  - *Mapped requirements:*
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors of affected
      software SHOULD be included — group composition.
    - **VP-08-012** (`vultron-protocol-spec.md`): Participants MAY engage a
      third-party Coordinator — group with coordinator.
    - **VP-08-014** (`vultron-protocol-spec.md`): Other parties MAY be included
      as Participants when necessary — flexible group composition.

---

## 6. Communication and Messaging

- **story_2022_016** — "As a Participant, limited ACK of vulnerability / full advisory"
  - *Mapped requirements:*
    - **VP-03-009** (`vultron-protocol-spec.md`): Recipients SHOULD send RK in
      acknowledgment of any R* message — acknowledgment requirement.
    - **RF-02-001** (`response-format.md`): Accept responses MUST use `Accept`
      activity type — formal acceptance of report.
    - **RF-08-001** (`response-format.md`): Response activities MUST include
      `inReplyTo` field — tracing response back to original.

- **story_2022_028** — "As a vendor or coordinator, want others to find me"
  - *Mapped requirements:*
    - **VP-02-001** (`vultron-protocol-spec.md`): Coordinators MUST have a
      clearly defined and publicly available policy — discoverability.
    - **IE-02-001** (`inbox-endpoint.md`): The endpoint URL MUST be
      discoverable from actor profile — inbox discoverability.
    - **AR-01-001** (`agentic-readiness.md`): The API MUST expose a
      machine-readable OpenAPI JSON schema — programmatic discovery.

- **story_2022_039** — "As a Participant, communicate with another case Participant"
  - *Mapped requirements:*
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to other Participants.
    - **RF-01-001** (`response-format.md`): Response activities MUST conform to
      ActivityStreams 2.0 — message format.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      delivery mechanism.

- **story_2022_040** — "As a Participant, unicast/point-to-point communication"
  - *Mapped requirements:*
    - **OX-04-001** (`outbox.md`): For actors on the same server, delivery MUST
      write directly to the recipient's inbox — local unicast delivery.
    - **OX-05-001** (`outbox.md`): For remote actors, MAY deliver via HTTP POST
      (`PROD_ONLY`) — remote unicast delivery.
    - **RF-06-002** (`response-format.md`): Response activities MUST be
      addressed to the initiating actor — targeted addressing.

- **story_2022_041** — "As a Participant, broadcast to all Participants in a case"
  - *Mapped requirements:*
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to all Participants — broadcast state changes.
    - **OX-03-001** (`outbox.md`): Activities in an actor's outbox MUST be
      delivered to recipient inboxes — outbox-based broadcast.

- **story_2022_042** — "As a Participant, communicate with a subset of Participants"
  - *Mapped requirements:*
    - **VP-05-007** (`vultron-protocol-spec.md`): Embargo participation SHOULD
      be limited to the smallest possible set — subset communication.
    - **OX-03-001** (`outbox.md`): Activities in an actor's outbox MUST be
      delivered to recipient inboxes — selective delivery.

- **story_2022_043** — "As a Participant, communicate in a common case channel"
  - *Mapped requirements:*
    - **CM-06-001** (`case-management.md`): When the CaseActor updates
      canonical case state, it MUST broadcast to all Participants.
    - **OX-03-001** (`outbox.md`): Activities in an actor's outbox MUST be
      delivered to recipient inboxes — channel delivery.

- **story_2022_044** — "As a Participant, communicate with selected case Participants"
  - *Mapped requirements:*
    - **OX-03-001** (`outbox.md`): Activities in an actor's outbox MUST be
      delivered to recipient inboxes — selective delivery.
    - **VP-08-006** (`vultron-protocol-spec.md`): The inviting Participant
      SHOULD NOT share the vulnerability report — selective disclosure.

- **story_2022_058** — "As a Participant, share a draft advisory with others"
  - *Mapped requirements:*
    - **VP-05-006** (`vultron-protocol-spec.md`): Embargo Participants SHOULD
      NOT knowingly release information — shared draft under embargo.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      delivery of draft advisory.
    - **RF-01-001** (`response-format.md`): Response activities MUST conform to
      ActivityStreams 2.0 — message format for draft sharing.

- **story_2022_059** — "As a Participant, share draft advisory and request feedback"
  - *Mapped requirements:*
    - **VP-05-006** (`vultron-protocol-spec.md`): Embargo Participants SHOULD
      NOT knowingly release information — embargo-constrained sharing.
    - **RF-02-001** (`response-format.md`): Accept responses MUST use `Accept`
      activity type — feedback as Accept/Reject on draft.
    - **RF-08-001** (`response-format.md`): Response activities MUST include
      `inReplyTo` field — feedback references draft.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      delivery mechanism.

- **story_2022_060** — "As a Participant, request advisory draft from a Participant"
  - *Mapped requirements:*
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to others — draft availability announcement.
    - **RF-01-001** (`response-format.md`): Response activities MUST conform to
      ActivityStreams 2.0 — request/response format.

- **story_2022_061** — "As a Participant, request another Participant's status"
  - *Mapped requirements:*
    - **VP-01-001** (`vultron-protocol-spec.md`): Participants SHOULD track the
      state of other Participants — state inquiry.
    - **VP-01-002** (`vultron-protocol-spec.md`): Participants SHOULD track the
      RM states of other Participants — RM state request.
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to others — announcement satisfies query.

- **story_2022_062** — "As a Participant, state my status so others are aware"
  - *Mapped requirements:*
    - **VP-02-019** (`vultron-protocol-spec.md`): CVD Participants SHOULD
      announce RM state transitions to other Participants.
    - **VP-03-005** (`vultron-protocol-spec.md`): Participants SHOULD send RD
      when the report prioritization is deferred.
    - **VP-03-006** (`vultron-protocol-spec.md`): Participants SHOULD send RA
      when the report prioritization is accepted.
    - **VP-03-007** (`vultron-protocol-spec.md`): Participants SHOULD send RC
      when the report is closed.
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce RM, EM, or CVD Case State.

- **story_2022_081** — "As a Participant, communicate important public state change"
  - *Mapped requirements:*
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to all Participants — state change announcement.
    - **VP-12-001** (`vultron-protocol-spec.md`): Vendor Awareness messages
      SHOULD be sent only by Vendors who become aware of the vulnerability.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      delivery mechanism for announcements.

- **story_2022_098** — "As a Participant, communicate with all Participants in a case"
  - *Mapped requirements:*
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to all Participants — broadcast mechanism.
    - **CM-06-001** (`case-management.md`): When CaseActor updates state, MUST
      broadcast to all Participants — case-level broadcast.
    - **OX-03-001** (`outbox.md`): Activities in an actor's outbox MUST be
      delivered to recipient inboxes — delivery to all.

- **story_2022_099** — "As a Participant, communicate with non-vendor Participants"
  - *Mapped requirements:*
    - **VP-08-014** (`vultron-protocol-spec.md`): Other parties MAY be included
      as Participants when necessary — non-vendor inclusion.
    - **OX-03-001** (`outbox.md`): Activities in an actor's outbox MUST be
      delivered to recipient inboxes — delivery mechanism.

- **story_2022_100** — "As a Participant, be included on distribution list for advisories"
  - *Mapped requirements:*
    - **VP-12-001** (`vultron-protocol-spec.md`): Vendor Awareness messages
      SHOULD be sent only by Vendors who become aware — awareness notifications.
    - **OX-03-001** (`outbox.md`): Activities in an actor's outbox MUST be
      delivered to recipient inboxes — subscription/distribution mechanism.
    - **OX-04-001** (`outbox.md`): For actors on the same server, delivery MUST
      write directly to the recipient's inbox — local distribution.

---

## 7. Publication and Disclosure

- **story_2022_015** — "As a Participant, notify others of intent to publish"
  - *Mapped requirements:*
    - **VP-05-014** (`vultron-protocol-spec.md`): Participants SHOULD NOT
      publish information before embargo terminates — pre-publish notice.
    - **VP-09-001** (`vultron-protocol-spec.md`): Embargoes SHALL terminate
      immediately when information about the vulnerability is made public.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      delivery of publication intent notification.

- **story_2022_017** — "As a Participant, share my draft publication with others"
  - *Mapped requirements:*
    - **VP-05-006** (`vultron-protocol-spec.md`): Embargo Participants SHOULD
      NOT knowingly release information — draft shared within embargo.
    - **RF-01-001** (`response-format.md`): Response activities MUST conform to
      ActivityStreams 2.0 — format for sharing draft.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      delivery mechanism.

- **story_2022_018** — "As a Participant, aware of public exploit, tell others"
  - *Mapped requirements:*
    - **VP-09-003** (`vultron-protocol-spec.md`): Embargoes SHOULD terminate
      early when there is evidence of exploit availability.
    - **VP-09-006** (`vultron-protocol-spec.md`): Embargoes MAY terminate early
      when evidence of exploit publication exists.
    - **VP-14-002** (`vultron-protocol-spec.md`): Once Exploit Publication has
      occurred, new embargoes have restricted scope.
    - **VP-11-002** (`vultron-protocol-spec.md`): If information has been made
      public, participants should initiate embargo termination.

- **story_2022_019** — "As a Participant, aware of exploitation in the wild, tell others"
  - *Mapped requirements:*
    - **VP-11-003** (`vultron-protocol-spec.md`): Participants SHALL initiate
      embargo termination upon becoming aware of exploitation.
    - **VP-11-006** (`vultron-protocol-spec.md`): If attacks are known to have
      occurred, Participants SHOULD act accordingly.
    - **VP-11-007** (`vultron-protocol-spec.md`): Participants SHOULD initiate
      embargo termination when attacks are observed.
    - **VP-12-002** (`vultron-protocol-spec.md`): Once attacks observed, fix
      development SHOULD be accelerated.
    - **VP-14-003** (`vultron-protocol-spec.md`): Once attacks observed, new
      embargoes have restricted scope.

- **story_2022_020** — "As a Participant, publish a vulnerability (external to protocol)"
  - *Mapped requirements:*
    - **VP-05-005** (`vultron-protocol-spec.md`): Embargo termination SHALL NOT
      be construed as an obligation to publish — no forced publication.
    - **VP-05-020** (`vultron-protocol-spec.md`): Participants MAY publish
      information about the vulnerability when embargo ends.
    - **VP-09-001** (`vultron-protocol-spec.md`): Embargoes SHALL terminate
      immediately when information is made public — publication triggers.
    - **VP-14-001** (`vultron-protocol-spec.md`): Once Public Awareness has
      happened — implications for embargo state.

- **story_2022_037** — "As a vendor, publish vulnerability advisories"
  - *Mapped requirements:*
    - **VP-05-020** (`vultron-protocol-spec.md`): Participants MAY publish
      information when embargo ends — advisory publication timing.
    - **VP-12-001** (`vultron-protocol-spec.md`): Vendor Awareness messages
      SHOULD be sent only by Vendors — vendor-side announcement.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      delivery of advisory announcement.

- **story_2022_069** — "As a Participant, tell others that I published"
  - *Mapped requirements:*
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to other Participants.
    - **VP-12-001** (`vultron-protocol-spec.md`): Vendor Awareness messages
      SHOULD be sent only by Vendors who become aware.
    - **VP-09-001** (`vultron-protocol-spec.md`): Embargoes SHALL terminate
      immediately when information is made public — consequence of publishing.

- **story_2022_070** — "As a Participant, convey how information I provide can be used"
  - *Mapped requirements:*
    - **VP-05-006** (`vultron-protocol-spec.md`): Embargo Participants SHOULD
      NOT knowingly release information — use constraint.
    - **VP-16-001** (`vultron-protocol-spec.md`): Vulnerability details MUST
      NOT appear in embargo representation — separation constraint.
  - *No further mapped requirements* (TLP-level information use policies
    have no direct current spec requirement).

- **story_2022_071** — "As a Participant, convey information use while obeying TLP"
  - *Mapped requirements:*
    - **VP-05-006** (`vultron-protocol-spec.md`): Embargo Participants SHOULD
      NOT knowingly release information — TLP-analogous constraint.
    - **VP-16-001** (`vultron-protocol-spec.md`): Vulnerability details MUST
      NOT appear in embargo representation — content restriction.
  - *No further mapped requirements* (TLP tagging is not specified in
    current specs).

- **story_2022_072** — "As a Participant, convey what restricted info I will accept"
  - *Mapped requirements:*
    - **EP-01-002** (`embargo-policy.md`): The embargo policy record MUST
      include required fields — policy expresses what info is accepted.
    - **VP-05-007** (`vultron-protocol-spec.md`): Embargo participation SHOULD
      be limited to the smallest possible set — restriction principle.
  - *No further mapped requirements* (TLP acceptance policy is not
    specified in current specs).

- **story_2022_073** — "As a Participant, convey TLP restriction level I will accept"
  - *Mapped requirements:*
    - **EP-01-003** (`embargo-policy.md`): The embargo policy record SHOULD
      include optional fields — policy fields for restriction level.
  - *No further mapped requirements* (TLP acceptance level is not
    specified in current specs).

- **story_2022_083** — "As a Participant, contribute to advisory creation and publication"
  - *Mapped requirements:*
    - **VP-05-020** (`vultron-protocol-spec.md`): Participants MAY publish
      information when embargo ends — advisory publication.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      delivery of advisory contribution.
    - **CM-02-007** (`case-management.md`): VulnerabilityCase MUST include a
      `notes` list — advisory draft content in notes.

- **story_2022_107** — "As a Vendor, convey vulnerability status to other Participants"
  - *Mapped requirements:*
    - **VP-02-019** (`vultron-protocol-spec.md`): CVD Participants SHOULD
      announce RM state transitions to other Participants.
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants SHOULD announce
      RM, EM, or CVD Case State changes.
    - **CM-03-001** (`case-management.md`): The system MUST implement the three
      interacting state machines — RM/EM/CS status tracking.
    - **CM-04-001** (`case-management.md`): Handlers processing RM state
      transitions MUST update participant RM state.
    - **VP-12-001** (`vultron-protocol-spec.md`): Vendor Awareness messages
      SHOULD be sent only by Vendors.

- **story_2022_108** — "As a Vendor, convey vulnerability status to Users/the Public"
  - *Mapped requirements:*
    - **VP-12-001** (`vultron-protocol-spec.md`): Vendor Awareness messages
      SHOULD be sent only by Vendors — public status announcement.
    - **VP-14-001** (`vultron-protocol-spec.md`): Once Public Awareness has
      happened — implications for state.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      public outbox for status delivery.

- **story_2022_109** — "As a Vendor, convey reason component not affected to Participants"
  - *Mapped requirements:*
    - **VP-03-003** (`vultron-protocol-spec.md`): Participants SHOULD send RI
      when the report validation process determines invalid — not-affected.
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants SHOULD announce
      RM, EM, or CVD Case State changes.

- **story_2022_110** — "As a Vendor, convey reason component not affected to Public"
  - *Mapped requirements:*
    - **VP-12-001** (`vultron-protocol-spec.md`): Vendor Awareness messages
      SHOULD be sent only by Vendors — public not-affected message.
    - **OX-01-001** (`outbox.md`): Each actor MUST have an outbox collection —
      public outbox delivery.

---

## 8. Bug Bounty and Incentives

- **story_2022_011** — "As a Participant, provide bug bounty program info to reporters"
  - *Mapped requirements:*
    - **EP-01-001** (`embargo-policy.md`): An Actor profile MAY include an
      `embargo_policy` field — profile fields for program information.
  - *No further mapped requirements* (bug bounty program description
    has no direct current spec requirement).

- **story_2022_055** — "As a Participant, state that I paid or received a bounty"
  - *No mapped requirements* (bounty payment state is not covered by
    current specs).

- **story_2022_056** — "As a Participant, ask if another Participant paid a reporter"
  - *No mapped requirements* (bounty inquiry is not covered by current
    specs).

- **story_2022_057** — "As a Participant, ask a reporter if they were paid"
  - *No mapped requirements* (bounty inquiry to reporter is not covered
    by current specs).

- **story_2022_084** — "As a vendor, reward the reporter by paying a bounty"
  - *No mapped requirements* (bug bounty payment is not covered by
    current specs).

- **story_2022_085** — "As a reporter, be rewarded with a bounty"
  - *No mapped requirements* (receiving a bounty is not covered by
    current specs).

---

## 9. Prioritization, Assessment, and Fix Verification

- **story_2022_075** — "As a Participant, see response times/states of other Participants"
  - *Mapped requirements:*
    - **VP-01-001** (`vultron-protocol-spec.md`): Participants SHOULD track the
      state of other Participants — state visibility.
    - **VP-01-002** (`vultron-protocol-spec.md`): Participants SHOULD track the
      RM states of other Participants — RM state visibility.
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to others — state updates received.

- **story_2022_082** — "As a non-vendor Participant, be informed of CVD for risk assessment"
  - *Mapped requirements:*
    - **VP-08-014** (`vultron-protocol-spec.md`): Other parties MAY be included
      as Participants when necessary — non-vendor inclusion for risk assessment.
    - **VP-03-012** (`vultron-protocol-spec.md`): Participants whose state
      changes SHOULD announce to others — status updates support risk assessment.
    - **VP-08-004** (`vultron-protocol-spec.md`): All known Vendors of affected
      software SHOULD be included — relevant parties informed.

- **story_2022_086** — "As a Participant, prioritize response to requests"
  - *Mapped requirements:*
    - **VP-02-014** (`vultron-protocol-spec.md`): For Valid reports, the
      Participant SHOULD perform a prioritization step.
    - **VP-02-024** (`vultron-protocol-spec.md`): Vendors SHOULD communicate
      their prioritization choices when prioritizing.
    - **VP-02-034** (`vultron-protocol-spec.md`): Participants MAY
      re-prioritize Accepted or Deferred cases.

- **story_2022_087** — "As a Participant, share info to prioritize work on a report"
  - *Mapped requirements:*
    - **VP-02-014** (`vultron-protocol-spec.md`): For Valid reports, the
      Participant SHOULD perform a prioritization step.
    - **VP-02-024** (`vultron-protocol-spec.md`): Vendors SHOULD communicate
      their prioritization choices — shared prioritization data.
    - **VP-01-001** (`vultron-protocol-spec.md`): Participants SHOULD track the
      state of other Participants — state supports prioritization.

- **story_2022_103** — "As a Participant, give Finder opportunity to confirm fix"
  - *Mapped requirements:*
    - **VP-02-013** (`vultron-protocol-spec.md`): Participants SHOULD provide
      Reporters an opportunity to update their reports — feedback opportunity.
    - **VP-02-011** (`vultron-protocol-spec.md`): Once a Vendor confirms that a
      reported vulnerability affects a product — fix confirmation context.
