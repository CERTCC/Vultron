# User Story Traceability Matrix

This document maps user stories from `docs/reference/user_stories/` to formal
requirements in `specs/`. It is a **traceability reference**, not a
requirements document. User stories capture stakeholder intent; the
requirements in `specs/` specify system behaviour.

Stories are grouped by theme. Each story entry lists the mapped spec
requirements with a brief traceability note. Stories with no clear mapping
to an existing requirement are marked *No mapped requirements*.

Source user stories: `docs/reference/user_stories/story_2022_NNN.md`
Source specifications: `specs/*.yaml`

<!-- EDITOR NOTES (for anyone hand-editing the section tables below):
  1. Each section is an HTML <table> so that a story addressed by several specs
     can rowspan the story cells. For md_in_html to process the markdown links
     inside cells, the `markdown` attribute MUST be present on EVERY level of
     the table (table -> thead/tbody -> tr, then markdown="span" on each td).
     Drop it from any level and that subtree's links silently render as raw
     text — and broken anchors in raw text are NOT caught by the strict build.
  2. Spec IDs link to the requirement's GROUP anchor on its tier page, e.g.
     `../specs/protocol.md#vp-02` for VP-02-001. The strict link check only
     knows heading anchors, so never link a per-requirement `#vp-02-001` (see
     mkdocs.yml `validation.links.anchors`). The tier page (protocol /
     architecture / project / process) is the requirement's `kind` in the
     spec registry, not its source `.yaml` file. -->

---

## Table of Contents

