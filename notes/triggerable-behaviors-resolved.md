---
title: "Triggerable Behaviors: Resolved Design Decisions and Audit Results"
status: active
description: >
  Resolved trigger implementation decisions (P30-1 through P30-3), BT requirement
  for trigger use cases, general-purpose vs. demo-only trigger classification,
  trigger audit results, wrapper pattern, sync-log-entry context field, and
  testing patterns.
related_specs:
  - specs/triggerable-behaviors.yaml
  - specs/behavior-tree-integration.yaml
  - specs/configuration.yaml
  - specs/code-style.yaml
related_notes:
  - notes/triggerable-behaviors.md
  - notes/bt-integration.md
  - notes/bt-fuzzer-nodes.md
  - notes/do-work-behaviors.md
  - notes/domain-model-separation.md
  - notes/protocol-event-cascades.md
relevant_packages:
  - transitions
  - vultron/adapters/driving/fastapi
  - vultron/core/use_cases/triggers
  - vultron/bt
---

# Triggerable Behaviors: Resolved Design Decisions and Audit Results

> See also: [triggerable-behaviors.md](triggerable-behaviors.md) for the first half of these design notes.

## Resolved Design Decisions: Trigger Implementation (P30-1 through P30-3)

These decisions were reached during initial implementation of the trigger
endpoints in `vultron/api/v2/routers/triggers.py`.

### P30-1: Outbox Diff Strategy for Retrieving the Resulting Activity

`trigger_validate_report` (and similar BT-backed triggers) needs to return
the resulting ActivityStreams activity in the response body (TRIG-04-001).
The BT writes the new activity ID to `actor.outbox.items` via the
`UpdateActorOutbox` node.

**Design decision**: Snapshot the actor's outbox ID set before BT execution,
then subtract after execution to find newly added activity IDs. The diff is a
set subtraction on string IDs.

**Rationale**: Avoids modifying the bridge layer or BT nodes for a specific
trigger use case. Concurrency-safe as long as each BT execution produces a
distinct UUID-based activity ID (guaranteed by existing BT node
implementations).

**Implication**: This approach couples the trigger endpoint to the outbox
data model. If the outbox model changes (e.g., moving to a separate outbox
collection), the snapshot/diff logic must also be updated.

### P30-2: Report Triggers are Procedural (invalidate-report, reject-report)

`invalidate-report` and `reject-report` are implemented procedurally, not
as BT trees. Per AGENTS.md guidance, simple linear workflows with no
branching SHOULD use procedural code.

- `invalidate-report`: Creates `RmInvalidateReport` (TentativeReject) directly.
- `reject-report`: Creates `RmCloseReport` (Reject) directly; requires a
  non-empty `note` field (TRIG-03-004).

**Shared helper**: `_add_activity_to_outbox()` was extracted to DRY up the
outbox-append pattern across multiple trigger endpoints (avoids repeating the
same DataLayer read → append → write sequence).

**`reject-report` `note` field semantics**: The spec says the value SHOULD be
non-empty (not MUST). An empty `note` string logs a WARNING but is accepted.
This is enforced via a `@field_validator` on `RejectReportRequest.note` rather
than a `NonEmptyString` type, because the rule is advisory (SHOULD), not
mandatory (MUST).

### P30-3: Case Triggers are Procedural (engage-case, defer-case)

`engage-case` and `defer-case` are also implemented procedurally. Key pattern
differences from report triggers:

- **`_resolve_case()` helper**: Reads the case from the DataLayer and returns
  HTTP 404 if absent or HTTP 422 if the resolved object is not a
  `VulnerabilityCase`. Shared across case-scoped trigger endpoints.
- **`_update_participant_rm_state()` helper**: Locates the actor's own
  `CaseParticipant` record in the DataLayer (participants are stored as ID
  strings in `case.case_participants`, so each must be fetched individually)
  and updates `participant_statuses`. If no participant record exists for the
  actor, a WARNING is logged and the endpoint still returns 202 (non-blocking).
