---
source: TRIGGER-927-CASEACTOR-ROUTING
timestamp: '2026-06-22T19:34:27.699484+00:00'
title: CaseActor routing must fail fast when emit node has no CaseActor ID
type: learning
---

BT emit nodes that need the CaseActor's ID (e.g., to set `actor=case_actor_id`
on an outbound activity) MUST read it from the blackboard and return FAILURE
immediately if absent — not fall back to the triggering actor's ID or an
empty string. The subtle bug: using the triggering actor as a fallback silently
sends activities attributed to the wrong actor, passes all assertions in unit
tests that use a single-DL setup, and only surfaces in multi-actor demos.

**Promoted**: 2026-06-22 — captured in `specs/participant-case-replica.yaml`
(PCR-08-011) and `AGENTS.md` (CaseActor routing fail-fast pitfall).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
