---
title: Participant Case Replica — Implementation Notes
status: active
description: "Design notes for participant case replicas: per-actor case copies and synchronization model."
related_specs:
  - specs/participant-case-replica.md
  - specs/case-management.md
  - specs/sync-log-replication.md
relevant_packages:
  - vultron/core/behaviors/case
  - vultron/core/models
  - vultron/core/use_cases
---

# Participant Case Replica — Implementation Notes

**Relates to**: `specs/participant-case-replica.md`

**Cross-references**: `specs/case-management.md`,
`specs/sync-log-replication.md`, `specs/actor-knowledge-model.md`

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Does each participant need a stub CaseActor clone? | No — one Actor, one inbox; routing is an internal concern. | Separate per-participant-per-case actors would explode the actor registry and add wire-protocol complexity with no protocol benefit. |
| What is the unified mechanism for delivering a full case snapshot? | `Announce(VulnerabilityCase)` at all lifecycle stages. | `Announce` is semantically correct ("I am telling you about this") for both initial delivery and ongoing updates. `Create(Case)` retains its "case was created" semantics but is not the snapshot vehicle. |
| Who triggers initial sync for the original participants? | CaseActor sends `Announce(VulnerabilityCase)` as part of case initialization. | Consistent with the unified mechanism; no special-casing required. |
| Who triggers initial sync for late-joining participants? | CaseActor auto-sends `Announce(VulnerabilityCase)` as a cascade when it processes `Accept(Invite)`. | Implements the protocol-event-cascade pattern: acceptance implies participant is added implies snapshot is sent. |
| Who may update a participant's local case replica? | Only the CaseActor. Reject and log at WARNING for any other sender. | Enforces the single-writer invariant (CM-02-002). Matches the idea's explicit requirement. |
| Does the case owner follow the same replica rules? | Yes. Even the case owner routes through the CaseActor and never writes directly to its local copy. | Reinforces CM-02-010 (distinct CaseActor and owner actor identities). |
| Which field routes a case-scoped message to the right local handler? | `context` field, set to the case ID. | Already the established pattern in all demos. Consistent with AS2 semantics. |
| What happens when an activity arrives with an unknown case context? | Queue, warn, request resync. Drop if no snapshot arrives within timeout. | Handles out-of-order delivery (snapshot and follow-up arrive in wrong order) without silently dropping or corrupting state. |
| Should an actor maintain a report-to-case mapping? | Yes. Allows reporter actors to recognize that an `Announce(Case)` is a response to their prior `Offer(Report)`. | Enables the "reporter checks their open submissions" flow described in the idea. |

---

## Architecture Overview

```text
Participant Actor (single inbox)
  ├── Activity with context=case_id_A → Case-A replica handler
  ├── Activity with context=case_id_B → Case-B replica handler
  └── Activity with unknown context   → Queue + resync request
```

There is one externally-addressable Actor. Case-scoped routing is fully
internal. The CaseActor (one per case, run by the case owner) is the only
entity that may update participant replicas.

```text
Case Lifecycle:
  Case created
    └── CaseActor sends Announce(VulnerabilityCase) to each initial participant
          └── Participant creates local replica on first receipt
          └── Participant updates local replica on subsequent receipt

  New participant invited and accepts
    └── CaseActor processes Accept(Invite)
          └── CaseActor adds participant to case
          └── CaseActor sends Announce(VulnerabilityCase) to new participant
                └── New participant creates local replica
```

---

## `Announce(VulnerabilityCase)` as Unified Bootstrap

The `Announce` activity is the correct AS2 verb for "I am informing you about
this object." This covers both:

- **Initial delivery**: participant does not yet have a local copy; the
  `Announce` handler checks for an existing replica, finds none, and creates
  one.
- **Subsequent updates**: participant already has a local copy; the `Announce`
  handler merges the received state.

The receiver's handler does NOT need to know which case of its lifecycle the
delivery is at:

```python
class AnnounceVulnerabilityCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AnnounceVulnerabilityCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case = request.case

        if case is None:
            logger.warning(
                "announce_case: no case object in event from actor '%s'",
                actor_id,
            )
            return

        # PCR-03-001: only accept updates from the CaseActor for this case
        case_actor_id = _resolve_case_actor(case.id_, self._dl)
        if case_actor_id is not None and actor_id != case_actor_id:
            logger.warning(
                "announce_case: actor '%s' is not the CaseActor for case '%s'"
                " — update rejected (PCR-03-001)",
                actor_id,
                case.id_,
            )
            return

        existing = self._dl.read(case.id_)
        if existing is None:
            logger.info(
                "announce_case: creating local replica for case '%s'",
                case.id_,
            )
            self._dl.save(case)
        else:
            logger.info(
                "announce_case: updating local replica for case '%s'",
                case.id_,
            )
            # Merge authoritative fields from CaseActor snapshot
            self._dl.save(case)
```

---

## Late-Joiner Bootstrap: Cascade from `Accept(Invite)`

