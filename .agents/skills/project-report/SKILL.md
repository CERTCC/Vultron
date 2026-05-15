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

1. **Git log** — commits merged within the date range:

   ```bash
   git log --oneline --after=<start_date> --until=<end_date> \
     --merges --pretty=format:"%h %s"
   ```

2. **GitHub PRs** — all PRs merged during the period:

   ```bash
   gh pr list --repo CERTCC/Vultron \
     --state merged \
     --json number,title,mergedAt,body \
     --jq '[.[] | select(.mergedAt >= "<start_date>T00:00:00Z"
                     and .mergedAt <= "<end_date>T23:59:59Z")]'
   ```

3. **History entries** — read the `plan/history/<YYMM>/` folder(s) that
   overlap the period. For multi-month periods, read each relevant YYMM
   folder's index and entry files. Focus on `implementation/`, `priority/`,
   and `learning/` subdirectories; skip `report/` entries.

### Phase 3 — Analyze and group

Review the gathered data against the theme heuristics in
[REFERENCE.md](REFERENCE.md).

1. Map each significant PR and history entry to one of the theme categories
   (e.g., Protocol automation, Multi-actor scenarios, API / architecture,
   Developer tooling, Bug fixes, Documentation, Dependencies).
2. Identify the 4–7 most prominent themes of the period.
3. Skip or aggregate trivial changes (single-line fixes, routine bumps).
4. Plan a single aggregate sentence for dependency-only PRs — do not list
   them individually.
5. Note any significant work that started but did not finish in the period;
   flag those with an "in progress" caveat.

### Phase 4 — Draft the report

Write the full report following the structure and tone guidelines in
[REFERENCE.md](REFERENCE.md):

- **Frontmatter**: `title`, `type`, `period_start`, `period_end`, `timestamp`
- **Executive summary**: 2–4 sentences covering overall productivity, the
  2–4 major themes, and any notable caveats
- **Theme sections** (4–7): one H2 heading per theme; lead with the
  user-visible capability or outcome; link significant PRs inline using
  `[PR #NNN](https://github.com/CERTCC/Vultron/pull/NNN)`
- **Footer line**: `*Report covers: <start> through <end> | Repository:
  [CERTCC/Vultron](https://github.com/CERTCC/Vultron)*`

Hold the draft in memory — do not write to the output path yet.

### Phase 5 — Review with user

Use `ask_user` to present the draft. Offer:
`["Looks good — write it out", "I have feedback"]`

If the user selects "I have feedback", incorporate the feedback and ask again.

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
