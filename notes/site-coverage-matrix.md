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
| `cvd-practitioner` | 0 | 7 | 14 | 9 | 0 |
| `platform-developer` | 0 | 5 | 45 | 45 | 0 |
| `process-researcher` | 0 | 5 | 2 | 12 | 14 |
| `project-contributor` | 0 | 0 | 14 | 16 | 0 |
| `ALL` | 3 | 2 | 1 | 0 | 0 |

Reader-facing pages that declare both keys: 138.
Pages that declare neither yet are listed in
`vultron/metadata/docs/page_frontmatter_baseline.txt`, not here;
working-record pages carry no level (DF-11-012) and are not counted.