When a new participant accepts an invitation, the `AcceptInviteToCaseUseCase`
MUST trigger `Announce(VulnerabilityCase)` to the new participant as a cascade.
This is a BT subtree, not a procedural post-BT call:

```python
# Inside the AcceptInviteToCase BT, after AddParticipantToCase node:
#
#  SequenceNode
#    ├── ValidateAcceptInviteNode
#    ├── AddParticipantToCaseNode
#    └── AnnounceFullCaseToNewParticipantNode  ← cascade node
```

`AnnounceFullCaseToNewParticipantNode` reads the current full case from the
DataLayer and enqueues `Announce(VulnerabilityCase)` to the new participant's
inbox via the outbox.

---

## `context` Field as Case Routing Key

All case-scoped activities MUST carry `context` set to the case ID. This
applies to both directions:

**CaseActor → Participant:**

```python
activity = AnnounceVulnerabilityCaseActivity(
    actor=case_actor.id_,
    object_=case,
    to=[participant_actor.id_],
    context=case.id_,   # PCR-04-002
)
```

**Participant → CaseActor:**

```python
activity = AddNoteToCase(
    actor=participant_actor.id_,
    object_=note,
    target=case,
    to=[case_actor.id_],
    context=case.id_,   # PCR-04-002
)
```

The inbox dispatcher MUST extract `context` from the activity and use it
to look up the relevant case replica before routing to the handler.

---

## Report-to-Case Mapping

When a reporter actor submits a report (`Offer(VulnerabilityReport)`), the
local DataLayer SHOULD record:

```python
class ReportCaseLink(BaseModel):
    report_id: str
    case_id: str | None = None
```

When the reporter later receives `Announce(VulnerabilityCase)` and the case's
`vulnerability_reports` list includes the known report ID, the handler links
the case to the report:

```python
# In AnnounceVulnerabilityCaseReceivedUseCase.execute():
for report_ref in case.vulnerability_reports:
    report_id = _as_id(report_ref)
    link = dl.read(f"report-case-link/{url_encode(report_id)}")
    if link is not None and link.case_id is None:
        link.case_id = case.id_
        dl.save(link)
        logger.info(
            "announce_case: linked report '%s' to case '%s'",
            report_id, case.id_,
        )
```

---

## Unknown Case Context Handling

When the inbox dispatcher encounters a `context` that does not match any
known local case:

```python
def dispatch_case_scoped_activity(activity, dl):
    case_id = activity.context
    if dl.read(case_id) is None:
        logger.warning(
            "dispatch: unknown case context '%s' for activity '%s'"
            " — queuing for resync",
            case_id, activity.id_,
        )
        _enqueue_pending(activity)
        _request_case_snapshot(case_id, activity.actor, dl)
        return

    # Normal routing
    ...
```

Pending activities are keyed by `case_id`. When `Announce(VulnerabilityCase)`
arrives and creates the replica, the dispatcher MUST replay any pending
activities queued for that case ID.

---

## Layer and Import Rules

- `AnnounceVulnerabilityCaseReceivedUseCase` lives in
  `vultron/core/use_cases/received/case.py`.
- The CaseActor authority check (`_resolve_case_actor`) looks up the
  CaseActor via `dl.by_type("Service")` filtered to `context == case_id`.
  This lookup is idempotent and safe to call multiple times.
- The late-joiner bootstrap node belongs in
  `vultron/core/behaviors/case/` as part of the invite-acceptance BT,
  not in the use-case `execute()` body.
- `ReportCaseLink` belongs in `vultron/core/models/` and MUST NOT reference
  any wire-layer types.

---

## Testing Patterns

```python
# PCR-07-001: Announce from CaseActor creates local replica
def test_announce_creates_replica(dl, case_actor, new_case):
    activity = AnnounceVulnerabilityCaseActivity(
        actor=case_actor.id_,
        object_=new_case,
        to=["https://example.org/reporter"],
        context=new_case.id_,
    )
    event = build_event(activity, actor_id="https://example.org/reporter")
    AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()
    assert dl.read(new_case.id_) is not None


# PCR-07-003: Announce from non-CaseActor is rejected
def test_announce_from_non_case_actor_rejected(dl, imposter_actor, new_case,
                                               caplog):
    activity = AnnounceVulnerabilityCaseActivity(
        actor=imposter_actor.id_,
        object_=new_case,
        to=["https://example.org/reporter"],
        context=new_case.id_,
    )
    event = build_event(activity, actor_id="https://example.org/reporter")
    with caplog.at_level(logging.WARNING):
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()
    assert dl.read(new_case.id_) is None
    assert "not the CaseActor" in caplog.text


# PCR-07-005: Activity with unknown context is queued, not applied
def test_unknown_context_queued(dl, case_scoped_note_activity):
    # case does not exist in dl yet
    dispatch_case_scoped_activity(case_scoped_note_activity, dl)
    assert dl.read(case_scoped_note_activity.context) is None
    assert _is_enqueued(case_scoped_note_activity.id_)
```
