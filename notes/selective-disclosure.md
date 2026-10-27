---
title: Selective Disclosure and Redaction (Design Direction)
status: draft
kind: plan
tracks:
  - "#3258"
  - "#4568"
description: >
  Design direction for referencing objects without inlining them and for
  explicit redaction of withheld fields. Neither exists yet; the delivered
  VulnerabilityCase stub is in notes/stub-objects.md.
related_specs:
  - specs/message-validation.yaml (AKM-03-001, MV-10-002)
  - specs/actor-knowledge-model.yaml (AKM-05-006, AKM-05-007)
related_notes:
  - notes/stub-objects.md
  - notes/wire-core-boundary.md
  - notes/protocol-asks.md
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

## Redaction: `None` ≠ Redacted (#4568)

A privacy-aware protocol distinguishes three states a JSON/Pydantic model
usually conflates:

- **Absent**: the sender does not know the value, or it does not apply.
- **`None`**: the field exists but has no value.
- **Redacted**: the field has a value the sender is deliberately withholding from
  this recipient.

A candidate wire form is a micro-structure in place of the value:

```json
{
  "id": "https://example.com/cases/abc123",
  "type": "VulnerabilityCase",
  "name": {"type": "Redacted", "reason": "Embargo pending"}
}
```

It lets a recipient tell "the case has no name" from "the name is withheld" and
show a meaningful placeholder. Any such structure must also exist in the core
domain model, so a handler receiving a redacted field preserves the redaction
intent rather than reading `None`. AS2's `summary` can carry a human-readable
reason ("Case details restricted pending embargo acceptance.") on an otherwise
minimal object.

Redaction is also the mechanism a reduced delivery tier for Observers would need.
CM-25-003 rules that tier out today, so it would be amended first.
