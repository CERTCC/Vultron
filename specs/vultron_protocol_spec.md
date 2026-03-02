# Vultron Protocol Specification

## Overview

Requirements extracted from the Vultron Protocol documentation covering
participant state tracking, Report Management (RM), Embargo Management (EM),
CVD Case State (CS) messaging, model interactions, and implementation guidance.

**Sources**:
`docs/reference/formal_protocol/states.md`,
`docs/reference/formal_protocol/messages.md`,
`docs/reference/formal_protocol/transitions.md`,
`docs/topics/process_models/rm/index.md`,
`docs/topics/process_models/em/index.md`,
`docs/topics/process_models/em/principles.md`,
`docs/topics/process_models/em/negotiating.md`,
`docs/topics/process_models/em/defaults.md`,
`docs/topics/process_models/em/working_with_others.md`,
`docs/topics/process_models/em/early_termination.md`,
`docs/topics/process_models/em/split_merge.md`,
`docs/topics/process_models/model_interactions/rm_em.md`,
`docs/topics/process_models/model_interactions/rm_em_cs.md`,
`docs/topics/process_models/cs/transitions.md`,
`docs/reference/ssvc_crosswalk.md`,
`docs/howto/general_implementation.md`,
`docs/howto/em_icalendar.md`

---

## Participant State Tracking (SHOULD)

- `VP-01-001` Participants SHOULD track the state of other Participants in a
  case to inform their own decision making
  - Source: `docs/reference/formal_protocol/states.md`
  - VP-01-001 is-implemented-by CM-03-002
  - VP-01-001 is-implemented-by CM-03-003
  - VP-01-001 is-implemented-by CM-03-004
  - VP-01-001 is-implemented-by CM-03-005
- `VP-01-002` Participants SHOULD track the RM states of the other Participants
  in the case
  - Source: `docs/reference/formal_protocol/messages.md`
  - VP-01-002 is-implemented-by CM-03-002
  - VP-01-002 is-implemented-by CM-04-001

## Participant State Tracking (MUST NOT)

- `VP-01-003` Adequate operation of the protocol MUST NOT depend on perfect
  information across all Participants
  - Source: `docs/reference/formal_protocol/states.md`
  - **Gap**: Not addressed by any current implementation spec

---

## Report Management (RM): Receiving Reports (MUST)

- `VP-02-001` Coordinators MUST have a clearly defined and publicly available
  mechanism for receiving reports
  - Source: `docs/topics/process_models/rm/index.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-02-002` Participants MUST prioritize Valid cases
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-002 is-implemented-by CM-04-001
- `VP-02-003` Participants initiating CVD with others MUST do so from the
  Accepted state
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-003 is-implemented-by CM-04-001

## Report Management (RM): Receiving Reports (MUST NOT)

- `VP-02-004` Participants MUST NOT close cases or reports from the Valid state
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-004 is-implemented-by CM-03-007

## Report Management (RM): Receiving Reports (SHOULD)

- `VP-02-005` Vendors SHOULD have a clearly defined and publicly available
  mechanism for receiving reports
  - Source: `docs/topics/process_models/rm/index.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-02-006` Participants SHOULD subject each Received report to a validation
  process resulting in a valid or invalid designation
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-006 is-implemented-by CM-03-001
  - VP-02-006 is-implemented-by CM-04-001
- `VP-02-007` Participants SHOULD have a clearly defined process for validating
  reports in the Received state
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-007 is-implemented-by CM-03-001
  - VP-02-007 is-implemented-by CM-04-001
- `VP-02-008` Participants SHOULD have a clearly defined process for
  transitioning reports from the Received state to the Valid or Invalid states
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-008 is-implemented-by CM-03-001
  - VP-02-008 is-implemented-by CM-04-001
- `VP-02-009` Participants SHOULD proceed only after validating the reports they
  receive
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-009 is-implemented-by CM-03-001
  - VP-02-009 is-implemented-by CM-04-001
- `VP-02-010` Participants SHOULD transition all valid reports to the Valid state
  and all invalid reports to the Invalid state
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-010 is-implemented-by CM-03-001
  - VP-02-010 is-implemented-by CM-04-001
- `VP-02-011` Once a Vendor confirms that a reported vulnerability affects one
  or more of their products or services, the Vendor SHOULD designate the report
  as Valid
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-011 is-implemented-by CM-03-001
  - VP-02-011 is-implemented-by CM-04-001
- `VP-02-012` Participants SHOULD temporarily hold reports that they cannot
  validate pending additional information
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-012 is-implemented-by CM-03-001
  - VP-02-012 is-implemented-by CM-04-001
- `VP-02-013` Participants SHOULD provide Reporters an opportunity to update
  their report with additional information before closing it
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-013 is-implemented-by CM-03-001
  - VP-02-013 is-implemented-by CM-04-001
- `VP-02-014` For Valid reports, the Participant SHOULD perform a prioritization
  evaluation to decide whether to accept or defer the report
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-014 is-implemented-by CM-03-001
  - VP-02-014 is-implemented-by CM-04-001
- `VP-02-015` Participants SHOULD create a case from reports entering the Valid
  state to track the report's progress through the CVD process
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-015 is-implemented-by BT-10-001
  - VP-02-015 is-implemented-by CM-05-002
- `VP-02-016` Participants SHOULD have a bias toward accepting rather than
  deferring Valid cases up to their work capacity limits
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-016 is-implemented-by CM-03-001
  - VP-02-016 is-implemented-by CM-04-001
