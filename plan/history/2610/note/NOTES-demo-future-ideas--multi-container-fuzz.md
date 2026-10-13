---
source: NOTES-demo-future-ideas--multi-container-fuzz
timestamp: '2026-10-12T23:51:10.144399+00:00'
title: 'Demo future ideas: multi-container fuzz scenario (idea, no tracking issue)'
type: note
---

Archived from `notes/demo-future-ideas.md` by #4497 (notes sweep). No issue tracked the
multi-container idea, and a plan note holds only tracked work. Its one live constraint
(container reset and STOCHASTIC bundle configuration via environment variables must be
designed first) is kept in `notes/call-out-simulation-plan.md` § "Multi-Actor In-Process
Simulation (#1732, DEMOMA-18)", which tracks epic #1161. The in-process fuzz row stays
in the note. Original row and paragraph:

---

| Scenario | Issue | Description | Status |
|----------|-------|-------------|--------|
| In-process fuzz | #1732 (planned under #1178) | FCV in-process; STOCHASTIC bundles; N configurable iterations; `vultron demo fuzz` CLI command | planned |
| Multi-container fuzz | *(future Idea under "stochastic demos" Epic)* | Containerised variant of the in-process fuzz scenario; each actor in its own container; STOCHASTIC bundles configurable via environment; container state reset between iterations | idea-stage |

The in-process fuzz scenario is misfiled here: it does have a spec group,
DEMOMA-18, so DEMOCI-11-010 places it in the [planned scenario
register](#planned-scenario-register). It cannot move there until DEMOMA-18
carries the MS-13-003 `trigger: {type: scenario_start, value: <name>}` marker the
partition check keys on.

The multi-container variant is deferred until container reset and STOCHASTIC
bundle configuration via environment variables are designed. See
`notes/call-out-simulation-plan.md` § "Multi-Actor In-Process Simulation
(#1732, DEMOMA-18)" for the design decisions reached in the #1178 planning
session.
