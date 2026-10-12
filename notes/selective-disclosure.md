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
related_notes:
  - notes/stub-objects.md
  - notes/wire-core-boundary.md
  - notes/protocol-asks.md
relevant_packages:
  - vultron/wire/as2
  - vultron/core/models
---

# Selective Disclosure and Redaction (Design Direction)

Outbound initiating activities carry full inline typed objects (AKM-03-001).
That raises two concerns this plan addresses, beyond the one sanctioned
`VulnerabilityCase` stub ([stub-objects.md](stub-objects.md)):

1. **Verbosity**: inlining a full case or report in every activity that
   references it may become a performance problem.
2. **Privacy**: an actor may want to convey an object's identity and type without
   its contents.

## Dereferencing a URI Reference (#3258)

In AS2 the idiomatic way to reference an object you are not inlining is a URI or
a `Link`, which the receiver dereferences. Vultron has no mechanism for Actor B to
dereference a URI from Actor A's message into the resolved object, so today a
sender must inline the full object or accept an opaque reference. Bare URIs and
`Link` objects already parse in all four positions MV-10-002 names; what is
missing is resolution. This is a prototype limitation, not a production property,
so dict-shaped partial objects must not become the workaround.

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
