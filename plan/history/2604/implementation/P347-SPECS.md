---
title: "P347-SPECS \u2014 Spec and Notes Updates for Trigger Completeness"
type: implementation
date: '2026-04-21'
source: P347-SPECS
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7325
legacy_heading: "P347-SPECS \u2014 Spec and Notes Updates for Trigger Completeness\
  \ (COMPLETE 2026-04-21)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-21'
---

## P347-SPECS — Spec and Notes Updates for Trigger Completeness

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7325`
**Canonical date**: 2026-04-21 (git blame)
**Legacy heading**

```text
P347-SPECS — Spec and Notes Updates for Trigger Completeness (COMPLETE 2026-04-21)
```

**Legacy heading dates**: 2026-04-21

Updated three documentation files to reflect the full set of trigger endpoints
implemented in PRIORITY-347:

- `specs/triggerable-behaviors.yaml`: Added TRIG-02-004 (Case Management
  Behaviors: `create-case`, `add-report-to-case`, `add-note-to-case`,
  `submit-report`) and TRIG-02-005 (Participant Management Behaviors:
  `suggest-actor-to-case`, `invite-actor-to-case`, `accept-case-invite`).
  Updated TRIG-03-001 request body requirements to include the new behaviors
  and added an `invite_id` requirement for `accept-case-invite`. Expanded
  TRIG-02-003 Verification to cover the new requirement IDs.

- `specs/multi-actor-demo.yaml`: Added DEMOMA-05-001 and DEMOMA-05-002
  requiring that all actor-initiated actions in scenario demos MUST be driven
  through the trigger API, not by direct inbox injection.

- `notes/protocol-event-cascades.md`: Added a concrete 4-step
  suggest→invite→accept→record cascade example (with implementation
  requirements referencing TRIG-02-005 and DEMOMA-05-001).