- `VP-02-017` Reports SHOULD exit the Deferred state when work is resumed (to
  Accepted) or when the Participant has determined no further action will be
  taken (to Closed)
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-017 is-implemented-by CM-03-001
  - VP-02-017 is-implemented-by CM-04-001
- `VP-02-018` Reports SHOULD be moved to the Closed state once a Participant has
  completed all outstanding work tasks and is fairly sure they will not pursue
  further action
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-018 is-implemented-by CM-03-001
  - VP-02-018 is-implemented-by CM-04-001
- `VP-02-019` CVD Participants SHOULD announce their RM state transitions to the
  other Participants in a case
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-019 is-implemented-by CM-06-001
- `VP-02-020` Participants SHOULD create a case for all Valid reports
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-020 is-implemented-by BT-10-001
  - VP-02-020 is-implemented-by CM-05-002
- `VP-02-021` Participants SHOULD act in accordance with their own policy and
  process when deciding when to transition RM states
  - Source: `docs/reference/formal_protocol/messages.md`
  - VP-02-021 is-implemented-by CM-03-001
  - VP-02-021 is-implemented-by CM-04-001
- `VP-02-022` Participants SHOULD NOT mark duplicate reports as invalid
  - Source: `docs/reference/formal_protocol/messages.md`
  - VP-02-022 is-implemented-by CM-03-001
  - VP-02-022 is-implemented-by CM-04-001
- `VP-02-023` Duplicate reports SHOULD pass through the Valid state, although
  they MAY be subsequently deferred in favor of the original
  - Source: `docs/reference/formal_protocol/messages.md`
  - VP-02-023 is-implemented-by CM-03-001
  - VP-02-023 is-implemented-by CM-04-001
- `VP-02-024` Vendors SHOULD communicate their prioritization choices when
  making either a defer or accept transition out of the Valid, Deferred, or
  Accepted states
  - Source: `docs/reference/ssvc_crosswalk.md`
  - VP-02-024 is-implemented-by CM-03-001
  - VP-02-024 is-implemented-by CM-04-001

## Report Management (RM): Receiving Reports (MAY)

- `VP-02-025` Participants MAY perform a more technical report validation process
  before exiting the Received state
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-025 is-implemented-by CM-03-001
  - VP-02-025 is-implemented-by CM-04-001
- `VP-02-026` Participants MAY create a case object to track any report in the
  Received state
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-026 is-implemented-by CM-03-001
  - VP-02-026 is-implemented-by CM-04-001
- `VP-02-027` Participants MAY set a timer to move reports from Invalid to Closed
  after a set period of inactivity
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-027 is-implemented-by CM-03-001
  - VP-02-027 is-implemented-by CM-04-001
- `VP-02-028` Participants MAY choose to perform a shallow technical analysis on
  Valid reports to prioritize further effort
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-028 is-implemented-by CM-03-001
  - VP-02-028 is-implemented-by CM-04-001
- `VP-02-029` A report MAY enter and exit the Accepted state a number of times
  as a Participant resumes or pauses work
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-029 is-implemented-by CM-03-001
  - VP-02-029 is-implemented-by CM-04-001
- `VP-02-030` A report MAY enter and exit the Deferred state a number of times
  as a Participant pauses or resumes work
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-030 is-implemented-by CM-03-001
  - VP-02-030 is-implemented-by CM-04-001
- `VP-02-031` CVD Participants MAY set a policy timer on reports in the Deferred
  state to ensure they are moved to Closed after a set period of inactivity
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-031 is-implemented-by CM-03-001
  - VP-02-031 is-implemented-by CM-04-001
- `VP-02-032` Participants MAY create a case for Invalid reports
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-032 is-implemented-by CM-03-001
  - VP-02-032 is-implemented-by CM-04-001
- `VP-02-033` Participants MAY periodically revalidate Invalid reports to
  determine if they have become Valid
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-033 is-implemented-by CM-03-001
  - VP-02-033 is-implemented-by CM-04-001
- `VP-02-034` Participants MAY re-prioritize Accepted or Deferred cases
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-034 is-implemented-by CM-03-001
  - VP-02-034 is-implemented-by CM-04-001
- `VP-02-035` Participants MAY close Accepted or Deferred cases or Invalid
  reports
  - Source: `docs/topics/process_models/rm/index.md`
  - VP-02-035 is-implemented-by CM-03-001
  - VP-02-035 is-implemented-by CM-04-001

---

## RM Messaging (MUST)

- `VP-03-001` Participants MUST be in RM Accepted to send a Report Submission
  ($RS$) message to someone else
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-001 is-implemented-by CM-04-001
- `VP-03-002` Vendor Recipients receiving a new Report Submission MUST
  transition their CVD Case State to Vendor Aware
  ($q^{cs} \xrightarrow{\mathbf{V}} Vfd\cdots$)
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-002 is-implemented-by CM-04-004

## RM Messaging (SHOULD)

