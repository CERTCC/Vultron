---
description: >
  Where an existing ticketing, embargo, or threat-monitoring workflow emits
  Vultron messages, milestone by milestone.
stakeholder_type: [platform-developer]
level: 300
---

# Process Implementation Notes

{% include-markdown "../includes/not_normative.md" %}

Use this page to find where your existing workflow intersects the Vultron Protocol, so that each milestone your system already records emits the protocol message that reports it.
Vultron does not replace a tracker, an embargo calendar, or a threat-intelligence feed; it asks each of them to speak at the moments the protocol cares about.
You finish with a list of your own workflow's milestones, each paired with the message it emits and the guide that shows how to send it.

!!! note "Scope of this page"

    This page is about integrating *your* system.
    For the architecture of the reference implementation — hexagonal boundaries, the ActivityStreams inbox pipeline, behavior tree orchestration — see [Reference Implementation Architecture](../topics/reference_architecture.md).

---

## Prerequisites

- A workflow you already run for vulnerability reports, embargoes, or public-disclosure monitoring.
- Working knowledge of the three process models the protocol is built from: [Report Management (RM)](../topics/process_models/rm/index.md), [Embargo Management (EM)](../topics/process_models/em/index.md), and [Case State (CS)](../topics/process_models/cs/index.md).
  Each milestone below is a transition in one of them.
- The [formal message names](../reference/formal_protocol/messages.md) the transitions carry.
  Each one is paired below with the activity guide that shows how to send it on the wire.

---

## Map your report workflow onto RM

The RM process is close to an ordinary [IT Service Management (ITSM)](https://en.wikipedia.org/wiki/IT_service_management){:target="_blank"} incident or service-request workflow, so a ticketing system, a Kanban board, or a bug tracker can carry it with few changes.
The change that is needed is at the milestones: intercept each one and emit the [RM message](../reference/formal_protocol/messages.md#rm-message-types) that reports it.

| When your workflow records that… | Emit | How |
|---|---|---|
| a report has arrived | Report Acknowledgement (RK) | [How to Acknowledge a Report](activitypub/activities/acknowledge.md) |
| validation is complete | Report Valid (RV) or Report Invalid (RI) | [How to Report a Vulnerability](activitypub/activities/report_vulnerability.md) |
| prioritization is complete | Report/Case Accepted (RA) or Report/Case Deferred (RD) | [How to Advance a Case Through Report Management](activitypub/activities/manage_case.md) |
| the report or case is closed | Report Closed (RC), or the case closure | [How to Advance a Case Through Report Management](activitypub/activities/manage_case.md) |

If your workflow has a validation step but no explicit prioritization step, treat the decision to assign the ticket to an engineer as prioritization and emit RA there.

### Share pre-publication drafts through the case

Participants in a multi-party case often share advisory drafts during the embargo.
The protocol does not prescribe that exchange, because the case can complete without it.
If your workflow has a draft-review step, carry it as case notes: the General Inquiry (GI) and General Acknowledgement (GK) [messages](../reference/formal_protocol/messages.md#other-message-types) are enough, and [How to Post a Status Update or a Case Note](activitypub/activities/status_updates.md) shows the activity.
The [ISO/IEC 29147:2018 crosswalk](../reference/iso_crosswalks/iso_29147_2018.md) maps that standard's advisory-publication clauses onto the same messages.

---

## Map your embargo handling onto EM

The EM process fixes when publication restrictions lift.
It does not schedule what each participant publishes afterwards.
Most participants publish at their own pace shortly after the embargo ends, and when closer coordination is needed the participants arrange it among themselves.

- If your system tracks an embargo end date, emit the proposal, acceptance, and termination messages from that record — see [How to Establish an Embargo](activitypub/activities/establish_embargo.md) and [How to Revise or Terminate an Embargo](activitypub/activities/manage_embargo.md).
- If your system labels sensitive information with the [Traffic Light Protocol (TLP)](https://www.first.org/tlp){:target="_blank"}, keep doing so.
  An embargo declaration can carry the label: "This case is <span style="color:#FFC000;background-color:#000000">**TLP:AMBER**</span> until 2024-03-31 23:59:59 UTC, at which time it becomes <span style="color:#FFFFFF;background-color:#000000">**TLP:CLEAR**</span>."
  The [CERT Guide to Coordinated Vulnerability Disclosure (CVD)](https://certcc.github.io/CERT-Guide-to-CVD/howto/operation/opsec/){:target="_blank"} covers TLP in CVD in more detail.

---

## Map your fix and monitoring workflows onto CS

The CS model has two halves, and they attach to different parts of your organization.
The Vendor Awareness, Fix Readiness, and Fix Deployed substates are specific to each Vendor or Deployer; the Public Awareness, Exploit Public, and Attacks Observed substates are shared by the whole case.
All six emit [CS messages](../reference/formal_protocol/messages.md#cs-message-types), and [How to Post a Status Update or a Case Note](activitypub/activities/status_updates.md) shows the activity for each.

### The fix path

Changes to a Vendor's development process are small and sit at three milestones.

| When your workflow records that… | Emit |
|---|---|
| the report has reached you as the Vendor | Vendor Awareness (CV) |
| a fix is ready | Fix Readiness (CF), and consider terminating any active embargo so publication can proceed |
| the fix has been deployed, where you also deploy | Fix Deployed (CD) |

A Deployer that is not the Vendor has one integration point: emit CD when deployment is complete.
Deployers other than the Vendor are rarely case participants, but the message exists for when they are.

### The public-awareness path

The other half of the CS model depends on watching public and private sources for leaked information, research publications, and adversary activity.
That is the work a threat-intelligence or threat-analysis function already does, so wire it to emit the message for what it finds.

| When your monitoring detects… | Emit |
|---|---|
| the vulnerability has been published | Public Awareness (CP) |
| an exploit has been published | Exploit Public (CX) |
| attacks are being observed | Attacks Observed (CA) |

Some of that detection can be automated:

- analysts or search agents watch for early publication of the vulnerability,
- Intrusion Detection System (IDS) and Intrusion Prevention System (IPS) signatures deployed before the fix is available give early warning of adversary activity, and
- code-publication and malware-analysis platforms are watched for exploit publication or use.

---

## Claim conformance

Once your milestones emit their messages, your system is a candidate for a conformance claim.
A claim names the capability sets you provide and the roles you take on ([§12.1 of the specification](../reference/vultron-spec/index.md#121-conformance-model-overview)), and conformance tests check it from the outside, in the four layers [§12.5](../reference/vultron-spec/index.md#125-conformance-testing-approach) defines.
Independent implementations are tested against the first three; the fourth applies only to the reference implementation.
