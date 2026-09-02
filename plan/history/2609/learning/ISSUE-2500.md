---
title: "normalize-wire-to-core ratchet threshold lowered to >20, leaving a 40-entry blind spot"
type: learning
timestamp: "2026-09-01T18:49:21Z"
source: ISSUE-2500
signal: tooling-issue
---

`test/architecture/test_normalize_wire_to_core_ratchet.py:89` checks `assert len(VOCABULARY) > 20` and `assert len(WIRE_TYPE_MAP) > 20` (split from a previous combined `> 50` check).

**Why:** If a circular-import guard or missing subpackage import leaves ~25 entries in each registry, both `> 20` guards pass while ~40 wire types are absent, making the shadow-collision and normalization ratchets give vacuously correct results.

**How to apply:** Raise each threshold to ≥35 (half the real count ~70) so a partial population fails immediately. Pre-existing issue discovered during code review of PR for #2500.

## Audit disposition (2026-09-02)

Resolved, and more strongly than this entry proposed. `test/architecture/test_normalize_wire_to_core_ratchet.py` now asserts `> 50` for both VOCABULARY and WIRE_TYPE_MAP; the entry recommended >=35.
