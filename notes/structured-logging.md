---
title: Structured Logging — Narrative Standard and Infrastructure Demotion Guide
status: active
kind: guidance
tags: [logging, observability, debugging]
description: >
  Log-call shape (SL-01-005: literal template plus lazy positional args, never an
  f-string), how correlation fields reach a record (SL-02-003: boundary filter,
  not per-call `extra=`), narrative log template (SL-04-006), infrastructure
  demotion list (SL-04-007), and where new narrative lines go so INFO logs read
  as a CVD protocol story.
related_specs:
  - specs/structured-logging.yaml
related_notes:
  - notes/codebase-structure.md
  - notes/bt-integration.md
  - notes/lint-tooling.md
  - notes/devcontainer-tooling.md
  - notes/demo-ci-diagnostics.md
  - notes/bt-pitfalls.md
---

# Structured Logging — Narrative Standard and Infrastructure Demotion Guide

Actor INFO logs must read as the story of what the protocol did, for developers
debugging a run and for contributors checking a CI transcript: every state transition
at INFO (SL-04-001), persistence bookkeeping at DEBUG.

---

## Log-Call Shape: Template Plus Lazy Arguments (SL-01-005)

Every log call passes a **literal template** and its values as **positional
arguments**, never an f-string, `.format()`, or concatenation:

```python
logger.info("Actor %s engaged case %s", actor_id, case_id)
```

`logging` keeps `msg` and `args` apart until a handler emits, and the project relies on
all three consequences:

- **The template is the event's identity**, so tests, greps, and log tools can group
  and assert on it.
- **Rendering faults stay inside logging** (`Handler.handleError`) instead of raising in
  a BT node, where `update()` is the only sanctioned catch (BT-HELPER-01).
- **Rendering is deferred**, so a filtered record never pays for `str()`.

Only rendering is deferred: argument expressions still run at the call. A guard whose
only purpose was avoiding f-string formatting goes; a guard around an expensive call
(`unicode_tree(tree)`, a demo `logfmt(obj)`) stays, with a one-line comment saying why.
Enforced by ruff `G001`–`G004`.

**A plain `py_trees` node's `self.logger` cannot take lazy arguments.** It is
`py_trees.logging.Logger`, whose methods take one pre-rendered message, so
`self.logger.debug("tick %s", n)` raises `TypeError`, and ruff identifies loggers by
receiver name, so pre-rendering fails the gate. Log through the stdlib logger that
`node_logger(node)` (`vultron/core/behaviors/node_logger.py`) returns; the Vultron node
bases rebind `self.logger` to it. A module-level helper logging for a node binds
`log = node_logger(node)` first: ruff cannot see a call on a call result, so
`node_logger(node).error(f"...")` would pass `G004` unchecked.

**A message built once for two consumers is one `%s` argument.** A node that composes a
`feedback_message` and also logs it calls `self.logger.warning("%s", msg)`, so the text
has one source and the call still has a literal template.

### `extra=` is not the other option

The template rule decides how the **message text** gets its values. Correlation fields
(`activity_id`, `actor_id`; SL-02) are record **attributes**, set by ambient context at
the processing boundary and a `logging.Filter` (SL-02-003), not by per-call `extra=`,
which would duplicate the same values at hundreds of sites. Naming an actor or case in
the message is for the reader (SL-04-006) and does not satisfy SL-02 (SL-02-004).
Output format is the formatter's job and never requires touching a call site.

---

## Narrative Template (SL-04-006)

A BT leaf node or service method that writes a protocol-visible state change SHOULD
log at INFO:

```text
Actor '<actor_id>' <verb> '<object_id>' (<STATE_A> → <STATE_B>)
```

| Domain | Verb | Example | Helper |
|---|---|---|---|
| RM | `RM:` | `Actor 'finder' RM: RECEIVED → ACCEPTED for case 'c'` | `log_rm_transition()` |
| CS/VFD, CS/PXA | `CS:` | `Actor 'vendor' CS: vfd → Vfd (fix ready) for case 'c'` | `log_cs_transition()` |
| EM | `embargo` | `Actor 'finder' embargo PROPOSED → ACTIVE for case 'c'` | `log_em_transition()` |
| Case | `engaged case` | `Actor 'finder' engaged case 'c' (RM VALID → ACCEPTED)` | `log_case_engagement()` |
| Invite | `received case invite` | `Actor 'finder' received case invite for 'c' from 'coord'` | `log_invite_received()` |
| BT failure | `BT execution` | `BT execution completed: Status.FAILURE after 3 ticks - <reason>` | none (`BTBridge`) |

`vultron/core/behaviors/narrative_log.py` owns the wording: call the helper rather than
formatting the string at the call site, so it cannot drift (CS-22-001).
`cs_event_label()` names every CS sub-dimension a transition advanced. There is
deliberately no `log_bt_failure()`: `BTBridge.execute_tree` already emits one INFO
record per terminal status. The existing embargo-propose messages and demo-step markers
follow this pattern and MUST NOT be changed.

---

## Infrastructure Patterns to Demote to DEBUG (SL-04-007)

Each pattern MUST be at DEBUG or lower. The executable form is
`test/architecture/test_infrastructure_logs_not_at_info.py`; add a newly demoted pattern
to its `DEMOTED_FRAGMENTS` rather than relying on a manual grep.

