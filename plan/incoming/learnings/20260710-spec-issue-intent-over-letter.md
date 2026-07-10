---
title: Reconcile spec/issue letter vs. intent when they conflict with architecture
type: learning
timestamp: 2026-07-10
source: ISSUE-1272
---

While implementing #1272 (auto_create_case gate), the issue body and the
authoritative spec CM-15-001 contradicted each other, and the issue body
contained a factual error about the codebase.

- Issue §4 claimed the BT "already has access to ActorConfig through the
  blackboard." False — `actor_config` is threaded as a **constructor arg**
  through `create_receive_report_case_tree(..., actor_config=...)` to nodes
  (same pattern as `default_case_roles` / `CreateCaseOwnerParticipant`). The
  received-report path passed `None` (no per-actor config resolution exists).
- CM-15-001 (as written) said the use case "MUST NOT invoke
  `create_receive_report_case_tree`" when False; the issue body wanted an
  in-tree gate that *does* invoke the tree. Mutually exclusive.

Resolution (endorsed by maintainer): treat the **observable behavior** as the
real requirement, not the mechanism. Reworded CM-15-001 to specify the outcome
(no case created, outbox unchanged) and bless either enforcement location.
Implemented both a BT condition node (canonical, per BT-15-001) AND a
use-case routing short-circuit (analogous to existing recipient guards).

Guidance for future agents: neither specs nor issue text are meant to
constrain the *right* solution — they steer away from bad ones. When they
conflict with the codebase's own architecture principles (here: BT-first,
thin use-cases) or contain stale/incorrect premises, implement the intent,
then **capture the correction back into the spec and issue** (edit the spec
YAML; comment on the issue) rather than silently complying or silently
diverging. Use AskUserQuestion to surface genuine design forks.

Also: BT gate placement matters. The AGENTS.md-recommended idempotency idiom
`Selector(Sequence(guard, work), Success)` **masks** flow FAILURE. When a
downstream FAILURE must still propagate (case creation can genuinely fail),
use `Sequence[gate, existing_Selector]` instead so the gate fails-safe without
masking real failures.

Scope boundary captured as follow-up #1319: no production dispatch path
resolves a per-actor ActorConfig yet, so the flag is reachable only via
injected config (unit-tested). Runtime resolution + vendor seed-config
(needed by #1221) tracked there.
