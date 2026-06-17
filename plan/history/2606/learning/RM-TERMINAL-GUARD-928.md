---
source: RM-TERMINAL-GUARD-928
timestamp: '2026-06-15T20:16:01.555928+00:00'
title: RM terminal guard ordering
type: learning
---

`ValidateRMTransitionNode` must evaluate terminal-state rules before its `current == new` short-circuit. If equality is checked first, repeated `CLOSED -> CLOSED` updates are treated as successful no-ops at validation time but still flow through append/broadcast/log-cascade paths as new status IDs. Guarding terminal `RM.CLOSED` first prevents duplicate closure cascades and keeps `close_case` retries from creating new canonical ledger entries.

**Promoted**: 2026-06-15 — captured in `specs/case-management.yaml` (CM-04-007) and `AGENTS.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/978>.
