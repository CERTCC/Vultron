---
title: Nodes with instance-computed blackboard keys cannot use static input_ports()
type: learning
timestamp: "2026-08-21T00:00:00+00:00"
source: ISSUE-1885
signal: design-question
---

Three nodes in `case/nodes/participant/owner.py` (`PersistOwnerCaseNode`,
`AdvanceOwnerRmToAcceptedNode`, `RecordOwnerJoinedEventNode`) compute their
blackboard keys dynamically from the constructor's `report_id` parameter:

```python
_seg = report_id.split("/")[-1] if report_id else "default"
self._participant_case_key = f"participant_case_{_seg}"
```

`input_ports()` is a classmethod — it cannot access instance state, so these
keys cannot be declared there. Attempting to use `DataLayerActionWithPorts` with
`self._blackboard_client.register_key(...)` in `setup()` fails because
`_blackboard_client` is typed Optional and Pyright correctly flags `.register_key`
on None.

Decision made in #1885: revert these nodes to `DataLayerAction`. They must
stay unmigrated until a design that accommodates dynamic key names is adopted
(e.g., a port template or a runtime-registration extension).

This is a known gap in the typed-Ports migration that will surface again in
Parts 4 and 5 (#1886, #1887). Flag for consideration in the finalization issue.

**Promoted**: 2026-08-24 — captured in notes/py-trees-ports-adoption.md.
Docs PR: [PR URL TBD].
