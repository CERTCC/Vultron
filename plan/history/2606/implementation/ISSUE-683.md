---
source: ISSUE-683
timestamp: '2026-06-02T21:05:17.682026+00:00'
title: 'fix: promote Final BT state log from DEBUG to INFO'
type: implementation
---

## fix: promote Final BT state log from DEBUG to INFO

**Issue**: #683 (incomplete fix from #667/#669)

### Symptoms

`Final BT state:` tree visualization logs appeared at DEBUG level in
demo output, even though the PR #669 acceptance criteria for #667 stated
"BT structure logs moved to INFO".

### Root cause

PR #669 had an explicit comment "Log transition result at INFO; final
structure at DEBUG" — an intentional but incorrect decision. The single
`self.logger.debug(f"Final BT state:\n{tree_repr}")` call in
`vultron/core/behaviors/bridge.py` was never promoted.

### Fix

- Changed `logger.debug` → `logger.info` for the Final BT state log in
  `BTBridge.execute_tree()` and removed the misleading comment.
- Added two regression tests asserting log level is INFO for both
  SUCCESS and FAILURE outcomes.

**Validation**: All 2561 unit tests pass. All four linters clean.
