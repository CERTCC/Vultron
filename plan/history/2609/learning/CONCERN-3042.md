---
source: CONCERN-3042
timestamp: '2026-09-28T19:08:05.650040+00:00'
title: 'Sibling demo scenarios: the replica sync-verification race guard was copied,
  not missing'
type: learning
---

The `_phase_sync_verification` fix (`wait_for_case_on_container` +
`wait_for_contiguous_ledger_coverage` before the notes phase) was added only to
`fcv_reject_demo.py` under ISSUE-2390. Six sibling scenarios call
`participant_adds_note_to_case` in chained note-reply sequences and are subject
to the same replication race, so they remain intermittently vulnerable.

## Acceptance criteria

- [ ] AC-1: Each sibling scenario that chains `participant_adds_note_to_case`
  performs the same sync verification before its notes phase.
- [ ] AC-2: The guard is factored into a shared helper rather than copied per
  scenario.

## Provenance

Recovered from `plan/incoming/learnings/20260826-sibling-demo-async-race-not-fixed.md`
during the 2026-09-02 learnings-queue audit; never filed.

## Planning outcome (2026-09-28)

AC-1 was already satisfied on `origin/main`: every scenario module under
`vultron/demo/scenario/` defines a `_phase_sync_verification` that gates on the
Finder holding the case and on contiguous ledger coverage of the authority's
tail, and calls it before `_phase_notes_exchange`. The eight per-scenario flake
bugs spawned from the same learning (#2728–#2733, #2747, #2748) closed on
2026-08-27 via PR #2756, which migrated the waits from `demo_check` to
`demo_gate`; the fv scenario was found already correct. The per-note race inside
a chained exchange is handled inside `participant_adds_note_to_case`, which
gates on the note arriving at the watching container.

AC-2 was the real defect: the phase body was copied into every scenario module,
and the same read-tail-then-poll-replicas block was copied a second time into
every `_phase_case_closure`, with timeouts that drifted (literals of 15 s or
45 s by replica label in most modules, 30 s or 45 s in fcvcv after #2337, and
no timeout at all — the primitive's default — in fv, fvv and fcv-reject) and
the same unit test repeated in every scenario test file except fcv-reject's.
The concern was recharacterised as a DEMOMA-17-001 extraction: one shared
coverage-wait helper and one shared sync-verification phase helper in
`vultron/demo/helpers/sync.py`, migration of all scenario modules, collapse of
the duplicated tests, and an architecture ratchet that forbids scenario modules
from calling the coverage primitive directly.

**Resolved**: 2026-09-28 — implementation tracked in #3846.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3845>.
Spec: `specs/multi-actor-demo.yaml` (DEMOMA-23-005, DEMOMA-23-006,
DEMOMA-23-007).
Notes: `notes/demo-scenario-authoring.md`.
