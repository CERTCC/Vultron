---
title: Sentinel stubs must be synced to the catalog when the upstream FUZZ-08f task closes
type: learning
timestamp: '2026-07-14T00:00:00Z'
source: ISSUE-1177-b
---

When FUZZ-08f (Sentinel shape, issue #1175) was completed, the three Sentinel
catalog entries in `bt-fuzzer-nodes-report-management.md` all carried the note
`*(to be implemented — see FUZZ-08f)*`. Only `NewValidationInfoSentinel` was
actually added; `NewPrioritizationInfoSentinel` and `NewDeploymentInfoSentinel`
were left unimplemented.

The pattern to watch for: a catalog entry with `New-arch cross-ref: *(to be
implemented — see FUZZ-08x)*` where the referenced issue is now CLOSED is a
gap. The domain-sweep audit (FUZZ-08h) is the right place to catch these; the
fix is a small addition to `call_out_point.py` and a catalog cross-ref update.

**Promoted**: 2026-07-15 — captured in notes/bt-fuzzer-nodes-report-management.md.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1458>8>8>8>8>.
