---
title: Selective Disclosure and Redaction (Design Direction)
status: draft
kind: plan
tracks:
  - "#3258"
  - "#6511"
description: >
  Design direction for referencing objects without inlining them, and for
  previews beyond the case's, which reuse the preview-only redaction marker
  (ADR-0193) and the field-by-field profile (ADR-0217). The delivered case
  preview, its profile and the loose forms are in notes/stub-objects.md.
related_specs:
  - specs/message-validation.yaml (AKM-03-001, MV-10-002, MV-12)
  - specs/actor-knowledge-model.yaml (AKM-05-006, AKM-05-007)
  - specs/case-management.yaml (CM-17-005, CM-17-010, CM-17-013, CM-17-025)
related_notes:
  - notes/stub-objects.md
  - notes/wire-core-boundary.md
  - notes/protocol-asks.md
  - notes/as2-vocabulary-alignment.md
  - notes/vulnerability-items.md
relevant_packages:
  - vultron/wire/as2
  - vultron/core/models
---

# Selective Disclosure and Redaction (Design Direction)

In this codebase outbound initiating activities carry full inline typed objects
(AKM-03-003, a prototype shortcut; the protocol allows either form, AKM-03-001).
That raises two concerns this plan addresses, beyond the one sanctioned
`VulnerabilityCase` stub ([stub-objects.md](stub-objects.md)):

1. **Verbosity**: inlining a full case or report in every activity that
   references it may become a performance problem.
2. **Privacy**: an actor may want to convey an object's identity and type without
   its contents.

## Dereferencing a URI Reference (#3258)

In AS2 the idiomatic way to reference an object you are not inlining is a URI or
a `Link`, which the receiver dereferences. Vultron resolves only a few references:
a participant fetches a case object from the CASE_MANAGER's case-scoped read
(AKM-05-006) when an activity cannot be classified without it, and the other
cases AKM-05-007 lists. A `Link` is never resolved, so a sender must still inline
the full object or accept an opaque reference. This is a prototype limitation,
not a production property, so dict-shaped partial objects must not become the
workaround.

## Redaction Builds a Preview (#4568, ADR-0193)

A field can be absent (unknown or not applicable), `null` (no value), or
**redacted**: it has a value the sender withholds from this recipient. Only a
preview can say the last one. A preview is a limited view of an object for a
recipient not yet entitled to it, never the object itself. The case stub is the
first, and is the case's AS2 `preview` (ADR-0205); wider previews (report,
reserved vul record, draft advisory) are #6257.

- **Wire form** (MV-12-003): `{"type": "Redacted", "summary": "<reason>"}`,
  `summary` optional, no other field, never the withheld value. `Redacted` is
  declared as a Vultron extension term under the rule #5743 writes.
- **Previews only** (MV-12-002): a receiver refuses a marker outside a
  preview. A full object never holds one, so no domain field widens to "value or
  marker" and a stored case never carries one. Withholding one field of an
  otherwise full object is not supported: the shared, hash-chained ledger would
  hide it from the whole case anyway.
- **Not anonymity.** Hiding a participant's identity (#2562) gives the others a
  working stand-in, an alias a Coordinator relays through, held in the shared
  case for good. A redaction is a visible gap, usually lifted on admission, and
  a redacted identity cannot be addressed.
- **Not CM-09's redacted case view.** `RedactedVulnerabilityCase` (CM-09-001)
  is a planned production type: a whole, separate case object for an invitee.
  A preview marker withholds single fields of a limited view; neither replaces
  the other.

The marker type is `vultron/core/models/redacted.py`, registered in
`WIRE_TYPE_MAP`, and refuses every field but `type` and `summary`.
`reads_as_typed_reference` excludes `Redacted`, so a marker of only `id` and
`type` is a marker, never a reference.

**A receiver reads a preview as sent** (MV-12-001, MV-12-006): a marker anywhere
inside it, at any depth, and each nested object as far as the sender showed it.
It decides on the invitation, not on the preview's shape, so it does not refuse
a cut-down nested object. It still refuses a marker outside a preview, a
preview out of place (MV-10-002), and a case preview without its own `id`,
`type` or `summary` (MV-10-001). The walk in
`vultron/wire/as2/case_reference_placement.py` stops at a preview, so it meets
a marker only outside one.

## A Preview Is Cut by a Profile (ADR-0217)

The case preview is cut from the case field by field: the protocol sets an
envelope, the operations each field permits, and this codebase picks one per
field in a static profile, so the cut makes no choice per invitation. The
case's profile, its loose forms and the receiver's envelope check are built;
their rules are in [stub-objects.md](stub-objects.md), and the field table is
in `docs/reference/case_model_fields.md` § `CasePreview`.

A wider preview (report, reserved vul record, draft advisory, #6257) takes the
same shape: a hand-written loose type of its object, a profile naming every
field, and an envelope check where its receiver recognizes it by position. A
later profile may share a loose type, which is why the check is not in the
type.
