---
name: project-report
description: >
  Generate a project report summarizing project progress for a given time
  period (month, quarter, or year-to-date). Gathers data from plan/history,
  git log, and GitHub PRs, then produces a capability-focused narrative with
  an executive summary and section headings. Use when the user asks for a
  project report, sponsor update, or monthly/quarterly summary — e.g.
  "/project-report May 2026" or "/project-report Q1 2026".
---

# Skill: Project Report

## Quick start

```text
/project-report <period>
```

Examples: `April 2026`, `May 2026`, `Q1 2026`, `Q2 2026`, `2026`

## Workflow

### Phase 1 — Parse the time period

Compute the date range and output path. The output folder is always the
`YYMM` of the **end date** (capped at today for open-ended periods):

| Input | Date range | Output YYMM |
|---|---|---|
| `April 2026` | 2026-04-01 – 2026-04-30 | `2604` |
| `May 2026` | 2026-05-01 – 2026-05-31 | `2605` |
| `Q1 2026` | 2026-01-01 – 2026-03-31 | `2603` |
| `Q2 2026` | 2026-04-01 – 2026-06-30 | `2606` |
| `Q3 2026` | 2026-07-01 – 2026-09-30 | `2609` |
| `Q4 2026` | 2026-10-01 – 2026-12-31 | `2612` |
| `2026` (full year, run in May) | 2026-01-01 – 2026-05-15 | `2605` |

Output path:

```text
plan/history/<YYMM>/report/project-report-<YYYYMMDD>-<YYYYMMDD>.md
```

Example: `plan/history/2604/report/project-report-20260401-20260430.md`

If the file already exists, overwrite silently (reports are regenerable).
Report files are **exempt from history immutability rules**.

### Phase 2 — Gather data in parallel

Run all of these simultaneously:

1. **Git log**:

Use `ask_user` to show the draft. Offer:
`["Looks good — write it out", "I have feedback"]`

### Phase 6 — Write to file

Write the approved report to the path computed in Phase 1.
Prepend YAML frontmatter:

```yaml
---
title: "<Period> Project Report"
type: report
period_start: "<YYYY-MM-DD>"
period_end: "<YYYY-MM-DD>"
timestamp: "<generation ISO datetime>"
---
```
