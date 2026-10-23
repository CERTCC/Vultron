---
source: CONCERN-3836
timestamp: '2026-09-30T14:05:04.820343+00:00'
title: Decide whether embargo termination prunes open revision proposals from the
  open-proposal records (EP-08-003)
type: learning
---

## Problem

EP-08-003 says the record of open proposals MUST NOT retain a proposal "whose embargo has terminated". #3470 prunes the terminated embargo's own entry from `proposed_embargoes` and `pending_embargo_proposal_index` in `EmbargoLifecycle.terminate_active_embargo`. It does **not** prune open *revision* proposals against that embargo: `propose_embargo` during `ACTIVE → REVISE` appends a distinct `EmbargoEvent` id, and after `REVISE → EXITED` those revision entries survive in both records.

They then compete in the next default selection once the case leaves `EXITED` and a new proposal is made: `find_embargo_proposal_id` orders every open entry by `end_time`, so a stale revision of a dead embargo can be the earliest-expiring candidate.

## Why it was left out of #3470

EP-08-003's text reaches the terminated embargo, not proposals *about* it. Deciding that a termination decides every open revision too is a small semantic call (they are proposals no one accepted or rejected), and the standards review of #3470 recommended settling it separately rather than widening that PR.

## Acceptance criteria

- [ ] AC-1: Decide, and record in EP-08-003's note (or a new EP-08 entry), whether termination decides the open revision proposals against the terminated embargo. The default expectation is yes: a revision of an embargo that no longer exists cannot be accepted.
- [ ] AC-2: If yes, `terminate_active_embargo` prunes every open proposal whose `EmbargoEvent` is a revision of the terminated embargo, through `VulnerabilityCase.discard_proposed_embargo`, and a test asserts both records are empty after teardown with a revision pending.
- [ ] AC-3: `notes/embargo-lifecycle.md` § "Prune on decision" loses the sentence naming this gap.

## Reference

Source: standards review of #3470. Spec: EP-08-003. ADR-0100. Prior art: `terminate_active_embargo` in `vultron/core/services/embargo_lifecycle/activation.py`; `propose_embargo` in `proposals.py` (the append site).

**Resolved**: 2026-09-30 — implementation tracked in #3914. Decision recorded as ADR-0113 (embargo revision negotiation relays through the CASE_MANAGER; the ledger carries state but never asks), planned as a bundle with Concerns #3892 and #3863.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3912>.
Spec: `specs/embargo-policy.yaml` (EP-09, EP-04-011, EP-08-004); `specs/em-behavior.yaml` (EMB-03 description).
Notes: `notes/embargo-lifecycle.md`.
