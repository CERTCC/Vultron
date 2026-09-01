---
title: "design: cast() used to bridge extract_intent return type to AnyReceivedEvent"
type: learning
timestamp: 2026-09-01
source: ISSUE-2491
signal: design-question
---

`extract_intent()` takes `event_class: type[VultronEvent]` and returns
`event_class(...)`. Pyright types that expression as `VultronEvent`, which is
broader than the declared return `AnyReceivedEvent` (a Union of all concrete
subclasses). To satisfy `reportReturnType` without overloads (which would
require 50 @overload variants), the implementation uses
`cast(AnyReceivedEvent, event_class(...))`.

**Tradeoff**: `cast()` suppresses the type error without any runtime check.
If a caller passes an unregistered `event_class` that is not in `AnyReceivedEvent`,
the return value would still be typed as `AnyReceivedEvent` at the call site. In
practice this cannot happen since `event_class` always comes from the semantic
registry (which only stores the known concrete subclasses), but it is a silent
assumption.

**Alternative considered**: TypeVar overloads. Rejected because 50 overloads for
each concrete subclass would be impractical and harder to maintain than the union.
