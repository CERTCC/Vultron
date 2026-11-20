---
title: "Projecting a CSAF Document From a Case (Design Direction)"
status: draft
kind: plan
tracks:
  - "#6706"
  - "#6785"   # products and statuses in the projection
  - "#6791"
  - "#5130"
  - "#6758"   # epic: CVE record and Vulnerability Note adapters on the same port
description: >
  Design direction for producing a CSAF 2.1 document from a participant's case
  replica (ADR-0219): a call site's profile cuts the case and its ledger into a
  preview, and a CSAF renderer translates only the preview. The profiles, the
  preview's ledger list and the renderer are built (CSAF-06); this holds what is
  not: the two call sites, the format-neutral port, the rendering rules still
  open, and the call-site requirement text #6706 adds.
related_specs:
  - specs/csaf-report-content.yaml
  - specs/case-management.yaml (CM-17)
  - specs/message-validation.yaml (MV-12)
  - specs/behavior-tree-integration.yaml (BT-20-004)
related_notes:
  - notes/selective-disclosure.md
  - notes/csaf-report-content.md
  - notes/vulnerability-items.md
  - notes/core-wire-rendering-port.md
  - notes/wire-core-boundary.md
relevant_packages:
  - vultron/core/models
  - vultron/wire/csaf
  - vultron/core/behaviors/report
  - vultron/adapters/driving/fastapi
---

# Projecting a CSAF Document From a Case (Design Direction)

A participant produces a CSAF 2.1 document from its replica in two steps: its call
site's profile cuts the case into a preview, then a renderer translates the
preview into CSAF (ADR-0219). Built: the public and joined profiles
(`vultron/core/models/case_projection_profile.py`), the preview's ledger list and
`CasePreview.for_projection`, the cut and the call site's inputs
(`ProjectionCut`, `ProjectionInputs` in `vultron/core/models/case_projection.py`)
and the CSAF renderer
(`vultron/wire/csaf/projection.py`); `specs/csaf-report-content.yaml` CSAF-06
states their rules. No call site uses them yet.

## Where the Code Goes

- **The draft step reaches the renderer through a port.** Core never imports wire
  (ARCH-01-001), so the deterministic backend of `DraftAdvisoryArtifact`
  (`vultron/core/behaviors/report/publish_artifact_tree.py`) cuts the preview in
  core and calls an injected render port that the adapter layer wires to the CSAF
  renderer, in the pattern of `WireRenderPort` (`notes/core-wire-rendering-port.md`).
  It is a new port, not `WireRenderPort`: that port renders one object for
  delivery, while this one takes a `ProjectionCut` with the call site's
  `ProjectionInputs`. A missing port is a wiring error, never a fallback.
- **The projection port names no format; each format is an adapter.** The port
  takes a `ProjectionCut` (`ProjectionCut.of(case, ledger, profile)`, which carries
  the profile's name and label so a document cannot be labelled by another
  profile) and `ProjectionInputs`; neither names a format, and the CSAF
  adapter fixes the category, `csaf_base`. A CVE record drafted at the CVE ID
  assignment call-out and a CERT Vulnerability Note in the VINCE publication
  format are later adapters (#6759, #6760). A port shaped for CSAF would make each
  later format build a port of its own (CS-22-001).
- **The call site supplies the inputs.** `tracking.status` is `final` at
  publication and `interim` at the joined endpoint, because the case continues to
  change. With no caller credit, the call site passes
  `reporter_acknowledgments(case)` as the default (ADR-0218).
- **The operator endpoint is a read.** It reads the actor's replica, cuts it with
  the joined profile and returns the rendered JSON. It writes nothing to the
  DataLayer, adds no ledger entry and sends no activity. The operator gives the
  document to the outside party out of band.
- **No invite-site call site yet.** It waits until Vultron can invite a party that
  does not use Vultron.

## Rendering Rules Not Built Yet

- **Derived involvement statuses (#6791).** The renderer makes only `completed`
  actions, one per act the joined profile keeps. `outstanding`, `deferred` and
  `discontinued` derive from the state at the preview's position (the crosswalk
  concept mapping, `docs/reference/csaf_crosswalk/concept_mapping.md`); adding one
  bumps the joined profile's version.
- **A category other than `csaf_base` (#6785).** The renderer takes the category
  from its call site, and `csaf_base` is the only one while the case holds no
  products (ADR-0187). Once a vendor's record holds products and authored product
  statuses (ADR-0220), a call site renders the category whose requirements its
  preview meets (`notes/affected-products.md` § "The Projection"). A projection
  never copies a reporter's product tree: that republishes the reporter's claim as
  the projector's.
- **Acknowledgments in a Vulnerability Report (#6785).** In `csaf_base` an absent
  list carries no "no credit wanted" meaning; the Vulnerability Report rule of
  ADR-0218 applies once a projection can use that category.

## Requirement Text the Call Sites Add

These land in CSAF-06 with #6706, with the tests that check them. Each cites
ADR-0219.

- MUST: The draft step of the publication pipeline MUST use the public profile,
  and the operator CSAF endpoint MUST use the joined profile.
- MUST NOT: The operator CSAF endpoint MUST NOT write to the DataLayer, add a
  ledger entry or send an activity.
