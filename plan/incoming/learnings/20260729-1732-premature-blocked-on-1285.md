---
title: "#1732 (in-process fuzz scenario) was premature — depends on Epic #1285 builders"
type: learning
timestamp: "2026-07-29"
source: ISSUE-1732
signal: scope-dependency
---

#1732 (FUZZ-08e: in-process FCV fuzz simulation) was picked up for build after
its stated blockers (#1178, #1793) closed, but a cascade-reachability analysis
showed it is premature.

**Finding:** of the 11 call-out-bearing `create_*_tree` builders, only
`create_validate_report_tree` is wired into a live use case
(`SvcValidateReportUseCase`). The other 10 (embargo negotiation, develop/deploy
fix, publication, prioritization subtree, acquire exploit (+strategy), assign
vul-id, report-to-others, close-report) have **no use-case caller** — reachable
today only by constructing the tree directly (as
`vultron/demo/fuzzer/stochastic_demo.py` does). The triggers a controller would
issue to drive an FCV case (engage, propose-embargo, close) route through
separate simplified trigger BTs (`engage_case_trigger_bt`,
`propose_embargo_trigger_bt`, …) that contain zero call-out points.

Consequence: AC-3 (DEMOMA-18-003, MUST — "all actors STOCHASTIC, each call-out
decision drawn from the fuzzer distribution") is unsatisfiable end-to-end via
the real cascade (AC-4). The automatic submit→deliver→process path hits zero
call-out decisions; only validation is reachable even with explicit lifecycle
triggers.

Wiring those builders into the cascade is the scope of Epic **#1285 (FUZZ-D:
Production BT factory functions)** and children #1246–#1257 (+ #1395 Composer
wiring), all open. #1732 is the capstone that exercises them end-to-end.

**Action taken (2026-07-29):** reparented #1732 from #1284 → #1285; wired
`blockedBy` #1246–#1257 + #1395 (full set — AC-3 needs every domain, so a subset
would under-block); Schedule → Later; unassigned. No scenario code written.

**Lesson for build selection:** a leaf issue's declared `blockedBy` set can be
incomplete. Before building a scenario/integration task, verify the capabilities
its ACs assume are actually reachable in code (not just that the named blockers
closed) — the same "verify ACs against current code before starting" pitfall,
extended to cross-epic capability dependencies. The `blockedBy` graph here was
missing the entire #1285 dependency, which is what let #1732 look ready.
