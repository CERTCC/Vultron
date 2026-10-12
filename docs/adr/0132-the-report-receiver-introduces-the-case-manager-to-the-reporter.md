---
status: proposed
date: 2026-10-12
created: 2026-10-12
updated: 2026-10-12
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Sonnet 5.5; ADR-0041, ADR-0109; specs/case-bootstrap-trust.yaml CBT-01-001,
  CBT-01-005; specs/case-management.yaml CM-12-003, CM-22-001
informed: []
stakeholder_type: [project-contributor]
partially_supersedes: 0041-caseactor-authoritative-case-initialization.md
---

# The Report Receiver Introduces the CASE_MANAGER to the Reporter

## Context and Problem Statement

A reporter sends an `Offer(VulnerabilityReport)` to one actor, the report receiver.
Before ADR-0041, the receiver then sent the reporter a `Create(VulnerabilityCase)`.
That message told the reporter that a case now exists for its report and who maintains it.
The reporter trusted it because it came from the actor the reporter had addressed (CBT-01-005).

ADR-0041 moved case creation to the CASE_MANAGER.
It also moved the reporter's `Create(VulnerabilityCase)` to the CASE_MANAGER, and it dropped the receiver's message to the reporter.
The reporter now sends a report to one actor and receives a case from a different actor it never addressed.
Nothing the reporter wrote earlier names that actor, so there is nothing for the reporter to check the sender against.
The code works around this with a `direct` route that trusts a sender because the sender's own snapshot names it CASE_MANAGER.
A snapshot the sender wrote proves nothing, and the route is the bypass reported in #4472.

The specs now disagree.
CBT-01-001, CBT-01-005, CM-12-003 and the Protocol Specification (§4.5, §5.4.2) say the receiver sends the reporter's bootstrap.
ADR-0041, CM-22-001 and CP-09-001 say the CASE_MANAGER does.
This ADR settles which actor the reporter trusts, and why.

## Decision Drivers

- A reporter must trust only an actor it chose, or one that actor vouches for.
- A reporter's trust anchor must be a record the reporter wrote itself before the case arrived, never a roster the sender supplies.
- The receiver already knows the CASE_MANAGER, because it addressed the case proposal to it and holds its `Accept`.
- `Accept(Offer(VulnerabilityReport))` and `RK` mean receipt and validation of the report.
  They must not also carry case-creation meaning.
- `Announce(VulnerabilityCase)` is reserved for the trusted CASE_MANAGER's later syncs (CBT-02-001).
- Owner and CASE_MANAGER may be the same actor, or two actors.
  The design must work either way.

## Considered Options

1. The receiver sends the reporter a full `Create(VulnerabilityCase)` that names the CASE_MANAGER it delegated to.
   The CASE_MANAGER sends its `Create(VulnerabilityCase)` to the Case Owner only.
2. The CASE_MANAGER keeps sending the reporter's bootstrap, and the reporter checks it against something the receiver sent earlier.
3. The CASE_MANAGER sends the reporter's bootstrap, and the specs are amended to say the reporter trusts it because the snapshot names the sender.

## Decision Outcome

Chosen option: "The receiver sends the reporter a full `Create(VulnerabilityCase)`", because it restores the one anchor the reporter already has, and it needs the fewest changes to the existing requirements.

1. After the receiver accepts and trusts the CASE_MANAGER's `Create(VulnerabilityCase)`, it sends the reporter a `Create(VulnerabilityCase)` as itself.
   The message carries the full case with every participant inline, and it names the CASE_MANAGER the receiver delegated case maintenance to.
   It references the reporter's submitted report.
2. The reporter trusts that message only when a record the reporter wrote earlier ties the report to the sender.
   It then stores the report-to-case link, the sender as case creator, and the named CASE_MANAGER (CBT-01-006).
3. The CASE_MANAGER no longer addresses the reporter in its `Create(VulnerabilityCase)`.
   It sends that message to the Case Owner only.
   Its first message to the reporter is a later `Announce`, which the reporter accepts because the introduction named it.
4. `Accept(Offer(VulnerabilityReport))` and `RK` keep their receipt and validation meaning.
   `Announce` keeps its meaning as the CASE_MANAGER's sync.
5. The `direct` bootstrap route, which trusts a sender because its own snapshot names it, is removed.
   A `Create(VulnerabilityCase)` from an actor that no local anchor names is refused, and nothing is stored.
6. Owner and CASE_MANAGER MAY be one actor.
   Distinct identities are the normal case for the proposal flow, and no requirement forces them.

This partially supersedes ADR-0041.
It replaces only the decision that the CASE_MANAGER sends the reporter's bootstrap.
The CASE_MANAGER stays the creator and the authoritative source of the case, and it stays the `actor` of its own `Create(VulnerabilityCase)`.

### Consequences

- Good, because the reporter's message flow reads as a story: I sent a report to you, and you tell me a case exists and whom you delegated it to.
- Good, because the trust check needs no new anchor and the `direct` route and its bypass go away.
- Good, because the receipt and sync message meanings stay as they are.
- Bad, because the reporter's replica comes from the receiver's relay of the case, one hop later than a direct send from the CASE_MANAGER.
- Bad, because the receiver must keep the case snapshot long enough to relay it, and it vouches for the roster it relays.
- Neutral, because a receiver that is also the CASE_MANAGER sends one message to the reporter, as before ADR-0041.

## Validation

- A test sends `Create(VulnerabilityCase)` from an actor that no local anchor names, with a snapshot naming that sender as CASE_MANAGER, and asserts a refusal and an empty store (CBT-05-002).
- A test in the proposal flow asserts the reporter accepts the receiver's introduction, and the CASE_MANAGER's later `Announce`.
- A test asserts the CASE_MANAGER's `Create(VulnerabilityCase)` has the Case Owner as its only addressee.

## More Information

Source: #4473, which settles the trust anchor for #4472.
Docs and spec rewording follows from this decision: CBT-01-001, CBT-01-005, CM-12-003, CM-22-001, CP-09-001, and Protocol Specification §4.5 and §5.4.2.
