---
source: CONCERN-4425
timestamp: '2026-10-09T21:16:59.757806+00:00'
title: Every state change emits a ledger entry and replicas copy it
type: learning
---

## Summary

Every state change in a case causes a message to emit, and the CASE_MANAGER's reaction to one event may need to commit several ledger entries, not one.
Replicas copy what the entries carry and never derive or infer anything: "if it is not in the replicated ledger, it didn't happen", and two cases at the same ledger position must be identical.
Parts of the specs, ADRs and code may still assume one trigger or one tree produces one ledger entry, and may leave replicas to infer state the CASE_MANAGER never ledgered.
This Concern is the place to revisit that overall.

## Surface Symptom vs. Underlying Problem

**Surface symptom.** While building #4384 (PR #4396), a replica could not build the invitee's inert participant record without inventing it.
The CASE_MANAGER created the record when it sent a stub Invite and committed only the Invite's entry.

**Underlying problem.** ADR-0114 ("every other participant learns of the new member from the stub Invite's entry") and ADR-0116 (dropped the participant entry as redundant) assumed one trigger produces one entry.
Inviting an actor and creating the participant record that tracks them are two state changes, and each needs its own ledger entry.
The same assumption may sit elsewhere, so the fix is not only on the stub Invite path.

**What is already right and should be left alone:** the CASE_MANAGER does the thing, commits the ledger, and the ledger replicates (CLP-09-001, ADR-0111).
Sealed outbound bodies stay unchanged (VM-08-003, OX-07-001).

## Category

Design / architecture consistency (ledger fidelity).

## Severity

Medium.
A replica that infers state can drift from the CASE_MANAGER, and the drift is silent until two copies are compared.

## Evidence

- PR #4396 (#4384): replica differs from the CASE_MANAGER after a stub Accept (VF `Vf`, consent signed, ids and clock-minted times). Its pr-verify audit found the stub Reject and `case.recommendation_recommender_index` also not replayed.
- #4395: the accept-recommendation path committed a stub Invite entry for a joined or closed participant.
- `test/architecture/test_ledger_event_types_are_replayed.py`: `KNOWN_UNREPLAYED` rows are known violations of RSH-08-004.
- ADR-0114 and ADR-0116 wording above.

## Impact if Ignored

Replicas diverge from the CASE_MANAGER on fields nobody compares, each new feature adds another inferred write, and the replay functions planned in #4294 and #4295 would encode inference instead of copying.

## Suggested Action

Audit, then decide, in one pass:

1. Every CASE_MANAGER state change has a corresponding ledger entry (specs CLP, RSH-08, SYNC, CM; the event-type registry; the `KNOWN_UNREPLAYED` rows; code paths).
2. No replica effect derives or reconstructs state (new ids, clock-minted times, re-run lifecycle logic) where it could copy the entry.
3. No spec, ADR or doc says or implies one trigger gives one entry.
4. Write the rule down once, as a spec requirement ("every state change emits a message"), and pin it with an architecture test.

## References

Related: #4294, #4295 (replay participant status and consent from the ledger, ADR-0124), #4384, #4396, #4395, #4053, epic #4283

ADR-0114, ADR-0116, RSH-08-004, CLP-09-001.

---

**Resolved**: 2026-10-09 — implementation tracked in #4294, #4295, #4439, #4440, #4441, #4442, #4443, #4444.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4453>.
Spec: `specs/case-ledger-processing.yaml` (new CLP-07-013, CLP-07-014; CLP-09-003 reworded), `specs/case-management.yaml` (CM-23-016 reworded).
Notes: `notes/case-ledger-authority.md` § "Every Change Is an Entry; Replicas Copy".
ADR: ADR-0124 revision 2 (copy model); ADR-0116 and ADR-0122 amended in place.

Decisions: copy, not compute. Every case-file change is its own entry: the act first, then one CASE_MANAGER-authored Create/Update per further change, carrying the object in full. An act whose activity states the change is that change's entry. Replicas never mint ids, read clocks or run lifecycle logic. The rule has no exceptions. Case bookkeeping (recommendation index, offer records, pending markers) is outside the case file. The received Update(VulnerabilityCase) path is removed.
