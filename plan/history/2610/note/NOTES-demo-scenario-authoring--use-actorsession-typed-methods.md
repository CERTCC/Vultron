---
source: NOTES-demo-scenario-authoring--use-actorsession-typed-methods
timestamp: '2026-10-12T23:53:32.177190+00:00'
title: 'Demo scenario authoring: ActorSession migration notice (delivered)'
type: note
---

Archived from `notes/demo-scenario-authoring.md` by #4497 (notes sweep): the
`ActorSession` migration is delivered. `vultron/demo/actor_session.py` exists,
`vultron/demo/helpers/actions.py` and
`test/architecture/test_demo_trigger_client_matches_actor.py` are deleted, and
`post_to_trigger` is now called only from `actor_session.py` itself. The lasting
rule (DEMOMA-26-001) stays in the note as a one-paragraph item.

---

## Use ActorSession Typed Methods, Not `post_to_trigger` Directly (DEMOMA-26)

Once `ActorSession` is available (#3398), demo scripts under
`vultron/demo/scenario/` and `vultron/demo/exchange/` MUST use its typed methods
for all trigger endpoint calls. Calling `post_to_trigger` directly is prohibited
at those call sites (DEMOMA-26-001).

**Why:** `post_to_trigger` accepts a bare `str` behavior name and an untyped
`dict` body. A misspelled behavior name is a 404 at runtime; a misspelled body
key is silently dropped because trigger request models use `extra="ignore"`
(TRIG-03-002), producing an undetectable no-op. `ActorSession` makes both
mistakes unrepresentable at the call site.

**What changes on migration:**

- `vultron/demo/helpers/actions.py` is deleted; its wrappers become
  `ActorSession` methods (DEMOMA-26-005).
- The architecture ratchet test
  `test/architecture/test_demo_trigger_client_matches_actor.py` is deleted only
  after the last `post_to_trigger` call site is removed — it is the migration's
  own safety net until then (DEMOMA-26-006).

**Until `ActorSession` lands**, the existing `post_to_trigger`-based helpers in
`vultron/demo/helpers/` remain correct. The `Optional[T]` return-type rule in the
section above still applies to any helper that extracts a result from a
`post_to_trigger` call wrapped in `demo_step`.

Source: #3356, DEMOMA-26
