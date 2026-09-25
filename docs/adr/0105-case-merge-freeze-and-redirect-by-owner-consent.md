---
status: proposed
date: 2026-09-25
deciders: Allen D. Householder
consulted: []
informed: CERT/CC Vultron protocol team
stakeholder_type: [project-contributor]
---

# Two Cases for One Vulnerability Merge by Owner Consent: the Offered Case Freezes and Redirects

## Context and Problem Statement

A Report is not a Case.
A Report is the object of the initial `Offer`, and a Case exists only once a recipient accepts it.
When the same Report goes to more than one recipient, each recipient can accept it and create its own Case.
The protocol permits this on purpose: a Finder must be able to report to more than one party.

The common form is sequential, not concurrent.
A Reporter gets no answer from its first recipient, asks a Coordinator for help, and the Coordinator accepts first.
The two Cases can also arise independently, when two Finders report the same vulnerability to different parties.

The Reporter's side of this is a bookkeeping problem, and CBT-06 settles it: each `Offer` names one recipient, and the Reporter keeps one report-to-case link per (Report, recipient).
Knowing about both Cases gives the Reporter nothing to act on, because the Reporter owns neither Case.
The decision belongs to the Case Owners, and it arises when the Owner of one Case learns that the other Case exists.

The question this record settles is: when two Case Owners find that their Cases cover the same vulnerability, how do the Cases become one?

## Decision Drivers

- A Case Owner cannot lose control of its Case without consenting.
- A Participant cannot be placed under an Owner, embargo, or timeline it never accepted.
- Each Case has its own hash-chained, append-only ledger with its own `logIndex` sequence and genesis hash (CLP-08).
- Existing flows for offer-and-accept (Case Ownership Transfer, ADR-0053) and for admitting Participants (invitation and embargo consent) should be reused, not duplicated.
- References to the retired Case must still resolve after the merge.

## Considered Options

- Reconcile the two ledgers into one
- Freeze one Case and redirect it to the other, by Owner consent
- Leave merging out of scope; the Reporter mediates by hand

## Decision Outcome

Chosen option: "Freeze one Case and redirect it to the other, by Owner consent", because it keeps every ledger intact, needs no new consent model, and gives Participants of both Cases one place to coordinate.

The decision has these parts.

1. **Merging is between Case Owners.**
   The Reporter does not merge Cases, and knowing about both Cases does not oblige it to act.
   How an Owner learns about the other Case is out of scope: any channel counts.
2. **The Owner of the Case to be retired offers, and the surviving Owner decides.**
   The Owner of Case2 offers to merge Case2 into Case1, and the Owner of Case1 accepts or rejects the offer.
   No Owner can absorb a Case whose Owner did not offer it.
   The offer and the answer follow the Case Ownership Transfer pattern of ADR-0053: each is routed through the Case's CASE_MANAGER and recorded in that Case's ledger.
3. **On acceptance, Case2 freezes and redirects to Case1.**
   Case2's ledger accepts no further entries after the entry that records the merge.
   Case2 remains readable, and every request addressed to Case2 is redirected to Case1.
   Case1 and Case2 record each other through the existing parent/child/sibling case references (ADR-0017), which today no code writes; the merge spec chooses which field each side uses.
4. **Case2's Participants join Case1 by invitation, not by transfer.**
   Case1's CASE_MANAGER invites each Case2 Participant through the normal invitation flow.
   Each Participant accepts or declines, and a Participant that accepts consents to Case1's embargo in the usual way.
   The existing embargo merge requirements (VP-10, "Embargo Case Splits and Merges") apply to Case1's embargo negotiation.
5. **A Participant that declines keeps a frozen record and leaves the coordination.**
   Its copy of Case2 is frozen and read-only, like everyone else's.
   Case1's CASE_MANAGER records the decline, so Case1's Participants know that a party holding the vulnerability details is not in Case1.
   The decliner's Report Management state in Case2 closes when Case2 freezes.
   What the decliner still owes the embargo it accepted in Case2 is **not** decided here.
   That question is tracked separately: see [More Information](#more-information).

### Consequences

- Good, because no ledger is rewritten: both chains stay valid and verifiable, and Case2's history remains readable where it was.
- Good, because consent is explicit at both levels: Owner to Owner for the merge, and Participant by Participant for joining Case1.
- Good, because the offer, invitation, and embargo-consent flows already exist, so the merge adds one exchange and one frozen state rather than a parallel admission path.
- Bad, because a frozen Case and a redirect are new states the whole protocol must respect: every received-side handler for a Case2 activity needs a defined answer.
- Bad, because a Participant can end the merge outside Case1, so Case1 must plan disclosure around a party it cannot coordinate with.
- Neutral, because keeping both Cases open and bridging them is a different answer to a different need, and is not ruled out (see below).

## Validation

The merge requirements are written as a spec group derived from this record, and each `kind: protocol` entry carries a marker test.
Review confirms that no merge path writes to a frozen Case's ledger and that no Participant is added to Case1 except by accepting an invitation.

## Pros and Cons of the Options

### Reconcile the two ledgers into one

- Good, because the result is a single history.
- Bad, because two hash-chained, append-only ledgers with independent `logIndex` sequences and genesis hashes do not merge without rewriting at least one of them, which destroys the property the chain exists to give.
- Bad, because every replica of either Case must then re-verify a history that changed underneath it.

### Freeze one Case and redirect it to the other, by Owner consent

- Good, because both ledgers stay append-only and intact.
- Good, because it reuses the ownership-transfer and invitation flows.
- Bad, because it adds a frozen state and a redirect that every Case-scoped handler must honour.

### Leave merging out of scope; the Reporter mediates by hand

- Good, because it costs nothing now.
- Bad, because the Reporter owns neither Case and cannot act on what it knows.
- Bad, because Participants in the two Cases never learn the other exists, and the duplicate coordination stays invisible to the protocol.

## More Information

- Source: Concern [#3366](https://github.com/CERTCC/Vultron/issues/3366) (one Report becoming two Cases).
- Reporter-side bookkeeping: CBT-06 in `specs/case-bootstrap-trust.yaml`.
- Offer-and-accept routing pattern reused here: [ADR-0053](0053-ownership-transfer-routed-via-caseactor.md).
- Case cross-reference fields: [ADR-0017](0017-domain-wire-object-separation.md).
- Open follow-up: what a Participant that declines to join Case1 still owes the embargo it accepted in Case2, and whether the answer depends on which Case's embargo is longer.
- Open follow-up: keeping both Cases open, with a software participant in both that relays between them, as an alternative to merging when two Cases have good reason to stay separate (for example, different coordinators serving different communities on different timelines).
