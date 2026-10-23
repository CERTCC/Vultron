---
title: "extract_event() always uses 72h RSVP floor; per-actor floor not enforced"
type: learning
timestamp: "2026-08-31T00:00:00Z"
source: ISSUE-2850
signal: concern
---

The convenience wrapper `extract_event()` in `vultron/semantic_registry/__init__.py`
calls `extract_intent()` without forwarding any actor config; it always uses
the 72-hour default floor (`_DEFAULT_MIN_RSVP_WINDOW`).

Callers that have an actor context with a non-default `ActorConfig.min_rsvp_window`
must bypass `extract_event()` and call `extract_intent()` directly, passing
`min_rsvp_window=actor_config.min_rsvp_window`.

This is not documented at the call site and is easy to overlook, which means
deployments with a non-default floor will silently use 72 h unless the adapter
layer explicitly reaches for `extract_intent()`.

**Suggested follow-up**: either thread `ActorConfig` (or just its
`min_rsvp_window`) into `extract_event()` via an optional parameter, or add a
note to `extract_event()`'s docstring warning callers about this gap.

## Audit disposition (2026-09-02)

Filed as #3045. Verified still present: extract_event() takes only (activity).
