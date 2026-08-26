---
source: CONCERN-2640
timestamp: '2026-08-26T15:44:45.205244+00:00'
title: Build workflow lacks compose-before-create discovery gates
type: learning
---

Build skill and related workflow skills lack prescriptive compose-before-create
discovery procedures, causing agents to build new code when existing
implementations, base classes, or helpers could be composed or extended.

**Surface:** Agents produce duplicate implementations, copy-paste bugs, and
parallel versions of the same logic that diverge silently.

**Underlying:** The workflow tells agents *what to value* (DRY, reuse) but not
*what to do* — no structured search procedures, no discovery gates outside BT
nodes, and no blocking check fires before the agent commits to coding.

**Resolved**: 2026-08-26 — implementation tracked in #2643, #2644, #2645, #2646.
Epic: #2647.
