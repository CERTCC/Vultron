---
source: CONCERN-4764
timestamp: '2026-10-16T20:36:01.878517+00:00'
title: 'Copy model: a failure between an act''s entry and its consent-row entries
  leaves the act without its rows'
type: learning
---

## Problem

Under the copy model (ADR-0124, CLP-07-013) one embargo act commits several ledger entries: the act's own entry, then one CASE_MANAGER `Create`/`Update(EmbargoConsent)` entry per consent row it changes. `commit_and_apply_embargo_entries()` (`vultron/core/behaviors/embargo/copy_commit.py`) commits them one at a time and, when a later commit fails, saves the changes of the entries already committed.

That keeps the CASE_MANAGER and every replica in step, but it can leave the case in a state no single act produces. Example: a proposal's `Invite(EmbargoEvent)` commits (the `PROPOSE` step is applied), and the first `Create(EmbargoConsent)` commit fails. The register now holds the proposal, but some participants hold no row for it. ADR-0122 says every register entry has a row on every participant, and `CaseParticipant.consent_for()` raises on a missing row, so later reads of that proposal (the relay, an answer) fail.

Nothing re-commits the missing rows: a repeated propose trigger proposes a new embargo, and a redelivered received proposal is stopped by its idempotency guard.

## Why it matters

A transient commit failure in the middle of an act leaves a case the CASE_MANAGER cannot finish working, on every node.

## Options

1. Recover on the next run: a node that finds a committed act whose consequence entries are missing commits them, keyed on the act. #4715 does this for one act only, the stub re-issue (`ReissueStubInvitesNode._rows_owed`), whose replacement's invitee row is re-committed by the next run; no other converted arm has a repair pass.
2. Make the act and its consequences one ledger append (a batch commit), so they land together or not at all.
3. Accept the state and make readers tolerate a missing row (rejected by ADR-0122 today).

Found while building #4715 (proposals and answers under the copy model). A participant's answer is not affected: its own entry carries its row (ADR-0122). The same gap holds for every other converted arm with consequence rows: a proposal's `Create(EmbargoConsent)` rows, a relayed Invite's row, the CASE_MANAGER's own withdrawal, and the arms #4714, #4716 and #4717 convert.

**Resolved**: 2026-10-16 — implementation tracked in #4855.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4854>.

Spec: `specs/case-ledger-processing.yaml` (CLP-07-015).

Notes: `notes/case-ledger-authority.md`.

Decision: ADR-0146 — the act stores its decided entries as case bookkeeping before its first commit; the next CASE_MANAGER embargo tree for the case finishes them before its guards.
