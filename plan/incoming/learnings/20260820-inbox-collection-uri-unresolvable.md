---
title: Inbox addressing check must treat collection URIs as unresolvable (Liberal Accept)
type: learning
timestamp: 2026-08-20T20:30:00Z
source: ISSUE-2445
signal: spec-ambiguity
---

IE-11-002 says the inbox must accept Activities whose addressing is
"absent or unresolvable". The word "unresolvable" was ambiguous in the
original spec draft.

During implementation, three integration tests failed because demo
Activities used `to=f"{case.id_}/participants"` (a collection URI) and
were delivered to an actor's own inbox. The short-ID of
`{case_id}/participants` is "participants", which doesn't match any
actor's short ID, so the original implementation incorrectly refused
these legitimate deliveries.

**Interpretation adopted**: an address is "unresolvable" if
`dl.find_actor_by_short_id(strip_id_prefix(addr))` returns None — i.e.,
the address does not correspond to any specific actor in the local
DataLayer. Collection URIs (e.g., `{case_id}/participants`), group
addresses, and external-actor URIs all satisfy this condition.

**Implementation**: `_activity_addressed_to()` accepts an optional `dl`
parameter. When DL is provided, any non-matching address that doesn't
resolve to a known actor triggers Liberal Accept (return True) before
the refusal. Without DL, the short-ID-only check applies (used in
isolated unit tests).

Documented in IE-11-002 (updated statement/rationale) and ADR-0068
(Consequences section).