- **State update target**: The participant document is updated directly, not
  the case document, consistent with existing BT node patterns.
- **Relationship to receive-side BTs**: `EngageCaseBT`/`DeferCaseBT` handle
  the *inbound* case — recording another actor's already-made decision.
  The trigger endpoints handle the *outbound* case — the local actor deciding
  to engage or defer. The `EvaluateCasePriority` BT node is
  **outgoing-only** and does NOT appear in the receive-side trees.

### Request Model DRY Pattern

When implementing trigger request models, check existing models first:

- `ValidateReportRequest` and `InvalidateReportRequest` are identical;
  prefer a shared base class over two independent models.
- `RejectReportRequest` extends the base by adding a required `note` field.
- All request models SHOULD use `model_config = ConfigDict(extra="ignore")`
  for forward-compatibility (TRIG-03-002).

**See also**: `specs/triggerable-behaviors.yaml`.

---

## BT Requirement for Trigger Use Cases

Trigger use cases follow the same BT requirement as received use cases:
all protocol-observable behaviors MUST be implemented as BT nodes or
subtrees. A trigger endpoint's `execute()` method is permitted to contain
infrastructure glue (build event, set up blackboard), but the domain logic
MUST live in the BT.

In particular, trigger use cases MUST NOT call `SvcXxxUseCase().execute()`
or equivalent domain functions procedurally after `bridge.execute_with_setup()`
returns. Cascades from the triggering action to downstream protocol behaviors
must be expressed as BT child subtrees.

