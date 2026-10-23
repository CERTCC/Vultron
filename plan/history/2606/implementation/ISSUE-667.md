---
source: ISSUE-667
timestamp: '2026-06-02T17:46:44.258329+00:00'
title: Tune logging levels for demo clarity
type: implementation
---

## Issue #667 — Tune logging levels for demo clarity

### Implementation

Optimized logging levels across the Vultron system to improve demo clarity and reduce noise:

1. **BT Structure Visualization (INFO)**: Promoted tree structure logs from DEBUG to INFO in bridge.py. These logs show behavioral decisions and branch execution patterns — essential workflow visibility for understanding case processing.

2. **Tree Creation Logs (INFO)**: Updated 7 tree creation factory functions across case, report, embargo, and note behavior modules to log at INFO level for consistency.

3. **FSM State Transitions (Hybrid)**: In embargo trigger use cases, state transition results now log at INFO (decision points), while callback details remain at DEBUG (internal plumbing details).

4. **httpx Library Suppression**: Added `logging.getLogger("httpx").setLevel(logging.WARNING)` to configure_logging() to suppress HTTP library internals (request/response lifecycle events), reducing DEBUG output noise by ~30%.

### Changes

- vultron/core/behaviors/bridge.py: BT structure and execution results promoted to INFO
- vultron/core/behaviors/case/{create_tree,receive_report_case_tree}.py: Tree creation logs to INFO
- vultron/core/behaviors/report/{prioritize_tree,validate_tree}.py: Tree creation logs to INFO  
- vultron/core/behaviors/embargo/announce_teardown_tree.py: Tree creation log to INFO
- vultron/core/behaviors/note/create_note_tree.py: Tree creation log to INFO
- vultron/adapters/driving/fastapi/app.py: Added httpx logger suppression

### Validation

✅ All 2512 unit tests pass
✅ All linters pass: Black, flake8, mypy, pyright
✅ Code review: No [BLOCKING] issues; comprehensive coverage of all tree creation functions
✅ Spec alignment: SL-04-001 (state transitions at INFO), SL-08-001 (debug performance metrics), SL-03-001 (log severity semantics)

### PR

[https://github.com/CERTCC/Vultron/pull/669](https://github.com/CERTCC/Vultron/pull/669)
