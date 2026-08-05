---
source: ISSUE-1554
timestamp: '2026-08-05T14:47:20.803993+00:00'
title: 'Migrate inline em_state reads to ReadEmStateNode (issue #1554)'
type: implementation
---

## Issue #1554 — Migrate remaining inline em_state accesses in BT nodes

Migrated inline `case.current_status.em.state` reads in `SetEmbargoActiveNode` and the former monolithic `ApplyEmbargoTeardownNode` to use `ReadEmStateNode` throughout.

**AC-1**: `SetEmbargoActiveNode._apply_transition()` now accepts `current_em: EM`; `update()` reads via `ReadEmStateNode`.

**AC-2/AC-3**: Three new single-responsibility teardown nodes added to `teardown.py`:

- `HasEmbargoActiveNode` — EM-state guard (FAILURE when already EXITED)
- `ClearActiveEmbargoNode` — EM→EXITED + `active_embargo=None` in one batched `datalayer.save()`
- `ResetParticipantConsentNode` — resets all participant PEC to NO_EMBARGO

`ActiveTeardown` sequence in `announce_teardown_tree.py` updated to wire the three new nodes.

**AC-4**: 5 new test classes, 18 new test methods.

PR: <https://github.com/CERTCC/Vultron/pull/1971>
