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

A "B → A" tier means the recipe was re-triaged from B to A in G16
(#2844); its per-recipe entry stays under the Tier B heading with the
re-triage rationale. "(sequenced)" means authorable once the named
prerequisite Tasks land.

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

**Prerequisite (found in #2844)**: a report added to an existing case is
stored only on the receiving replica and never written to the canonical case
ledger, so later joiners and ledger resyncs do not see it. The Task is blocked
by the core fix (#3665). The same fix blocks the two-reporter consolidation scenario
(#1231).

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

These recipes were originally filed as needing features or actor configurations
not yet available. Each has a corresponding Idea issue.

### Re-triage (G16, #2844, 2026-09-24)

The Tier B gap statements were written in July 2026 (#2051) and several had
gone stale by the time they were sorted. The re-triage checked each against the
code and specs of the day and reached a different verdict for three of the six.

| Recipe | Verdict | Why |
|---|---|---|
| x03 | Blocked — party discovery | Unchanged. Ejected from G08 (#2836) to G13 (#2841), which is deferred. |
| x05 | Blocked — pseudonymity | No pseudonym or redacted-view mechanism exists (#2562, G13, deferred). |
| x12 | Authorable, sequenced | Needs a case created already public, which EP-04-008 specifies but is not built. Task #3673. |
| x16 | Authorable now | The multi-vendor invite and suggest flows already exist. The gap statement was stale. Task #3674. |
| x17 | Blocked — admission | An outsider has no protocol act for asking to join a case (#3670). |
| x21 | Authorable now | A mid-case coordinator invite plus ownership transfer is exactly `fvcv-handoff`. The gap statement was stale. Task #3675. |

**Do not re-derive these gaps from the entries below.** The *Gap* lines record
what the re-triage found, not what the original filing said.

### x03 — Unable to engage vendor contact

**Protocol mapping**: Reporter cannot find a contact → escalates to a
Coordinator acting as a routing intermediary before the case is even created.

**Gap**: How a Reporter addresses a party it cannot identify. This is party
discovery, not a pre-case phase: ADR-0096 decided Vultron has no pre-case
phase, and that verdict does not unblock x03. It needs the actor identity model
that G13 (#2841) owns.

**Idea issue**: #2060 — open, blocked by G13.

---

### x05 — Vendor hostile to reporters

**Protocol mapping**: Reporter routes through Coordinator as an anonymising
proxy. Coordinator forwards the report to Vendor without revealing the
Reporter's identity.

**Gap**: Pseudonymity (#2562, owned by G13, deferred). Two facts make it a real
gap rather than an authoring task. No redacted case view is implemented
(CM-09-001 is a SHOULD that CM-09-004 lets the prototype defer). An invitee
also receives the full case snapshot on acceptance (CM-17-004), so every
participant sees every other participant.

**Rejected approximation**: the Coordinator files the report as Reporter while
the Finder stays out of the case. It runs, but it shows only that the Finder
is not a participant. That says nothing about protocol privacy, so it is not
worth building.

**Idea issue**: #2061 — open, blocked by #2562.

---

### x12 — Vulnerability public before vendor awareness

**Protocol mapping**: CS.P flips before the Vendor has received *any* report.
The Vendor learns of the vulnerability from public sources rather than a
Reporter inbox.

**Inject design**: A vendor-only variant. The Vendor self-reports a
vulnerability it learned of publicly and the case is created with P already
set. EP-04-008 then requires the case to stay at `EM.NONE`, with no embargo
ever created.

**Why sequenced, not approximated**: today every case is created at the
default CS and receives a default embargo (`InitializeDefaultEmbargoNode` has
no eligibility guard). Self-reporting and then publishing immediately would
record the history as vendor-aware-then-public and create an embargo only to
tear it down, which inverts the point of the recipe. The scenario waits for
case creation to honour P at creation (#3390, which skips the protocol default
embargo when P/X/A is already set) and for the vendor-only scenario it builds
on.

**Vultron issue**: Task #3673 under epic #1160, blocked by the vendor-only
scenario (#3667) and #3390.

---

### x16 — Known downstream vendors in supply chain

**Protocol mapping**: The originating vendor knows which downstream vendors are
affected and brings them in as MPCVD participants.

**Gap (none — stale)**: The original statement said existing demos don't model
an upstream-invites-downstream pattern with policy synchronisation. Both halves
exist:

- **Multi-vendor invites**: `fvv` has the owning vendor invite a second vendor.
  `fcvcv` and `fvcv-extension` have a non-owner participant suggest one.
- **Policy synchronisation**: shortest-wins at case creation (EP-04-003).
  Late invitees receive the active embargo in the Invite (CM-17-002), and
  revision cycles are what x18 already exercises.

**Inject design**: the new step is a *Vendor* participant (not the Case
Owner) suggesting the downstream vendors. CM-16-001 permits any participant to
suggest.

**Vultron issue**: Task #3674 under epic #1160.

---

### x17 — Unknown downstream vendors

**Protocol mapping**: The originating vendor cannot enumerate affected
downstream parties. A short embargo is followed by public disclosure, after
which downstream vendors identify themselves.

**Gap**: Two gaps, and this recipe needs both:

- **Admission**: an outsider has no protocol act for asking to join a case.
  The only `as:Join` in the vocabulary is an existing participant engaging.
- **Discovery**: how an outsider learns which case, or which CaseActor, to
  address. That is G13's (#2841, deferred), alongside x03.

**Rejected approximation**: the downstream vendor contacts an existing
participant off-protocol and is invited after publication. That demonstrates
a late invite, which other scenarios already cover, not self-identification.

**Idea issue**: #2064 — open, blocked by the admission Concern #3670.

---

### x21 — Failing CVD case — escalate to coordinator

**Protocol mapping**: The parties in a failing case bring in a Coordinator
mid-case to mediate.

**Gap (none for the owner-initiated form — stale)**: `fvcv-handoff` already
invites a Coordinator into an active case and transfers ownership to it
(CM-21). The recipe adds only a failure precursor, such as an x06-style stall
or an x08/x19 extension deadlock.

**Blocked variant**: when the Case Owner *is* the failing party, a Reporter
can only suggest a Coordinator (CM-16), and the suggestion waits on the
owner's acceptance with no deadline and no consequence when it goes
unanswered. That is a protocol-asks question, not a scenario (Concern #3669
under epic #3188).

**Not modelled**: how a mediator behaves. `CVDRole.COORDINATOR` exists, and
differentiated actor behaviour belongs to #1646 (deferred).

**Vultron issue**: Task #3675 under epic #1160.

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
| x12 | Vuln public before vendor aware | B → A (sequenced) | #3673 |
| x13 | Out-of-scope report | C | — |
| x14 | Policy violation in discovery | C | — |
| x15 | Second independent report | A | #2058 |
| x16 | Known downstream vendors | B → A | #3674 |
| x17 | Unknown downstream vendors | B | #2064 |
| x18 | Incompatible disclosure policies | A | #2059 |
| x20 | Unanticipated media attention | C | — |
| x21 | Failing case — escalate to coordinator | B → A | #3675 |
