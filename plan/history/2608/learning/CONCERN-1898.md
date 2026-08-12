---
source: CONCERN-1898
timestamp: '2026-08-10T19:33:05.608167+00:00'
title: SE-07 phrase slot-coverage — defaultdict masks unfillable slots
type: learning
---

## What Was Learned

The SE-07 parametrized tests used `defaultdict(lambda: "X")` to fill all
phrase slots, which masked a class of bug: a `SemanticEntry` phrase referencing
`{context}`, `{origin}`, or `{inner_object}` would pass the test but produce a
dangling `"—"` fallback at render time because the runtime pipeline
(`CaseTimelineEvent.summary`, `event_phrase()`) never populates those three
slots.

The fix is two-layer:

1. **Structural allowlist test** (`test_no_phrase_uses_unpopulated_slots` in
   `test/test_semantic_registry.py`) — fails if any phrase references a slot
   outside `{actor}`, `{object}`, `{target}`. Module-level constants
   `_RUNTIME_POPULATED_SLOTS` and `_RESERVED_UNPOPULATED_SLOTS` document the
   split.

2. **Behavioural render tests** (`TestEventPhraseBehavioural`,
   `TestSummarySlotsFilledBehavioural` in `test/demo/test_report.py`) — call
   `event_phrase()` and `CaseTimelineEvent.summary` with real event-type values
   and assert no trailing `"—"` and no un-substituted `{slot}` markers remain.

## Spec Impact

- `specs/semantic-extraction.yaml`: SE-07-002 annotated with runtime-population
  note; SE-07-005 (structural allowlist MUST) and SE-07-006 (behavioural render
  MUST) added.
- `AGENTS.md`: pitfall entry added — phrases MUST use only `{actor}`,
  `{object}`, `{target}`.

## Outcome

Docs PR: <https://github.com/CERTCC/Vultron/pull/2149>
Implementation issue: #2150 (build: implement SE-07-005/006 render-pipeline
slot coverage tests; blocked-by #1898, child of epic #1937)
