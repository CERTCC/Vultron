# Trigger Classification: Demo vs General-Purpose

**Cross-references**: `specs/triggerable-behaviors.md` (TRIG-08, TRIG-09,
TRIG-10), `specs/configuration.md` (CFG-04), `notes/triggerable-behaviors.md`,
`notes/protocol-event-cascades.md`

---

## Background

Vultron's trigger API (`POST /actors/{id}/trigger/{behavior}`) was designed to
let external callers (operators, agentic clients, demo scripts) initiate
protocol behaviors that an actor would normally drive from its internal state.
Over time, demo scripts added triggers that exist purely to puppeteer actors
through steps their own BTs should handle autonomously. These "puppet string"
triggers accumulate technical debt: they look like general-purpose API
operations, but they are scaffolding that would not belong in a production
deployment.

IDEA-26041003 introduces a formal classification and a separate URL prefix
(`/demo/`) so the distinction is explicit in URLs, OpenAPI docs, and at
runtime.

---

## Classification Criteria

| Category | Criterion | Examples |
|---|---|---|
| **General-purpose** | Represents a legitimate external stimulus or an intentional actor decision that an operator or agentic client would make | `validate-report`, `propose-embargo`, `submit-report`, `engage-case` |
| **Demo-only** | Only needed to puppeteer an actor through a step its own BT would handle autonomously in a real deployment | `add-note-to-case`, `sync-log-entry` |

**Key test**: Would a real autonomous actor ever need an external caller to
drive this step? If yes → general. If the BT should always handle it → demo.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| What makes a trigger demo-only? | External stimulus / intentional decision = general; BT puppet string = demo-only | Mirrors the definition of "triggerable behavior" vs "reactive behavior" |
| How is the classification expressed? | Separate URL prefix `/demo/` + OpenAPI tags + conditional router mounting | Visible in logs, Swagger, and at the protocol level; no ambiguity |
| How is the run mode configured? | `RunMode(StrEnum)` in `ServerConfig`, env var `VULTRON_SERVER__RUN_MODE`, default `PROTOTYPE` | StrEnum avoids bare string matching; env var plays well with Docker Compose |
| What is `RunMode.PROD`? | Demo router not mounted → HTTP 404 for `/demo/` paths | Cleanest approach; no runtime feature-flag logic in route handlers |
| Should `add-note-to-case` be generalized? | Yes → `add-object-to-case` at `/trigger/`; `add-note-to-case` becomes a `/demo/` wrapper | General principle: demos should use generalized triggers with specific object types |
| Should `sync-log-entry` stay at `/trigger/`? | No → move to `/demo/` | In a correct implementation, log entries commit automatically as a cascade; manual triggering is demo scaffolding |
| Should `add-report-to-case` be generalized? | Keep at `/trigger/`; implement as a type-validating wrapper on `add-object-to-case` | Linking a report to a case is a real operator action (e.g., deduplication) |
| What about `create-case`? | Keep at `/trigger/` | Coordinators legitimately open cases from scratch |
| What HTTP status in prod for `/demo/` paths? | HTTP 404 (routes not mounted) | Natural result; no special error handling needed |

---

## RunMode Enum

```python
# vultron/enums.py  (or vultron/config.py — whichever holds RunMode)
from enum import StrEnum

class RunMode(StrEnum):
    PROTOTYPE = "prototype"
    PROD = "prod"
```

`RunMode` MUST use `StrEnum` so comparisons like `run_mode == RunMode.PROD`
are string-safe and survive serialization/deserialization from the environment
or YAML config without bare `"prod"` string literals scattered through the
codebase.

---

## AppConfig Integration

`RunMode` lives in `ServerConfig` (CFG-04):

```python
# vultron/config.py
class ServerConfig(BaseSettings):
    base_url: str = "http://localhost:7999"
    log_level: str = "INFO"
    run_mode: RunMode = RunMode.PROTOTYPE
```

Environment variable override: `VULTRON_SERVER__RUN_MODE=prod`
YAML override:

```yaml
server:
  run_mode: prod
```

---

## Demo Router Conditional Mounting

```python
# vultron/adapters/driving/fastapi/app.py  (or wherever routers are registered)
from vultron.config import get_config
from vultron.enums import RunMode

config = get_config()
if config.server.run_mode == RunMode.PROTOTYPE:
    app.include_router(demo_router)
```

`demo_router` uses `prefix="/actors"` and `tags=["Demo Triggers"]` so all
demo endpoints appear grouped and clearly labelled in the Swagger UI.

---