- `VP-03-003` Participants SHOULD send $RI$ when the report validation process
  ends in an invalid determination
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-003 is-implemented-by OX-02-001
- `VP-03-004` Participants SHOULD send $RV$ when the report validation process
  ends in a valid determination
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-004 is-implemented-by OX-02-001
- `VP-03-005` Participants SHOULD send $RD$ when the report prioritization
  process ends in a deferred decision
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-005 is-implemented-by OX-02-001
- `VP-03-006` Participants SHOULD send $RA$ when the report prioritization
  process ends in an accept decision
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-006 is-implemented-by OX-02-001
- `VP-03-007` Participants SHOULD send $RC$ when the report is closed
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-007 is-implemented-by OX-02-001
- `VP-03-008` Participants SHOULD send $RE$ regardless of state when any error
  is encountered
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-008 is-implemented-by OX-02-001
- `VP-03-009` Recipients SHOULD send $RK$ in acknowledgment of any $R*$ message
  except $RK$ itself
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-009 is-implemented-by RF-08-001
- `VP-03-010` Recipients who receive an $R*$ message (other than $RS$) while in
  RM Start ($q^{rm} \in S$) SHOULD respond with both $RE$ to signal the error
  and $GI$ to find out what the sender expected
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-010 is-implemented-by RF-05-001
- `VP-03-011` Recipients SHOULD acknowledge $RE$ messages ($RK$) and inquire
  ($GI$) as to the nature of the error
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-011 is-implemented-by RF-05-001
- `VP-03-012` Participants whose state changes in the RM, EM, or CVD Case State
  Models SHOULD send a message to other Participants for each transition
  - Source: `docs/reference/formal_protocol/messages.md`
  - VP-03-012 is-implemented-by CM-06-001

## RM Messaging (MAY)

- `VP-03-013` Recipients MAY ignore messages received on Closed cases
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-03-013 is-implemented-by ID-04-002

---

## Embargo Management (EM) Process (MUST)

- `VP-04-001` Accepted embargoes MUST eventually terminate
  - Source: `docs/topics/process_models/em/index.md`
  - **Gap**: Not addressed by any current implementation spec

## Embargo Management (EM) Process (SHALL)

- `VP-04-002` A CVD case SHALL NOT have more than one active embargo at a time
  - Source: `docs/topics/process_models/em/index.md`
  - VP-04-002 is-implemented-by CM-03-003

## Embargo Management (EM) Process (MAY)

- `VP-04-003` An embargo MAY be proposed
  - Source: `docs/topics/process_models/em/index.md`
  - VP-04-003 is-implemented-by CM-03-003
  - VP-04-003 is-implemented-by CM-04-003
- `VP-04-004` Once proposed, an embargo MAY be accepted or rejected
  - Source: `docs/topics/process_models/em/index.md`
  - VP-04-004 is-implemented-by CM-03-003
  - VP-04-004 is-implemented-by CM-04-003
- `VP-04-005` Once accepted, revisions MAY be proposed, which MAY in turn be
  accepted or rejected
  - Source: `docs/topics/process_models/em/index.md`
  - VP-04-005 is-implemented-by CM-03-003
  - VP-04-005 is-implemented-by CM-04-003

---

## Embargo Principles (SHALL)

- `VP-05-001` An embargo SHALL specify an unambiguous date and time as its
  endpoint
  - Source: `docs/topics/process_models/em/principles.md`
  - VP-05-001 is-implemented-by EP-01-002
  - VP-05-001 is-implemented-by EP-01-003
- `VP-05-002` An embargo SHALL NOT be used to indefinitely delay publication of
  vulnerability information, whether through repeated extension or by setting a
  long-range endpoint
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-003` An embargo SHALL begin at the moment it is accepted
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-004` Adding Participants to an existing embargo SHALL NOT constitute
  release or publication so long as those Participants accept the terms of the
  embargo
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-005` Embargo termination SHALL NOT be construed as an obligation to
  publish
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec

## Embargo Principles (SHOULD)

- `VP-05-006` Embargo Participants SHOULD NOT knowingly release information about
  an embargoed case until all proposed embargoes have been explicitly rejected,
  no proposed embargo has been explicitly accepted in a timely manner, the
  expiration date/time of an accepted embargo has passed, or an accepted embargo
  has been terminated prior to expiration
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-007` Embargo participation SHOULD be limited to the smallest possible
  set of individuals and organizations needed to adequately address the
  vulnerability report
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-008` Embargo duration SHOULD be limited to the shortest duration
  possible to adequately address the vulnerability report
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-009` Embargoes SHOULD be of short duration, from a few days to a few
  months
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-010` Participants stopping work on a case SHOULD notify remaining
  Participants of their intent to adhere to or disregard any existing embargo
  associated with the case
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-011` Participants SHOULD continue to comply with any active embargoes
  to which they have been a party, even if they stop work on the case
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-012` Participants who leave an Active embargo SHOULD be removed by the
  remaining Participants from further communication about the case
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-013` Participants SHOULD consider other Participants' history of
  cooperation when evaluating the terms of a proposed embargo
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-014` Participants SHOULD NOT publish information about the vulnerability
  when there is an active embargo
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec

## Embargo Principles (MAY)

- `VP-05-015` Additional Participants MAY be added to an existing embargo upon
  accepting the terms of that embargo
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-016` Participants MAY propose a new embargo or revision to an existing
  embargo at any time within the constraints outlined in the Negotiating
  Embargoes guidance
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-017` Participants MAY reject proposed embargo terms for any reason
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-018` Participants in an embargo MAY exit the embargo at any time
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-019` A Participant's refusal to accept embargo terms MAY result in that
  Participant being left out of the CVD case entirely
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-05-020` Participants MAY publish information about the vulnerability when
  there is no active embargo
  - Source: `docs/topics/process_models/em/principles.md`
  - **Gap**: Not addressed by any current implementation spec

---

## Embargo Negotiation (MUST NOT)

