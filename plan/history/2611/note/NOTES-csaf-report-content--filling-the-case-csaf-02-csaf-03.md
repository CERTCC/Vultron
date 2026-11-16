---
source: NOTES-csaf-report-content--filling-the-case-csaf-02-csaf-03
timestamp: '2026-11-16T18:31:36.038579+00:00'
title: Filling the case (CSAF-02, CSAF-03)
type: note
---

**Archived:** 2026-11-16
**Reason:** delivered — core/services/report_case_inputs.py (case_inputs_from_claims) and nodes/proposal_case_inputs.py; the BTBridge key-scoping rule stays in the note as guidance; the proposer-fills item is tracked by #6197

---

## Filling the case (CSAF-02, CSAF-03)

- **One mapping.** `case_inputs_from_claims(claims, *, reference_time, stated)`
  in `vultron.core.services.report_case_inputs` is the only CSAF-03 mapping; the
  submit-report trigger (#6092) reuses it with its own "now". `StatedReportFields`
  carries the Offer's and report's values, which always win (CSAF-02-003).
- **The CASE_MANAGER reads the carried Offer.** The proposer and the
  CASE_MANAGER are two roles of one coordinating function, so the CSAF document
  on the Offer a `Create(CaseProposal)` carries (CP-01-008) is still the initial
  report (CSAF-02-002). The extractor reads that Offer's report into
  `CreateCaseProposalReceivedEvent.claims_readings`, with the report's own name
  and summary; a proposal with no inline Offer fills nothing (CP-01-021).
  `ResolveReportCaseInputsNode` and `CreateCaseFromProposalNode` run on the
  new-case arm only, so a proposal that resolves to an existing case changes
  nothing (EP-04-029). A proposer that fills the values itself and carries them
  on the proposal is allowed, not built.
- **"Now" is the CASE_MANAGER's receipt of the proposal**, the act's instant, not
  the Offer's `published` (CLP-15-003) and not the receiver's receipt, which no
  message carries. A `disclosure_date` equal to it counts as past (CSAF-03-003).
  The Offer's `proposedEmbargo` is measured from the same instant
  (`sender_embargo_proposal_inputs`), so one clock decides between the two.
- **A `proposedEmbargo` that is no longer terms states nothing.** One already
  ended, or about another subject, is read as no proposal: it neither shapes the
  case nor sets the document's date aside (CSAF-02-003).
- **The first document fills.** A report with several
  `csaf_vulnerability_report` documents fills the case from the first; the
  others stay display only, so two documents never compete for one input.
- **P/X/A are the case's first status**, built at construction, not a
  transition. X starts with P (the pX to PX invariant). A case that starts with
  P, X or A gets no embargo (EP-04-020), so it takes no embargo end, not even a
  stated one, and its future disclosure dates stay display only, neither applied
  nor overridden.
- **Items and references are claims until the case exists.**
  `ReportCaseInputs` carries the vulnerabilities that name themselves (a `cve` or
  an `ids` entry) and the document-level references as claims, and
  `CreateCaseFromProposalNode` builds and stores the objects, so the shared
  mapping mints no id on the Reporter's side (CSAF-03-008, CSAF-03-009). The
  case lists them by id, and each is its own `Add(record, target=<case>)` entry
  after the genesis entry (CLP-07-021, `notes/vulnerability-items.md`). The case's
  `Create` also carries them inline, so the owner that seeds from it holds them
  (AKM-02-004).
- **A CSAF embargo end is a sender proposal.** With no `proposedEmbargo` on the
  Offer, the node seeds `sender_proposed_embargo` with an `EmbargoEvent` whose id
  derives from the proposal (`csaf_proposed_embargo_id`), so it competes with the
  owner's actor default by shortest-wins and redelivery names the same event.
  `BTBridge` scopes both sender keys and `report_case_inputs` to the execution
  (`managed_keys`), because an output port outlives its run: unscoped, a later
  proposal stating no terms took the previous report's embargo (BT-09).
