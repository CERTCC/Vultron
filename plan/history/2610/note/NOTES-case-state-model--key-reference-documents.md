---
source: NOTES-case-state-model--key-reference-documents
timestamp: '2026-10-12T19:32:57.173907+00:00'
title: Key Reference Documents
type: note
---

**Archived:** 2026-10-12
**Reason:** reading list; the docs pages are reachable from the docs nav
**Superseded by:** docs/topics/process_models/model_interactions/index.md

---

## Key Reference Documents

The following documents explain this distinction in depth and MUST be
consulted when implementing state-related handlers or BT nodes:

- `docs/topics/process_models/model_interactions/index.md` — canonical
  explanation of the participant-agnostic vs. participant-specific split
- `docs/reference/activitypub/objects.md` — how objects are structured in the
  ActivityStreams vocabulary
- `docs/topics/case_lifecycle/case_model.md` — the case model as implemented
  (`docs/howto/case_object.md` is now a moved stub pointing here)
- `docs/topics/behavior_logic/msg_cs_bt.md` — behavior tree logic for CS
  message handling
- `docs/topics/process_models/cs/index.md` — CS model overview
- `docs/topics/process_models/cs/transitions.md` — CS transitions, diagrams, and
  grammar
- `docs/reference/formal_protocol/states.md` — formal participant state space;
  per-role state-space counts are in
  `docs/topics/measuring_cvd/state_space_size.md`
- `docs/reference/formal_protocol/conclusion.md` — protocol design conclusions
