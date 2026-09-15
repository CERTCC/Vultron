## 12. Conformance [N]

### 12.1 Conformance Model Overview

Conformance is two-dimensional: **capability sets** (what protocol machinery an
implementation provides) and a **role profile** (which roles it claims). A
conformance claim names capability sets and roles directly:

> `CapabilitySet [+ CapabilitySet ...] / Role [+ Role ...]`

Examples: `Observer / Reporter`, `Observer / Vendor`, `Observer / Vendor + Deployer`,
`Observer + Authority + Hosting / Coordinator + Case Owner`.

The Observer capability set is required for all participation.
Role obligations are additive and orthogonal: no role subsumes another.

Capability set names and role names come from §12.2 and §12.3 respectively.

**Roles and capability expectations.** The relationship between roles and
capabilities is bidirectional. An implementation must have the capability
prerequisites for a role before it can be assigned that role (§12.3.1).
Conversely, holding a role in a case creates an expectation that the
implementation has those capabilities — other participants act on that
assumption. See §11.1 for the role assignment gatekeeping rules.

!!! warning "Capability sets are not the same as conformance test layers"
    This project uses two distinct schemes, and they must not be conflated:

    - **Capability sets**, defined here, describe *what an implementation
      provides* — a claim an implementer makes about their software.
    - **Conformance test layers (L1–L4)**, used in the behavioral conformance
      material, describe *what a test verifies* — syntax, semantics, behavior,
      and internal process structure. These are orthogonal: an Observer
      implementation is tested at layers L1 through L3.

    Earlier drafts of this document used `T0`/`T1`/`T2` for capability tiers and
    `L0`/`L1`/`L2` before that. Both sets of labels are superseded.
