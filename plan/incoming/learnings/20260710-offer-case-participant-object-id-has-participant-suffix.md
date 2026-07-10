---
title: "offer_case_participant_activity: event.object_id carries #participant suffix, not actor URI"
type: learning
timestamp: 2026-07-10T14:00:00Z
source: ISSUE-1298
---

`offer_case_participant_activity(recommended, ...)` builds a `CaseParticipant`
with `id_=f"{recommended.id_}#participant"`. When the resulting wire activity is
extracted via `extract_event()`, the event's `object_id` is the CaseParticipant
URI (e.g. `https://example.org/actors/vendor#participant`), not the actor URI.

Use cases that need the actor ID must extract it from the CaseParticipant's
`attributed_to` field:

```python
participant_obj = getattr(request.activity, "object_", None)
raw_actor = getattr(participant_obj, "attributed_to", None)
actor_id = getattr(raw_actor, "id_", None) or request.object_id
```

The fallback `request.object_id` still has the `#participant` suffix and should
only be used as a last resort — log a warning if it's reached.
