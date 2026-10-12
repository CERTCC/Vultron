---
title: Stub Objects
status: active
kind: guidance
description: >
  Rules for the VulnerabilityCase stub, the only stub type the protocol
  permits. The wider selective-disclosure and redaction design is a plan in
  notes/selective-disclosure.md.
related_specs:
  - specs/stub-objects.yaml
  - specs/message-validation.yaml
  - specs/case-management.yaml (CM-11-013, CM-17-010, MV-10-001)
related_notes:
  - vultron/core/ports/AGENTS.md
  - notes/wire-core-boundary.md
  - notes/case-joining.md
  - notes/selective-disclosure.md
relevant_packages:
  - vultron/wire/as2
---

# Stub Objects

The `VulnerabilityCase` stub (`as_VulnerabilityCaseStub`) is the only stub type
the protocol permits (MV-10-001, narrowed by ADR-0090). Requirements: MV-10 in
`specs/message-validation.yaml`. Referencing other objects without inlining them,
and explicit redaction, are not built: see
[selective-disclosure.md](selective-disclosure.md).

## Why Only `VulnerabilityCase`

An invitee must evaluate a case *before* accepting, and the case cannot be shared
until they accept (MV-10-005). So the stub is transient: a placeholder that
rehydrates into the full object once the invitee is admitted. Everywhere else,
send the full inline object (AKM-03-001), or a bare URI or `Link` for an object
the recipient already holds.

The stub has its own wire `type`, `VulnerabilityCaseStub`, ID `<case-id>/stub`,
and a `caseId` field naming the case (CM-11-013). A receiver recognizes it by
`type` alone and resolves the case from `caseId`, never by parsing the ID. Its
`type` is also what routes it through semantic extraction; a stub without one
routes to `UNKNOWN`.

## Do Not Add Stubs of Other Types

A recognized inline object that fails its own class's validation is refused
(MV-04-003). Do not reintroduce arbitrary-type partial objects to get past that
refusal: a partial inline object and a corrupt one are indistinguishable to the
parser, which is why the refusal exists.

## Receiving a Stub

Look the full object up in the local DataLayer by `id`; if absent, the stub is a
placeholder until the full case is shared. A stub never overwrites a full object
already held (MV-10-003) and never creates a new domain record (MV-10-004).

## Building the Stub

- The stub discloses only `id`, `type`, `caseId`, `summary`, and the embargo
  terms when active (CM-17-010). It overrides the `published` and `updated`
  defaults it would inherit, or `model_dump(exclude_none=True)` leaks them.
- `summary` is required. The case owner sets `VulnerabilityCase.stub_summary`
  before emitting a stub Invite; `_project_case_to_stub()` refuses with
  `VultronActivityConstructionError` when it is absent, and
  `as_VulnerabilityCaseStub._refuse_absent_summary` refuses an inbound stub with
  no `summary` key.
- The stub's `caseStatus` is built for the stub, not read from the case, and
  serializes only its identity and `emState` (CM-17-002). A `pxaState` on the wire
  would state a PXA value nobody observed.
- `AnnounceVulnerabilityCaseReceivedUseCase` needs the full inline case on
  `activity.object_`, so `extract_intent()` keeps rich `object_`, `target`, and
  `context` values when `include_activity=True`.
