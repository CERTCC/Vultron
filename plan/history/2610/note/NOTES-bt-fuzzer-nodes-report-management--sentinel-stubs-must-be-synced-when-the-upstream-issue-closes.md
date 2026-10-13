---
source: NOTES-bt-fuzzer-nodes-report-management--sentinel-stubs-must-be-synced-when-the-upstream-issue-closes
timestamp: '2026-10-12T19:38:59.831070+00:00'
title: Sentinel Stubs Must Be Synced When the Upstream Issue Closes
type: note
---

**Archived:** 2026-10-12
**Reason:** obsolete: the three Sentinel stub classes exist and are slated for removal; the FUZZ-08 sweep procedure no longer applies
**Superseded by:** ADR-0097; BT-18-013; #3424

---

## Sentinel Stubs Must Be Synced When the Upstream Issue Closes

(ISSUE-1177, 2026-07-14)

A catalog entry with `New-arch cross-ref: *(to be implemented — see FUZZ-08x)*`
where the referenced issue is now **closed** is a gap — the stub was never
promoted.

When FUZZ-08f (Sentinel shape, issue #1175) closed, three catalog entries
here carried `*(to be implemented — see FUZZ-08f)*`:

- `NewValidationInfoSentinel` — was implemented; cross-ref updated.
- `NewPrioritizationInfoSentinel` — left unimplemented.
- `NewDeploymentInfoSentinel` — left unimplemented.

Only the first was added; the other two remained as unimplemented stubs with
no matching class in `call_out_point.py`.

**Pattern to apply** during domain-sweep audits (FUZZ-08h style):

1. Grep catalog entries for `*(to be implemented — see FUZZ-08x)*`.
2. Check if the referenced issue is closed.
3. If closed but the class is absent from `call_out_point.py`, it is a gap —
   add the class and update the catalog cross-ref line.

The domain-sweep audit is the right checkpoint for this; catching it there
prevents gaps from persisting across multiple closed issues.
