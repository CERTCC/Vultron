---
title: CVD Recipe Scenario Injects
status: active
description: >
  Classification of CERT Guide to CVD problem-solving recipes as Vultron
  scenario injects. Each recipe is mapped to the Vultron protocol constructs
  involved and assigned to an implementability tier.
relevant_packages:
  - vultron/demo/scenario
  - vultron/demo/exchange
related_notes:
  - notes/demo-future-ideas.md
  - notes/demo-ci-scenario-coverage.md
  - notes/call-out-configuration.md
related_specs:
  - specs/multi-actor-demo.yaml
source: IDEA-1223
---

# CVD Recipe Scenario Injects

This file classifies the 21 CERT Guide to CVD "Recipe Cards" from
`https://certcc.github.io/CERT-Guide-to-CVD/howto/coordination/cvd_recipes/`
as Vultron scenario injects. Local source: `wip_notes/cvd_recipes.md` and
`wip_notes/recipes/`.

Each recipe maps to one or more Vultron protocol dimensions (RM, EM, CS). The
classification answers: *is this inject implementable today?*

---

## Implementability Tiers

| Tier | Label | Meaning |
|---|---|---|
| A | Implementable now | Maps cleanly to existing RM/EM/CS transitions and demo infrastructure |
| B | Needs protocol/infra work | Requires new demo actors, new protocol flows, or features not yet built |
| C | Out of scope | Not Vultron-protocol-visible; vendor-internal policy; no new state transitions |

---

## Tier A — Implementable Now

These recipes produce scenario injects that exercise existing Vultron state
machines. Each has a corresponding Task issue under epic #1160.

### x02 — Evidence of active exploitation during embargo

**Recipe card**: Roles: Reporter. Phase: Reporting, Validation, Remediation.

**Protocol mapping**:

- CS dimension flip: `x → X` (exploit public) and/or `a → A` (active attacks)
- EM: active embargo is immediately rendered moot; transitions `EM.ACTIVE → EM.EXITED`
- All participants must be ready to terminate embargo and publish immediately

**Inject design**: Inject a CS status update mid-scenario that sets `X=True` or
`A=True`. Verify that demo actors proceed to the Public Awareness phase without
waiting for the nominal embargo expiry date.

**Vultron issue**: Tracked as a Task under epic #1160.

---

### x06 — Vendor stops responding

**Recipe card**: Roles: Reporter. Phase: Reporting, Validation, Remediation, Public Awareness.

**Protocol mapping**:

- RM: Vendor's `RM.ACCEPTED` never transitions forward; embargo clock expires
- EM: after agreed date passes with no vendor action, Reporter may exit embargo
- Trigger: no response for ≥2 weeks + embargo deadline passed *or* 6+ weeks silence

**Inject design**: After case creation and embargo establishment, the Vendor
actor's trigger endpoint is not called. The Reporter actor waits past the
embargo date, then exercises the `close_case` / publication path unilaterally.

**Vultron issue**: Tracked as a Task under epic #1160.

---

### x07 — Vendor explicitly declines to act

**Recipe card**: Roles: Reporter. Phase: Validation and prioritization.

**Protocol mapping**:

- RM: Vendor transitions `RM.VALID → RM.DEFERRED` or `RM.INVALID` without ACCEPTED
- Reporter's obligation to the Vendor coordination process terminates
- Reporter may proceed to Public Awareness independently

**Inject design**: After report submission and validation, the Vendor actor sends
a `Reject(Report)` rather than `Accept(Report)`. Verify Reporter can proceed
through the rest of the CVD lifecycle unilaterally.

**Vultron issue**: Tracked as a Task under epic #1160.

---

### x08/x19 — Vendor requests embargo extension (combined)

**Recipe card**: x08 from Reporter/Coordinator perspective; x19 from Vendor
perspective. Roles: Reporter, Coordinator, Vendor. Phase: Remediation.

**Protocol mapping**:

