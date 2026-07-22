---
title: Deterministic BT test wrappers must inherit production node classes
type: learning
timestamp: "2026-07-22T00:00:00+00:00"
source: ISSUE-1565
---

When writing behavior-contract tests for probabilistic call-out-point nodes
(e.g., `DevelopExploit(OftenSucceed)`, `PurchaseExploit(RarelySucceed)`), the
deterministic wrapper must subclass the **production node** with `AlwaysSucceed`
as a secondary base — not a fresh class that only inherits from the abstract
mixin and `AlwaysSucceed`.

Correct pattern:

```python
class _DeterministicDevelopExploit(DevelopExploit, AlwaysSucceed):
    pass
```

Wrong pattern (does NOT catch regressions in `DevelopExploit.output_keys`):

```python
class _Wrapper(ComposerCallOutPoint, AlwaysSucceed):
    output_keys = {"developed_exploit_artifact": str}  # duplicated, not inherited
```

The second form would pass even if `DevelopExploit.output_keys` was emptied or
renamed, because it declares its own independent `output_keys`. The first form
inherits `output_keys` from the production class, so any regression there is
caught immediately.

**Promoted**: 2026-07-22 — captured in `test/AGENTS.md`.
Docs PR: TBD (fill in after PR is opened).
