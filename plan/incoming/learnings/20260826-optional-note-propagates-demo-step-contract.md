---
title: "Optional[as_Note] return propagates demo_step suppression contract to all callers"
type: learning
timestamp: "2026-08-26"
source: ISSUE-2390
signal: design-question
---

Changing `participant_adds_note_to_case` from `-> as_Note` to `-> Optional[as_Note]`
was the correct fix, but it propagates `demo_step`'s exception-suppression contract
to every caller: each must now guard `.id_` accesses on the returned value.

The alternative — raising outside `demo_step` — would crash the scenario even when the
failure is non-fatal, defeating the purpose of the context manager.

**Pattern**: any demo helper that calls `post_to_trigger` inside a `demo_step` and
extracts a result ID must return `Optional[T]` rather than `T`. Callers should treat
`None` as "step failed, demo_step already recorded it" and skip dependent steps via
conditional `in_reply_to`.
