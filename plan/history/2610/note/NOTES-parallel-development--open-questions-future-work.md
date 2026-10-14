---
source: NOTES-parallel-development--open-questions-future-work
timestamp: '2026-10-14T14:28:42.872490+00:00'
title: 'parallel-development: open questions, previous conventions'
type: note
---

Archived from `notes/parallel-development.md` by #4498: the plan items are
resolved or tracked elsewhere. Diff-size thresholds were recalibrated from the
merged-PR distribution and live in `vultron/metadata/planning/size_bands.py`
(`pr-size --table`). Which `Status` transitions come from built-in Projects
workflows versus the reconcile job is AC-4 of #3713. The loop-agent idea had no
design and no tracking issue. The retired `group:` label convention is history;
the note keeps only "do not recreate `group:` labels".

---

## Open Questions / Future Work

- **Diff-size threshold tuning**: The 50/300 line thresholds are a starting
  point. Revisit after the first 20–30 PRs to calibrate against observed
  complexity.
- **Mirror mechanics**: which `Status` transitions GitHub Projects' built-in
  workflows can own (for example, "item closed → Done") and which need the
  reconcile job is decided in #3713.
- **Loop-agent construction**: The revised `build` skill (issue selection +
  PR creation) is the foundation for a fully autonomous learn/plan/build loop
  agent. Design of that agent is deferred.

### Previous conventions (archived)

Before June 2026, issues used `group:<slug>` labels to mark priority group
membership and `group:unscheduled` to mark items not yet in `PRIORITIES.md`.
These labels have been deleted. Do not recreate them. Until 2026-09, every
issue carried its own Schedule value and new issues defaulted to `Someday`.