- `VP-06-001` CVD Participants MUST NOT propose or accept a new embargo
  negotiation when information about the vulnerability is already known to the
  public ($q^{cs} \in \cdots P \cdots$), an exploit is publicly available
  ($q^{cs} \in \cdots X \cdot$), or the vulnerability is being actively
  exploited ($q^{cs} \in \cdots A$)
  - Source: `docs/topics/process_models/em/negotiating.md`
  - VP-06-001 is-implemented-by CM-04-003
  - VP-06-001 is-implemented-by CM-04-004

## Embargo Negotiation (SHOULD)

- `VP-06-002` CVD Participants SHOULD NOT propose or accept a new embargo when
  the fix for a vulnerability has already been deployed ($q^{cs} \in VFDpxa$)
  - Source: `docs/topics/process_models/em/negotiating.md`
  - VP-06-002 is-implemented-by CM-04-003
- `VP-06-003` Receivers SHOULD accept any embargo proposed by Reporters
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-004` Participants SHOULD explicitly accept or reject embargo proposals
  in a timely manner; embargo agreement or rejection SHOULD NOT be tacit
  - Source: `docs/topics/process_models/em/negotiating.md`
  - VP-06-004 is-implemented-by RF-02-001
  - VP-06-004 is-implemented-by RF-03-001
  - VP-06-004 is-implemented-by RF-04-001
- `VP-06-005` Participants SHOULD make reasonable attempts to retry embargo
  negotiations when prior proposals have been rejected or otherwise failed to
  achieve acceptance
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-006` Participants SHOULD remain flexible in adjusting embargo terms as
  the case evolves
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec

## Embargo Negotiation (SHALL)

- `VP-06-007` Submitting a report when an embargo proposal is pending
  ($q^{em} \in P$) SHALL be construed as the Sender's acceptance of the
  proposed terms
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec

## Embargo Negotiation (MAY)

