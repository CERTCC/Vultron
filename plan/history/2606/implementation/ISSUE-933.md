---
source: ISSUE-933
timestamp: '2026-06-15T18:17:57.682848+00:00'
title: Inline nested protocol objects in canonical CaseLedgerEntry payloadSnapshot
type: implementation
---

## Issue #933 — Inline nested protocol objects in canonical CaseLedgerEntry payloadSnapshot (no bare ID-string substitutions)

Implemented deterministic snapshot inlining for known nested reference fields so canonical CaseLedgerEntry payloadSnapshot entries no longer depend on bare ID-string substitutions for protocol-significant nested objects. Added context-bound dereference guards to prevent cross-case object leakage during inlining, and wired the same logic through both received-side log commits and BT lifecycle commit nodes.

PR: <https://github.com/CERTCC/Vultron/pull/963>
