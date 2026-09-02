---
title: "extract_intent: min_rsvp_window passed as parameter, not read from ActorConfig"
type: learning
timestamp: "2026-08-31T00:00:00Z"
source: ISSUE-2850
signal: design-question
---

Issue #2850 required `extract_intent()` to honour the actor's configured
`min_rsvp_window` when clamping inbound RSVP deadlines (EP-07-003).

**Decision**: add `min_rsvp_window: timedelta = _DEFAULT_MIN_RSVP_WINDOW` as
an explicit parameter rather than reading `ActorConfig` inside the function.

**Reason**: `extract_intent()` lives in `vultron/wire/as2/extractor/`, which
is the wire layer. Importing `ActorConfig` from `vultron/config/` there would
tighten a dependency that is not required by hexagonal architecture. Passing
the value as a parameter keeps the wire extractor stateless and testable.

**Implication**: Callers that want actor-specific enforcement must retrieve
`ActorConfig.min_rsvp_window` and pass it explicitly to `extract_intent()`.
The convenience wrapper `extract_event()` in `vultron/semantic_registry/` uses
the 72 h default for all calls — see companion concern note.
