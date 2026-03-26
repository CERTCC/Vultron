## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

## `notes/state-machine-findings.md` completion-status section is aspirational

The "Completion Status" table in section 9 of
`notes/state-machine-findings.md` lists commit hashes (`fix-em-wire-boundary`,
`refactor-em-propose`, `refactor-em-terminate`, etc.) that do **not** appear
in the actual git history. The corresponding code changes **are** in the
codebase (OPP-01, OPP-02, OPP-03, OPP-07 partial, OPP-08 via P90-1, OPP-09
minimum step via P90-2), but they were committed under different names or
bundled into the P90 work. The "Status: Refactoring complete — all P and OPP
items addressed" header is broadly correct but the commit references are
inaccurate. A future refresh of that file should replace the fictional commit
hashes with the actual git log references or remove them.

OPP-05 (consolidate duplicate participant RM helpers) is explicitly NOT done
— two near-duplicate functions remain:

- `_find_and_update_participant_rm()` in `vultron/core/behaviors/report/nodes.py`
- `update_participant_rm_state()` in `vultron/core/use_cases/triggers/_helpers.py`
This is captured as TECHDEBT-39 in `plan/IMPLEMENTATION_PLAN.md`.

---

## `dl.save()` is the canonical persistence pattern for core code

After TECHDEBT-32b, `dl.save(obj)` is the **sole** approved pattern for
persisting domain objects from core code:

```python
# Correct
dl.save(case)
dl.save(participant)
dl.save(actor_obj)

# Now removed from codebase (do not reintroduce):
dl.update(obj.as_id, object_to_record(obj))   # core importing adapter
save_to_datalayer(dl, obj)                      # redundant core helper
```

The `save_to_datalayer()` helper has been deleted. The `object_to_record`
import from adapter is banned in core. Future core/BT code must use
`dl.save(obj)` exclusively.

TECHDEBT-32c remains open: `vultron/wire/as2/rehydration.py` imports
`get_datalayer` from the TinyDB adapter as a fallback — this is a
wire-imports-adapter violation to be fixed separately.

---

## TECHDEBT-34 complete: EM state machine guards added

Three unguarded `em_state = EM.ACTIVE` sites in `vultron/core/use_cases/` now
have explicit guards:

- **Trigger-side** (`SvcEvaluateEmbargoUseCase`): machine adapter raises
  `VultronConflictError` on invalid state.
- **Receive-side** (`AddEmbargoEventToCaseReceivedUseCase`,
  `AcceptInviteToEmbargoOnCaseReceivedUseCase`): `is_valid_em_transition()`
  check with WARNING log; proceeds regardless (state-sync override pattern).

All `rm_state=RM.XXX` in core are constructor args for new status objects, not
transitions — documented justification for bypassing machine guard. The
`append_rm_state()` guard already enforces validity for all RM mutation paths.

---

## 2026-03-25 Outbox and CaseActor notes

As preface and clarification to Outbox and CaseActor implementation, note
that we are on a path toward a design in which each actor is essentially
isolated in its own process and environment and can only interact locally with
their own data and state, and with other actors through sending and receiving
Vultron AS2 messages. Assume that any design choices you make now have to
continue to work when multiple actors are running in completely independent
and autonomous environments (e.g., containers), and so each actor has to be
able to manage its own state and data. Services like outbox delivery cannot
assume local access to other actors data or state. They must be designed to
consume a local outbox but then deliver to remote inboxes wherever they may
live via the front-end fastapi adapter.

Given this constraint, it is also unlikely that you will be able to have the
outbox delivery mechanism check for idempotency by looking at the datalayer
directly because they won't have access to it. Instead, the inbox handler or
fastapi adapter inbound should be able to handle duplicate messages
gracefully, perhaps responding with an appropriate HTTP status code if a
duplicate is detected while processing an incoming message.

## 2026-03-25 Avoid BaseModel directly in adapters or core

While we use Pydantic's BaseModel to define data classes throughout the code,
we need to avoid using BaseModel as a type hint for functions, (python)
Protocols, or port interfaces between layers. Although it's an easy way to
quickly implemement data conversions from core to wire formats and vice
versa, it either creates too tight a coupling between layers, or it leads to
leaky abstractions where the core must be aware of the wire format. We
really do need to ensure that port interfaces are clean and sufficiently
abstracted so that we're not inadvertently coupling objects across
boundaries without very well-defined data transformation layers. Using
`BaseModel` in type hints indicates that we haven't thought enough about
what data is actually passing through the interface and whether we have the
right abstractions in place.

---

## 2026-03-25 OX-1.1/1.2/1.3: delivery is HTTP POST, idempotency is at inbox

Outbox delivery (OX-1.1) uses async HTTP POST to `{actor_uri}/inbox/` via
`httpx.AsyncClient` in `DeliveryQueueAdapter.emit()`. Direct DataLayer
writes to recipient inboxes are **not** used — each actor is isolated in
its own process/container and cannot access other actors' DataLayers.

OX-1.3 idempotency is enforced at `POST /actors/{id}/inbox/`: the endpoint
checks `actor.inbox.items` (the persistent received log) before enqueueing
and returns 202 immediately on a duplicate activity ID.

The `shared_dl` parameter on `outbox_handler` covers the case where
activities are stored in the shared DataLayer (POST /inbox path) vs.
the actor's own DL (POST /outbox path).

Trigger use-cases and BT nodes that create outgoing activities now call
`dl.record_outbox_item(actor_id, activity_id)` so items are enqueued in
the `{actor_id}_outbox` table that `outbox_handler` drains, regardless of
whether the calling code holds the shared or actor-scoped DataLayer.

---

## 2026-03-25 CA-2 follow-up: actor+case identifies the participant

The final action-rules contract is `GET /actors/{actor_id}/cases/{case_id}/action-rules`.
Within a case, the `(actor_id, case_id)` pair is sufficient to identify the
single matching `CaseParticipant`, so callers should not also supply a
participant ID. The router stays on the actor surface, while the use case
resolves the case-scoped participant internally from `actor_participant_index`
with a fallback scan of `case_participants`.
