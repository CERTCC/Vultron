---
title: Site Coverage Matrix — Stakeholder Type × Level
status: active
description: >
  Generated count of reader-facing docs/ pages per stakeholder_type and level
  (DF-11-008). A gap here is planning input, never a merge blocker.
related_notes:
  - notes/site-information-architecture.md
related_specs:
  - specs/diataxis-requirements.yaml
---

<!-- GENERATED from docs/ page frontmatter by `uv run docs-site --write` — do not edit (DF-11-008) -->

# Site Coverage Matrix — Stakeholder Type × Level

How many reader-facing `docs/` pages declare each `stakeholder_type`
at each `level`. Read it against the expected shape described in
[site-information-architecture.md](site-information-architecture.md):
`ALL` heavy at 100 and thinning as the level climbs, the named types
diverging above it. An empty cell is a gap someone has to decide about;
nothing fails because of one.

`ALL` is its own row, not spread across the others. A page listing two
types is counted in both of their rows.

| Stakeholder type | 100 | 200 | 300 | 400 | 500 |
|---|---:|---:|---:|---:|---:|
| `cvd-practitioner` | 1 | 14 | 14 | 5 | 0 |
| `platform-developer` | 1 | 11 | 52 | 39 | 0 |
| `process-researcher` | 1 | 7 | 2 | 12 | 15 |
| `project-contributor` | 1 | 0 | 19 | 13 | 0 |
| `ALL` | 5 | 2 | 1 | 0 | 0 |

Reader-facing pages that declare both keys: 153.
Working-record pages carry no level (DF-11-012) and are not counted.
