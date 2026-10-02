---
source: CONCERN-2257
timestamp: '2026-10-01T20:38:44.851552+00:00'
title: Failed Add/Remove(CaseParticipant) receipt diverges the roster — narrowed to
  participant removal semantics
type: learning
---

## Symptoms

When `AddCaseParticipantReceivedBT` fails, the receiving actor logs a WARNING
and returns. The participant is never added to the case roster, but the sender
is told the activity was processed. Every subsequent fan-out from that actor
(`Announce(CaseLedgerEntry)`, embargo notifications, status broadcasts) silently
omits the missing participant.

Unlike #2255 — which is about the *reporting* channel — this is a durable
divergence in replicated case state: two participants disagree about who is on
the case, permanently, with no reconciliation path.

## Root cause (hypothesis)

`vultron/core/use_cases/received/case_participant.py:70-77`:

```python
if result.status != Status.SUCCESS:
    logger.warning(
        "AddCaseParticipantReceivedBT did not succeed"
        " for participant '%s' / case '%s': %s", ...
    )
```

`execute()` then returns `None`. `RemoveCaseParticipantFromCaseReceivedUseCase`
(same file, lines 114-121) has the identical shape, so a failed removal leaves a
stale participant on the roster.

Roster membership is the input to every fan-out loop, so a dropped
`Add(CaseParticipant)` is not a lost notification — it is a lost *edge* in the
case's participant graph that all future messages route around.

## Done when

A failed `Add`/`Remove(CaseParticipant)` receipt either (a) leaves the roster
convergent with the sender's view, or (b) is durably recorded as a divergence
that a reconciliation path can act on. Silent permanent divergence is not
acceptable.

## Components involved

- `vultron/core/use_cases/received/case_participant.py`
- `vultron/core/behaviors/case/add_case_participant_received_tree.py`
- `vultron/core/behaviors/case/remove_case_participant_received_tree.py`

## Related

- #2255 — received-side failures cannot reach `InboxOutcome` (reporting half)
- #2235 — same warn-and-discard shape on the status path

## Blocked PRs

- #3090 (2026-09-02)

---

**Recharacterized** (2026-10-01): the reporting half was already fixed by #2255. Roster convergence runs through the ledger, and #3814 and #3733 own the gating and sender-authority parts. What remained was that `Remove(CaseParticipant)` had no protocol meaning (no emitter, no canonical signature, no replay node), and that the CASE_MANAGER's direct `Add(CaseParticipant)` after an invite acceptance was redundant.

**Resolved**: 2026-10-01. Implementation is tracked in #4079, #4080, #4081, #4083 and #4084. Decision (ADR-0116): removal is a stored fact on the participant record, and being active is computed by one case-level check. The case publishes a computed `activeParticipants` view. Only the Case Owner requests removal. The owner's received `Remove` is the single ledger entry, and the removed party gets a direct notice. Removal leaves consent untouched, and bound signatories that are no longer active are told when the embargo ends or shortens. `Add(CaseParticipant)` only reinstates, and the after-acceptance `Add` is dropped. Authority to act on a case requires being active.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4078>.
Spec: `specs/case-management.yaml` (CM-31).
Notes: `notes/case-joining.md`.
