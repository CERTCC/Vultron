---
source: ISSUE-1242
timestamp: '2026-07-13T20:54:24.633264+00:00'
title: 'FUZZ-08h: Apply ActuatorCallOutPoint to all Actuator-shaped fuzzer nodes'
type: implementation
---

## Issue #1242 — FUZZ-08h: Implement all Actuator-shaped call-out points (cross-domain)

Applied ActuatorCallOutPoint mixin to 11 remaining Actuator-shaped fuzzer nodes across 5 files (OnEmbargoExit, OnEmbargoAccept, OnEmbargoReject in embargo.py; PreCloseAction in close_report.py; MonitorDeployment in deploy_fix.py; Publish in publication.py; RemoveRecipient, SetRcptQrmR, InjectParticipant and its 3 subclasses in report_to_others.py). Each node gains a BT-18-001 blackboard contract docstring and the ActuatorCallOutPoint import. The pre-existing exemplars OnAccept and OnDefer (done in #1151) were excluded. 56 new parametrized unit tests added. Code review found one vacuous test (non-write test used empty output_keys fixture); fixed to use a declared key with a negative assertion. PR: <https://github.com/CERTCC/Vultron/pull/1400>
