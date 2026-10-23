---
source: CC1-MYPY
timestamp: '2026-05-05T18:28:08.019856+00:00'
title: Untyped closures invisible to mypy; use _get_id() for AS2 context fields
type: learning
---

## 2026-05-05 CC1-MYPY — `VultronActivity.context` was typed wrong in snapshot builder

When extracting `_build_activity_snapshot` from the untyped closure inside
`extract_intent`, mypy correctly flagged that `context=context` passed a raw
`as_Object` to a field typed `NonEmptyString | None`.  The original closure
was invisible to mypy because untyped function bodies are not checked.

Fix: use `_get_id(context)` (consistent with how `origin` is handled).
This converts the AS2 object to its string ID — the semantically correct
value for a snapshot field.

**Promoted**: 2026-05-05 — pitfall captured in `AGENTS.md` ("Untyped Closures
Are Invisible to mypy — Extract to Named Functions").
