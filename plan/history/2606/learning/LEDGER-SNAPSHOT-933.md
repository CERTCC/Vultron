---
source: LEDGER-SNAPSHOT-933
timestamp: '2026-06-15T20:17:11.303528+00:00'
title: Guard nested payloadSnapshot inlining with case-context match
type: learning
---

Inlining nested payloadSnapshot references by blindly resolving `dl.read(id)` is unsafe: it can leak unrelated local objects into canonical `CaseLedgerEntry` snapshots when inbound activities carry attacker-controlled IDs. The inlining path must enforce a case-context match (`resolved.context == payloadSnapshot.context`) before replacing any bare ID with an inline object. This keeps CLP-07 self-contained snapshots while preventing cross-case data disclosure.

**Promoted**: 2026-06-15 — captured in `specs/case-ledger-processing.yaml` (CLP-07-008) and `AGENTS.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/978>.
