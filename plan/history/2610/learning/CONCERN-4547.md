---
source: CONCERN-4547
timestamp: '2026-10-14T17:22:58.128023+00:00'
title: 'Participation after an embargo decline is already settled: inert, not removed'
type: learning
---

## Problem

When a participant answers an embargo invitation with a decline (consent state `DECLINED`), the protocol does not say what happens to their case participation.
They could be removed from the case automatically, or stay in the case but be excluded from embargo-protected content.

## What is already settled

- EMB-17-004: case participation survives an embargo no-op, so removal is not automatic on the late-accept path.
- The general `DECLINED` case is still open.

## Why it matters

Implementations cannot decide who receives embargo-protected case content after a decline, and the recipient rules (CM-10, ADR-0114) have no input to key on.

## Source

Found during the notes sweep for #4495 (PR #4546); the question was archived in `plan/history/2610/note/NOTES-participant-embargo-consent--open-questions.md` with no tracking issue.

---

**Resolved**: 2026-10-14 — closed as already resolved; no implementation issues.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4622>.

The concern was written from an archived open question that predates the
active-participant rules. Current specs, code and tests on `main` answer it
with the "stays in, excluded" option:

- CM-10-004, CM-31-002 (ADR-0114, ADR-0116): while an embargo is active, a
  participant is active only if its consent row for that embargo is `AGREED`.
  A `DECLINED` participant is inert: on the roster, sent no case content.
- CM-31-004: only the Case Owner removes a participant; the CASE_MANAGER MUST
  NOT remove one on its own initiative, so a decline never removes anyone.
- CM-10-007, CM-18-003: a decliner still receives embargo Invites and can be
  re-invited (`DECLINED → INVITED`).
- CM-10-006: when the embargo ends, the decliner is admitted again and sent
  the withheld ledger suffix.
- The recipient rules key on `is_signatory` in
  `vultron/core/participants/recipients.py`; `test/core/models/test_case_active_participant.py`
  and `test/core/participants/test_recipients.py` cover the declined case.

The sibling question from the same archived note — a separate owner
notification on `DECLINED`/`TIMED_OUT` — stays open as #4548.
