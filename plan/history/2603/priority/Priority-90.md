---
source: Priority-90
timestamp: '2026-03-10T00:00:00+00:00'
title: 'Priority 90: Fully address ADR-0013 and OPP-06'
type: priority
---

`docs/adr/0013-unify-rm-state-tracking.md` was created to capture the decision to unify state
tracking for the RM lifecycle. As noted in `archived_notes/state-machine-findings.md`,
there are a number of steps to be taken to fully implement this
decision. We need to clearly identify and execute those steps before we
proceed with the next priority. These need to be added to `notes/`, `specs/`,
and `plan/IMPLEMENTATION_PLAN.md` tasks as appropriate.

We should also capture references to OPP-06
in the relevant `notes/` files, and in `specs/` and in the implementation
plan.

This priority covers both *capturing* the tasks, requirements, and notes,
and *implementing* the changes needed to fully realize this aspect of the
design.
