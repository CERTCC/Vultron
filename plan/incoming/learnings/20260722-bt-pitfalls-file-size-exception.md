---
title: "bt-pitfalls.md intentionally exceeds 500-line guideline as a single-scenario file"
type: learning
timestamp: "2026-07-22"
source: ISSUE-1612
signal: design-question
---

`notes/bt-pitfalls.md` is ~1007 lines, which exceeds the PD-01-002 guideline
of 500 lines per notes file. The decision to keep it as one file is correct
under PD-01-003: all BT debugging pitfalls belong to a single agent task
scenario ("Load when: debugging a BT that returns unexpected FAILURE/SUCCESS").
Splitting would require an agent to load multiple files for the same task.

The 500-line limit is a heuristic, not an absolute cap. Files with a single
coherent "Load when" scenario that happen to accumulate many pitfall entries
are exempt from splitting. The entry in notes/README.md makes the scenario
explicit.
