## 13. Conformance [N]

### 13.1 Conformance Model Overview

Conformance is two-dimensional: **capability sets** (what protocol machinery an
implementation provides) and a **role profile** (which roles it claims). A
conformance claim names capability sets and roles directly:

> `CapabilitySet [+ CapabilitySet ...] / Role [+ Role ...]`

Examples: `Case Observer / Reporter`, `Case Observer / Vendor`, `Case Observer / Vendor + Deployer`,
`Case Observer + Case Decision + Case Hosting / Coordinator + Case Owner`.

The Case Observer capability set is required for all participation.
Role obligations are additive and orthogonal: no role subsumes another.

Capability set names and role names come from [§13.2 Capability Sets](../conformance.md#132-capability-sets) and [§13.3 Role Taxonomy](../conformance.md#133-role-taxonomy) respectively.

**Roles and capability expectations.** The relationship between roles and
capabilities is bidirectional. An implementation must have the capability
prerequisites for a role before it can be assigned that role ([§13.3.1 Process Roles](../conformance.md#1331-process-roles)).
Conversely, holding a role in a case creates an expectation that the
implementation has those capabilities — other participants act on that
assumption. See [§12.1 Role Assignment](../interactions.md#121-role-assignment-n) for the role assignment gatekeeping rules.

!!! warning "Capability sets are not the same as conformance test layers"
    This project uses two distinct schemes, and they must not be conflated:

    - **Capability sets**, defined here, describe *what an implementation
      provides* — a claim an implementer makes about their software.
    - **Conformance test layers (L1–L4)**, used in the behavioral conformance
      material, describe *what a test verifies* — syntax, semantics, behavior,
      and internal process structure. These are orthogonal: a Case Observer
      implementation is tested at layers L1 through L3.

    A conformance claim names capability sets; a test result names a layer. The
    two are answering different questions and are not interchangeable.
