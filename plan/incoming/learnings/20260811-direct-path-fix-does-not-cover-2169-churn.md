---
title: Direct-path RM.VALID gate (#2134) does not resolve the #2169 CLP-08-005 churn
type: learning
timestamp: 2026-08-11
source: ISSUE-2134
signal: concern
---

## Concern

The #2134 fix gates direct-path `engage-case` on the receiver's own committed
`RM.VALID`, resolving the fcvcv HTTP 422 race. It does **not** address the
separate transient CLP-08-005 churn tracked in **#2169** (fvcv-handoff finder
still hits "ledger empty, genesis hash unavailable" — CaseActor fan-out before
the chain is anchored). That churn self-heals and is non-fatal; the fatal
fvcv-handoff failure is the ownership-transfer step (#2178, owner-handled).

## Why it matters

The direct-path gate proves *"this participant reached VALID"* before advancing,
which is the correct causal precondition for engage-case. The #2169 churn is a
different causal gap on the **finder/invite** side (a participant is asked to act
on a case whose chain is not yet anchored/replicated to it). Fixing one does not
fix the other; they share the CLP-08-005 symptom but not the root cause.

## Status

Already tracked — no new issue filed. See #2169 (open) and #2178 (ownership
transfer, owner-handled). This note records that #2134's scope deliberately
excludes them.
