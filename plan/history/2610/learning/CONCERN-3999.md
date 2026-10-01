---
source: CONCERN-3999
timestamp: '2026-10-01T13:59:26.653110+00:00'
title: Story scripts duplicate _collect_item_lines
type: learning
---

`scripts/apply_story_mappings.py:42` and `scripts/backfill_stories.py:99` each define `_collect_item_lines()`, and the two bodies are identical apart from the docstring. `apply_story_mappings.py`'s module docstring says it uses "the same line-by-line state machine as backfill_stories.py", so the copy is deliberate. It is still the copy-paste CS-22-001 forbids: a fix to how either script finds where a YAML list item ends will not reach the other.

This was found in the pre-PR review of #3998 (the ruff migration, #3352), which touched both files only mechanically.

Resolution: move the helper to one shared place that both scripts import. Alternatively, if either script is a finished one-shot migration, delete it, as #3988 did for `migrate_spec_kinds.py`. `test/metadata/specs/test_backfill_stories_script.py` covers `backfill_stories.py`, and `vultron/metadata/specs/lint.py` refers to the scripts.

Governing specs: CS-22-001

**Resolved**: 2026-10-01 — implementation tracked in #4016. The duplicate is introduced by the ruff migration PR (#3998, closing #3352), so #4016 is blocked by #3352 and lands after it. Neither script is deleted: both are still live (`backfill_stories.py` is tested and selects through `sr_11_003_gate_applies()`; `apply_story_mappings.py` is needed for #2717).
