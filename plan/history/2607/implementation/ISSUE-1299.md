---
source: ISSUE-1299
timestamp: '2026-07-10T16:31:57.522615+00:00'
title: Add EvaluateDefaultRolesNode — Evaluator BT call-out point for actor role assignment
type: implementation
---

## Issue #1299 — impl: add EvaluateDefaultRolesNode

Added EvaluateDefaultRolesNode (ADR-0024 Evaluator shape) to the CaseActor inbox BT for Offer(Actor, Case) processing. Prototype writes [CVDRole.VENDOR] to blackboard (CM-15-003). Wired before EmitOfferCaseParticipantToOwnerNode in create_recommend_actor_to_case_received_tree. PR: <https://github.com/CERTCC/Vultron/pull/1330>