| Pattern | Why DEBUG |
|---|---|
| `Final BT state:` tree dump | BT scaffolding, not story |
| `DataLayer stored/saved/updated X 'ID'` | Persistence internals; the higher-level "Created X" line is the story |
| `Parsing activity from ...` | HTTP handler internals |
| `Processing outbox for actor ...` | Preamble; the delivery result is the meaningful line |
| `process_payload: outcome ...` / `run_inbox_pipeline: status=...` | Mechanical pipeline completion |
| `sync adapter: queued Announce(CaseLedgerEntry) ...` | Fires per recipient per entry |
| `store_embedded_participants: stored participant ...` | Fires per participant on every case announcement |
| `... already exists locally` / `already stored — skipping` | Routine idempotency skips |
| `discover_actors()` full `logfmt()` actor dump | Only the ID is meaningful |

`transitions` library chatter (`Finished processing state X ...`, `Executed callback`)
cannot be demoted at the call site: `suppress_third_party_info_noise()` in
`vultron/logging_setup.py` pins those loggers to WARNING whenever the app level is
above DEBUG, from both the server and the demo CLI. Add a new noisy library to `NOISY_INFO_LOGGERS` there.

### Static wiring stays out of DEBUG too

DEBUG is for run-time state. A line that restates code — identical every time the
same tree is built — costs CI time and buries the lines that matter. In the CI
demos, two such kinds were about 64% of every container's DEBUG bytes (#4600):

- **py_trees port registration** (`Port 'x': Registered blackboard key ...`), one
  line per port per tree build. Every `setup_ports(...)` call passes
  `logger=port_wiring_logger()` (`vultron/core/behaviors/node_logger.py`), and the
  same `suppress_third_party_info_noise()` call pins that logger at INFO through
  `STATIC_WIRING_LOGGERS`. To see the wiring, set it to DEBUG after startup; the
  pinning overwrites any level set earlier.
  `test/architecture/test_setup_ports_use_port_wiring_logger.py` fails a call
  that omits the logger.
- **The pre-tick tree dump** is gone: before the first tick every node is unrun,
  and `Final BT state:` repeats the same shape with each node's result.

The per-node `X.tick()` / `X.stop(...)` lines stay. Their statuses repeat the final
tree, but they bracket each node's own output, which is how a DataLayer read or an
error line is attributed to the node that wrote it.

---

## Implementation Guidance

### Where to add new log lines

In the **BT leaf node** that performs the state write, not the use-case `execute()`,
and at the **narrowest choke point that knows the before-state**:

- RM: `CreateParticipantStatusNode` is the one write path for per-participant RM
  state, and its `_log_transitions()` is the one RM log path
  (`vultron/core/behaviors/case/nodes/participant/status.py`). A new RM-writing node
  MUST route through it, or its transition is missing from the INFO narrative.
- CS: `CreateParticipantStatusNode` writes both VFD and PXA snapshots;
  `TransitionCStoFixReady` / `TransitionCStoFixDeployed` delegate to it and log only at
  DEBUG, since they do not know the origin state.

A trigger use case that needs the before-state captures it in `_prepare()` before the BT
mutates anything (see `SvcEngageCaseUseCase`).

### Checklist before adding a "log the reason" AC

1. **Does a record already fire there?** Enrich it instead of adding a second INFO line
   (for example, fold `get_failure_reason()` into `BTBridge.execute_tree`'s record).
2. **Is the discriminator available at the call site?** A line scoped to "non-owner
   actors" needs that predicate at every call site of the emitting function.
3. **Is `case_id` actually passed?** If no production call site passes it, the field is
   empty in every real line; find a frame that has the value.
4. **Is the defect missing information or a missing line?** `"BT FAILURE for case ''"`
   adds noise without signal.

### No-op and monotonicity guards for state-transition lines

- **Guard the no-op.** Read the after-state back from storage rather than hardcoding the
  target (BTs succeed via idempotent paths); if `before == after`, emit nothing.
  `log_cs_transition()` and `log_em_transition()` do this; any new helper MUST.
- **Guard monotonicity.** CS/RM/EM move forward only; a backward move is an anomaly,
  logged at WARNING with a distinct label (`REGRESSION_LABEL`, `"state regression"`,
  in `narrative_log.py`), not a normal transition line.

Running the same BT write twice and asserting the second emits nothing catches a
missing no-op guard, a missing monotonicity guard, and a hardcoded target at once.

---

## Grep check after refactor

The demotion list is enforced by
`test/architecture/test_infrastructure_logs_not_at_info.py`, which walks `vultron/` with
`ast`. Its docstring lists what it cannot see (inline `getLogger(...).info`, pre-built
messages); extend the test rather than assume coverage.

## Bulk Logging-Level Refactors Need a Consistency Grep Pass

Grep every matching function before commit: a partial sweep leaves two conventions in
the same module.

## Designed Self-Healing Recovery Paths MUST NOT Log at ERROR

A node whose failure a wired fallback handles (a Selector sibling, a reject-and-replay
loop) logs a self-healing event: use WARNING or INFO and name the recovery in the
message. ERROR is for conditions with no recovery path (ISSUE-2169).
