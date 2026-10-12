---
source: CONCERN-4473
timestamp: '2026-10-12T16:17:22.570918+00:00'
title: 'Reporter bootstrap trust: the report receiver introduces the CASE_MANAGER'
type: learning
---

## Concern

The specs disagree about who sends the reporter's bootstrap `Create(VulnerabilityCase)`, and so about what the reporter checks before it trusts the CASE_MANAGER.

- CBT-01-001 says the case creator sends the one-time bootstrap to the report submitter, and CBT-01-005 says the submitter trusts it only if it "comes from the same actor that received the report".
- CM-12-003 says the case owner queues `Create(Case)` to notify the reporter.
- The Protocol Specification says the same: §4.5 Trust and Bootstrap Semantics ("the receiving party creates the case, it sends the reporter a case-creation message") and §5.4.2 Routing Topology, exception 2.
- ADR-0041 and CP-09-001 make the CASE_MANAGER the creator of the case and the `actor` of `Create(VulnerabilityCase)`, and the reference implementation sends the reporter's bootstrap from the CASE_MANAGER.

When the report receiver does not hold the `CASE_MANAGER` role, the reporter never addressed the actor that sends its bootstrap.
So CBT-01-005's check cannot pass as written.
The code works around this with a `direct` route that trusts a sender the snapshot names as CASE_MANAGER, and that route is the trust bypass in the companion Bug filed with this Concern.

## Question for a decision

What trust anchor does the reporter check, in the ADR-0041 split topology, before it accepts a bootstrap from a CASE_MANAGER it never addressed?
Some possible answers:

1. The report receiver introduces the CASE_MANAGER to the reporter in a message the reporter can check against its own `Offer` (for example, it names the CASE_MANAGER in its reply to the report), and the reporter then accepts a bootstrap only from that actor.
2. The report receiver sends the reporter's bootstrap itself, as the specs say today, and ADR-0041 is amended to allow that for the reporter.
3. Something else.

Whatever is chosen, CBT-01-001, CBT-01-005, CM-12-003, §4.5 and §5.4.2 need rewording to match.

## Related inconsistency

CM-02-010 says the actor that holds `CASE_MANAGER` and the Case Owner MUST have distinct actor identities.
CM-02-015 says the direct-mint path registers the creating actor with both `CASE_OWNER` and `CASE_MANAGER`.
Both cannot hold.

Found while writing the #3063 explanation page (`docs/topics/case_lifecycle/case_authority_and_trust.md`), which states CBT-01-005 as written and points to this Concern.

Where: specs/case-bootstrap-trust.yaml

**Decision**: the report receiver sends the reporter a full `Create(VulnerabilityCase)` naming the CASE_MANAGER it delegated to (ADR-0132, proposed; partially supersedes ADR-0041). The CASE_MANAGER's `Create(VulnerabilityCase)` goes to the Case Owner only. The `direct` bootstrap route is removed. CM-02-010 is relaxed to MAY: owner and CASE_MANAGER may be one actor.

**Resolved**: 2026-10-12 — implementation tracked in #4511 (and #4472 re-wired as blocked by it).
Docs PR: <https://github.com/CERTCC/Vultron/pull/4509>.
Spec: `specs/case-bootstrap-trust.yaml`, `specs/case-management.yaml`.
Notes: `notes/case-bootstrap-trust.md`.
