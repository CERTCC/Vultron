---
title: NoDataAvailable surfaces in initialise(), not setup()
type: learning
timestamp: "2026-07-29T00:00:00Z"
source: ISSUE-1808
signal: spec-ambiguity
---

The py_trees `BehaviourWithPorts` API raises `NoDataAvailable` when `get_input()`
is called on a port whose key has no value on the blackboard — which happens in
`initialise()` at the start of the first tick, not during `setup_ports()` or
`setup()`.

The initial spec entries (BTND-03-011) and ADR-0044 both stated that the error
surfaces "at setup time" / "at `setup_ports()` time". This is incorrect:
`setup_ports()` only registers key access; the read and the potential raise happen
in `initialise()`.

The spec and ADR were corrected before the PR was opened, but this is a recurring
source of confusion: "early error detection" means "at the start of the first tick"
(earlier than mid-tick `KeyError` from direct attribute access), not "before any tick."

**Implication for tests**: A missing-required-port test should call `setup_ports()`
(with no remappings → default namespace keys; blackboard empty), then call
`get_input("port_name")` and assert `NoDataAvailable`. Calling only `setup_ports()`
and asserting an error there will produce a false-passing test.

**Promoted**: 2026-07-31 — captured in `notes/bt-pitfalls.md` (NoDataAvailable timing section) and `specs/behavior-tree-node-design.yaml` BTND-03-011 already corrected.
Docs PR: TBD.
