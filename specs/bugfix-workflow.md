# Bugfix Workflow Specification

## Overview

Requirements for the agent bugfix skill: root-cause depth analysis, user
engagement, escalation of discovered issues, and lifecycle archiving of
completed bug fixes.

**Source**: `plan/IDEAS.md` IDEA-26041704 (root-cause depth),
IDEA-26042202 (bug archiving)
**Note**: These requirements govern agent skill behaviour, not runtime code.

---

## Phase 2 — Clarification (MUST)

- `BFW-01-001` The agent MUST confirm the selected bug with the user before
  beginning any implementation work.
- `BFW-01-002` The agent MUST confirm its reproduction scenario description
  with the user and update its understanding if the user disagrees.
- `BFW-01-003` The agent MUST confirm the expected behaviour with the user
  and probe for edge cases when any are unclear.
- `BFW-01-004` The agent MUST confirm fix scope (files, components, tests,
  docs) with the user before proceeding.
- `BFW-01-005` The agent MUST NOT proceed to Phase 3 implementation until the
  user has explicitly confirmed or corrected every point in BFW-01-001 through
  BFW-01-004.

## Phase 2b — Root Cause Depth (MUST)

- `BFW-02-001` Unless the user has already indicated a broader underlying issue
  in Phase 2, the agent MUST ask whether the observed symptom is a surface
  manifestation of a deeper structural issue before locking in scope.
- `BFW-02-002` If the user confirms a deeper issue exists, the agent MUST ask
  which of the related concerns the current fix should address and adjust the
  agreed scope accordingly.
- `BFW-02-003` Implementation MUST remain blocked until Phase 2b produces a
  user-confirmed scope.
- `BFW-02-004` Phase 2b questions SHOULD reference specific code paths, data
  flows, or invariants the agent has identified as plausible root causes,
  rather than asking open-ended questions.

## Escalation (MUST)

- `BFW-03-001` When Phase 2 or Phase 2b analysis surfaces additional related
  issues beyond the confirmed scope, the agent MUST file each as a new entry in
  `plan/BUGS.md` using the `BUG-YYMMDDXX` ID scheme with a brief description
  and reproduction pointer.
- `BFW-03-002` The agent MUST NOT pursue newly discovered issues in the current
  run; only the confirmed-scope fix is implemented.
- `BFW-03-003` The commit message for the fix SHOULD reference any new bugs
  filed during analysis (e.g., `Also filed: BUG-YYMMDDXX`).

## Bug Archiving (MUST)

- `BFW-04-001` When a bug fix passes validation, the agent MUST append a
  completion summary for the bug to `plan/IMPLEMENTATION_HISTORY.md` in the
  same format used by the build skill (see `notes/bugfix-workflow.md` for the
  template).
- `BFW-04-002` After archiving, the agent MUST remove the bug's entry entirely
  from `plan/BUGS.md`. No tombstone, `FIXED` marker, checkbox, or closed-notice
  MAY remain.
- `BFW-04-003` `plan/BUGS.md` MUST contain only open (unfixed) bugs at all
  times.
- `BFW-04-004` Any bug already marked fixed in `plan/BUGS.md` from a prior run
  MUST be moved to `plan/IMPLEMENTATION_HISTORY.md` the next time an agent
  opens `plan/BUGS.md`, even if no new fix work is done in that run.