- `VP-06-008` CVD Participants MAY propose or accept a new embargo when the fix
  for a vulnerability is ready but has neither been made public nor deployed
  ($q^{cs} \in VFdpxa$); such an embargo SHOULD be brief and used only to allow
  Participants to prepare for timely publication or deployment
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-009` CVD Participants MAY propose or accept an embargo in all other
  case states ($q^{cs} \in \cdots pxa$)
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-010` Participants MAY accept or reject any proposed embargo as they see
  fit
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-011` Receivers MAY propose embargo terms they find more favorable
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-012` Participants MAY withdraw their own unaccepted Proposed embargo
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-013` Participants MAY interpret another Participant's failure to respond
  to an embargo proposal in a timely manner as a rejection of that proposal
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-014` In the absence of an explicit accept or reject response from a
  Receiver in a timely manner, the Sender MAY proceed consistent with an EM
  state of None ($q^{em} \in N$)
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-015` In a case where the embargo state is None and for which an embargo
  has been proposed and either explicitly or tacitly rejected, Participants MAY
  take any action they choose with the report, including immediate publication
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-016` Participants MAY withhold a report from a Recipient until an
  initial embargo has been accepted
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-06-017` Participants MAY use short embargo periods to cover their report
  validation process and subsequently revise the embargo terms pending the
  outcome of their validation or prioritization processes
  - Source: `docs/topics/process_models/em/negotiating.md`
  - **Gap**: Not addressed by any current implementation spec

---

## Embargo Default Policies (SHALL)

- `VP-07-001` If neither Sender nor Receiver proposes an embargo and no policy
  defaults apply, no embargo SHALL exist
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-001 is-implemented-by EP-01-002
  - VP-07-001 is-implemented-by EP-03-001
- `VP-07-002` A Receiver's default embargo specified in its vulnerability
  disclosure policy SHALL be treated as an initial embargo proposal
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-002 is-implemented-by EP-01-002
- `VP-07-003` If the Receiver has declared a default embargo in its
  vulnerability disclosure policy and the Sender proposes nothing to the
  contrary, the Receiver's default embargo SHALL be considered as an accepted
  proposal
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-003 is-implemented-by EP-03-002
- `VP-07-004` If the Sender proposes an embargo longer than the Receiver's
  default, the Receiver's default SHALL be taken as accepted and the Sender's
  proposal taken as a proposed revision
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-004 is-implemented-by EP-03-002
- `VP-07-005` If the Sender proposes an embargo shorter than the Receiver's
  default, the Sender's proposal SHALL be taken as accepted and the Receiver's
  default taken as a proposed revision
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-005 is-implemented-by EP-03-002

## Embargo Default Policies (SHOULD)

- `VP-07-006` Report Recipients SHOULD post a default embargo period as part of
  their Vulnerability Disclosure Policy to set expectations with potential
  Reporters
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-006 is-implemented-by EP-01-003
  - VP-07-006 is-implemented-by EP-02-001
  - VP-07-006 is-implemented-by EP-03-001
- `VP-07-007` If the Sender proposes an embargo and the Receiver has no default
  embargo specified by policy, the Receiver SHOULD accept the Sender's proposal
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-007 is-implemented-by EP-03-001
- `VP-07-008` When two or more embargo proposals are open and no embargo has yet
  been accepted ($q^{em} \in P$), Participants SHOULD accept the shortest one
  and propose the remainder as revisions
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-008 is-implemented-by EP-03-001
- `VP-07-009` When two or more embargo revisions are open and an embargo is
  active ($q^{em} \in R$), Participants SHOULD accept or reject them
  individually in earliest-to-latest expiration order
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-009 is-implemented-by EP-03-001

## Embargo Default Policies (MAY)

- `VP-07-010` Participants MAY include a default embargo period as part of a
  published Vulnerability Disclosure Policy
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-010 is-implemented-by EP-01-001
  - VP-07-010 is-implemented-by EP-03-001
- `VP-07-011` When the Receiver has no default, the Receiver MAY propose a
  revision after accepting the Sender's proposal
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-011 is-implemented-by EP-01-001
  - VP-07-011 is-implemented-by EP-03-001
- `VP-07-012` When the Sender proposes longer than the Receiver's default, the
  Receiver MAY accept or reject the proposed extension
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-012 is-implemented-by EP-01-001
  - VP-07-012 is-implemented-by EP-03-001
- `VP-07-013` When the Sender proposes shorter than the Receiver's default, the
  Sender MAY accept or reject the Receiver's proposed revision
  - Source: `docs/topics/process_models/em/defaults.md`
  - VP-07-013 is-implemented-by EP-01-001
  - VP-07-013 is-implemented-by EP-03-001

---

## Multi-Party Coordination (SHALL)

- `VP-08-001` When inviting a new Participant to a case with an existing embargo,
  the inviting Participant SHALL propose the existing embargo to the invited
  Participant
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - VP-08-001 is-implemented-by CM-06-001

## Multi-Party Coordination (SHOULD)

- `VP-08-002` Participants SHOULD attempt to establish an embargo as early in
  the process of handling the case as possible
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-003` Participants SHOULD follow consensus agreement to decide embargo
  terms
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-004` All known Vendors of affected software SHOULD be included as
  Participants
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-005` A newly invited Participant to a case with an existing embargo
  SHOULD accept the existing embargo
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-006` The inviting Participant SHOULD NOT share the vulnerability report
  with a newly invited Participant unless the new Participant has accepted the
  existing embargo
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-007` Participants with short default embargo policies SHOULD consider
  accepting longer embargoes in MPCVD cases
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-008` Potential Participants with a longer default policy than an
  existing case SHOULD accept the embargo terms offered
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-009` Participants in a case with an existing embargo SHOULD notify
  Vendors with a longer default embargo policy
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-010` Participants known to leak or provide vulnerability information to
  adversaries as a matter of policy or historical fact SHOULD be treated similar
  to Participants with brief disclosure policies
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec

## Multi-Party Coordination (MAY)

- `VP-08-011` When consensus fails to reach agreement on embargo terms,
  Participants MAY appoint a case lead to resolve conflicts
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-012` Participants MAY engage a third-party Coordinator to act as a
  neutral case lead to resolve conflicts between Participants
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-013` Third-party Coordinators MAY be included as Participants
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-014` Other parties MAY be included as Participants when necessary and
  appropriate
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-015` The inviting Participant MAY interpret a potential Participant's
  default embargo policy in accordance with default acceptance strategies
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-016` A newly invited Participant MAY propose a revision after accepting
  the existing embargo
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-017` Participants in an MPCVD case MAY delay notifying potential
  Participants with short default embargo policies until their policy aligns
  with the agreed embargo
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-018` After accepting an existing embargo, newly invited Participants
  with a longer default policy MAY propose a revision to accommodate their
  preferences
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-019` Existing Participants MAY accept or reject a proposed revision
  from a newly invited Participant
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-020` Participants in a case with an existing embargo MAY choose to
  extend the embargo to accommodate a newly added Participant
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-08-021` Participants MAY decline to participate in future CVD cases
  involving parties with a history of violating previous embargoes
  - Source: `docs/topics/process_models/em/working_with_others.md`
  - **Gap**: Not addressed by any current implementation spec

---

## Embargo Early Termination (SHALL)

- `VP-09-001` Embargoes SHALL terminate immediately when information about the
  vulnerability becomes public ($q^{cs} \in \{\cdots P \cdots, \cdots X \cdot\}$)
  - Source: `docs/topics/process_models/em/early_termination.md`
  - VP-09-001 is-implemented-by CM-04-003

## Embargo Early Termination (SHOULD)

- `VP-09-002` Participants SHOULD be prepared with contingency plans in the
  event of early embargo termination
  - Source: `docs/topics/process_models/em/early_termination.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-09-003` Embargoes SHOULD terminate early when there is evidence that the
  vulnerability is being actively exploited by adversaries
  ($q^{cs} \in \{\cdots A\}$)
  - Source: `docs/topics/process_models/em/early_termination.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-09-004` Embargoes SHOULD terminate early when there is evidence that
  adversaries possess exploit code for the vulnerability
  - Source: `docs/topics/process_models/em/early_termination.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-09-005` Participants SHOULD consider the software supply chain when
  determining an appropriate quorum of Vendors for release
  - Source: `docs/topics/process_models/em/early_termination.md`
  - **Gap**: Not addressed by any current implementation spec

## Embargo Early Termination (MAY)

- `VP-09-006` Embargoes MAY terminate early when there is evidence that
  adversaries are aware of the technical details of the vulnerability
  - Source: `docs/topics/process_models/em/early_termination.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-09-007` Embargoes MAY terminate early when a quorum of Vendor Participants
  is prepared to release fixes ($q^{cs} \in VF\cdots$), even if some Vendors
  remain unprepared
  - Source: `docs/topics/process_models/em/early_termination.md`
  - **Gap**: Not addressed by any current implementation spec

---

## Embargo Case Splits and Merges (SHALL)

- `VP-10-001` If no new embargo has been proposed or agreement has not been
  reached following a case merge, the earliest of the previously accepted
  embargo dates SHALL be adopted for the merged case
  - Source: `docs/topics/process_models/em/split_merge.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-10-002` If an earlier embargo date is needed for a child case following a
  case split, consideration SHALL be given to the impact that ending the embargo
  on that case will have on the other child cases retaining a later embargo date
  - Source: `docs/topics/process_models/em/split_merge.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-10-003` Participants in a child case SHALL communicate any subsequently
  agreed changes from the inherited embargo to the Participants of the other
  child cases
  - Source: `docs/topics/process_models/em/split_merge.md`
  - **Gap**: Not addressed by any current implementation spec

## Embargo Case Splits and Merges (SHOULD)

- `VP-10-004` A new embargo SHOULD be proposed when any two or more CVD cases
  are to be merged and multiple parties have agreed to different embargo terms
  prior to the merger
  - Source: `docs/topics/process_models/em/split_merge.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-10-005` When a case is split into two or more parts, any existing embargo
  SHOULD transfer to the new cases
  - Source: `docs/topics/process_models/em/split_merge.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-10-006` If any of the new cases need to renegotiate the embargo inherited
  from the parent case, any new embargo SHOULD be later than the inherited
  embargo
  - Source: `docs/topics/process_models/em/split_merge.md`
  - **Gap**: Not addressed by any current implementation spec

## Embargo Case Splits and Merges (MAY)

- `VP-10-007` Participants MAY propose revisions to the embargo on a merged case
  as usual
  - Source: `docs/topics/process_models/em/split_merge.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-10-008` Participants approaching a case split MAY engage a Coordinator to
  act as a trusted third party to help resolve and coordinate embargo
  dependencies for the new cases
  - Source: `docs/topics/process_models/em/split_merge.md`
  - **Gap**: Not addressed by any current implementation spec

---

## EM Messaging (SHALL)

- `VP-11-001` Participants SHALL NOT negotiate embargoes where the vulnerability
  or its exploit is public or attacks are known to have occurred
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-11-001 is-implemented-by CM-04-003
  - VP-11-001 is-implemented-by CM-04-004
- `VP-11-002` If information about the vulnerability or an exploit has been made
  public, Participants SHALL terminate the embargo
  ($q^{cs} \in \{\cdots P \cdots, \cdots X \cdot\}$)
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-11-002 is-implemented-by CM-04-003
  - VP-11-002 is-implemented-by CM-04-004
- `VP-11-003` Participants SHALL initiate embargo termination upon becoming aware
  of publicly available information about the vulnerability or its exploit code
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-11-003 is-implemented-by CM-04-003
  - VP-11-003 is-implemented-by CM-04-004

## EM Messaging (SHOULD)

- `VP-11-004` Participants SHOULD send $EK$ in acknowledgment of any other $E*$
  message except $EK$ itself
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-11-004 is-implemented-by RF-08-001
- `VP-11-005` Participants SHOULD acknowledge ($EK$) and inquire ($GI$) about
  the nature of any error reported by an incoming $EE$ message
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-11-005 is-implemented-by RF-05-001
  - VP-11-005 is-implemented-by RF-08-001
- `VP-11-006` If attacks are known to have occurred, Participants SHOULD
  terminate the embargo ($q^{cs} \in \cdots A$)
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-11-006 is-implemented-by CM-04-003
  - VP-11-006 is-implemented-by CM-04-004
- `VP-11-007` Participants SHOULD initiate embargo termination upon becoming
  aware of attacks against an otherwise unpublished vulnerability
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-11-007 is-implemented-by CM-04-003
  - VP-11-007 is-implemented-by CM-04-004
- `VP-11-008` If early embargo termination is desired but the termination
  date/time is in the future, this SHOULD be achieved through an Embargo
  Revision Proposal and additional communication
  - Source: `docs/reference/formal_protocol/messages.md`
  - **Gap**: Not addressed by any current implementation spec

## EM Messaging (MAY)

- `VP-11-009` Participants MAY begin embargo negotiations before sending the
  report itself in an $RS$ message; therefore it is not an error for an $E*$
  message to arrive while the Recipient is unaware of the report
  ($q^{rm} \in S$)
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-11-009 is-implemented-by CM-04-003
- `VP-11-010` Participants MAY reject any embargo proposals or revisions for any
  reason
  - Source: `docs/reference/formal_protocol/transitions.md`
  - VP-11-010 is-implemented-by CM-04-003

---

## CVD Case State (CS) Messaging (SHOULD)

- `VP-12-001` Vendor Awareness ($CV$) messages SHOULD be sent only by
  Participants with direct knowledge of the notification (i.e., either the
  Participant who sent the report to the Vendor or the Vendor upon receipt of
  the report)
  - Source: `docs/reference/formal_protocol/messages.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-12-002` Once attacks have been observed, fix development SHOULD
  accelerate, the embargo teardown process SHOULD begin, and publication and
  deployment SHOULD follow as soon as is practical
  - Source: `docs/topics/process_models/cs/transitions.md`
  - **Gap**: Not addressed by any current implementation spec

---

## RM-EM Interactions (SHOULD)

- `VP-13-001` The EM process SHOULD begin when a recipient is in RM Received
  ($q^{rm} \in R$) whenever possible
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-001 is-implemented-by CM-03-001
  - VP-13-001 is-implemented-by CM-03-003
- `VP-13-002` Embargo Management SHOULD NOT begin in an inactive RM state
  ($q^{rm} \in \{I, D, C\}$)
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-002 is-implemented-by CM-04-003
- `VP-13-003` Embargo Management SHOULD NOT begin with a proposal from a
  Participant in RM Invalid ($q^{rm} \in I$)
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-003 is-implemented-by CM-04-003
- `VP-13-004` Embargo Management SHOULD NOT proceed from EM Proposed to EM
  Accepted when RM is Invalid or Closed ($q^{rm} \in \{I, C\}$)
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-004 is-implemented-by CM-04-003
  - VP-13-004 is-implemented-by CM-04-001
- `VP-13-005` Participants SHOULD NOT close reports
  ($q^{rm} \in \{I,D,A\} \xrightarrow{c} C$) while an embargo is active
  ($q^{em} \in \{A, R\}$)
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-005 is-implemented-by CM-04-001
  - VP-13-005 is-implemented-by CM-04-003
- `VP-13-006` Reports with no further tasks SHOULD be held in Deferred or
  Invalid ($q^{rm} \in \{D, I\}$) until the embargo has terminated
  ($q^{em} \in X$)
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-006 is-implemented-by CM-04-001
  - VP-13-006 is-implemented-by CM-04-003
- `VP-13-007` Participants who choose to close a report while an embargo remains
  in force SHOULD communicate their intent to either continue to adhere to the
  embargo or terminate their compliance with it
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-007 is-implemented-by CM-06-001
- `VP-13-008` Any changes to a Participant's intention to adhere to an active
  embargo SHOULD be communicated clearly in addition to any necessary RM or EM
  state change notifications
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-008 is-implemented-by CM-06-001

## RM-EM Interactions (SHALL NOT)

- `VP-13-009` A Participant's closure or deferral ($q^{rm} \in \{C, D\}$) of a
  report while an embargo remains active ($q^{em} \in \{A, R\}$) and while
  other Participants remain engaged SHALL NOT automatically terminate the embargo
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-009 is-implemented-by CM-03-003
  - VP-13-009 is-implemented-by CM-04-005

## RM-EM Interactions (MAY)

- `VP-13-010` The EM process MAY begin prior to the report being sent to a
  potential Participant ($q^{rm} \in S$)
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-010 is-implemented-by CM-03-001
  - VP-13-010 is-implemented-by CM-03-003
  - VP-13-010 is-implemented-by CM-04-003
- `VP-13-011` Embargo Management MAY begin in any of the active RM states
  ($q^{rm} \in \{R, V, A\}$)
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-011 is-implemented-by CM-03-001
  - VP-13-011 is-implemented-by CM-03-003
  - VP-13-011 is-implemented-by CM-04-003
- `VP-13-012` Embargo Management MAY run in parallel to validation
  ($q^{rm} \in \{R,I\} \xrightarrow{\{v,i\}} \{V,I\}$) and prioritization
  ($q^{rm} \in V \xrightarrow{\{a,d\}} \{A,D\}$) activities
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-012 is-implemented-by CM-03-001
  - VP-13-012 is-implemented-by CM-03-003
  - VP-13-012 is-implemented-by CM-04-003
- `VP-13-013` EM revision proposals and acceptance or rejection of those
  proposals MAY occur during any of the valid yet unclosed RM states
  ($q^{rm} \in \{V, A, D\}$)
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-013 is-implemented-by CM-03-001
  - VP-13-013 is-implemented-by CM-03-003
  - VP-13-013 is-implemented-by CM-04-003
- `VP-13-014` Outstanding embargo negotiations ($q^{em} \in P$) MAY continue in
  RM Invalid ($q^{rm} \in I$) if additional information may be forthcoming to
  promote the report from Invalid to Valid
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-014 is-implemented-by CM-03-001
  - VP-13-014 is-implemented-by CM-03-003
  - VP-13-014 is-implemented-by CM-04-003
- `VP-13-015` Embargo Management MAY proceed from EM Proposed to EM Accepted
  when RM is neither Invalid nor Closed ($q^{rm} \in \{R, V, A, D\}$)
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-015 is-implemented-by CM-03-001
  - VP-13-015 is-implemented-by CM-03-003
  - VP-13-015 is-implemented-by CM-04-003
- `VP-13-016` Embargo Management MAY proceed from EM Proposed to EM None
  ($q^{em} \in P \xrightarrow{r} N$) when RM is Invalid or Closed
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-016 is-implemented-by CM-03-001
  - VP-13-016 is-implemented-by CM-03-003
  - VP-13-016 is-implemented-by CM-04-003
- `VP-13-017` Participants MAY choose to terminate their compliance with an
  embargo at any time
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-017 is-implemented-by CM-03-001
  - VP-13-017 is-implemented-by CM-03-003
  - VP-13-017 is-implemented-by CM-04-003
- `VP-13-018` Upon receipt of a Participant's notification of intent to end
  their compliance with an embargo, other Participants MAY choose to terminate
  the embargo
  - Source: `docs/topics/process_models/model_interactions/rm_em.md`
  - VP-13-018 is-implemented-by CM-03-001
  - VP-13-018 is-implemented-by CM-03-003
  - VP-13-018 is-implemented-by CM-04-003

---

## RM-EM-CS Interactions (SHALL NOT)

- `VP-14-001` Once Public Awareness has happened ($q^{cs} \in \cdots P \cdots$),
  new embargoes SHALL NOT be sought and any existing embargo SHALL terminate
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-001 is-implemented-by CM-04-003
  - VP-14-001 is-implemented-by CM-04-004
- `VP-14-002` Once Exploit Publication has occurred
  ($q^{cs} \in \cdots X \cdot$), new embargoes SHALL NOT be sought and any
  existing embargo SHALL terminate
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-002 is-implemented-by CM-04-003
  - VP-14-002 is-implemented-by CM-04-004
- `VP-14-003` Once Attacks have been observed ($q^{cs} \in \cdots A$), new
  embargoes SHALL NOT be sought
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-003 is-implemented-by CM-04-004

## RM-EM-CS Interactions (MUST)

- `VP-14-004` Participants MUST treat attacks as an event that could occur at
  any time and adapt their process as needed in light of available information
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-004 is-implemented-by CM-04-004

## RM-EM-CS Interactions (SHOULD)

- `VP-14-005` Once a case has reached Vendor Aware ($q^{cs} \in Vfdpxa$) for at
  least one Vendor, if the EM process has not started, it SHOULD begin as soon
  as possible
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-005 is-implemented-by CM-04-003
- `VP-14-006` Any proposed embargo SHOULD be decided (accept or reject) soon
  after the first Vendor is notified
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-006 is-implemented-by CM-04-003
- `VP-14-007` Once a case has reached Fix Ready ($q^{cs} \in VF\cdot pxa$), new
  embargo negotiations SHOULD NOT start and proposed but not-yet-agreed-to
  embargoes SHOULD be rejected
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-007 is-implemented-by CM-04-003
- `VP-14-008` Existing embargoes ($q^{em} \in \{Active, Revise\}$) when Fix
  Ready is reached SHOULD prepare to terminate soon
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-008 is-implemented-by CM-04-003
- `VP-14-009` Participants SHOULD accept reasonable extension proposals to allow
  trailing Vendors to catch up before publication when possible
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-14-010` By the time a fix has been deployed ($q^{cs} \in VFD\cdots$), new
  embargoes SHOULD NOT be sought and any existing embargo SHOULD terminate
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-010 is-implemented-by CM-04-003
- `VP-14-011` Exploit Publishers who are Participants in pre-public CVD cases
  ($q^{cs} \in \cdots p \cdots$) SHOULD comply with the protocol, especially
  when they also fulfill other roles (e.g., Finder, Reporter, Coordinator,
  Vendor)
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-14-012` Exploit Publishers SHOULD NOT release exploit code while an
  embargo is active ($q^{em} \in \{A, R\}$)
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - **Gap**: Not addressed by any current implementation spec
- `VP-14-013` Once Attacks have been observed ($q^{cs} \in \cdots A$), any
  existing embargo SHOULD terminate
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - VP-14-013 is-implemented-by CM-04-003
  - VP-14-013 is-implemented-by CM-04-004

## RM-EM-CS Interactions (MAY)

- `VP-14-014` In MPCVD cases where some Vendors reach Fix Ready before others,
  Participants MAY propose an embargo extension to allow trailing Vendors to
  catch up before publication
  - Source: `docs/topics/process_models/model_interactions/rm_em_cs.md`
  - **Gap**: Not addressed by any current implementation spec

---

## Implementation Guidance (SHOULD)

- `VP-15-001` Vultron Protocol messages SHOULD use well-defined format
  specifications (e.g., JSON Schema, protobuf, XSD)
  - Source: `docs/howto/general_implementation.md`
  - VP-15-001 is-implemented-by MV-02-001
- `VP-15-002` `PROD_ONLY` Vultron Protocol implementations SHOULD use common
  API patterns (e.g., REST, WebSockets) for inter-participant communication
  - Source: `docs/howto/general_implementation.md`
  - **See also**: `specs/http-protocol.md`
- `VP-15-003` `PROD_ONLY` Vultron Protocol implementations SHOULD use
  transport-layer encryption to protect sensitive data in transit
  - Source: `docs/howto/general_implementation.md`
  - VP-15-003 is-implemented-by ENC-01-001
  - VP-15-003 is-implemented-by ENC-02-001
  - VP-15-003 is-implemented-by ENC-03-001

## Implementation Guidance (MAY)

- `VP-15-004` `PROD_ONLY` Vultron Protocol implementations MAY use end-to-end
  encryption to protect sensitive data in transit
  - Source: `docs/howto/general_implementation.md`
  - VP-15-004 is-implemented-by ENC-02-001
  - VP-15-004 is-implemented-by ENC-02-002
- `VP-15-005` `PROD_ONLY` Vultron Protocol implementations MAY use encryption
  to protect sensitive data at rest
  - Source: `docs/howto/general_implementation.md`
  - **Gap**: Not addressed by any current implementation spec

---

## Embargo Representation Privacy (MUST NOT)

- `VP-16-001` Vulnerability details MUST NOT appear in embargo representation
  data (e.g., embargo scheduling or notification messages)
  - Source: `docs/howto/em_icalendar.md`
  - **Note**: Extracted as a general privacy principle; iCalendar is no longer
    the target format
  - VP-16-001 is-implemented-by MV-05-001
  - VP-16-001 is-implemented-by MV-05-002

## Embargo Representation Privacy (SHOULD)

- `VP-16-002` A case or vulnerability identifier SHOULD appear in embargo
  representation data along with an indication that it relates to an embargo
  expiration
  - Source: `docs/howto/em_icalendar.md`
  - VP-16-002 is-implemented-by OID-01-001
- `VP-16-003` Case or vulnerability identifiers SHOULD NOT carry any information
  that reveals potentially sensitive details about the vulnerability
  - Source: `docs/howto/em_icalendar.md`
  - VP-16-003 is-implemented-by OID-01-001
