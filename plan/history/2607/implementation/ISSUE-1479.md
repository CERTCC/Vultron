---
source: ISSUE-1479
timestamp: '2026-07-17T16:09:11.386958+00:00'
title: Generate docs/reference/specs/ kind pages from spec YAML using markdown-exec
type: implementation
---

## Issue #1479 — docs: generate docs/reference/specs/ kind pages from spec YAML using markdown-exec

Implemented six auto-generated reference pages under docs/reference/specs/ (one per SpecKind), each rendered at build time from specs/*.yaml via markdown-exec.

Key deliverables:

- vultron/metadata/specs/docs_render.py: new MkDocs Material renderer with priority badges, cross-kind anchor links, and ECA details blocks
- SpecTag.BEHAVIORAL + SpecFile.tags field in schema.py
- export_yaml round-trip fix in render.py (_file_to_dict now includes tags)
- 6 new docs pages + nav wiring in mkdocs.yml
- 36 tests in test_docs_render.py + kind-page coverage guard

Code-review findings fixed: no-op _spec_anchor replace, behavioral heading inversion (H4/H3 → H3/H4).
DEFER: BehavioralSpec validator name shadow (pre-existing, filed as separate bug).

PR: <https://github.com/CERTCC/Vultron/pull/1485>
