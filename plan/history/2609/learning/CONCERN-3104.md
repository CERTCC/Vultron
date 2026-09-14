---
source: CONCERN-3104
timestamp: '2026-09-14T17:13:18.210700+00:00'
title: 'call-out infrastructure: no runtime guard against RUNNING from call-out backends'
type: learning
---

Call-out point backends that return `Status.RUNNING` stall the parent `Sequence`. The reference implementation's call-out infrastructure (`vultron/core/behaviors/call_out/`) had no wrapper, assertion, or timeout that detects or rejects `RUNNING` from a call-out node. The stall was invisible until manual tree inspection: the `BTBridge` busy-loops on a root `RUNNING` up to `max_iterations` (100), then fails with an opaque "exceeded max iterations" message that never names the offending node; in single-tick / nested-Sequence contexts `RUNNING` propagates as-is.

Surfaced during code review for PR #3094 (issue #2974); the how-to guide warns against the pattern, but a warning alone does not prevent the failure.

**Resolution**: Reframed from a narrow local fix to enforcing a codebase-wide invariant — no Vultron BT node returns `Status.RUNNING` (already the design principle in ADR-0080). Made normative by new spec requirement `BT-18-011`, enforced by two mechanisms: (1) a runtime guard at the call-out bundle seam that raises a non-`VultronError` on `RUNNING` (so the bridge classifies it as `internal_error`, not a protocol FAILURE), covering backends injected from outside the repo; and (2) a static architecture ratchet forbidding `return Status.RUNNING` anywhere under `vultron/`, covering in-repo authored nodes. No new ADR — enforces ADR-0080.

**Resolved**: 2026-09-14 — implementation tracked in #3194.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3191>.
Spec: `specs/behavior-tree-integration.yaml` (BT-18-011).
