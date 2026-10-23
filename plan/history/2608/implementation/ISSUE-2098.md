---
source: ISSUE-2098
timestamp: '2026-08-07T20:40:49.992774+00:00'
title: 'fix: resolve TODOs in wire-layer vocab examples (embargo.py, report.py) and
  demo pacman.py'
type: implementation
---

## Issue #2098 — fix: resolve TODOs in wire-layer vocab examples and demo

Resolved `embargo.py` `choose_preferred_embargo()` TODO — `as_Question` is
correct (it is a poll). Resolved `report.py` `read_report()` TODO — documented
why `Read(Report)` is the correct RK acknowledgment message. Removed stale
pydantic TODO from `pacman.py` — `PacmanBlackboard` already uses pydantic idioms.

PR: <https://github.com/CERTCC/Vultron/pull/2111>
