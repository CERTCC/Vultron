---
source: ISSUE-3252
timestamp: '2026-09-15T15:21:14.372747+00:00'
title: double DB read in announce tree accepted as known pattern
type: note
---

## Issue #3252 — announce_tree double CheckIsCaseManagerNode evaluation

Two CheckIsCaseManagerNode instances in the announce tree evaluate for every non-CASE_MANAGER announce (once in the authority arm, once in the Inverter participant gate). Each call does one indexed SQL read plus participant iteration. Evaluated memoization via blackboard cache — adds coupling between independent node instances without measurable benefit at expected load. Closed as accepted behavior. See: <https://github.com/CERTCC/Vultron/issues/3252#issuecomment-5682822789>.
