---
source: NOTES-do-work-behaviors--triggerable-use-cases
timestamp: '2026-09-17T17:21:04.515105+00:00'
title: Do-Work as Triggerable Use Cases (Design Direction)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) realized as per-behavior factory trees in vultron/core/behaviors/report/
**Superseded by:** vultron/core/behaviors/report/ (deploy_fix_tree.py, develop_fix_tree.py, publication_tree.py)

---

## Do-Work as Triggerable Use Cases (Design Direction)

The simulation's `RMDoWorkBt` Fallback (see
`vultron/bt/report_management/_behaviors/do_work.py`) composed eight
sub-behaviors into a single BT subtree: `AcquireExploit`, `AssignVulID`,
`Deployment`, `DevelopFix`, `MonitorThreats`, `Publication`,
`MaybeReportToOthers`, and `OtherWork`.

As the reference implementation has matured, this structure has proven to be
an artifact of the simulation layer rather than a model to replicate in
`vultron/core/`. The individual sub-behaviors have migrated in two directions:

1. **Triggerable use cases** — behaviors such as deploy-fix, develop-fix,
   publication, and report-to-others are better expressed as discrete use
   cases (each with its own core factory function) that an external actor,
   API call, or sentinel agent can trigger when preconditions are met.

2. **Sentinel / event-detection touchpoints** — behaviors like
   `MonitorThreats` cannot be automated inside Vultron; they require an
   external sentinel agent that observes the environment and calls back into
   the system when it detects a relevant event (e.g., a public exploit,
   an attack in the wild).

**Consequence**: A `create_do_work_tree` factory function that replicates
the `RMDoWorkBt` compositor is **not needed** in the reference implementation.
The role of the old compositor is replaced by:

- Individual factory functions in `vultron/core/behaviors/report/` for each
  triggerable sub-behavior (most already exist).
- Specialized sentinel agents (outside `vultron/core/`) that recognize when
  a case-relevant event has occurred and trigger the appropriate use case.

The `OtherWork` placeholder node (an extensibility hook for unmodeled
activities) similarly has no direct core equivalent: anything that was
`OtherWork` in the simulation is either a future triggerable use case or a
future sentinel agent touchpoint. No `AlwaysSucceed` placeholder is needed
in the core layer.

**See also**: `specs/triggerable-behaviors.yaml`, `notes/agentic-workflow.md`.

---
