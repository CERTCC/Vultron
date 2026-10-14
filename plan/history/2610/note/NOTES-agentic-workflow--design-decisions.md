---
source: NOTES-agentic-workflow--design-decisions
timestamp: '2026-10-14T14:26:16.906829+00:00'
title: 'agentic-workflow: Design Decisions'
type: note
---

Archived from `notes/agentic-workflow.md` by #4498: rationale for delivered
pipeline choices, two rows about the retired `BUILD_LEARNINGS.md` file and the
retired `ingest-idea` skill. The open build/bugfix shared-phase work is tracked
in #3582; the learnings-queue rules live in `specs/build-workflow.yaml`
(BW-01, BW-02, BW-07) and `notes/agentic-workflow.md`.

---

## Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| Why separate `ingest-idea` from `learn`? | External ideas and internal build lessons are different sources with different quality gates | Ideas need a grill-me interview; build lessons are already structured enough to promote directly |
| Why is `update-plan` distinct from `build`? | Plan maintenance is a research task; execution is a coding task | Mixing them produces plans that drift from specs |
| Why restart the loop after each skill? | Higher-priority skills may be triggered by a lower-priority skill's outputs | Ensures design always precedes planning, planning always precedes building |
| Why no branching inside skills? | Clean boundaries enable future automation of the loop | A BT or script can inspect file-change signals to trigger the right skill |
| Why rename `IMPLEMENTATION_NOTES.md` to `BUILD_LEARNINGS.md`? | The old name implied general design notes; the new name signals a specific, focused role: a queue of code-execution observations for `learn` to promote | See `specs/build-workflow.yaml` BW-01-001 |
| Why not let `build` write directly to `notes/`? | `build`'s job is coding; documentation curation is `learn`'s domain. `BUILD_LEARNINGS.md` is the upstream channel for `build` to communicate observations; `learn` decides what to do with them | BW-01-001, BW-01-002 |
| Why are `build` and `bugfix` two skills rather than one? | Keep two skills. `work-issue` is the single type-routing entry point. The decided direction, pending #3582: each skill also gates on issue type and names the right skill for a mismatched issue, and the phases the two genuinely share (sync, claim, pre-claim AC gate, validate, finalize) move into `.agents/skills/shared/` fragments both include | The workflows diverge where it matters: `bugfix` investigates before briefing and writes the failing regression test first; `build` selects from the priority queue. A merged skill would carry both paths in every session, and these are the most-used skills in the suite, so a rewrite is the riskiest possible change (#1984, planned in #2838) |
| Why delete (not strike-through) processed learnings? | `BUILD_LEARNINGS.md` is a queue, not an archive. Processed entries live in `plan/history/` via `append-history learning`. Keeping the queue clean prevents accumulation of stale noise | BW-02-002 |
