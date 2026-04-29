---
title: "TECHDEBT-13a \u2014 Wire-boundary cleanup: test_policy.py"
type: implementation
date: '2026-03-11'
source: TECHDEBT-13a
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 1152
legacy_heading: "TECHDEBT-13a \u2014 Wire-boundary cleanup: test_policy.py\
  \ (COMPLETE 2026-03-11)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-11'
---

## TECHDEBT-13a — Wire-boundary cleanup: test_policy.py

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:1152`
**Canonical date**: 2026-03-11 (git blame)
**Legacy heading**

```text
TECHDEBT-13a — Wire-boundary cleanup: test_policy.py (COMPLETE 2026-03-11)
```

**Legacy heading dates**: 2026-03-11

Replaced `VulnerabilityReport` import (from `vultron.wire.as2.vocab.objects`)
with `VultronReport` (from `vultron.core.models.vultron_types`) in
`test/core/behaviors/report/test_policy.py`. This eliminates the residual V-23
violation where a core-layer test imported a wire-layer type. Tests pass via
duck-typing since `VultronReport` has the same fields (`as_id`, `name`,
`content`) as the wire-layer type the policy module already expects.

**Result**: 880 tests pass, 0 regressions. No production code changes.