## add-object-to-case Wrapper Pattern

Type-specific convenience triggers delegate to the general `add-object-to-case`
use case after validating the object type. This avoids duplicating case-add
logic.

### General trigger (at /trigger/)

```python
# vultron/core/use_cases/triggers/case.py
class SvcAddObjectToCaseUseCase:
    def __init__(self, dl: DataLayer, request: AddObjectToCaseTriggerRequest):
        self._dl = dl
        self._request = request

    def execute(self) -> dict:
        obj = self._dl.read(self._request.object_id)
        # attach obj to case, queue Add(obj, case) activity ...
```

### Type-specific wrapper (at /trigger/)

```python
# add-report-to-case calls add-object-to-case after type check
class SvcAddReportToCaseUseCase:
    def __init__(self, dl: DataLayer, request: AddReportToCaseRequest):
        self._dl = dl
        self._request = request

    def execute(self) -> dict:
        obj = self._dl.read(self._request.report_id)
        if not isinstance(obj, VulnerabilityReport):
            raise VultronError(f"{self._request.report_id} is not a Report")
        # delegate
        inner = SvcAddObjectToCaseUseCase(
            self._dl,
            AddObjectToCaseTriggerRequest(
                case_id=self._request.case_id,
                object_id=self._request.report_id,
            ),
        )
        return inner.execute()
```

### Demo-only Note wrapper (at /demo/)

```python
# add-note-to-case is a demo convenience: pre-creates a Note then delegates
class DemoAddNoteToCaseUseCase:
    def __init__(self, dl: DataLayer, request: AddNoteToCaseRequest):
        self._dl = dl
        self._request = request

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

---

## Trigger Audit Results

Full inventory as of IDEA-26041003 ingestion:

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

---

## sync-log-entry and the Context Field Format

Moving `sync-log-entry` to `/demo/` surfaces a related design note about
how a future production "force-sync" operation would work.

SYNC-03-004 already requires that participants include their log tail hash
in the `context` field of messages sent to the CaseActor. The intended
format is:

```text
context: "<case-id>#<tail-hash-of-sender-log-replica>"
```

Example:

```text
context: "https://example.org/cases/abc123#sha256:deadbeef..."
```

This allows the CaseActor to immediately detect that a participant is out
of sync and initiate a replay without the participant explicitly requesting
one. A proper `force-sync` trigger (if ever added under `/trigger/`) would
need to build on this mechanism: a peer would first advertise its current
tail hash, then the replay sender would emit only the entries the peer is
missing.

Until that protocol mechanism is defined, `sync-log-entry` remains a
demo scaffold and must stay under `/demo/`.

---

## Testing Patterns

```python
# Verify demo router is NOT mounted in prod mode
def test_demo_router_absent_in_prod(monkeypatch, test_client):
    monkeypatch.setenv("VULTRON_SERVER__RUN_MODE", "prod")
    reload_config()
    response = test_client.post("/actors/alice/demo/add-note-to-case", json={})
    assert response.status_code == 404

# Verify demo router IS mounted in prototype mode
def test_demo_router_present_in_prototype(monkeypatch, test_client):
    monkeypatch.setenv("VULTRON_SERVER__RUN_MODE", "prototype")
    reload_config()
    response = test_client.post(
        "/actors/alice/demo/add-note-to-case",
        json={"case_id": "...", "note_name": "Test", "note_content": "..."},
    )
    assert response.status_code == 202

# Verify add-note-to-case is absent from /trigger/
def test_add_note_not_at_trigger_prefix(test_client):
    response = test_client.post("/actors/alice/trigger/add-note-to-case", json={})
    assert response.status_code == 404

# Verify RunMode StrEnum round-trips through environment
def test_run_mode_env_var(monkeypatch):
    monkeypatch.setenv("VULTRON_SERVER__RUN_MODE", "prod")
    reload_config()
    assert get_config().server.run_mode == RunMode.PROD
    assert get_config().server.run_mode == "prod"  # StrEnum equality
```

---

## Layer and Import Rules

- `RunMode` MUST be defined in a neutral shared module (e.g., `vultron/enums.py`
  alongside `MessageSemantics`) so it can be imported by both core modules
  and adapter-layer routers without creating circular dependencies.
- The demo router module MUST NOT be imported unconditionally; it MUST be
  imported and registered inside the `if run_mode == PROTOTYPE` branch to
  avoid importing demo scaffolding in production deployments.
- Demo use-case classes MUST live under a separate path such as
  `vultron/core/use_cases/demo/` to make the boundary visible in the
  package structure.