| Section | Line | Stories | Theme |
|---------|------|---------|-------|
| [1. Vulnerability Reporting](#1-vulnerability-reporting) | ~47 | 001–020 | Report submission, reception, validation, tracking |
| [2. Policy Discovery and Management](#2-policy-discovery-and-management) | ~214 | 021–030 | Disclosure policies, policy publication and lookup |
| [3. Embargo Management](#3-embargo-management) | ~393 | 031–050 | Embargo proposals, negotiation, termination |
| [4. Case Management and Participant Roles](#4-case-management-and-participant-roles) | ~576 | 051–080 | Case creation, participants, coordinators, roles |
| [5. Actor Identity, Privacy, and Security](#5-actor-identity-privacy-and-security) | ~1013 | 081–090 | Actor registration, identity, privacy constraints |
| [6. Communication and Messaging](#6-communication-and-messaging) | ~1216 | 091–100 | Inbox/outbox, notifications, acknowledgements |
| [7. Publication and Disclosure](#7-publication-and-disclosure) | ~1457 | 101–106 | Coordinated publication, advisories, disclosure timing |
| [8. Bug Bounty and Incentives](#8-bug-bounty-and-incentives) | ~1708 | 107–109 | Bug bounty programs and incentives |
| [9. Prioritization, Assessment, and Fix Verification](#9-prioritization-assessment-and-fix-verification) | ~1763 | 110–111 | SSVC scoring, fix readiness |

---

## 1. Vulnerability Reporting

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>User Story ID</th>
<th>Story text</th>
<th>Spec ID</th>
<th>Spec detail</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_001](story_2022_001.md)</td>
<td rowspan="4" markdown="span">As a Finder, discover how to report a vulnerability</td>
<td markdown="span">[VP-02-001](../specs/protocol.md#vp-02)</td>
<td markdown="span">Coordinators MUST have a clearly defined and publicly available policy — intake discovery.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-005](../specs/protocol.md#vp-02)</td>
<td markdown="span">Vendors SHOULD have a clearly defined and publicly available policy — intake discovery.</td>
</tr>
<tr markdown="1">
<td markdown="span">[IE-02-001](../specs/protocol.md#ie-02)</td>
<td markdown="span">The endpoint URL MUST be discoverable from actor profile — system support for finding intake.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-001](../specs/protocol.md#ep-01)</td>
<td markdown="span">An Actor profile MAY include an `embargo_policy` field — policy discovery mechanism.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_002](story_2022_002.md)</td>
<td rowspan="4" markdown="span">As a Participant, receive reports submitted via platform</td>
<td markdown="span">[VP-03-001](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants MUST be in RM Accepted to send a Report Submission — pre-condition for receipt.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-002](../specs/protocol.md#vp-03)</td>
<td markdown="span">Vendor Recipients receiving a new Report Submission MUST process it — receiving obligation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[IE-02-002](../specs/protocol.md#ie-02)</td>
<td markdown="span">The endpoint MUST accept POST requests only — HTTP intake for report submission.</td>
</tr>
<tr markdown="1">
<td markdown="span">[HP-00-001](../specs/protocol.md#hp-00)</td>
<td markdown="span">Handlers MUST interpret received activities as assertions about the sender's state — semantics of receipt.</td>
</tr>
<tr markdown="1">
<td rowspan="6" markdown="span">[story_2022_012](story_2022_012.md)</td>
<td rowspan="6" markdown="span">As a Participant, report a new vulnerability</td>
<td markdown="span">[VP-02-015](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants SHOULD create a case from reports entering the Valid state — report-to-case transition.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-001](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants MUST be in RM Accepted to send a Report Submission — submission precondition.</td>
</tr>
<tr markdown="1">
<td markdown="span">[MV-01-001](../specs/protocol.md#mv-01)</td>
<td markdown="span">Incoming payloads MUST conform to ActivityStreams 2.0 structure — message format for report submission.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VAM-02-002](../specs/protocol.md#vam-02)</td>
<td markdown="span">`SUBMIT_REPORT` MUST be represented as `Offer(VulnerabilityReport)` — submission wire mapping.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VAM-02-004](../specs/protocol.md#vam-02)</td>
<td markdown="span">`VALIDATE_REPORT` MUST be represented as `Accept(Offer(VulnerabilityReport))` — validation result.</td>
</tr>
<tr markdown="1">
<td markdown="span">[IE-02-002](../specs/protocol.md#ie-02)</td>
<td markdown="span">The endpoint MUST accept POST requests only — HTTP entry point for report.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_038](story_2022_038.md)</td>
<td rowspan="4" markdown="span">As a vendor or coordinator, receive vulnerability reports</td>
<td markdown="span">[VP-03-002](../specs/protocol.md#vp-03)</td>
<td markdown="span">Vendor Recipients receiving a new Report Submission MUST process it — receiving obligation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[IE-02-002](../specs/protocol.md#ie-02)</td>
<td markdown="span">The endpoint MUST accept POST requests only — HTTP intake.</td>
</tr>
<tr markdown="1">
<td markdown="span">[MV-01-001](../specs/protocol.md#mv-01)</td>
<td markdown="span">Incoming payloads MUST conform to ActivityStreams 2.0 structure — validation on receipt.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-001](../specs/protocol.md#vp-02)</td>
<td markdown="span">Coordinators MUST have a clearly defined and publicly available policy — intake advertised.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_077](story_2022_077.md)</td>
<td rowspan="3" markdown="span">As a Participant, ask further questions about a report</td>
<td markdown="span">[VP-02-025](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants MAY perform a more technical report validation process — allows follow-up inquiry.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-008](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD send RE regardless of state when any error occurs — error/inquiry path.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-011](../specs/protocol.md#vp-03)</td>
<td markdown="span">Recipients SHOULD acknowledge RE messages and inquire about the error — bidirectional inquiry.</td>
</tr>
<tr markdown="1">
<td rowspan="6" markdown="span">[story_2022_101](story_2022_101.md)</td>
<td rowspan="6" markdown="span">As a Coordinator, validate the report before engaging</td>
<td markdown="span">[VP-02-006](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants SHOULD subject each Received report to a validation process — validation obligation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-007](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants SHOULD have a clearly defined process for validating reports — process definition.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-009](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants SHOULD proceed only after validating the reports they receive — gating.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-025](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants MAY perform a more technical report validation process — technical validation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-003](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD send RI when the report validation process determines invalid — send result.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-004](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD send RV when the report validation process determines valid — send result.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_102](story_2022_102.md)</td>
<td rowspan="3" markdown="span">As a Coordinator, collect artifacts (PoC, analysis)</td>
<td markdown="span">[VP-02-025](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants MAY perform a more technical report validation process — artifact collection.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-028](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants MAY choose to perform a shallow technical analysis on the reported vulnerability.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-05-002](../specs/protocol.md#cm-05)</td>
<td markdown="span">A VulnerabilityCase MUST reference at least one VulnerabilityReport — case ties to report artifacts.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_111](story_2022_111.md)</td>
<td rowspan="4" markdown="span">As a Vendor, identify which products are affected</td>
<td markdown="span">[VP-02-011](../specs/protocol.md#vp-02)</td>
<td markdown="span">Once a Vendor confirms that a reported vulnerability affects one or more products — acknowledgment.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-015](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants SHOULD create a case from reports entering the Valid state — per-product case creation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-025](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants MAY perform more technical report validation — scope analysis.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-05-006](../specs/protocol.md#cm-05)</td>
<td markdown="span">One report MAY describe multiple vulnerabilities; one case MAY cover multiple reports — model support.</td>
</tr>
</tbody>
</table>

## 2. Policy Discovery and Management

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>User Story ID</th>
<th>Story text</th>
<th>Spec ID</th>
<th>Spec detail</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_003](story_2022_003.md)</td>
<td rowspan="4" markdown="span">As a Participant, discover others' policies</td>
<td markdown="span">[VP-02-001](../specs/protocol.md#vp-02)</td>
<td markdown="span">Coordinators MUST have a clearly defined and publicly available policy — policy discoverability.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-005](../specs/protocol.md#vp-02)</td>
<td markdown="span">Vendors SHOULD have a clearly defined and publicly available policy — policy discoverability.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-001](../specs/protocol.md#ep-01)</td>
<td markdown="span">An Actor profile MAY include an `embargo_policy` field — machine-readable policy on actor profile.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-02-001](../specs/protocol.md#ep-02)</td>
<td markdown="span">Each Actor SHOULD expose its embargo policy at a well-known endpoint (`PROD_ONLY`) — policy endpoint.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_004](story_2022_004.md)</td>
<td rowspan="4" markdown="span">As a Participant, parse and evaluate others' policies</td>
<td markdown="span">[EP-01-002](../specs/protocol.md#ep-01)</td>
<td markdown="span">The embargo policy record MUST include specified fields — machine-parseable structure.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-003](../specs/protocol.md#ep-01)</td>
<td markdown="span">The embargo policy record SHOULD include additional fields — richer parseable structure.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-004](../specs/protocol.md#ep-01)</td>
<td markdown="span">The embargo policy record MUST be serializable as a Pydantic model — programmatic parsing support.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-07-001](../specs/protocol.md#vp-07)</td>
<td markdown="span">If neither Sender nor Receiver proposes an embargo and no policy — default policy evaluation.</td>
</tr>
<tr markdown="1">
<td rowspan="5" markdown="span">[story_2022_005](story_2022_005.md)</td>
<td rowspan="5" markdown="span">As a Participant, optimize all of the policies involved</td>
<td markdown="span">[VP-07-003](../specs/protocol.md#vp-07)</td>
<td markdown="span">If the Receiver has declared a default embargo, use it — policy reconciliation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-07-004](../specs/protocol.md#vp-07)</td>
<td markdown="span">If the Sender proposes an embargo longer than the Receiver's default — negotiation rule.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-07-005](../specs/protocol.md#vp-07)</td>
<td markdown="span">If the Sender proposes an embargo shorter than the Receiver's default — negotiation rule.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-03-001](../specs/protocol.md#ep-03)</td>
<td markdown="span">Before proposing an embargo, retrieve potential Participant's policy (`PROD_ONLY`) — pre-proposal.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-03-002](../specs/protocol.md#ep-03)</td>
<td markdown="span">Compatibility evaluation MUST check that policy fields are compatible (`PROD_ONLY`) — compatibility check.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_006](story_2022_006.md)</td>
<td rowspan="4" markdown="span">As a Participant, decide if I will/can engage</td>
<td markdown="span">[VP-02-006](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants SHOULD subject each Received report to a validation process — engagement gating.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-014](../specs/protocol.md#vp-02)</td>
<td markdown="span">For Valid reports, the Participant SHOULD perform a prioritization step — engagement decision.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-016](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants SHOULD have a bias toward accepting rather than deferring — acceptance policy.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-021](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants SHOULD act in accordance with their own policy and the policies of others.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_007](story_2022_007.md)</td>
<td rowspan="3" markdown="span">As a Participant, flag when policy trouble is detected</td>
<td markdown="span">[VP-03-008](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD send RE regardless of state when any error occurs — error signal.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-11-002](../specs/protocol.md#vp-11)</td>
<td markdown="span">If information about the vulnerability has been made public, initiate embargo termination.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-06-001](../specs/protocol.md#vp-06)</td>
<td markdown="span">CVD Participants MUST NOT propose or accept a new embargo in specific states — constraint flag.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_008](story_2022_008.md)</td>
<td rowspan="3" markdown="span">As a Participant, warn Participants, invoke other channels</td>
<td markdown="span">[VP-03-008](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD send RE when any error occurs — error notification.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-11-003](../specs/protocol.md#vp-11)</td>
<td markdown="span">Participants SHALL initiate embargo termination upon becoming aware of exploitation — escalation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-11-005](../specs/protocol.md#vp-11)</td>
<td markdown="span">Participants SHOULD acknowledge and inquire about unexpected embargo state changes.</td>
</tr>
<tr markdown="1">
<td rowspan="5" markdown="span">[story_2022_009](story_2022_009.md)</td>
<td rowspan="5" markdown="span">As a Participant, post/advertise my policy</td>
<td markdown="span">[VP-02-001](../specs/protocol.md#vp-02)</td>
<td markdown="span">Coordinators MUST have a clearly defined and publicly available policy — publication obligation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-005](../specs/protocol.md#vp-02)</td>
<td markdown="span">Vendors SHOULD have a clearly defined and publicly available policy — publication recommendation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-07-006](../specs/protocol.md#vp-07)</td>
<td markdown="span">Report Recipients SHOULD post a default embargo period as part of their policy — embargo policy post.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-001](../specs/protocol.md#ep-01)</td>
<td markdown="span">An Actor profile MAY include an `embargo_policy` field — machine-readable policy on profile.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-02-001](../specs/protocol.md#ep-02)</td>
<td markdown="span">Each Actor SHOULD expose its embargo policy at a well-known endpoint (`PROD_ONLY`) — policy endpoint.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_021](story_2022_021.md)</td>
<td rowspan="3" markdown="span">As a Participant, advertise locale aspects of policy</td>
<td markdown="span">[EP-01-002](../specs/protocol.md#ep-01)</td>
<td markdown="span">The embargo policy record MUST include specified fields — locale/scope fields in policy.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-003](../specs/protocol.md#ep-01)</td>
<td markdown="span">The embargo policy record SHOULD include additional optional fields — extended locale fields.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-001](../specs/protocol.md#vp-02)</td>
<td markdown="span">Coordinators MUST have a clearly defined and publicly available policy — policy publication.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_022](story_2022_022.md)</td>
<td rowspan="3" markdown="span">As a Participant, advertise scope of CVD capability</td>
<td markdown="span">[VP-02-001](../specs/protocol.md#vp-02)</td>
<td markdown="span">Coordinators MUST have a clearly defined and publicly available policy — scope in policy.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-005](../specs/protocol.md#vp-02)</td>
<td markdown="span">Vendors SHOULD have a clearly defined and publicly available policy — scope in policy.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-002](../specs/protocol.md#ep-01)</td>
<td markdown="span">The embargo policy record MUST include required fields — structured scope definition.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_076](story_2022_076.md)</td>
<td rowspan="2" markdown="span">As a VDP operator, want protocol to support VDP</td>
<td markdown="span">[VP-02-001](../specs/protocol.md#vp-02)</td>
<td markdown="span">Coordinators MUST have a clearly defined and publicly available policy — VDP policy expression.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-001](../specs/protocol.md#ep-01)</td>
<td markdown="span">An Actor profile MAY include an `embargo_policy` field — policy field applicable to VDP operators.</td>
</tr>
</tbody>
</table>

## 3. Embargo Management

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>User Story ID</th>
<th>Story text</th>
<th>Spec ID</th>
<th>Spec detail</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td rowspan="5" markdown="span">[story_2022_010](story_2022_010.md)</td>
<td rowspan="5" markdown="span">As a Participant, publish/share embargo dates</td>
<td markdown="span">[VP-04-003](../specs/protocol.md#vp-04)</td>
<td markdown="span">An embargo MAY be proposed — initial proposal mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-04-004](../specs/protocol.md#vp-04)</td>
<td markdown="span">Once proposed, an embargo MAY be accepted or rejected — acceptance/rejection workflow.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-001](../specs/protocol.md#vp-05)</td>
<td markdown="span">An embargo SHALL specify an unambiguous date and time — date specification requirement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-07-006](../specs/protocol.md#vp-07)</td>
<td markdown="span">Report Recipients SHOULD post a default embargo period as part of their policy — default sharing.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-002](../specs/protocol.md#ep-01)</td>
<td markdown="span">The embargo policy record MUST include specified fields — structured date fields.</td>
</tr>
<tr markdown="1">
<td rowspan="5" markdown="span">[story_2022_014](story_2022_014.md)</td>
<td rowspan="5" markdown="span">As a Participant, negotiate and renegotiate embargo schedules</td>
<td markdown="span">[VP-04-001](../specs/protocol.md#vp-04)</td>
<td markdown="span">Accepted embargoes MUST eventually terminate — termination requirement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-04-003](../specs/protocol.md#vp-04)</td>
<td markdown="span">An embargo MAY be proposed — initial proposal.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-04-005](../specs/protocol.md#vp-04)</td>
<td markdown="span">Once accepted, revisions MAY be proposed — renegotiation mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-06-004](../specs/protocol.md#vp-06)</td>
<td markdown="span">Participants SHOULD explicitly accept or reject embargo proposals — explicit negotiation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-06-005](../specs/protocol.md#vp-06)</td>
<td markdown="span">Participants SHOULD make reasonable attempts to retry embargo negotiations.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_023](story_2022_023.md)</td>
<td rowspan="4" markdown="span">As a Participant, constrain communication to enforce embargo</td>
<td markdown="span">[VP-05-006](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo Participants SHOULD NOT knowingly release embargo information — information restriction.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-007](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo participation SHOULD be limited to the smallest possible set — access restriction.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-006](../specs/protocol.md#vp-08)</td>
<td markdown="span">The inviting Participant SHOULD NOT share the vulnerability report without embargo — need-to-know.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-16-001](../specs/protocol.md#vp-16)</td>
<td markdown="span">Vulnerability details MUST NOT appear in embargo representation — separation of concerns.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_024](story_2022_024.md)</td>
<td rowspan="2" markdown="span">As a Finder/Reporter, constrain communication for anonymity</td>
<td markdown="span">[VP-08-017](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants in an MPCVD case MAY delay notifying potential Participants — controlled disclosure.</td>
</tr>
<tr markdown="1">
<td markdown="span">—</td>
<td markdown="span">*No further mapped requirements* (reporter anonymity has no direct requirement in current specs).</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_025](story_2022_025.md)</td>
<td rowspan="3" markdown="span">As a Vendor/Deployer, constrain until patch published</td>
<td markdown="span">[VP-05-006](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo Participants SHOULD NOT knowingly release information — pre-patch restriction.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-014](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants SHOULD NOT publish information before embargo terminates.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-14-007](../specs/protocol.md#vp-14)</td>
<td markdown="span">Once Fix Ready, new embargoes have reduced scope — fix-ready transition.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_026](story_2022_026.md)</td>
<td rowspan="3" markdown="span">As a Coordinator, constrain communication within embargo</td>
<td markdown="span">[VP-05-006](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo Participants SHOULD NOT knowingly release information — coordinator obligation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-006](../specs/protocol.md#vp-08)</td>
<td markdown="span">The inviting Participant SHOULD NOT share the vulnerability report — need-to-know enforcement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-007](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo participation SHOULD be limited to the smallest possible set — minimal disclosure.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_027](story_2022_027.md)</td>
<td rowspan="3" markdown="span">As a Participant, address Participants constraints/entity lists</td>
<td markdown="span">[VP-05-013](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants SHOULD consider other Participants' history of embargo compliance — reputation check.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-010](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants known to leak information SHOULD be excluded from embargoes — exclusion mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-021](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants MAY decline to participate in future CVD cases with known leakers.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_078](story_2022_078.md)</td>
<td rowspan="3" markdown="span">As a coordinator, drive better/shorter embargo timelines</td>
<td markdown="span">[VP-05-008](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo duration SHOULD be limited to the shortest duration feasible — coordinator goal.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-009](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargoes SHOULD be of short duration, from a few days to a few months — target range.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-003](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants SHOULD follow consensus agreement to decide embargo terms — coordinator drives.</td>
</tr>
<tr markdown="1">
<td rowspan="5" markdown="span">[story_2022_079](story_2022_079.md)</td>
<td rowspan="5" markdown="span">As a coordinator, collect and optimize embargo timelines</td>
<td markdown="span">[VP-07-001](../specs/protocol.md#vp-07)</td>
<td markdown="span">If no embargo policy and no proposal — default determination rule.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-07-003](../specs/protocol.md#vp-07)</td>
<td markdown="span">If Receiver has a default embargo, use it as the starting point.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-07-004](../specs/protocol.md#vp-07)</td>
<td markdown="span">If Sender proposes longer than Receiver's default — negotiation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-07-005](../specs/protocol.md#vp-07)</td>
<td markdown="span">If Sender proposes shorter than Receiver's default — negotiation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-003](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants SHOULD follow consensus agreement to decide embargo terms.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_080](story_2022_080.md)</td>
<td rowspan="4" markdown="span">As a Participant, disclose sooner but minimize others' risk</td>
<td markdown="span">[VP-05-020](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants MAY publish information when embargo terminates — publish timing.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-14-011](../specs/protocol.md#vp-14)</td>
<td markdown="span">Exploit Publishers who are Participants in pre-public CVD cases MUST notify others.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-14-012](../specs/protocol.md#vp-14)</td>
<td markdown="span">Exploit Publishers SHOULD NOT release exploit code while an embargo is active.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-14-014](../specs/protocol.md#vp-14)</td>
<td markdown="span">In MPCVD cases where some Vendors reach Fix Ready before others — staggered disclosure.</td>
</tr>
</tbody>
</table>

## 4. Case Management and Participant Roles

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>User Story ID</th>
<th>Story text</th>
<th>Spec ID</th>
<th>Spec detail</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_013](story_2022_013.md)</td>
<td rowspan="4" markdown="span">As a Participant, add a Participant (de-duplicate)</td>
<td markdown="span">[VP-08-001](../specs/protocol.md#vp-08)</td>
<td markdown="span">When inviting a new Participant to a case with an existing embargo — invite protocol.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors of affected software SHOULD be included — inclusion obligation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-013](../specs/protocol.md#vp-08)</td>
<td markdown="span">Third-party Coordinators MAY be included as Participants — multi-party inclusion.</td>
</tr>
<tr markdown="1">
<td markdown="span">[ID-01-001](../specs/architecture.md#id-01)</td>
<td markdown="span">All activities MUST have globally unique `id` fields — de-duplication via unique IDs.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_029](story_2022_029.md)</td>
<td rowspan="4" markdown="span">As a Vendor/Deployer/Other, assign own ID to a case</td>
<td markdown="span">[OID-01-001](../specs/protocol.md#oid-01)</td>
<td markdown="span">All ActivityStreams object IDs MUST use full URI form — ID format requirement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OID-01-002](../specs/protocol.md#oid-01)</td>
<td markdown="span">IDs MUST be globally unique within the system — uniqueness enforcement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OID-01-003](../specs/protocol.md#oid-01)</td>
<td markdown="span">The canonical base URI for locally created objects MUST be configurable — local ID namespace.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-02-001](../specs/protocol.md#cm-02)</td>
<td markdown="span">Each VulnerabilityCase MUST have exactly one associated CaseActor — case ownership and identity.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_030](story_2022_030.md)</td>
<td rowspan="4" markdown="span">As a Participant, discover and map to global/shared case ID</td>
<td markdown="span">[OID-01-001](../specs/protocol.md#oid-01)</td>
<td markdown="span">All ActivityStreams object IDs MUST use full URI form — global ID format.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OID-01-002](../specs/protocol.md#oid-01)</td>
<td markdown="span">IDs MUST be globally unique within the system — global uniqueness.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-16-002](../specs/protocol.md#vp-16)</td>
<td markdown="span">A case or vulnerability identifier SHOULD appear in embargo representation — case ID in embargo.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-16-003](../specs/protocol.md#vp-16)</td>
<td markdown="span">Case or vulnerability identifiers SHOULD NOT carry sensitive information — ID privacy.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_031](story_2022_031.md)</td>
<td rowspan="3" markdown="span">As a Participant, get list of cases I am involved in</td>
<td markdown="span">[VP-01-001](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the state of other Participants in a case — state tracking.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-02-001](../specs/protocol.md#cm-02)</td>
<td markdown="span">Each VulnerabilityCase MUST have exactly one associated CaseActor — case listing support.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-07-001](../specs/protocol.md#cm-07)</td>
<td markdown="span">The system SHOULD expose an endpoint returning the set of valid next actions — case API.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_032](story_2022_032.md)</td>
<td rowspan="3" markdown="span">As a Participant, ask if another Participant is in a case</td>
<td markdown="span">[VP-01-001](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the state of other Participants — participant tracking.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors SHOULD be included — participation list.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-009](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants in a case SHOULD notify when a new Participant is added — membership events.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_033](story_2022_033.md)</td>
<td rowspan="2" markdown="span">As a Participant, request anonymity in a case</td>
<td markdown="span">[VP-08-017](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants in an MPCVD case MAY delay notifying potential Participants — controlled disclosure.</td>
</tr>
<tr markdown="1">
<td markdown="span">—</td>
<td markdown="span">*No further mapped requirements* (anonymity policy has limited current spec coverage).</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_045](story_2022_045.md)</td>
<td rowspan="3" markdown="span">As a Participant, produce a shared verified public record</td>
<td markdown="span">[VP-16-002](../specs/protocol.md#vp-16)</td>
<td markdown="span">A case or vulnerability identifier SHOULD appear in embargo representation — shared case ID.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OID-01-001](../specs/protocol.md#oid-01)</td>
<td markdown="span">All object IDs MUST use full URI form — stable record identifiers.</td>
</tr>
<tr markdown="1">
<td markdown="span">[SL-01-001](../specs/project.md#sl-01)</td>
<td markdown="span">All log entries MUST include `timestamp` field (`PROD_ONLY`) — auditable timeline.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_046](story_2022_046.md)</td>
<td rowspan="2" markdown="span">As a Participant, want the case to have a leader</td>
<td markdown="span">[CM-02-004](../specs/protocol.md#cm-02)</td>
<td markdown="span">CaseActor MUST know the case owner — leadership/ownership model.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-003](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants SHOULD follow consensus agreement to decide embargo terms — leader-driven consensus.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_047](story_2022_047.md)</td>
<td rowspan="3" markdown="span">As a Participant, propose a case leader, possibly myself</td>
<td markdown="span">[CM-02-004](../specs/protocol.md#cm-02)</td>
<td markdown="span">CaseActor MUST know the case owner — ownership field populated by leader proposal.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-012](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants MAY engage a third-party Coordinator to act as mediator — coordinator as leader.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-02-001](../specs/protocol.md#rf-02)</td>
<td markdown="span">Accept responses MUST use `Accept` activity type — accepting a leader proposal uses Accept activity.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_048](story_2022_048.md)</td>
<td rowspan="3" markdown="span">As a Participant, vote/accept a proposed case leader</td>
<td markdown="span">[RF-02-001](../specs/protocol.md#rf-02)</td>
<td markdown="span">Accept responses MUST use `Accept` activity type — acceptance mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-03-001](../specs/protocol.md#rf-03)</td>
<td markdown="span">Reject responses MUST use `Reject` activity type — rejection mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-02-005](../specs/protocol.md#cm-02)</td>
<td markdown="span">CaseActor MUST restrict certain activities to the case owner (`PROD_ONLY`) — ownership enforcement.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_049](story_2022_049.md)</td>
<td rowspan="2" markdown="span">As a Participant, announce the case leader to all Participants</td>
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to other Participants — announcement mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — delivery mechanism for announcement.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_050](story_2022_050.md)</td>
<td rowspan="3" markdown="span">As a Participant, transfer case leadership to another</td>
<td markdown="span">[CM-02-004](../specs/protocol.md#cm-02)</td>
<td markdown="span">CaseActor MUST know the case owner — ownership transfer.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-02-005](../specs/protocol.md#cm-02)</td>
<td markdown="span">CaseActor MUST restrict certain activities to the case owner (`PROD_ONLY`) — ownership change restriction.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-02-001](../specs/protocol.md#rf-02)</td>
<td markdown="span">Accept responses MUST use `Accept` activity type — new leader accepts the transfer.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_051](story_2022_051.md)</td>
<td rowspan="3" markdown="span">As a Participant, depose or step down as case leader</td>
<td markdown="span">[CM-02-004](../specs/protocol.md#cm-02)</td>
<td markdown="span">CaseActor MUST know the case owner — leader identity tracked.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-011](../specs/protocol.md#vp-08)</td>
<td markdown="span">When consensus fails to reach agreement on embargo terms — fallback when no leader.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-02-001](../specs/protocol.md#rf-02)</td>
<td markdown="span">Accept responses MUST use `Accept` activity type — replacement leader acceptance.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_052](story_2022_052.md)</td>
<td rowspan="4" markdown="span">As a Participant, add/notify others of new Participants</td>
<td markdown="span">[VP-08-001](../specs/protocol.md#vp-08)</td>
<td markdown="span">When inviting a new Participant to a case with an existing embargo — invitation protocol.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors of affected software SHOULD be included — obligation to include.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-005](../specs/protocol.md#vp-08)</td>
<td markdown="span">A newly invited Participant SHOULD be informed about the existing embargo — notification duty.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-009](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants SHOULD notify when a new Participant is added to a case.</td>
</tr>
<tr markdown="1">
<td rowspan="5" markdown="span">[story_2022_053](story_2022_053.md)</td>
<td rowspan="5" markdown="span">As a Participant, propose new Participants to a case</td>
<td markdown="span">[VP-08-001](../specs/protocol.md#vp-08)</td>
<td markdown="span">When inviting a new Participant to a case with an existing embargo — invitation process.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors SHOULD be included — who to propose.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-012](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants MAY engage a third-party Coordinator — coordinator as proposed participant.</td>
</tr>
<tr markdown="1">
<td markdown="span">[AKM-02-001](../specs/protocol.md#akm-02)</td>
<td markdown="span">An Actor MUST NOT assume that a recipient has knowledge of any object not previously shared — proposed-participant discovery.</td>
</tr>
<tr markdown="1">
<td markdown="span">[AKM-03-001](../specs/protocol.md#akm-03)</td>
<td markdown="span">Outbound initiating activities MUST carry the `object` field as a fully inline typed domain object — invite proposal payload integrity.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_054](story_2022_054.md)</td>
<td rowspan="3" markdown="span">As a Participant, vote/accept new Participants to a case</td>
<td markdown="span">[RF-02-001](../specs/protocol.md#rf-02)</td>
<td markdown="span">Accept responses MUST use `Accept` activity type — acceptance of invitation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-03-001](../specs/protocol.md#rf-03)</td>
<td markdown="span">Reject responses MUST use `Reject` activity type — rejection of invitation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-015](../specs/protocol.md#vp-08)</td>
<td markdown="span">The inviting Participant MAY interpret a non-response as non-participation.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_063](story_2022_063.md)</td>
<td rowspan="4" markdown="span">As a Participant, include a non-vendor role Participant</td>
<td markdown="span">[VP-08-014](../specs/protocol.md#vp-08)</td>
<td markdown="span">Other parties MAY be included as Participants when necessary and appropriate — non-vendor inclusion.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors of affected software SHOULD be included — vendor coverage before others.</td>
</tr>
<tr markdown="1">
<td markdown="span">[PRM-01-001](../specs/protocol.md#prm-01)</td>
<td markdown="span">VultronParticipant MUST expose a read-only `roles` property — role inspection for case membership.</td>
</tr>
<tr markdown="1">
<td markdown="span">[PRM-02-001](../specs/protocol.md#prm-02)</td>
<td markdown="span">`add_role()` MUST add a role to the participant's role set — role assignment for non-vendor participants.</td>
</tr>
<tr markdown="1">
<td markdown="span">[story_2022_064](story_2022_064.md)</td>
<td markdown="span">As a Participant, include the Government in the case</td>
<td markdown="span">[VP-08-014](../specs/protocol.md#vp-08)</td>
<td markdown="span">Other parties MAY be included as Participants when necessary and appropriate — government inclusion.</td>
</tr>
<tr markdown="1">
<td markdown="span">[story_2022_065](story_2022_065.md)</td>
<td markdown="span">As a Participant, include Industry/trade group in case</td>
<td markdown="span">[VP-08-014](../specs/protocol.md#vp-08)</td>
<td markdown="span">Other parties MAY be included as Participants when necessary and appropriate — industry group inclusion.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_066](story_2022_066.md)</td>
<td rowspan="3" markdown="span">As a Participant, stop participating in the case</td>
<td markdown="span">[VP-05-010](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants stopping work SHOULD notify remaining Participants.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-011](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants SHOULD continue to comply with any active embargoes even after stopping.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-012](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants who leave an Active embargo SHOULD be removed by the remaining Participants.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_067](story_2022_067.md)</td>
<td rowspan="3" markdown="span">As a Participant, stop participating and inform others</td>
<td markdown="span">[VP-05-010](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants stopping work SHOULD notify remaining Participants — notification obligation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-011](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants SHOULD continue to comply with active embargoes — compliance after stopping.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-13-009](../specs/protocol.md#vp-13)</td>
<td markdown="span">A Participant's closure or deferral of a report has implications for the embargo state.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_068](story_2022_068.md)</td>
<td rowspan="2" markdown="span">As a Participant, stop and no longer receive forwarded queries</td>
<td markdown="span">[VP-05-010](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants stopping work SHOULD notify remaining Participants — departure notification.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-012](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants who leave SHOULD be removed from the active embargo — removal from distribution.</td>
</tr>
<tr markdown="1">
<td rowspan="7" markdown="span">[story_2022_074](story_2022_074.md)</td>
<td rowspan="7" markdown="span">As a Participant, keep track of events and timelines</td>
<td markdown="span">[VP-01-001](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the state of other Participants — state tracking.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-01-002](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the RM states of the other Participants — RM state tracking.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-001](../specs/protocol.md#vp-05)</td>
<td markdown="span">An embargo SHALL specify an unambiguous date and time — timeline anchor.</td>
</tr>
<tr markdown="1">
<td markdown="span">[SL-04-001](../specs/project.md#sl-04)</td>
<td markdown="span">Log entries MUST include structured state-transition format (`PROD_ONLY`) — event log for tracking.</td>
</tr>
<tr markdown="1">
<td markdown="span">[SYNC-01-001](../specs/protocol.md#sync-01)</td>
<td markdown="span">The canonical recorded case log MUST be append-only — event timeline integrity.</td>
</tr>
<tr markdown="1">
<td markdown="span">[SYNC-01-002](../specs/protocol.md#sync-01)</td>
<td markdown="span">Each log entry MUST carry a monotonically increasing index scoped to its case — timeline ordering.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CLP-02-006](../specs/protocol.md#clp-02)</td>
<td markdown="span">`CaseLedgerEntry` MUST include a `log_index` field corresponding to `SYNC-01-002` — canonical ordering for recorded events.</td>
</tr>
<tr markdown="1">
<td rowspan="6" markdown="span">[story_2022_088](story_2022_088.md)</td>
<td rowspan="6" markdown="span">As a Participant, maintain knowledge of case state</td>
<td markdown="span">[VP-01-001](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the state of other Participants — state awareness.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-01-002](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the RM states of other Participants — RM awareness.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-01-001](../specs/protocol.md#cm-01)</td>
<td markdown="span">Each actor MUST have an isolated protocol state domain — state isolation per actor.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-01-002](../specs/protocol.md#cm-01)</td>
<td markdown="span">Each actor's RM state MUST be maintained independently per case — per-case state.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-07-001](../specs/protocol.md#cm-07)</td>
<td markdown="span">The system SHOULD expose an endpoint returning valid next actions — state-aware API.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CLP-04-006](../specs/protocol.md#clp-04)</td>
<td markdown="span">The canonical recorded log is the authoritative source of truth for case participant membership and case state — case-state knowledge derives from canonical history.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_104](story_2022_104.md)</td>
<td rowspan="4" markdown="span">As a Participant, address multiple vulnerabilities across vendors</td>
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors of affected software SHOULD be included — multi-vendor inclusion.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-10-004](../specs/protocol.md#vp-10)</td>
<td markdown="span">A new embargo SHOULD be proposed when any two or more CVD cases are merged.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-10-001](../specs/protocol.md#vp-10)</td>
<td markdown="span">If no new embargo has been proposed after a case split — split/merge embargo handling.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-05-006](../specs/protocol.md#cm-05)</td>
<td markdown="span">One report MAY describe multiple vulnerabilities; one case MAY cover multiple reports — data model.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_105](story_2022_105.md)</td>
<td rowspan="4" markdown="span">As a Vendor, address same vulnerability across products</td>
<td markdown="span">[VP-10-004](../specs/protocol.md#vp-10)</td>
<td markdown="span">A new embargo SHOULD be proposed when any two or more CVD cases are merged.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-10-001](../specs/protocol.md#vp-10)</td>
<td markdown="span">If no new embargo proposed after case split — per-product split embargo handling.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-14-014](../specs/protocol.md#vp-14)</td>
<td markdown="span">In MPCVD cases where some Vendors reach Fix Ready before others — staggered timelines.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-05-006](../specs/protocol.md#cm-05)</td>
<td markdown="span">One report MAY describe multiple vulnerabilities; one case MAY cover multiple reports — multi-product.</td>
</tr>
<tr markdown="1">
<td rowspan="6" markdown="span">[story_2022_106](story_2022_106.md)</td>
<td rowspan="6" markdown="span">As a Participant, want decentralized coordination process</td>
<td markdown="span">[VP-01-003](../specs/protocol.md#vp-01)</td>
<td markdown="span">Adequate operation of the protocol MUST NOT depend on perfect knowledge of all Participants.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-001](../specs/protocol.md#vp-15)</td>
<td markdown="span">Vultron Protocol messages SHOULD use well-defined format — interoperable, decentralized messaging.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-002](../specs/protocol.md#vp-15)</td>
<td markdown="span">Implementations SHOULD use common identity mechanisms (`PROD_ONLY`) — federated identity.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EDF-02-001](../specs/architecture.md#edf-02)</td>
<td markdown="span">Every protocol-significant action in Vultron MUST be triggered by an event — decentralized control flow.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EDF-03-001](../specs/protocol.md#edf-03)</td>
<td markdown="span">All cascade steps that do not require external input MUST be implemented as BT subtrees — automation within the actor.</td>
</tr>
<tr markdown="1">
<td markdown="span">[SBT-01-001](../specs/project.md#sbt-01)</td>
<td markdown="span">Sync log entry protocol flows MUST be implemented as behavior trees, not procedural use-case code — decentralized sync handling.</td>
</tr>
</tbody>
</table>

## 5. Actor Identity, Privacy, and Security

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>User Story ID</th>
<th>Story text</th>
<th>Spec ID</th>
<th>Spec detail</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_034](story_2022_034.md)</td>
<td rowspan="3" markdown="span">As a Participant, use global/federated user ID</td>
<td markdown="span">[OID-01-001](../specs/protocol.md#oid-01)</td>
<td markdown="span">All ActivityStreams object IDs MUST use full URI form — global ID format.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-002](../specs/protocol.md#vp-15)</td>
<td markdown="span">Implementations SHOULD use common identity mechanisms (`PROD_ONLY`) — federated identity.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-003](../specs/protocol.md#vp-15)</td>
<td markdown="span">Implementations SHOULD use common messaging protocols (`PROD_ONLY`) — interoperable identity use.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_035](story_2022_035.md)</td>
<td rowspan="3" markdown="span">As a Participant, have confidence in identity/group membership</td>
<td markdown="span">[ENC-01-001](../specs/protocol.md#enc-01)</td>
<td markdown="span">Each CaseActor MUST generate an asymmetric key (`PROD_ONLY`) — identity key material.</td>
</tr>
<tr markdown="1">
<td markdown="span">[ENC-01-002](../specs/protocol.md#enc-01)</td>
<td markdown="span">The CaseActor MUST publish its public key in its actor profile (`PROD_ONLY`) — verifiable identity.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-002](../specs/protocol.md#vp-15)</td>
<td markdown="span">Implementations SHOULD use common identity mechanisms (`PROD_ONLY`) — federated identity.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_036](story_2022_036.md)</td>
<td rowspan="3" markdown="span">As a non-vendor, determine integration of auth/authz</td>
<td markdown="span">[ENC-01-001](../specs/protocol.md#enc-01)</td>
<td markdown="span">Each CaseActor MUST generate an asymmetric key (`PROD_ONLY`) — auth model via keys.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-002](../specs/protocol.md#vp-15)</td>
<td markdown="span">Implementations SHOULD use common identity mechanisms (`PROD_ONLY`) — auth/authz integration.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-02-006](../specs/protocol.md#cm-02)</td>
<td markdown="span">CaseActor MUST enforce case-level authorization for all activities (`PROD_ONLY`) — authz enforcement.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_089](story_2022_089.md)</td>
<td rowspan="4" markdown="span">As a Participant, mechanism for message authentication/integrity</td>
<td markdown="span">[ENC-01-001](../specs/protocol.md#enc-01)</td>
<td markdown="span">Each CaseActor MUST generate an asymmetric key (`PROD_ONLY`) — signing key for integrity.</td>
</tr>
<tr markdown="1">
<td markdown="span">[ENC-01-002](../specs/protocol.md#enc-01)</td>
<td markdown="span">CaseActor MUST publish its public key (`PROD_ONLY`) — verifiable signatures.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-004](../specs/protocol.md#vp-15)</td>
<td markdown="span">Implementations MAY use end-to-end encryption (`PROD_ONLY`) — integrity mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-005](../specs/protocol.md#vp-15)</td>
<td markdown="span">Implementations MAY use encryption for messages (`PROD_ONLY`) — transport integrity.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_090](story_2022_090.md)</td>
<td rowspan="3" markdown="span">As a Participant, mechanism for all Participants' authentication</td>
<td markdown="span">[ENC-01-001](../specs/protocol.md#enc-01)</td>
<td markdown="span">Each CaseActor MUST generate an asymmetric key (`PROD_ONLY`) — participant authentication.</td>
</tr>
<tr markdown="1">
<td markdown="span">[ENC-01-003](../specs/protocol.md#enc-01)</td>
<td markdown="span">CaseActor MUST share its public key with Participants (`PROD_ONLY`) — key exchange for auth.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-002](../specs/protocol.md#vp-15)</td>
<td markdown="span">Implementations SHOULD use common identity mechanisms (`PROD_ONLY`) — identity framework.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_091](story_2022_091.md)</td>
<td rowspan="4" markdown="span">As a Participant, mechanism for confidential transport/storage</td>
<td markdown="span">[ENC-02-001](../specs/protocol.md#enc-02)</td>
<td markdown="span">Case Participants MAY encrypt messages (`PROD_ONLY`) — confidential transport.</td>
</tr>
<tr markdown="1">
<td markdown="span">[ENC-02-002](../specs/protocol.md#enc-02)</td>
<td markdown="span">When sending messages, encrypt using recipient's public key (`PROD_ONLY`) — encryption mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[ENC-01-004](../specs/protocol.md#enc-01)</td>
<td markdown="span">Private keys MUST be stored securely (`PROD_ONLY`) — confidential storage.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-15-004](../specs/protocol.md#vp-15)</td>
<td markdown="span">Implementations MAY use end-to-end encryption (`PROD_ONLY`) — end-to-end confidentiality.</td>
</tr>
<tr markdown="1">
<td rowspan="6" markdown="span">[story_2022_092](story_2022_092.md)</td>
<td rowspan="6" markdown="span">As a Participant, know who else is participating in a case</td>
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors of affected software SHOULD be included — full participant list.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-009](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants SHOULD notify others when a new Participant is added to a case.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-01-001](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the state of other Participants — state tracking implies membership.</td>
</tr>
<tr markdown="1">
<td markdown="span">[PCR-01-001](../specs/protocol.md#pcr-01)</td>
<td markdown="span">Each Vultron Actor MUST maintain its local case replica as an internal concern — participant membership is actor-local.</td>
</tr>
<tr markdown="1">
<td markdown="span">[PCR-02-002](../specs/protocol.md#pcr-02)</td>
<td markdown="span">When a new participant is added to a case, the CaseActor MUST send `Announce(VulnerabilityCase)` to that participant — replica bootstrap for membership awareness.</td>
</tr>
<tr markdown="1">
<td markdown="span">[PCR-04-002](../specs/protocol.md#pcr-04)</td>
<td markdown="span">All case-scoped protocol activities sent by the CaseActor MUST carry `context` set to the case ID — routing the membership replica.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_093](story_2022_093.md)</td>
<td rowspan="3" markdown="span">As a Participant, ensure Participant list is complete</td>
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors of affected software SHOULD be included — completeness obligation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-009](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants SHOULD notify others when a new Participant is added.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-01-001](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the state of other Participants — tracking supports list integrity.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_094](story_2022_094.md)</td>
<td rowspan="3" markdown="span">As a Participant, assess reputation of others to decide to engage</td>
<td markdown="span">[VP-05-013](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants SHOULD consider others' history of embargo compliance — reputation as input.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-010](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants known to leak information SHOULD be excluded from embargoes.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-021](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants MAY decline to participate in future CVD cases — reputation-driven decisions.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_095](story_2022_095.md)</td>
<td rowspan="3" markdown="span">As a Participant, provide evidence of reputation to others</td>
<td markdown="span">[VP-05-013](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants SHOULD consider others' history of embargo compliance — reputation-based trust.</td>
</tr>
<tr markdown="1">
<td markdown="span">[EP-01-001](../specs/protocol.md#ep-01)</td>
<td markdown="span">An Actor profile MAY include an `embargo_policy` field — policy as proxy for reputation.</td>
</tr>
<tr markdown="1">
<td markdown="span">—</td>
<td markdown="span">*No further mapped requirements* (reputation attestation has no direct current spec requirement beyond policy publication).</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_096](story_2022_096.md)</td>
<td rowspan="3" markdown="span">As a Participant, record/log trust/reputation of others</td>
<td markdown="span">[VP-05-013](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants SHOULD consider others' history of embargo compliance — basis for reputation log.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-010](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants known to leak information SHOULD be excluded — outcome of reputation tracking.</td>
</tr>
<tr markdown="1">
<td markdown="span">—</td>
<td markdown="span">*No further mapped requirements* (reputation logging is not specified in current specs).</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_097](story_2022_097.md)</td>
<td rowspan="3" markdown="span">As a Participant, organize own groups of other Participants</td>
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors of affected software SHOULD be included — group composition.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-012](../specs/protocol.md#vp-08)</td>
<td markdown="span">Participants MAY engage a third-party Coordinator — group with coordinator.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-014](../specs/protocol.md#vp-08)</td>
<td markdown="span">Other parties MAY be included as Participants when necessary — flexible group composition.</td>
</tr>
</tbody>
</table>

## 6. Communication and Messaging

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>User Story ID</th>
<th>Story text</th>
<th>Spec ID</th>
<th>Spec detail</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_016](story_2022_016.md)</td>
<td rowspan="3" markdown="span">As a Participant, limited ACK of vulnerability / full advisory</td>
<td markdown="span">[VP-03-009](../specs/protocol.md#vp-03)</td>
<td markdown="span">Recipients SHOULD send RK in acknowledgment of any R* message — acknowledgment requirement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-02-001](../specs/protocol.md#rf-02)</td>
<td markdown="span">Accept responses MUST use `Accept` activity type — formal acceptance of report.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-08-001](../specs/protocol.md#rf-08)</td>
<td markdown="span">Response activities MUST include `inReplyTo` field — tracing response back to original.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_028](story_2022_028.md)</td>
<td rowspan="3" markdown="span">As a vendor or coordinator, want others to find me</td>
<td markdown="span">[VP-02-001](../specs/protocol.md#vp-02)</td>
<td markdown="span">Coordinators MUST have a clearly defined and publicly available policy — discoverability.</td>
</tr>
<tr markdown="1">
<td markdown="span">[IE-02-001](../specs/protocol.md#ie-02)</td>
<td markdown="span">The endpoint URL MUST be discoverable from actor profile — inbox discoverability.</td>
</tr>
<tr markdown="1">
<td markdown="span">[AR-01-001](../specs/project.md#ar-01)</td>
<td markdown="span">The API MUST expose a machine-readable OpenAPI JSON schema — programmatic discovery.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_039](story_2022_039.md)</td>
<td rowspan="3" markdown="span">As a Participant, communicate with another case Participant</td>
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to other Participants.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-01-001](../specs/protocol.md#rf-01)</td>
<td markdown="span">Response activities MUST conform to ActivityStreams 2.0 — message format.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — delivery mechanism.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_040](story_2022_040.md)</td>
<td rowspan="3" markdown="span">As a Participant, unicast/point-to-point communication</td>
<td markdown="span">[OX-04-001](../specs/project.md#ox-04)</td>
<td markdown="span">For actors on the same server, delivery MUST write directly to the recipient's inbox — local unicast delivery.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-05-001](../specs/project.md#ox-05)</td>
<td markdown="span">For remote actors, MAY deliver via HTTP POST (`PROD_ONLY`) — remote unicast delivery.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-06-002](../specs/protocol.md#rf-06)</td>
<td markdown="span">Response activities MUST be addressed to the initiating actor — targeted addressing.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_041](story_2022_041.md)</td>
<td rowspan="2" markdown="span">As a Participant, broadcast to all Participants in a case</td>
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to all Participants — broadcast state changes.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-03-001](../specs/protocol.md#ox-03)</td>
<td markdown="span">Activities in an actor's outbox MUST be delivered to recipient inboxes — outbox-based broadcast.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_042](story_2022_042.md)</td>
<td rowspan="2" markdown="span">As a Participant, communicate with a subset of Participants</td>
<td markdown="span">[VP-05-007](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo participation SHOULD be limited to the smallest possible set — subset communication.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-03-001](../specs/protocol.md#ox-03)</td>
<td markdown="span">Activities in an actor's outbox MUST be delivered to recipient inboxes — selective delivery.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_043](story_2022_043.md)</td>
<td rowspan="2" markdown="span">As a Participant, communicate in a common case channel</td>
<td markdown="span">[CM-06-001](../specs/protocol.md#cm-06)</td>
<td markdown="span">When the CaseActor updates canonical case state, it MUST broadcast to all Participants.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-03-001](../specs/protocol.md#ox-03)</td>
<td markdown="span">Activities in an actor's outbox MUST be delivered to recipient inboxes — channel delivery.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_044](story_2022_044.md)</td>
<td rowspan="2" markdown="span">As a Participant, communicate with selected case Participants</td>
<td markdown="span">[OX-03-001](../specs/protocol.md#ox-03)</td>
<td markdown="span">Activities in an actor's outbox MUST be delivered to recipient inboxes — selective delivery.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-006](../specs/protocol.md#vp-08)</td>
<td markdown="span">The inviting Participant SHOULD NOT share the vulnerability report — selective disclosure.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_058](story_2022_058.md)</td>
<td rowspan="3" markdown="span">As a Participant, share a draft advisory with others</td>
<td markdown="span">[VP-05-006](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo Participants SHOULD NOT knowingly release information — shared draft under embargo.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — delivery of draft advisory.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-01-001](../specs/protocol.md#rf-01)</td>
<td markdown="span">Response activities MUST conform to ActivityStreams 2.0 — message format for draft sharing.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_059](story_2022_059.md)</td>
<td rowspan="4" markdown="span">As a Participant, share draft advisory and request feedback</td>
<td markdown="span">[VP-05-006](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo Participants SHOULD NOT knowingly release information — embargo-constrained sharing.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-02-001](../specs/protocol.md#rf-02)</td>
<td markdown="span">Accept responses MUST use `Accept` activity type — feedback as Accept/Reject on draft.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-08-001](../specs/protocol.md#rf-08)</td>
<td markdown="span">Response activities MUST include `inReplyTo` field — feedback references draft.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — delivery mechanism.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_060](story_2022_060.md)</td>
<td rowspan="2" markdown="span">As a Participant, request advisory draft from a Participant</td>
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to others — draft availability announcement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-01-001](../specs/protocol.md#rf-01)</td>
<td markdown="span">Response activities MUST conform to ActivityStreams 2.0 — request/response format.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_061](story_2022_061.md)</td>
<td rowspan="3" markdown="span">As a Participant, request another Participant's status</td>
<td markdown="span">[VP-01-001](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the state of other Participants — state inquiry.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-01-002](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the RM states of other Participants — RM state request.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to others — announcement satisfies query.</td>
</tr>
<tr markdown="1">
<td rowspan="5" markdown="span">[story_2022_062](story_2022_062.md)</td>
<td rowspan="5" markdown="span">As a Participant, state my status so others are aware</td>
<td markdown="span">[VP-02-019](../specs/protocol.md#vp-02)</td>
<td markdown="span">CVD Participants SHOULD announce RM state transitions to other Participants.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-005](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD send RD when the report prioritization is deferred.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-006](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD send RA when the report prioritization is accepted.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-007](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD send RC when the report is closed.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce RM, EM, or CVD Case State.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_081](story_2022_081.md)</td>
<td rowspan="3" markdown="span">As a Participant, communicate important public state change</td>
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to all Participants — state change announcement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-12-001](../specs/protocol.md#vp-12)</td>
<td markdown="span">Vendor Awareness messages SHOULD be sent only by Vendors who become aware of the vulnerability.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — delivery mechanism for announcements.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_098](story_2022_098.md)</td>
<td rowspan="3" markdown="span">As a Participant, communicate with all Participants in a case</td>
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to all Participants — broadcast mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-06-001](../specs/protocol.md#cm-06)</td>
<td markdown="span">When CaseActor updates state, MUST broadcast to all Participants — case-level broadcast.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-03-001](../specs/protocol.md#ox-03)</td>
<td markdown="span">Activities in an actor's outbox MUST be delivered to recipient inboxes — delivery to all.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_099](story_2022_099.md)</td>
<td rowspan="2" markdown="span">As a Participant, communicate with non-vendor Participants</td>
<td markdown="span">[VP-08-014](../specs/protocol.md#vp-08)</td>
<td markdown="span">Other parties MAY be included as Participants when necessary — non-vendor inclusion.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-03-001](../specs/protocol.md#ox-03)</td>
<td markdown="span">Activities in an actor's outbox MUST be delivered to recipient inboxes — delivery mechanism.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_100](story_2022_100.md)</td>
<td rowspan="3" markdown="span">As a Participant, be included on distribution list for advisories</td>
<td markdown="span">[VP-12-001](../specs/protocol.md#vp-12)</td>
<td markdown="span">Vendor Awareness messages SHOULD be sent only by Vendors who become aware — awareness notifications.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-03-001](../specs/protocol.md#ox-03)</td>
<td markdown="span">Activities in an actor's outbox MUST be delivered to recipient inboxes — subscription/distribution mechanism.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-04-001](../specs/project.md#ox-04)</td>
<td markdown="span">For actors on the same server, delivery MUST write directly to the recipient's inbox — local distribution.</td>
</tr>
</tbody>
</table>

## 7. Publication and Disclosure

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>User Story ID</th>
<th>Story text</th>
<th>Spec ID</th>
<th>Spec detail</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_015](story_2022_015.md)</td>
<td rowspan="3" markdown="span">As a Participant, notify others of intent to publish</td>
<td markdown="span">[VP-05-014](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants SHOULD NOT publish information before embargo terminates — pre-publish notice.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-09-001](../specs/protocol.md#vp-09)</td>
<td markdown="span">Embargoes SHALL terminate immediately when information about the vulnerability is made public.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — delivery of publication intent notification.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_017](story_2022_017.md)</td>
<td rowspan="3" markdown="span">As a Participant, share my draft publication with others</td>
<td markdown="span">[VP-05-006](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo Participants SHOULD NOT knowingly release information — draft shared within embargo.</td>
</tr>
<tr markdown="1">
<td markdown="span">[RF-01-001](../specs/protocol.md#rf-01)</td>
<td markdown="span">Response activities MUST conform to ActivityStreams 2.0 — format for sharing draft.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — delivery mechanism.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_018](story_2022_018.md)</td>
<td rowspan="4" markdown="span">As a Participant, aware of public exploit, tell others</td>
<td markdown="span">[VP-09-003](../specs/protocol.md#vp-09)</td>
<td markdown="span">Embargoes SHOULD terminate early when there is evidence of exploit availability.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-09-006](../specs/protocol.md#vp-09)</td>
<td markdown="span">Embargoes MAY terminate early when evidence of exploit publication exists.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-14-002](../specs/protocol.md#vp-14)</td>
<td markdown="span">Once Exploit Publication has occurred, new embargoes have restricted scope.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-11-002](../specs/protocol.md#vp-11)</td>
<td markdown="span">If information has been made public, participants should initiate embargo termination.</td>
</tr>
<tr markdown="1">
<td rowspan="5" markdown="span">[story_2022_019](story_2022_019.md)</td>
<td rowspan="5" markdown="span">As a Participant, aware of exploitation in the wild, tell others</td>
<td markdown="span">[VP-11-003](../specs/protocol.md#vp-11)</td>
<td markdown="span">Participants SHALL initiate embargo termination upon becoming aware of exploitation.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-11-006](../specs/protocol.md#vp-11)</td>
<td markdown="span">If attacks are known to have occurred, Participants SHOULD act accordingly.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-11-007](../specs/protocol.md#vp-11)</td>
<td markdown="span">Participants SHOULD initiate embargo termination when attacks are observed.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-12-002](../specs/protocol.md#vp-12)</td>
<td markdown="span">Once attacks observed, fix development SHOULD be accelerated.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-14-003](../specs/protocol.md#vp-14)</td>
<td markdown="span">Once attacks observed, new embargoes have restricted scope.</td>
</tr>
<tr markdown="1">
<td rowspan="4" markdown="span">[story_2022_020](story_2022_020.md)</td>
<td rowspan="4" markdown="span">As a Participant, publish a vulnerability (external to protocol)</td>
<td markdown="span">[VP-05-005](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo termination SHALL NOT be construed as an obligation to publish — no forced publication.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-020](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants MAY publish information about the vulnerability when embargo ends.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-09-001](../specs/protocol.md#vp-09)</td>
<td markdown="span">Embargoes SHALL terminate immediately when information is made public — publication triggers.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-14-001](../specs/protocol.md#vp-14)</td>
<td markdown="span">Once Public Awareness has happened — implications for embargo state.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_037](story_2022_037.md)</td>
<td rowspan="3" markdown="span">As a vendor, publish vulnerability advisories</td>
<td markdown="span">[VP-05-020](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants MAY publish information when embargo ends — advisory publication timing.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-12-001](../specs/protocol.md#vp-12)</td>
<td markdown="span">Vendor Awareness messages SHOULD be sent only by Vendors — vendor-side announcement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — delivery of advisory announcement.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_069](story_2022_069.md)</td>
<td rowspan="3" markdown="span">As a Participant, tell others that I published</td>
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to other Participants.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-12-001](../specs/protocol.md#vp-12)</td>
<td markdown="span">Vendor Awareness messages SHOULD be sent only by Vendors who become aware.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-09-001](../specs/protocol.md#vp-09)</td>
<td markdown="span">Embargoes SHALL terminate immediately when information is made public — consequence of publishing.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_070](story_2022_070.md)</td>
<td rowspan="3" markdown="span">As a Participant, convey how information I provide can be used</td>
<td markdown="span">[VP-05-006](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo Participants SHOULD NOT knowingly release information — use constraint.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-16-001](../specs/protocol.md#vp-16)</td>
<td markdown="span">Vulnerability details MUST NOT appear in embargo representation — separation constraint.</td>
</tr>
<tr markdown="1">
<td markdown="span">—</td>
<td markdown="span">*No further mapped requirements* (TLP-level information use policies have no direct current spec requirement).</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_071](story_2022_071.md)</td>
<td rowspan="3" markdown="span">As a Participant, convey information use while obeying TLP</td>
<td markdown="span">[VP-05-006](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo Participants SHOULD NOT knowingly release information — TLP-analogous constraint.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-16-001](../specs/protocol.md#vp-16)</td>
<td markdown="span">Vulnerability details MUST NOT appear in embargo representation — content restriction.</td>
</tr>
<tr markdown="1">
<td markdown="span">—</td>
<td markdown="span">*No further mapped requirements* (TLP tagging is not specified in current specs).</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_072](story_2022_072.md)</td>
<td rowspan="3" markdown="span">As a Participant, convey what restricted info I will accept</td>
<td markdown="span">[EP-01-002](../specs/protocol.md#ep-01)</td>
<td markdown="span">The embargo policy record MUST include required fields — policy expresses what info is accepted.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-05-007](../specs/protocol.md#vp-05)</td>
<td markdown="span">Embargo participation SHOULD be limited to the smallest possible set — restriction principle.</td>
</tr>
<tr markdown="1">
<td markdown="span">—</td>
<td markdown="span">*No further mapped requirements* (TLP acceptance policy is not specified in current specs).</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_073](story_2022_073.md)</td>
<td rowspan="2" markdown="span">As a Participant, convey TLP restriction level I will accept</td>
<td markdown="span">[EP-01-003](../specs/protocol.md#ep-01)</td>
<td markdown="span">The embargo policy record SHOULD include optional fields — policy fields for restriction level.</td>
</tr>
<tr markdown="1">
<td markdown="span">—</td>
<td markdown="span">*No further mapped requirements* (TLP acceptance level is not specified in current specs).</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_083](story_2022_083.md)</td>
<td rowspan="3" markdown="span">As a Participant, contribute to advisory creation and publication</td>
<td markdown="span">[VP-05-020](../specs/protocol.md#vp-05)</td>
<td markdown="span">Participants MAY publish information when embargo ends — advisory publication.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — delivery of advisory contribution.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-02-007](../specs/protocol.md#cm-02)</td>
<td markdown="span">VulnerabilityCase MUST include a `notes` list — advisory draft content in notes.</td>
</tr>
<tr markdown="1">
<td rowspan="5" markdown="span">[story_2022_107](story_2022_107.md)</td>
<td rowspan="5" markdown="span">As a Vendor, convey vulnerability status to other Participants</td>
<td markdown="span">[VP-02-019](../specs/protocol.md#vp-02)</td>
<td markdown="span">CVD Participants SHOULD announce RM state transitions to other Participants.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD announce RM, EM, or CVD Case State changes.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-03-001](../specs/protocol.md#cm-03)</td>
<td markdown="span">The system MUST implement the three interacting state machines — RM/EM/CS status tracking.</td>
</tr>
<tr markdown="1">
<td markdown="span">[CM-04-001](../specs/protocol.md#cm-04)</td>
<td markdown="span">Handlers processing RM state transitions MUST update participant RM state.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-12-001](../specs/protocol.md#vp-12)</td>
<td markdown="span">Vendor Awareness messages SHOULD be sent only by Vendors.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_108](story_2022_108.md)</td>
<td rowspan="3" markdown="span">As a Vendor, convey vulnerability status to Users/the Public</td>
<td markdown="span">[VP-12-001](../specs/protocol.md#vp-12)</td>
<td markdown="span">Vendor Awareness messages SHOULD be sent only by Vendors — public status announcement.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-14-001](../specs/protocol.md#vp-14)</td>
<td markdown="span">Once Public Awareness has happened — implications for state.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — public outbox for status delivery.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_109](story_2022_109.md)</td>
<td rowspan="2" markdown="span">As a Vendor, convey reason component not affected to Participants</td>
<td markdown="span">[VP-03-003](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD send RI when the report validation process determines invalid — not-affected.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants SHOULD announce RM, EM, or CVD Case State changes.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_110](story_2022_110.md)</td>
<td rowspan="2" markdown="span">As a Vendor, convey reason component not affected to Public</td>
<td markdown="span">[VP-12-001](../specs/protocol.md#vp-12)</td>
<td markdown="span">Vendor Awareness messages SHOULD be sent only by Vendors — public not-affected message.</td>
</tr>
<tr markdown="1">
<td markdown="span">[OX-01-001](../specs/project.md#ox-01)</td>
<td markdown="span">Each actor MUST have an outbox collection — public outbox delivery.</td>
</tr>
</tbody>
</table>

## 8. Bug Bounty and Incentives

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>User Story ID</th>
<th>Story text</th>
<th>Spec ID</th>
<th>Spec detail</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_011](story_2022_011.md)</td>
<td rowspan="2" markdown="span">As a Participant, provide bug bounty program info to reporters</td>
<td markdown="span">[EP-01-001](../specs/protocol.md#ep-01)</td>
<td markdown="span">An Actor profile MAY include an `embargo_policy` field — profile fields for program information.</td>
</tr>
<tr markdown="1">
<td markdown="span">—</td>
<td markdown="span">*No further mapped requirements* (bug bounty program description has no direct current spec requirement).</td>
</tr>
<tr markdown="1">
<td markdown="span">[story_2022_055](story_2022_055.md)</td>
<td markdown="span">As a Participant, state that I paid or received a bounty</td>
<td markdown="span">—</td>
<td markdown="span">*No mapped requirements* (bounty payment state is not covered by current specs).</td>
</tr>
<tr markdown="1">
<td markdown="span">[story_2022_056](story_2022_056.md)</td>
<td markdown="span">As a Participant, ask if another Participant paid a reporter</td>
<td markdown="span">—</td>
<td markdown="span">*No mapped requirements* (bounty inquiry is not covered by current specs).</td>
</tr>
<tr markdown="1">
<td markdown="span">[story_2022_057](story_2022_057.md)</td>
<td markdown="span">As a Participant, ask a reporter if they were paid</td>
<td markdown="span">—</td>
<td markdown="span">*No mapped requirements* (bounty inquiry to reporter is not covered by current specs).</td>
</tr>
<tr markdown="1">
<td markdown="span">[story_2022_084](story_2022_084.md)</td>
<td markdown="span">As a vendor, reward the reporter by paying a bounty</td>
<td markdown="span">—</td>
<td markdown="span">*No mapped requirements* (bug bounty payment is not covered by current specs).</td>
</tr>
<tr markdown="1">
<td markdown="span">[story_2022_085](story_2022_085.md)</td>
<td markdown="span">As a reporter, be rewarded with a bounty</td>
<td markdown="span">—</td>
<td markdown="span">*No mapped requirements* (receiving a bounty is not covered by current specs).</td>
</tr>
</tbody>
</table>

## 9. Prioritization, Assessment, and Fix Verification

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>User Story ID</th>
<th>Story text</th>
<th>Spec ID</th>
<th>Spec detail</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_075](story_2022_075.md)</td>
<td rowspan="3" markdown="span">As a Participant, see response times/states of other Participants</td>
<td markdown="span">[VP-01-001](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the state of other Participants — state visibility.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-01-002](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the RM states of other Participants — RM state visibility.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to others — state updates received.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_082](story_2022_082.md)</td>
<td rowspan="3" markdown="span">As a non-vendor Participant, be informed of CVD for risk assessment</td>
<td markdown="span">[VP-08-014](../specs/protocol.md#vp-08)</td>
<td markdown="span">Other parties MAY be included as Participants when necessary — non-vendor inclusion for risk assessment.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-03-012](../specs/protocol.md#vp-03)</td>
<td markdown="span">Participants whose state changes SHOULD announce to others — status updates support risk assessment.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-08-004](../specs/protocol.md#vp-08)</td>
<td markdown="span">All known Vendors of affected software SHOULD be included — relevant parties informed.</td>
</tr>
<tr markdown="1">
<td rowspan="6" markdown="span">[story_2022_086](story_2022_086.md)</td>
<td rowspan="6" markdown="span">As a Participant, prioritize response to requests</td>
<td markdown="span">[VP-02-014](../specs/protocol.md#vp-02)</td>
<td markdown="span">For Valid reports, the Participant SHOULD perform a prioritization step.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-024](../specs/protocol.md#vp-02)</td>
<td markdown="span">Vendors SHOULD communicate their prioritization choices when prioritizing.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-034](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants MAY re-prioritize Accepted or Deferred cases.</td>
</tr>
<tr markdown="1">
<td markdown="span">[TRIG-01-001](../specs/project.md#trig-01)</td>
<td markdown="span">Trigger endpoints use the `POST /actors/{actor_id}/trigger/{behavior-name}` path pattern — response prioritization can be exposed as a trigger.</td>
</tr>
<tr markdown="1">
<td markdown="span">[TRIG-01-004](../specs/project.md#trig-01)</td>
<td markdown="span">Trigger processing MUST NOT block the HTTP response — operator-driven prioritization remains async.</td>
</tr>
<tr markdown="1">
<td markdown="span">[TRIG-05-001](../specs/protocol.md#trig-05)</td>
<td markdown="span">Trigger endpoints SHOULD reuse existing BT trees rather than duplicating behavior logic — trigger wiring for prioritization.</td>
</tr>
<tr markdown="1">
<td rowspan="3" markdown="span">[story_2022_087](story_2022_087.md)</td>
<td rowspan="3" markdown="span">As a Participant, share info to prioritize work on a report</td>
<td markdown="span">[VP-02-014](../specs/protocol.md#vp-02)</td>
<td markdown="span">For Valid reports, the Participant SHOULD perform a prioritization step.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-024](../specs/protocol.md#vp-02)</td>
<td markdown="span">Vendors SHOULD communicate their prioritization choices — shared prioritization data.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-01-001](../specs/protocol.md#vp-01)</td>
<td markdown="span">Participants SHOULD track the state of other Participants — state supports prioritization.</td>
</tr>
<tr markdown="1">
<td rowspan="2" markdown="span">[story_2022_103](story_2022_103.md)</td>
<td rowspan="2" markdown="span">As a Participant, give Finder opportunity to confirm fix</td>
<td markdown="span">[VP-02-013](../specs/protocol.md#vp-02)</td>
<td markdown="span">Participants SHOULD provide Reporters an opportunity to update their reports — feedback opportunity.</td>
</tr>
<tr markdown="1">
<td markdown="span">[VP-02-011](../specs/protocol.md#vp-02)</td>
<td markdown="span">Once a Vendor confirms that a reported vulnerability affects a product — fix confirmation context.</td>
</tr>
</tbody>
</table>

---

## Gap Analysis: Stories with Insufficient Specification Coverage

(DOCS-3, 2026-04-23; updated 2026-08-25)

The following stories have no mapped requirements or only partial coverage in
`specs/`. Each cluster has an explicit prioritization decision recorded in a
dedicated tracking issue. All clusters are deferred: they are PROD_ONLY
concerns, and the prototype does not implement the infrastructure they require.

### Bug Bounty Stories — Deferred (#2563)

Deferred — tracked in #2563 (idea: bug bounty protocol support — scope
decision and vocabulary design). These stories require new protocol activity
types not present in the current spec. They are out-of-scope for the current
prototype and must be explicitly elevated to in-scope before any spec work
begins.

- **story_2022_055** — "As a Participant, state that I paid or received a bounty"
  — No spec. Deferred — see #2563.
- **story_2022_056** — "As a Participant, ask if another Participant paid a reporter"
  — No spec. Deferred — see #2563.
- **story_2022_057** — "As a Participant, ask a reporter if they were paid"
  — No spec. Deferred — see #2563.
- **story_2022_084** — "As a vendor, reward the reporter by paying a bounty"
  — No spec. Deferred — see #2563.
- **story_2022_085** — "As a reporter, be rewarded with a bounty"
  — No spec. Deferred — see #2563.
- **story_2022_011** — "As a Participant, provide bug bounty program info"
  — Partial: only `EP-01-001` mapped as a loose proxy. Deferred — see #2563.

### Privacy and Anonymity Stories — Deferred (#2562)

Deferred — tracked in #2562 (idea: privacy and anonymity spec — pseudonymous
reporting and actor alias support). These stories depend on
`specs/encryption.yaml` (all `PROD_ONLY`) and require cryptographic identity
infrastructure not implemented in the prototype.

- **story_2022_024** — "As a Finder/Reporter, constrain communication for anonymity"
  — Partial: only `VP-08-017` mapped. Deferred — see #2562.
- **story_2022_033** — "As a Participant, request anonymity in a case"
  — Partial: only `VP-08-017` mapped. Deferred — see #2562.

### Trust and Reputation Stories — Deferred (#2565)

Deferred — tracked in #2565 (idea: trust and reputation — machine-readable
compliance history for actor profiles). Depends on federated identity
infrastructure (#1156) not yet implemented.

- **story_2022_095** — "As a Participant, provide evidence of reputation to others"
  — Partial: only `VP-05-013` and `EP-01-001` mapped. Deferred — see #2565.
- **story_2022_096** — "As a Participant, record/log trust/reputation of others"
  — Partial: only `VP-05-013` and `VP-08-010` mapped. Deferred — see #2565.

### TLP (Traffic Light Protocol) Stories — Deferred (#2564)

Deferred — tracked in #2564 (idea: TLP field support — vocabulary extension
and enforcement rules). Requires alignment with the FIRST TLP 2.0 external
standard and cross-cutting vocabulary changes.

- **story_2022_070** — "As a Participant, convey how information I provide can be used"
  — Partial: only embargo-related constraints mapped. Deferred — see #2564.
- **story_2022_071** — "As a Participant, convey information use while obeying TLP"
  — Partial: same gap as story_2022_070 plus enforcement requirements.
  Deferred — see #2564.
- **story_2022_072** — "As a Participant, convey what restricted info I will accept"
  — Partial: `EP-01-002` and `VP-05-007` mapped as proxies. Deferred — see #2564.
- **story_2022_073** — "As a Participant, convey TLP restriction level I will accept"
  — Partial: `EP-01-003` mapped. Deferred — see #2564.
