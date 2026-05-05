---
source: TASK-CC.1
timestamp: '2026-05-05T12:14:36.585128+00:00'
title: 'CC.1: Reduce CC>15 violations and activate CC=15 gate'
type: implementation
---

## TASK-CC.1 — Phase 1: Reduce CC>15 violations to CC≤10 and activate CC=15 gate

Refactored all five functions exceeding CC=15 to CC≤10:

- **CC.1.1** `extract_intent` (CC=34→≤10): moved all inner helper functions
  (`_get_id`, `_get_id_list`, `_get_type`, `_to_domain_obj`,
  `_build_activity_snapshot`) to module-level private functions; extracted
  per-type domain-object builders (`_build_report_object`,
  `_build_case_object`, `_build_embargo_event_object`, etc.) and a dispatch
  table `_OBJ_BUILDERS`; introduced `_build_object_kwargs` to orchestrate
  them. Also fixed a latent mypy type error: `context` in `VultronActivity`
  snapshot now correctly passes `_get_id(context)` (string ID) instead of the
  raw AS2 object.
- **CC.1.2** `rehydrate` (CC=18→≤10): extracted `_resolve_string_id`,
  `_rehydrate_nested_object_field`, and `_cast_to_vocabulary_type` as
  module-level private functions.
- **CC.1.3** `thing2md` (CC=17→≤10): extracted `_mkrow`, `_get_thing_properties`,
  `_get_optional_list`, and `_build_thing_data` module-level helpers.
- **CC.1.4** `mock_datalayer` (CC=17→≤10): extracted `_mock_get_helper`,
  `_mock_read_helper`, `_mock_store`, `_mock_by_type_helper` to module level;
  fixture wired via `functools.partial`.
- **CC.1.5** `print_model` (CC=16→≤10): extracted `_write_node_links` and
  `_write_path_links` helpers.
- **CC.1.6** Gate: added `max-complexity = 15` to `.flake8`; added `flake8`
  pre-commit hook to `.pre-commit-config.yaml`; updated
  `.agents/skills/run-linters/SKILL.md` to document the CC gate.

All linters (Black, flake8, mypy, pyright) and unit tests pass cleanly.
