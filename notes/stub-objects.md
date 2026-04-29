---
title: Stub Objects and Selective Disclosure
status: active
description: >
  Design notes for lightweight stub object representations in Vultron wire
  messages; not yet implemented.
related_specs:
  - specs/stub-objects.yaml
  - specs/message-validation.yaml
related_notes:
  - notes/datalayer-design.md
relevant_packages:
  - vultron/wire/as2
---

# Stub Objects and Selective Disclosure

Design notes for lightweight object representations in Vultron wire messages.
These concepts are **not yet implemented** — this note captures the design
direction for future work.

---

## Motivation

Two separate concerns arise from the requirement that outbound Vultron wire
messages carry **full inline typed objects** (see `specs/message-validation.yaml`
MV-09-001):

1. **Verbosity / performance**: Full inline objects can be large. Sending a
   complete `VulnerabilityCase` or `VulnerabilityReport` in every activity that
   references them may eventually become a performance concern.

2. **Privacy / selective disclosure**: There are cases where an actor wants to
   convey the identity and type of an object to a recipient without sharing its
   full contents. For example, when inviting a new participant to a case, the
   case actor may want to share only enough information to allow the invitee to
   decide whether to accept — without disclosing sensitive vulnerability details
   before the invitee has agreed to the embargo.

---

## The Stub Object Pattern (AS2 Minimalist)

The most standards-compliant way to represent a lightweight object reference
in ActivityStreams 2.0 is to send a valid JSON-LD object containing only the
identity and type classification, omitting all other properties. In AS2, almost
all properties (including `content`, `summary`, and `published`) are optional.

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "id": "https://example.com/cases/abc123",
  "type": "VulnerabilityCase"
}
```

Many ActivityPub implementations treat this pattern as a "lazy-loading"
reference or a "header-only" object. The `id` allows the recipient to request
the full object if they have access; the `type` allows semantic routing to
proceed correctly.

### Using `summary` as a Status Indicator

If you want to maintain the original type but provide a human-readable reason
for the lack of content (e.g., "Restricted — accept embargo to view"), use the
`summary` property:

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "id": "https://example.com/cases/abc123",
  "type": "VulnerabilityCase",
  "summary": "Case details restricted pending embargo acceptance."
}
```

---

## Vultron Design Implications

### Semantic Routing Compatibility

A key requirement for stub objects in Vultron is that they must carry enough
information to pass through the **semantic extraction routing manifold**
(`vultron/wire/as2/extractor.py`). The extractor matches on
`(Activity type, object.type)` pairs. A stub object MUST include at least:

- `id` — for DataLayer lookup
- `type` — for semantic pattern matching

Without the `type` field, the stub would cause the activity to route to
`MessageSemantics.UNKNOWN`.

### Stub vs Full Object: When to Use Each

| Situation | Use |
|---|---|
| Normal protocol operation (Create, Offer, Invite, Announce) | Full inline typed object (MV-09-001) |
| Inviting a participant before embargo acceptance | Stub object (type + id + summary only) |
| Large object already known to recipient | Stub with `id` for DataLayer lookup |
| Privacy-sensitive fields must be withheld | Stub or redacted object (see below) |

### Recipient Handling

When a recipient receives a stub object, they should:

1. Attempt to look up the full object in their local DataLayer by `id`.
2. If not found, the stub serves as a placeholder until the full object is
   shared (e.g., after the recipient accepts the embargo).
3. Stub objects MUST NOT overwrite a full object already held in the DataLayer.

---

## Redaction: `None` ≠ Redacted

A related concept is **explicit redaction**: conveying that a field is
intentionally withheld, rather than simply absent. In JSON/Pydantic, `None`
and a missing field are often treated equivalently, but in a privacy-aware
protocol they carry different semantics:

- **Absent field**: The sender doesn't know this value, or it's not applicable.
- **`None`**: The field exists but has no value (null/empty).
- **Redacted**: The field has a value, but the sender is intentionally not
  sharing it with this recipient.

### Potential Approach

A micro-data structure could represent a redacted field explicitly:

```json
{
  "id": "https://example.com/cases/abc123",
  "type": "VulnerabilityCase",
  "name": {"type": "Redacted", "reason": "Embargo pending"}
}
```

This allows a recipient to distinguish "the case has no name" from "the case
name is being intentionally withheld." It also enables downstream logic to
display a meaningful placeholder rather than silently ignoring the field.

**Note**: Any redaction micro-structure used in wire messages must also be
reflected in the core domain model, so that if a handler receives a redacted
wire message, it can preserve the redaction intent rather than treating the
field as `None`.

---

## Relationship to Inline Object Requirement

The current requirement (MV-09-001) is that **outbound initiating activities
MUST carry fully inline typed domain objects**. Stub objects are a controlled
exception to this rule for the selective-disclosure use case.

The formal stub object requirements are now specified in
`specs/message-validation.yaml` MV-10 (Stub Objects), covering:

- Required fields (`id` + `type`; optional `summary`)
- Permitted field positions (`target` of `Invite`; `object_` of `Announce`
  when case content is embargoed)
- DataLayer anti-overwrite rule (MV-10-003)
- Prohibition on creating new domain records from stubs (MV-10-004)
- Full case delivery precondition (MV-10-005)
- Implied embargo consent when accepting a case invite (MV-10-006)

**Implementation notes (2026-04-21)**:

- `VulnerabilityCaseStub` MUST override the inherited `published` and
  `updated` defaults from `as_Object`. Otherwise `model_dump(exclude_none=True)`
  leaks timestamps and violates the "stub carries only id/type(+summary)"
  selective-disclosure rule.
- `event.activity` cannot be reduced to ID strings for `AnnounceVulnerabilityCase`
  handling. `AnnounceVulnerabilityCaseReceivedUseCase` needs the full inline
  `VulnerabilityCase` on `activity.object_`, so `extract_intent()` must
  preserve rich `object_` / `target` / `context` values when
  `include_activity=True`.
