---
name: wire-normalize-ratchet-threshold-weakened
description: test_normalize_wire_to_core_ratchet.py threshold was lowered from >50 to >20 entries, creating a 40-entry blind spot for partial-import failures
metadata:
  type: project
---

`test/architecture/test_normalize_wire_to_core_ratchet.py:89` checks `assert len(VOCABULARY) > 20` and `assert len(WIRE_TYPE_MAP) > 20` (split from a previous combined `> 50` check).

**Why:** If a circular-import guard or missing subpackage import leaves ~25 entries in each registry, both `> 20` guards pass while ~40 wire types are absent, making the shadow-collision and normalization ratchets give vacuously correct results.

**How to apply:** Raise each threshold to ≥35 (half the real count ~70) so a partial population fails immediately. Pre-existing issue discovered during code review of PR for #2500.
