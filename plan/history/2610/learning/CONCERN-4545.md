---
source: CONCERN-4545
timestamp: '2026-10-12T20:37:00.920912+00:00'
title: Trigger-made notes commit two ledger entries for one attachment
type: learning
---

## Summary

The add-note trigger sends the CASE_MANAGER both `Create(Note)` (whose note's `context` names the case) and `Add(Note, target=Case)`.
Since #4441, the CASE_MANAGER commits the `Create(Note)` as a `create_note` entry that attaches the note, and then commits the `Add(Note)` as an `add_note_to_case` entry whose attach is a no-op.
Every note made through the trigger therefore puts two entries in the ledger for one attachment.

No spec is violated: CLP-09-003 requires a commit for each act, and replaying the second entry is idempotent.
The question is whether one note should yield one entry.

## Options

- Keep both (status quo). The ledger records each wire message exchanged.
- Have the trigger send only `Create(Note)` with `context`, which states the attachment itself (CLP-07-013).
- Have the trigger send `Create(Note)` without `context`, followed by `Add(Note)`, so only the `Add` touches the case file.

Recommendation: the second option, since it gives one message, one entry and one change. It needs a check of the demo narrative edges and invariants that expect `add_note_to_case` (DEMOMA-16-001 lists it as a universal event type).

Governing specs: CLP-07-013, CLP-09-003, DEMOMA-16-001

Where: vultron/core/use_cases/triggers/note.py

---

**Resolved**: 2026-10-12. Implementation is tracked in #4549. That is a variant of the issue's second option: the trigger sends one `Create(Note)` whose note's `context` is the case, with no `target` on the Create and no follow-up `Add`. `Add(Note, target=Case)` stays a supported protocol message. #4549 is blocked by #4441, which is still open, because the double entry happens only once #4441 lands. The general question of telling what the protocol allows apart from what this implementation sends is filed as Idea #4550.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4551>.
