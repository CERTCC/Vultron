---
source: ISSUE-1480
timestamp: '2026-07-17T19:38:16.782805+00:00'
title: populate SpecTag tags across all 65 spec YAML files
type: implementation
---

## Issue #1480 — populate SpecTag tags across all 65 spec YAML files

Implemented file-level `tags:` entries across all 65 `specs/*.yaml` files using the `SpecTag` controlled vocabulary.

Updated `effective_tags()` in `registry.py` to support file-level tag inheritance, added `SpecRegistry.get_effective_tags(spec_id)` for registry-based resolution, updated `lint.py`, `render.py`, and `llm_export.py` to use inherited tags, and added `tags` attribute to graph nodes in `_build_graph`.

Added 5 tests covering inheritance, override, empty fallback, graph node population, and `export_json` output consistency.

PR: <https://github.com/CERTCC/Vultron/pull/1501>
