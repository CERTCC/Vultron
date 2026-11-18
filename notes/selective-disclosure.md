---
title: Selective Disclosure and Redaction (Design Direction)
status: draft
kind: plan
tracks:
  - "#3258"
  - "#6372"
  - "#6641"
description: >
  Design direction for referencing objects without inlining them, and the
  preview-only redaction marker (ADR-0193). The marker type exists, but no
  preview field accepts it yet; the delivered VulnerabilityCase stub is in
  notes/stub-objects.md.
related_specs:
  - specs/message-validation.yaml (AKM-03-001, MV-10-002, MV-12)
  - specs/actor-knowledge-model.yaml (AKM-05-006, AKM-05-007)
related_notes:
  - notes/stub-objects.md
  - notes/wire-core-boundary.md
  - notes/protocol-asks.md
  - notes/as2-vocabulary-alignment.md
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

- **Built from the full object, one choice per field** (MV-12-004): show the
  value, redact it, or leave it out. Leave it out by default, because a marker
  discloses that a value exists, and that is often the sensitive fact ("an
  exploit is known"). Redact only where the recipient needs to know the value
  exists, such as an invitee weighing whether to join.
- **Wire form** (MV-12-003): `{"type": "Redacted", "summary": "<reason>"}`,
  `summary` optional, no other field, never the withheld value. `Redacted` is
  declared as a Vultron extension term under the rule #5743 writes.
- **Previews only** (MV-12-001, MV-12-002): a receiver refuses a marker in any
  other position. A full object never holds one, so no domain field widens to
  "value or marker" and a stored case never carries one. Withholding one field
  of an otherwise full object is not supported: the shared, hash-chained ledger
  would hide it from the whole case anyway.
- **Not anonymity.** Hiding a participant's identity (#2562) gives the others a
  working stand-in, an alias a Coordinator relays through, held in the shared
  case for good. A redaction is a visible gap, usually lifted on admission, and
  a redacted identity cannot be addressed.

- **Not CM-09's redacted case view.** `RedactedVulnerabilityCase` (CM-09-001)
  is a planned production type: a whole, separate case object for an invitee.
  A preview marker withholds single fields of a limited view; neither replaces
  the other.

The marker type is `vultron/core/models/redacted.py`, registered in
`WIRE_TYPE_MAP`, and the type refuses every field but `type` and `summary`.
The receiver refusal holds for every declared field of a full object and for
every activity slot, because none of their types admits the marker.
`reads_as_typed_reference` excludes `Redacted`, so a marker of only `id` and
`type` is a marker, never a reference. A field that admits any embedded object
(`tag`, `attachment`) refuses one at the parse edge
(`refuse_misplaced_forms`), unless its preview type names it in
`redactable_fields` (`opens_to_redaction`). `CasePreview` opens no field yet;
Concern #6641 decides which, and #6372 opens them.

- **A leaky marker is the sender's fault, not the receiver's.** The parse edge
  sets aside an unknown key before the class validates (MV-11-003), so a marker
  carrying `content` or `id` arrives at `Redacted` without them. Do not add a
  parse-edge refusal of those keys: the receiver keeps the normal unknown-key
  handling, and MV-12-005 becomes a sender-side rule, the preview builder never
  putting a withheld value in a marker (MV-12-004; Concern #6641 plans it).
  `test_redaction_marker.py::test_a_marker_carrying_the_withheld_value_is_refused`
  still asserts the receiver-side refusal; #6641's amendment replaces it.
