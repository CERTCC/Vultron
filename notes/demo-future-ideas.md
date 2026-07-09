---
title: Future Demo Ideas
status: active
description: >
  Future demo scenarios and multi-actor workflow ideas for the Vultron
  prototype. Scenario planning tracked in GitHub Issues under epic #1093.
relevant_packages:
  - vultron/demo
related_notes:
  - notes/event-driven-control-flow.md
---

# Future Demo Ideas

## Scenario naming convention

Scenarios are named by the sequence of actor roles involved:

- **F** = Finder, **V** = Vendor, **C** = Coordinator, **D** = Deployer
- Numbers distinguish multiple actors of the same role (V1, V2, C1, C2)

## Implemented scenarios

| Scenario | File | Description |
|----------|------|-------------|
| FV | `vultron/demo/scenario/two_actor_demo.py` | Finder + Vendor; simple coordination |
| FVV | `vultron/demo/scenario/fvv_demo.py` | Finder → Vendor1 → Vendor2; no coordinator; independent fix paths (implements #1265) |

## Deprecated / idea-mine only

The following files exist but are based on much older code and no longer work.
They may be useful as reference for future scenario development but should not
be treated as working implementations.

| Scenario | File | Notes |
|----------|------|-------|
| FCV | `vultron/demo/scenario/three_actor_demo.py` | Obsolete; see planned scenarios below |
| FVCV (handoff) | `vultron/demo/scenario/multi_vendor_demo.py` | Obsolete; see #1214 for the planned replacement |

## Planned scenarios (from #1131 planning, 2026-07-06)

### Core multi-party scenarios

| Scenario | Issue | Description | Blocked by |
|----------|-------|-------------|------------|
| FCV | #1234 | F reports to C; C invites V; three-actor coordination | — |
| FVCV-extension | #1212 | V1 retains ownership; C is participant; C suggests V2 | — |
| FVCV-handoff | #1214 | V1 transfers ownership to C; C invites V2 | #1212 |
| FCCV-extension | #1215 | C1 retains case; C2 is participant; C2 asks C1 to invite V | — |
| FCCV-handoff | #1216 | C1 transfers to C2; C2 invites V | #1215 |
| FCVCV | #1217 | F+C1+V1+C2+V2 (5 actors) | #1212, #1215 |

### Role-expansion scenarios

| Scenario | Issue | Description |
|----------|-------|-------------|
| Deployer role | #1227 | V develops fix; D deploys in their environment |
| Case split/merge | #1229 | Parent/child/sibling case relationships |
| Multi-reporter | #1231 | Two Finders, one C consolidates into one case |

### Cross-cutting variations (composable with any scenario)

| Variation | Issue | Description |
|-----------|-------|-------------|
| Invitation rejection | #1218 | Invited actor transitions RM:R→I→C |
| Tentative rejection | #1221 | Invited actor transitions RM:R→I→V (reconsiders) |
| Embargo variations | #1222 | Negotiation, collapse, deliberate delay |
| CVD recipe injects | #1223 | Twists from the CERT Guide to CVD cvd_recipes |

### Pre-case ACK flow (`auto_create_case=False`)

Issue #1133 introduced `ActorConfig.auto_create_case` (default: `True`). When
`False`, the receiver stores the inbound report but does **not** auto-create a
`VulnerabilityCase`, enabling the receiver to send a pre-case
`Read(Offer(Report))` acknowledgment (`AckReportReceivedUseCase`) before
deciding to accept or reject.

The **tentative rejection → acceptance** scenario (#1221) is the first planned
demo to exercise this path:

1. Finder submits report.
2. Vendor (with `auto_create_case=False`) sends pre-case ACK via trigger.
3. Vendor invalidates report (RM:R→I) — "tentative rejection".
4. Vendor later validates (RM:I→V) and engages — "reconsideration".

Once #1221 is implemented, `ack_report` should be wired into
`EXPECTED_EVENT_TYPES` in `test/ci/test_case_ledger_invariants.py` (currently
excluded; see the comment at line 413 citing #1133).

See also: #1079 (multi-coordinator motivation from FIRSTCON 2026)

---

## Two-Actor Demo: Finder, Vendor coordinate in separate containers

Two actors, a finder and vendor, running in separate containers,
communicating through the Vultron Protocol. Finder reports vulnerability to
Vendor, and Finder proposes embargo, vendor accepts report, accepts embargo
creates case, adds report and embargo to case, adds finder as case
participant, adds two vulnerabilities to the case based on the report.
They exchange a few messages back and forth, maybe including a draft CVE
record or something like that. This will be a good demo for showing the basic
Vultron Protocol interactions and the behavior tree implementation.

## Three-Actor Demo: Finder, Vendor, Coordinator coordinate in separate containers

A three-actor demo (finder, vendor, coordinator). Finder reports to
coordinator. Coordinator creates case, adds finder as participant.
Coordinator has a default embargo policy that it applies to all cases.
Coordinator proposes embargo to finder, finder accepts. Coordinator adds
embargo to case. Coordinator invites Vendor to case, vendor tentatively
rejects (invalidates the report) with a message back to the Coordinator
asking a question. The Coordinator relays the question to the Finder.
Finder responds to Coordinator, Coordinator replies to vendor with the
Finder's response. Vendor accepts the report and the embargo and becomes
a participant in the case. A few messages are exchanged between the three
actors within the context of the case, including a draft CVE record that
they refine together. The Vendor announces to the case that they have
published, which triggers a case status update reflecting public
awareness. Finder reports they have published as well. Then the
coordinator closes the case.

## MultiParty Demo: Two-Actor expands to Coordinator and more Vendors

A demo in which the process initially looks like scenario 1 above and an
embargo is established, but
then the vendor realizes they need the assistance of a coordinator to get
more vendors engaged. They offer the coordinator the opportunity to take
over the case, and the coordinator accepts. The coordinator becomes the
new case owner, and the original finder and vendor remain participants.
The coordinator then invites two more vendors to the case with the
existing embargo. They accept and become participants. One of the added
vendors asks for the embargo to be extended, which triggers a discussion
between the participants, and they agree to extend the embargo in
principle. The coordinator triggers the case actor to propose a new
embargo with the agreed to terms. Participants agree to the new embargo.
They exchange a few more messages, the coordinator creates a CVE record
and distributes it for refinement. Coordinator and Finder announce
publication, followed quickly by the original vendor and the two added vendors.
The coordinator then closes the case.

Each of these demos would need to show actors running in independent
containers, communicating through the Vultron Protocol, with the CaseActor
managing the case state and enforcing the rules around who can do what within
the case.
CaseActor is probably also a "spin up on demand" container that gets
instantiated when a case is created.

> **Note (2026-07-06)**: These sketch descriptions are superseded by the
> structured scenario table above. The Two-Actor scenario is implemented.
> Three-Actor (FCV) is planned for re-implementation in #1234 (the existing
> file is deprecated). MultiParty corresponds to FVCV-handoff (#1214).
> See epic #1093 for the full planned scenario set.
