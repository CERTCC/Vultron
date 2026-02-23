# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate 
insights, issues, and learnings during the implementation process.

Add new items below this line

---

## BT-6: Notes and Status Handler Pre-Implementation Notes (2026-02-23)

Phase BT-6 implements the `status_updates` and `acknowledge` workflows
(`docs/howto/activitypub/activities/status_updates.md` and `acknowledge.md`).
All 7 handlers are currently stubs. Use procedural code (no BT needed — simple
CRUD with 1–2 steps per handler, no branching).

### Key Model Notes

- **`as_Note`**: Defined in `vultron/as_vocab/base/objects/object_types.py`.
  Use `as_NoteRef` for references. `AddNoteToCase` activity already defined in
  `vultron/as_vocab/activities/case.py`.
- **`CaseStatus`** / **`ParticipantStatus`**: Both defined in
  `vultron/as_vocab/objects/case_status.py`. `VulnerabilityCase.case_status` is a
  `list[CaseStatusRef]`. `CaseParticipant.participant_status` is a
  `list[ParticipantStatus]`.
- **`VulnerabilityCase` has no `notes` field**: The `AddNoteToCase` activity
  references a Note and a target Case, but `VulnerabilityCase` has no `notes`
  list. Two options: (a) add a `notes: list[as_NoteRef]` field to
  `VulnerabilityCase`, or (b) store notes only in DataLayer (note is persisted
  separately; no link from case to note). Option (a) is cleaner and consistent
  with how `case_participants` and `vulnerability_reports` are tracked.
  **Recommended: add `notes` field to `VulnerabilityCase`.**
- **`create_case_status`**: Creates a new `CaseStatus` and persists it. The
  case status tracks RM/EM/CS/VFD state. Handler should persist the new status
  object. The `add_case_status_to_case` handler then appends it to
  `case.case_status`.
- **Vocab examples**: `vocab_examples.py` already has `create_note()`,
  `add_note_to_case()`, `create_case_status()`, `add_status_to_case()`,
  `create_participant_status()` — use these as reference for handler inputs.

### BT-6.3: `ack_report` Review

`ack_report` already implements `RmReadReport`. The `acknowledge.md` doc
confirms `as:Read` is the correct activity type. Review against the doc
is a light verification task, not a reimplementation.

---

Previous agents are reporting that the IMPLEMENTATION_PLAN.md is too large 
to read at once. Is there a way to break it into smaller pieces? For example,
keep the IMPLEMENTATION_PLAN.md as a forward-looking plan and move the detailed
prior tasks and their status to a separate file that can be archived as needed?
E.g., "IMPLEMENTATION_LOG.md" or "IMPLEMENTATION_HISTORY.md" that would 
become an append-only file? Document choices into specs/project-documentation.md
and AGENTS.md files as appropriate.

---