- EM: Vendor is not ready → initiates `EM.REVISE` with a new proposed end date
- Reporter/Coordinator evaluates vendor's responsiveness history before deciding
- Outcomes: extend (accept revision) or decline (publish as-is)

**Inject design**: Near the nominal embargo expiry, the Vendor actor sends an
`EmbargoRevisionProposal`. The Reporter/Coordinator decides based on a
configurable policy whether to accept or decline. Two sub-cases:

1. Vendor cooperative → embargo extended (EM:REVISE → EM:ACTIVE with new date)
2. Vendor not acting in good faith → Reporter declines, proceeds to publication

**Vultron issue**: Tracked as a Task under epic #1160.

---

### x10 — Reporter stops responding

**Recipe card**: Roles: Vendor. Phase: Reporting, Validation, Remediation, Public Awareness.

**Protocol mapping**:

- Vendor continues through RM and CS lifecycle independently
- No embargo obligation to a non-communicating Reporter
- Vendor may apply bug bounty policy as appropriate

**Inject design**: After initial report submission, the Reporter actor's trigger
endpoint is not called again. Vendor proceeds through validation, fix
development, and publication without Reporter involvement.

**Vultron issue**: Tracked as a Task under epic #1160.

---

### x11 — Premature public disclosure

**Recipe card**: Roles: Vendor. Phase: Reporting, Validation, Remediation.

**Protocol mapping**:

- CS: `p → P` flip occurs before the nominal embargo expiry
- EM: active embargo is immediately rendered moot; transitions `EM.ACTIVE → EM.EXITED`
- All participants proceed to Public Awareness phase regardless of RM status

**Inject design**: Inject a CS status update mid-scenario that sets `P=True`
before the embargo expires. Verify all demo actors transition to the Public
Awareness phase and that the embargo is correctly exited.

**Vultron issue**: Tracked as a Task under epic #1160.

---

### x15 — Second independent report of embargoed vulnerability

**Recipe card**: Roles: Vendor. Phase: Reporting, Validation, Remediation.

**Protocol mapping**:

- A second Reporter joins the case (new RM lifecycle starts for that participant)
- Vendor must verify independence of the second report from the first
- Vendor should accelerate EM timeline given apparent ease of rediscovery
- Bug bounty policy for independent rediscovery applies

**Inject design**: After a case is under embargo, a second Reporter actor
submits the same vulnerability. Vendor actor receives both reports, verifies
independence (or overlap), and may accelerate the embargo timeline.

**Vultron issue**: Tracked as a Task under epic #1160.

---

### x18 — Incompatible disclosure policies across vendors

**Recipe card**: Roles: Reporter, Vendor, Coordinator. Phase: Reporting, Validation, Remediation.

**Protocol mapping**:

- MPCVD case with two or more vendors holding incompatible embargo policies
- Fast-moving vendor may exit EM:ACTIVE early; other vendors still in remediation
- Three response options: shorten embargo, delay notifying fast-mover, or notify
  fast-mover only at public-awareness time (generally least optimal)

**Inject design**: MPCVD scenario where Vendor1 has a short default embargo
policy and Vendor2 has a longer one. Verify that the EM negotiation (REVISE
cycles) can resolve the conflict, or that the coordinator elects to shorten the
embargo to match the fast-mover's policy.

**Vultron issue**: Tracked as a Task under epic #1160.

---

## Tier B — Needs Protocol Work or New Demo Infrastructure

These recipes are interesting but require features or actor configurations not
yet available. Each has a corresponding Idea issue for future planning.

### x03 — Unable to engage vendor contact

**Protocol mapping**: Reporter cannot find a contact → escalates to a
Coordinator acting as a routing intermediary before the case is even created.
This is a pre-case "find me a contact" flow not yet modelled in Vultron.

**Gap**: No protocol primitives for the "I can't find the vendor, help me reach
them" phase. Would require a coordinator discovery service or a new pre-case
message type.

**Idea issue**: #2060

---

### x05 — Vendor hostile to reporters

