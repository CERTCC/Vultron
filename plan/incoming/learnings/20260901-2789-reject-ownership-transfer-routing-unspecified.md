---
title: "CM-21 specifies Offer and Accept routing for ownership transfer but not Reject"
type: learning
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-2789
signal: spec-gap
---

## The gap

CM-21-005 and CM-21-006 are explicit about where the ownership-transfer `Offer`
and `Accept` go: both MUST be addressed to the CaseActor's inbox. There is no
corresponding requirement for `Reject(Offer(VulnerabilityCase))`. ADR-0053's
title and body cover "Offer and Accept"; the `Reject` is absent from the decision,
the concrete routing model and the validation section alike.

`RejectCaseOwnershipTransferReceivedUseCase` logs the rejection and does nothing
else, so the omission has no functional consequence today — which is precisely
why it can sit unnoticed until someone gives the reject path an effect.

## The interpretation taken

`vultron/demo/exchange/transfer_ownership_demo.py` addresses the `Reject` to the
CaseActor, matching the `Accept`. The reasoning is that the transferee is replying
to the *forwarded* Offer, whose `actor` is the CaseActor — so "reply to the sender"
and "route through the CaseActor" give the same answer, and no separate rule is
needed to justify it. The reject path is otherwise symmetric with the accept path
in the demo.

## Why it is worth a spec entry anyway

Three things become decisions the moment the reject path grows an effect, and none
is settled:

1. **Does a rejection get ledgered?** CM-21-007 commits a `CaseLedgerEntry` and
   broadcasts after a successful *accept*. If a rejection is protocol-significant
   — and "who declined ownership, and when" plausibly is, for the same reason
   participants need to know a transfer is pending — the CaseActor is the only
   actor that may write it (CLP-09), which makes CaseActor routing load-bearing
   rather than incidental.
2. **Does the original offerer learn of it?** With the Reject addressed to the
   CaseActor and no broadcast, the vendor who offered gets nothing at all. Today
   the offer simply expires into silence.
3. **Is a rejected offer re-offerable?** Nothing records that the transferee
   declined, so an identical Offer can be re-sent indefinitely.

Suggested shape: a CM-21-0xx entry mirroring CM-21-006 for the `Reject`, plus a
decision on whether rejection is a ledgered event. If the answer to (1) is yes,
this also wants an ADR-0053 amendment, since "route Offer and Accept through the
CaseActor" would become "route the whole negotiation".

---

**Promoted**: 2026-09-03 — captured in `specs/case-management.yaml` (new CM-21-010: `Reject(Offer(VulnerabilityCase))` MUST address the CaseActor inbox, symmetric with CM-21-006) and `notes/ownership-transfer.md` (Open Question on received-side handling of a rejected offer). Docs PR: <DOCS_PR_URL>.
