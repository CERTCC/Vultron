---
title: "spec-gap: AnyReceivedEvent union type has no SE spec requirement"
type: learning
timestamp: 2026-09-01
source: ISSUE-2491
signal: spec-gap
---

`AnyReceivedEvent` (added in `vultron/core/models/events/__init__.py`) is the
canonical public return type of `extract_intent()` and `extract_event()`. It
is defined as `Union[<all 50 concrete *ReceivedEvent subclasses>]`.

No spec entry in `specs/` documents:

1. That `extract_intent` MUST return a discriminated union (not a base-class alias), or
2. That `AnyReceivedEvent` is the required port-boundary type for the semantic
   extraction port.

CS-10-001 covers the general principle ("named, domain-typed objects at port
boundaries") and the type-narrowing tests reference it, but there is no SE-layer
spec (semantic-extraction) that mandates a discriminated union specifically.

A follow-up spec entry should be added covering:

- SE-XX-YYY: The semantic extraction port (extract_intent / extract_event) MUST
  declare its return type as the full discriminated union of concrete
  VultronEvent subclasses rather than the base VultronEvent type.
