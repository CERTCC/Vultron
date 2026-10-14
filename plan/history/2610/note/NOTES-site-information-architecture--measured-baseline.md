---
source: NOTES-site-information-architecture--measured-baseline
timestamp: '2026-10-14T14:26:59.139540+00:00'
title: 'site-information-architecture: measured baseline'
type: note
---

Archived from `notes/site-information-architecture.md` by #4498: a dated one-off measurement (2026-09-23) that the generated coverage matrix (DF-11-008, `notes/site-coverage-matrix.md`) replaced as the standing answer.

---

## Measured baseline

A dated one-off measurement, so later structural claims have something to be
compared against. **These numbers go stale the moment anything lands** — they
are a historical datum, not a live figure, and nothing downstream may restate
them (MS-16-001). The standing answer is DF-11-008's generated coverage matrix;
this table is what existed before there was one.

Measured 2026-09-23. Method, so it can be re-derived rather than trusted: page
totals from `docs/**/*.md`; the in-nav set from the `.md` targets parsed out of
`mkdocs.yml`; each quadrant count is the in-nav set filtered by path prefix, with
decision records counted under Reference because `docs/adr/` is navigated there,
and counting the archived ones (`docs/adr/archived/`, still navigated) but not
`adr/index.md`.

The decision-record row moved twice while this note was being written — once when
three ADRs landed on `main` mid-branch, once when ADR-0062 was archived. That is
the argument for DF-11-008's generated matrix in one line.

| | Pages |
|---|---|
| `docs/**/*.md` total | 549 |
| In nav | 336 |
| Not in nav (include fragments plus `not_in_nav` entries) | 213 |
| Tutorials | 7 |
| How-to Guides | 20 |
| Explanation | 97 |
| Reference | 206 |
| — of which decision records | 103 |
| — of which enumerated case states | 33 |
| — of which generated code pages | 22 |
| Retained design-history pages | 23 |
| Research pages (measurement, other uses, future work) | 22 |
| Capability model — the answer to the most common objection | 1 |

Reachability was checked and is *not* a problem: pages outside the nav are
almost entirely deliberate. The problem is proportion. Roughly 200 pages
written by the team, for the team or for the record, sit at the same visual
weight as the couple of dozen a newcomer can use.
