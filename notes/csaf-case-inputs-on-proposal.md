---
title: "The Report Receiver States a CSAF Report's Case Inputs on Its Proposal"
status: draft
kind: plan
tracks:
  - "#6722"
  - "#6723"
  - "#6725"
  - "#5130"
  - "#3188"
description: >
  Design for moving the CSAF case-input mapping to the report receiver: a core
  conversion turns the stored claims reading, the report and the Offer into a core
  CaseProposal whose caseInputs the CASE_MANAGER applies, with the CASE_MANAGER's
  own reading of the document kept as the fallback; the CASE_MANAGER judges every
  embargo date when it builds the case, and records a passed one as an embargo
  that was in force and has ended. Holds the requirement text the implementation
  adds to specs/case-proposal.yaml and specs/embargo-policy.yaml (ADR-0184).
related_specs:
  - specs/case-proposal.yaml
  - specs/csaf-report-content.yaml
  - specs/embargo-policy.yaml
related_notes:
  - notes/affected-products.md
  - notes/csaf-report-content.md
  - notes/case-proposal.md
  - notes/embargo-default-semantics.md
relevant_packages:
  - vultron/core/models
  - vultron/core/services
  - vultron/core/behaviors/case
  - vultron/wire/as2/vocab/objects
  - vultron/adapters/driven/trigger_activity_adapter
---

# The Report Receiver States a CSAF Report's Case Inputs on Its Proposal

The report receiver converts the CSAF report it received into the case inputs of
its `CaseProposal`, and the CASE_MANAGER applies them (ADR-0184). Nothing here
is built yet.

## Who Computes What

- **The receiver converts once, and the owner may edit.** One core function takes
  the stored claims reading, the report and the Offer, and returns a core
  `CaseProposal` whose `caseInputs` are filled by `case_inputs_from_claims`. The
  receiver may change that proposal before the adapter renders it. Core builds no
  `as_CaseProposal` (ARCH-01-001); the core model pairs with it (ARCH-25-003).
- **The receiver passes dates along unjudged.** `caseInputs` carries the earliest
  `vulnerabilities[].disclosure_date` as the document states it, and no P. Whether
  the date has passed is decided when the case is built, which can be well after
  the receiver's receipt when delivery retries.
- **The earliest date is enough.** It is the Reporter's proposed end when the
  Offer proposes none (CSAF-03-001). If it has passed at creation, the case is
  also public (CSAF-03-003), and the end is one that has passed (below).
- **The proposal's `caseInputs` is all or nothing.** Present, it speaks for every
  input and the CASE_MANAGER reads no document; absent, the CASE_MANAGER maps the
  Offer's document as before. Per-field fallback would refill a list the owner
  emptied, and cannot tell an unset X or A from one the owner cleared.
- **The Reporter's proposal stays the Reporter's.** It is the Offer's
  `proposedEmbargo`, else the converted disclosure date. The owner's side is its
  actor default on its profile, unchanged: the shorter one becomes active, the
  longer becomes a pending revision (EP-04-003, EP-04-016).

## A Proposed End That Has Passed

- **Record it as in force, then ended at its end time.** The case starts at
  `EM.EXITED`, so no later embargo can start: an exited case has no move out.
  Leaving the embargo out would let the owner's default, or a later proposal,
  start an embargo after the date that ended it.
- **Three register steps, one transaction.** PROPOSE, ACTIVATE, then TERMINATE
  with `END_TIME_REACHED`: each moves EM along one transition, so ADR-0130 needs
  no change. They run inside the case-creation act, as the default embargo's
  PROPOSE and ACCEPT do (EP-04-031), so no intermediate state is visible
  (EP-04-002). One step of PROPOSE with CANCEL is refused by the register's step
  rules and leaves the case at `EM.NONE`, from which a new embargo could start.
- **Shorter wins picks it.** A passed end is shorter than any actor default, so
  the Reporter's terms win (EP-04-003); no revision is registered for the losing
  term, since an exited embargo has none (EP-04-016).
- **This is not a new negotiation.** The embargo is the Reporter's earlier
  proposal and ended when the vul became public, so VP-06-001 (no embargo
  proposed or accepted once public) is not engaged. The code check that refuses
  any embargo on a case with P, X or A set must let this one through.
- **The end is part of creating the case.** `Create(VulnerabilityCase)` carries
  the register to the owner and the Reporter; no separate embargo-ending notice
  is sent.
- **Only a CSAF date makes the case public.** A disclosure date is the date the
  vul goes public; an Offer's `proposedEmbargo` end is not. A passed Offer
  proposal still starts the case at `EM.EXITED`, with P unset.

## Requirement Text the Implementation Adds

These land with the code that tests them, so no requirement states a rule a test
does not check. Each cites ADR-0184. The IDs are the next free ones at planning
time; re-check them against `origin/main` before landing.

In `specs/case-proposal.yaml`, group CP-01 (#6722, #6723):

- CP-01-022, MAY, `protocol`: A `CaseProposal` MAY carry, as `caseInputs`, the
  starting content its proposer states for the case: its name, summary, whether
  an exploit is public (X), whether attacks are observed (A), its vulnerability
  items, its case references and the earliest CSAF disclosure date.
- CP-01-023, MUST, `protocol`: A proposer MUST carry the CSAF disclosure date in
  `caseInputs` as the document states it, and MUST NOT state in `caseInputs`
  whether the vulnerability is public.
- CP-01-024, MUST, `protocol`: When a proposal carries `caseInputs`, the
  CASE_MANAGER MUST build the new case from them and MUST NOT read a CSAF
  document on the proposal's carried Offer.
- CP-01-025, MAY, `protocol`: When a proposal carries no `caseInputs`, the
  CASE_MANAGER MAY fill the case inputs from the CSAF document on the carried
  Offer (CSAF-02-001, CSAF-03).
- CP-01-026, MUST, `project`: In this implementation, a report receiver MUST send
  `caseInputs` on a proposal whose initial report carries a CSAF document of
  category `csaf_vulnerability_report`, and the CASE_MANAGER MUST apply
  CP-01-025 to a proposal that carries none.

Issue #6723 also rewrites the CSAF-02-001 note in
`specs/csaf-report-content.yaml`. It says the proposer's own record keeps every
value display only, which stops being true once the proposer converts the
document.

In `specs/embargo-policy.yaml`, group EP-04 (#6725):

- EP-04-033, MUST, `protocol`: When a sender's proposed embargo whose end is no
  later than the instant the CASE_MANAGER creates the case wins the comparison of
  EP-04-003, the CASE_MANAGER MUST record it as an embargo that was active and
  ended at its end time, so the case starts at `EM.EXITED`.
- EP-04-034, MUST NOT, `protocol`: For a case created under EP-04-033, the
  CASE_MANAGER MUST NOT start another embargo or register a revision.
- EP-04-035, MUST, `project`: This codebase MUST record the embargo of EP-04-033
  by the register's PROPOSE, ACTIVATE and TERMINATE steps, with the reason
  `END_TIME_REACHED`, inside the case-creation act.
- EP-04-020 is amended with them: when any of P, X or A is set at case creation,
  the CASE_MANAGER MUST NOT start the case with an embargo in force; it leaves the
  case at `EM.NONE`, or at `EM.EXITED` when EP-04-033 applies.

Issue #6725 also amends two items in `specs/csaf-report-content.yaml`. The
CSAF-03-001 note says a case that starts with P takes no disclosure date as its
end, and CSAF-03-003 says such a case starts with no embargo. Under EP-04-033 a
passed disclosure date is the Reporter's end, and the case starts at `EM.EXITED`.