**Protocol mapping**: Reporter routes through Coordinator as an anonymising
proxy. Coordinator forwards the report to Vendor without revealing the
Reporter's identity.

**Gap**: Vultron's RM lifecycle assumes Reporter identity is known to Vendor.
Anonymous/proxy reporting requires a new actor identity model or explicit
privacy-preserving routing primitives.

**Idea issue**: #2061

---

### x12 — Vulnerability public before vendor awareness

**Protocol mapping**: CS.P flips before the Vendor has received *any* report
(no RM state exists on Vendor side). Vendor discovers the vuln through external
monitoring rather than a Reporter inbox.

**Gap**: Current demo scenarios all start with a Finder submitting a report.
Modelling vendor-discovers-from-public requires a new entry point (Vendor
learns from CS.P transition without a prior RM.RECEIVED).

**Idea issue**: #2062

---

### x16 — Known downstream vendors in supply chain

**Protocol mapping**: Originating vendor knows which downstream vendors are
affected and must invite them as MPCVD participants. Requires
supply-chain-structured multi-vendor invite flows with coordinated embargo
pacing.

**Gap**: Existing MPCVD demos don't model an explicit "upstream vendor discovers
downstream dependents and invites them" pattern with policy synchronisation.

**Idea issue**: #2063

---

### x17 — Unknown downstream vendors

**Protocol mapping**: Similar to x16 but originating vendor cannot enumerate
affected downstream parties. Short embargo + public disclosure triggers
downstream self-identification.

**Gap**: Same as x16 plus requires a mechanism for downstream vendors to
self-register as affected after public disclosure.

**Idea issue**: #2064

---

### x21 — Failing CVD case — escalate to coordinator

**Protocol mapping**: Parties in a failing case engage a Coordinator mid-case
to mediate. Requires an actor joining an already-in-progress case in a Coordinator
role, not just as a participant.

**Gap**: Existing demos either start with a Coordinator or have no
Coordinator. Mid-case coordinator escalation requires case ownership transfer or
a new "invite coordinator mid-case" flow.

**Idea issue**: #2065

---

## Tier C — Out of Scope

These recipes do not produce new Vultron protocol state transitions and are not
worth modelling as demo injects.

| Recipe | Reason |
|---|---|
| x01 — Finder exits early | Minor RM variant (Reporter disengages); no new state |
| x04 — No bug bounty | Vendor-internal policy; not Vultron-protocol-visible |
| x09 — Too many vendors / excessive complexity | Already covered by MPCVD scenarios (FCVCV, etc.) |
| x13 — Out-of-scope report | Vendor-internal RM routing; INVALID is already modelled |
| x14 — Policy violation in discovery | Vendor-internal; orthogonal to CVD protocol state |
| x20 — Unanticipated media attention | External to protocol; no Vultron state to exercise |

---

## Summary Table

| Recipe | Title (abbreviated) | Tier | Issue |
|---|---|---|---|
| x01 | Finder lacks resources | C | — |
| x02 | Active exploitation during embargo | A | #2052 |
| x03 | Can't find vendor contact | B | #2060 |
| x04 | No bug bounty | C | — |
| x05 | Vendor hostile to reporters | B | #2061 |
| x06 | Vendor stops responding | A | #2053 |
| x07 | Vendor declines to act | A | #2054 |
| x08/x19 | Vendor requests embargo extension | A | #2055 |
| x09 | Too many vendors | C | — |
| x10 | Reporter stops responding | A | #2056 |
| x11 | Premature public disclosure | A | #2057 |
| x12 | Vuln public before vendor aware | B | #2062 |
| x13 | Out-of-scope report | C | — |
| x14 | Policy violation in discovery | C | — |
| x15 | Second independent report | A | #2058 |
| x16 | Known downstream vendors | B | #2063 |
| x17 | Unknown downstream vendors | B | #2064 |
| x18 | Incompatible disclosure policies | A | #2059 |
| x20 | Unanticipated media attention | C | — |
| x21 | Failing case — escalate to coordinator | B | #2065 |
