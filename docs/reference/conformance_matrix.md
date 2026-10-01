---
description: >
  Which capability sets each Vultron role requires, which transitions each
  role may drive, and the named configurations a conformance claim can use,
  as tables checked against the specification.
stakeholder_type: [platform-developer]
level: 400
---

# Conformance Matrix

{% include-markdown "../includes/not_normative.md" %}

A Vultron conformance claim names capability sets and roles: `CapabilitySet [+ CapabilitySet ...] / Role [+ Role ...]` ([§12.1 Conformance Model Overview](vultron-spec/conformance.md#121-conformance-model-overview)).
This page lays the two dimensions out as tables so that an implementer can read off what a given role claim requires.
The tables are derived from [§12 Conformance](vultron-spec/conformance.md#12-conformance-n) of the Vultron Protocol Specification, and a test fails when the roles, capability sets, or named configurations here stop matching the specification's own tables.
The specification is normative; this page is a view of it.

## Capability sets by role

A capability set is a property of software; a role is a position in a case ([§12.3.3 Roles and Capability Sets Are Independent](vultron-spec/conformance.md#1233-roles-and-capability-sets-are-independent)).
Every participant, whatever its roles, implements the Case Observer capability set ([§12.2 Capability Sets](vultron-spec/conformance.md#122-capability-sets)).
The two further sets are required by the two protocol authority roles they serve, and are optional for every process role.

| Role | Case Observer | Case Decision | Case Hosting |
|---|---|---|---|
| Reporter | Required | Optional | Optional |
| Vendor | Required | Optional | Optional |
| Deployer | Required | Optional | Optional |
| Coordinator | Required | Optional | Optional |
| CVE Numbering Authority (CNA) | Required | Optional | Optional |
| Observer | Required | Optional | Optional |
| Case Owner | Required | Required | Optional |
| Case Manager | Required | Optional | Required |

*Required* means the role cannot be held without the capability set.
*Optional* means the set adds obligations the role does not itself need.
Case Decision defines the Case Owner's governance capabilities, and Case Hosting requires holding the CASE_MANAGER role for each case it hosts ([§12.2 Capability Sets](vultron-spec/conformance.md#122-capability-sets)).
Neither set substitutes for Case Observer.

## Transitions each role may drive

Every participant tracks all five state machines: Report Management (RM), Embargo Management (EM), Participant Embargo Consent (PEC), and the two Case State (CS) dimensions, vendor aware, fix ready, fix deployed (VFD) and public aware, exploit public, attacks observed (PXA).
Which transitions a participant may drive depends on its roles ([§12.3.1 Process Roles](vultron-spec/conformance.md#1231-process-roles), [§12.4 Role-Specific Normative Requirements](vultron-spec/conformance.md#124-role-specific-normative-requirements)).

| Role | Drives |
|---|---|
| Reporter | Report Submission (RS); its own RM transitions |
| Vendor | Its own Fix Ready transition (CF) |
| Deployer | Its own Fix Deployed transition (CD) |
| Coordinator | Case participant management; its own RM transitions |
| CVE Numbering Authority (CNA) | CVE ID assignment; a participant without the role delegates it |
| Observer | No VFD drive obligations; may report PXA observations |
| Case Owner | Shared EM transitions; authorizes status adoption; offers case ownership transfer |
| Case Manager | Canonical ledger writes; case replica synchronization; roster operations on the Case Owner's behalf |

Any participant may report a PXA observation ([§12.4.2 Participant-Agnostic CS Transitions (PXA)](vultron-spec/conformance.md#1242-participant-agnostic-cs-transitions-pxa)); reporting is not adoption, which the CASE_MANAGER decides ([§10.3 Status Adoption: The Two-Seam Model](vultron-spec/interactions.md#103-status-adoption-the-two-seam-model)).

## Named configurations

Common combinations have names ([§12.2 Capability Sets](vultron-spec/conformance.md#122-capability-sets)).
The names are informative; a conformance claim lists the full capability sets.

| Configuration | Capability sets | Roles |
|---|---|---|
| Hosting Coordinator | Case Observer + Case Decision + Case Hosting | Coordinator + Case Owner |
| Self-coordinating Vendor | Case Observer + Case Decision + Case Hosting | Vendor + Deployer + Case Owner |
| Bug Bounty Platform | Case Observer + Case Hosting | Case Manager (Case Decision optional) |

## What the matrix does not say

Capability shapes ([Annex G Capability Shapes](vultron-spec/annex-g-capability-shapes.md#annex-g-capability-shapes-i)) are not part of any capability set, and a conformance claim does not state which shapes an implementation provides ([§12.6 Capability Shapes](vultron-spec/conformance.md#126-capability-shapes)).
Conformance test layers L1 through L4 ([§12.5 Conformance Testing Approach](vultron-spec/conformance.md#125-conformance-testing-approach)) describe what a test verifies, not what an implementation provides, and are not a column here.
The [Concept Taxonomy](vultron-taxonomy.md#view-3-conformance-view-custom) places this page among the other views of the protocol.