See `specs/behavior-tree-integration.yaml` BT-06-005 and BT-06-006, and
`notes/bt-integration.md` for the subtree composition model (see "Canonical CVD
Protocol Behavior Tree Reference" section).

---

## General-Purpose vs. Demo-Only Trigger Classification

> Spec: `specs/triggerable-behaviors.yaml` TRIG-08, TRIG-09, TRIG-10;
> `specs/configuration.yaml` CFG-04. Operating rules summary:
> `vultron/core/use_cases/triggers/AGENTS.md`.

### Background

Vultron's trigger API (`POST /actors/{id}/trigger/{behavior}`) lets
external callers initiate protocol behaviors. Over time, demo scripts
added triggers that exist purely to puppeteer actors through steps their
own BTs should handle autonomously — "puppet string" triggers. These
accumulate technical debt: they look like general-purpose API operations
but belong only in demo deployments.

IDEA-26041003 introduces a formal classification and a separate URL
prefix (`/demo/`) so the distinction is explicit in URLs, OpenAPI docs,
and at runtime.

### Classification Criteria

| Category | Criterion |
|---|---|
| **General-purpose** | Represents a legitimate external stimulus or an intentional actor decision that an operator or agentic client would make |
| **Demo-only** | Only needed to puppeteer an actor through a step its own BT would handle autonomously in a real deployment |

**Key test**: would a real autonomous actor ever need an external caller
to drive this step? If yes → general. If the BT should always handle it
→ demo-only.

### Trigger Audit Results

| Endpoint | Prefix | Classification | Notes |
|---|---|---|---|
| `validate-report` | `/trigger/` | General | Explicit RM decision |
| `invalidate-report` | `/trigger/` | General | Explicit RM decision |
| `reject-report` | `/trigger/` | General | Explicit RM decision |
| `engage-case` | `/trigger/` | General | Explicit RM decision |
| `defer-case` | `/trigger/` | General | Explicit RM decision |
| `close-report` | `/trigger/` | General | Explicit RM decision |
| `submit-report` | `/trigger/` | General | Finder initiating CVD is always an external stimulus |
| `create-case` | `/trigger/` | General | Coordinators legitimately open cases from scratch |
| `add-object-to-case` | `/trigger/` | General | **New** — replaces `add-note-to-case` as the general endpoint |
| `add-report-to-case` | `/trigger/` | General | Real deduplication/linking action; delegates to `add-object-to-case` |
| `propose-embargo` | `/trigger/` | General | Explicit EM decision |
| `accept-embargo` | `/trigger/` | General | Explicit EM decision |
| `reject-embargo` | `/trigger/` | General | Explicit EM decision |
| `propose-embargo-revision` | `/trigger/` | General | Explicit EM decision |
| `terminate-embargo` | `/trigger/` | General | Explicit EM decision |
| `suggest-actor-to-case` | `/trigger/` | General | Real CVD coordination action |
| `invite-actor-to-case` | `/trigger/` | General | Real CVD coordination action |
| `accept-case-invite` | `/trigger/` | General | Explicit actor decision |
| `add-note-to-case` | `/demo/` | Demo-only | Moved from `/trigger/`; wrapper on `add-object-to-case` |
| `sync-log-entry` | `/demo/` | Demo-only | Moved from `/trigger/`; should cascade automatically in production |

### Wrapper Pattern: `add-object-to-case`

Type-specific convenience triggers delegate to the general
`add-object-to-case` use case after validating the object type.

```python
# General trigger (at /trigger/) — accepts any object type
class SvcAddObjectToCaseUseCase:
    def __init__(self, dl: DataLayer, request: AddObjectToCaseTriggerRequest):
        self._dl = dl
        self._request = request

    def execute(self) -> dict:
        obj = self._dl.read(self._request.object_id)
        # attach obj to case, queue Add(obj, case) activity ...


# Type-specific wrapper (at /trigger/) — validates type, delegates
class SvcAddReportToCaseUseCase:
    def execute(self) -> dict:
        obj = self._dl.read(self._request.report_id)
        if not isinstance(obj, VulnerabilityReport):
            raise VultronError(f"{self._request.report_id} is not a Report")
        inner = SvcAddObjectToCaseUseCase(
            self._dl,
            AddObjectToCaseTriggerRequest(
                case_id=self._request.case_id,
                object_id=self._request.report_id,
            ),
        )
        return inner.execute()


# Demo-only note wrapper (at /demo/)
class DemoAddNoteToCaseUseCase:
    def execute(self) -> dict:
        note = as_Note(name=self._request.note_name,
                       content=self._request.note_content)
        self._dl.save(note)
        inner = SvcAddObjectToCaseUseCase(
            self._dl,
            AddObjectToCaseTriggerRequest(
                case_id=self._request.case_id,
                object_id=note.id_,
            ),
        )
        return inner.execute()
```

### `sync-log-entry` and the Context Field Format

Moving `sync-log-entry` to `/demo/` surfaces a design note about a
future production `force-sync` operation.

SYNC-03-004 already requires that participants include their log tail
hash in the `context` field of messages sent to the CaseActor:

```text
context: "https://example.org/cases/abc123#sha256:deadbeef..."
```

This allows the CaseActor to detect out-of-sync participants and initiate
a replay automatically. A proper `force-sync` trigger, if ever added
under `/trigger/`, would build on this mechanism. Until then,
`sync-log-entry` remains a demo scaffold under `/demo/`.

### Testing Patterns

```python
def test_demo_router_absent_in_prod(monkeypatch, test_client):
    monkeypatch.setenv("VULTRON_SERVER__RUN_MODE", "prod")
    reload_config()
    response = test_client.post("/actors/alice/demo/add-note-to-case", json={})
    assert response.status_code == 404

def test_demo_router_present_in_prototype(monkeypatch, test_client):
    monkeypatch.setenv("VULTRON_SERVER__RUN_MODE", "prototype")
    reload_config()
    response = test_client.post(
        "/actors/alice/demo/add-note-to-case",
        json={"case_id": "...", "note_name": "Test", "note_content": "..."},
    )
    assert response.status_code == 202

def test_add_note_not_at_trigger_prefix(test_client):
    response = test_client.post("/actors/alice/trigger/add-note-to-case", json={})
    assert response.status_code == 404
```
