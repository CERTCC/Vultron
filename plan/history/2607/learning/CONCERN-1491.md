---
source: CONCERN-1491
timestamp: '2026-07-20T14:14:35.677051+00:00'
title: 'specs: audit and fix kind mismatches at file, group, and item level'
type: learning
---

## Background

Issue #1490 fixed the 7 spec files where the *file-level* `kind:` was clearly wrong.
However, miscategorization exists at all three levels of the spec hierarchy —
file, group, and individual item — and the levels interact through inheritance.

## How kind inheritance works

The `kind:` field cascades downward as a default:

- **File-level** `kind:` is the default for all groups and items in that file
- **Group-level** `kind:` overrides the file default for all items in that group
- **Item-level** `kind:` overrides both, regardless of what the file or group says

This means **file and group kinds are purely a boilerplate-reduction convenience**.
The semantically important thing is that **each individual spec item ends up in the
correct category**. File and group kinds should reflect the majority of their
contents, but exceptions at any level must be overridden explicitly.

## Problem

Mixed-content files and groups cause specs to appear on the wrong category page.
The audit in #1490 only addressed file-level kind errors. Group-level and
item-level mismatches have never been systematically reviewed.

## Key finding during planning

`render_for_kind()` in `docs_render.py` filters by **file-level kind only** —
group/item kind overrides affect `spec-dump`/LLM export but are silently ignored
in published docs. This means adding YAML overrides alone is insufficient to fix
the wrong-page problem; the renderer must be updated to use `effective_kind()`.

## Work required

1. Update `render_for_kind()` to route groups by effective kind; groups with
   mixed-kind items appear on each matching page; non-matching items suppressed.
2. Audit all ~60 spec files bottom-up (item → group → file kind) and add
   group/item overrides as needed.
3. Add a linter warning for kind drift (suppressible via `lint_suppress`).

**Resolved**: 2026-07-20 — implementation tracked in #1528.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1527>.
Spec: `specs/spec-registry.yaml` (SR-09-001 through SR-09-004).
