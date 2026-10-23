---
source: CONCERN-1968
timestamp: '2026-08-05T17:34:11.513526+00:00'
title: Actor container INFO logs are too noisy to narrate the case story; key CVD
  state transitions are missing or buried
type: learning
---

## Summary

At INFO level, actor container logs are dominated by persistence plumbing
(`DataLayer stored/saved`), BT scaffolding (BT structure printout on every
execution), and protocol bookkeeping echoes (pipeline outcome, outbox
preambles, EM FSM callback lifecycle lines), making it impossible to "get
the story of the case from the actor's perspective." Simultaneously, the
most meaningful CVD milestones — RM state transitions per participant,
CS/VFD state changes (fix, deploy, publish), embargo lifecycle beyond
initial proposal, and case engagement — are either absent at INFO or only
visible buried inside DEBUG-level `PersistLogEntry` JSON payloads.

## Root Cause

INFO and DEBUG levels were assigned based on where code is convenient to
instrument, not based on "what would a reader need to follow the protocol
story." The result is two failures: high-volume infrastructure lines at
INFO that a reader must filter mentally, and missing narrative lines for
the exact events that matter most to understanding what the protocol is
doing.

## Resolution

Two-pass remediation tracked in #1988:

1. Demote ~10 infrastructure INFO patterns to DEBUG (SL-04-007)
2. Add ~8 missing INFO messages for CVD milestones following the
   `"Actor X did Y on case Z (STATE_A → STATE_B)"` template (SL-04-001,
   SL-04-006)

**Resolved**: 2026-08-05 — implementation tracked in #1988.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1987>.
Spec: `specs/structured-logging.yaml` (SL-04-006, SL-04-007).
Notes: `notes/structured-logging.md`.
