---
title: "Spec gap: BTND-03 has no requirement that a port's data_type be the most specific domain type"
type: learning
timestamp: 2026-09-01T21:00:00Z
source: ISSUE-2907
signal: spec-gap
---

Issue #2907 hardened the `participant_case` blackboard ports from
`data_type=object` to `data_type=VulnerabilityCase`. The change is load-bearing,
not cosmetic: py_trees enforces `data_type` on **both** sides —
`_set_output()` and `get_input()` each raise `TypeError` via
`_is_instance_of_type()` (`py_trees/ports.py`). Because
`DataLayerActionWithPorts._try_get_input()` catches only `NoDataAvailable` and
`NotImplementedError`, a `TypeError` propagates. So a wrong-typed value now
fails at the port boundary in `initialise()` instead of surfacing as an
`AttributeError` deep inside `update()` after the `cast()` introduced by #2490.

**The gap**: nothing in the spec corpus requires this. BTND-03-009 requires
that every port be *declared*; BTND-03-010 through BTND-03-013 cover
remappings, `get_input()`, output ports and execution-scoped keys. None of
them say anything about *what* `data_type` should be, so `data_type=object`
(which accepts literally anything) satisfies every current requirement.

**Scale**: ~147 `data_type=object` declarations remain in
`vultron/core/behaviors/` outside `helpers.py`. Many name a concrete domain
type in the port name and are guaranteed by their writer:

| Port | Sites | Guaranteed type |
|---|---|---|
| `new_case_participant` | 4 | `CaseParticipant` |
| `invitee_case` | 3 | `VulnerabilityCase` |
| `new_invite_participant` | 3 | `CaseParticipant` |
| `append_status_participant` | 3 | `CaseParticipant` |
| `log_entry` | 5 | `CaseLedgerEntry` |
| `owner_initial_status` | 1 | `ParticipantStatus` |
| `participant_accepted_status` | 1 | `ParticipantStatus` |

Others are legitimately `object` — `datalayer`, `actor_id`,
`trigger_activity_factory`, `sync_port`, `wire_render_port` are Protocols
rather than runtime-checkable classes, and `activity` (27 sites) spans the
whole AS2 vocabulary.

**First sweep already taken**: the pre-PR code review on #2907 flagged the same
`object` + `cast()` shape on the sync ledger handoff keys — `log_entry` in
`sync/nodes/chain.py` (×2) and `sync/nodes/fanout.py` (×4), and `replay_entry`
in `sync/nodes/replay.py` (×2). Those eight declarations were tightened to
`VultronCaseLedgerEntry` in the same PR, tracked as #3011. The remaining sites
in the table above are still open.

**Reusable mechanism**: `test/core/behaviors/port_contract.py` walks a
behaviors package and returns every leaf node declaring a given port, so a
contract test parametrizes over what the package *actually contains* rather
than a hard-coded roster that goes stale. Any future sweep should use it — a
hard-coded list cannot police a port contract, because the next node added
with `data_type=object` re-opens the hole while the suite stays green.

**Known consequence of the tightening**: a violated contract fails the *whole
tree*, not the one node. Analysed, with the reason the obvious alternative is
wrong, in [[20260901-2907-port-type-error-fails-whole-tree]] — settle that
question before sweeping the remaining sites, because `_try_get_input` is
shared by ~150 nodes and the choice is not per-port.

**Suggested resolution for `learn`**: add a BTND-03 requirement of the shape
"a port whose writer guarantees a single concrete domain class MUST declare
that class as its `data_type`; `data_type=object` is reserved for Protocol-typed
injections and genuinely polymorphic payloads", then file a sweep Task per
domain. Deliberately **not** done inside #2907, whose scope was the
`participant_case` key only.

Regression guard for the narrow case:
`test/core/behaviors/case/nodes/participant/test_typed_ports.py`.

Related: [[20260831-2490-blackboard-cast-design-question]] (the `cast()`
decision that made the declaration load-bearing).
