---
description: >
  Concepts that Vultron has and the Common Security Advisory Framework (CSAF)
  2.1 draft does not, and concepts that CSAF has and Vultron does not.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 400
page_type: reference
subject: neutral
---

# CSAF 2.1 Coverage Differences

{% include-markdown "../../includes/not_normative.md" %}

This page lists the concepts that only one of two models has: the Vultron Protocol, or the Common Security Advisory Framework (CSAF) 2.1 draft.
It is for readers who need to know what a conversion between the two models cannot carry.
The [concept mapping](concept_mapping.md) gives the concepts that both models have, and the [overview](overview.md) explains why the two models differ.

{% include-markdown "./_csaf_version.md" %}

Most items on this page need no change.
They come from the different purposes of the two models: CSAF records a disclosure, and Vultron controls how it proceeds.
An item that is also a proposal has a **Proposal** mark, and the [proposals](proposals.md) page gives it in full.
An item that Vultron could change has a **Vultron could** mark, and the [conclusions](conclusion.md) page links the issue that tracks it.
A gap in the Vultron object model is not always a design choice.
Some areas of the Vultron object model are not yet defined in detail, and an item says so when that is the reason.

---

## Concepts that Vultron has and CSAF does not

### Authority and entitlement

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>What it does</th>
<th>Note</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">[Case Owner](../glossary.md#cvd-roles-and-participants) and [Case Manager](../glossary.md#cvd-roles-and-participants)</td>
<td markdown="span">The Case Owner makes the case decisions. The Case Manager is the one writer of the case, and it keeps the [case ledger](../../topics/case_lifecycle/case_manager_and_ledger.md).</td>
<td markdown="span">A CSAF document has one issuing party, and only that party revises it.</td>
</tr>
<tr markdown="1">
<td markdown="span">[Ledger admission](../../topics/case_lifecycle/case_manager_and_ledger.md#only-admitted-entries)</td>
<td markdown="span">The Case Manager admits or refuses each claim that a participant sends, before it changes the case.</td>
<td markdown="span">CSAF has no step that accepts or refuses a statement in a document.</td>
</tr>
<tr markdown="1">
<td markdown="span">Entitlement to case content, with [Active and Inert Participants](../glossary.md#cvd-roles-and-participants)</td>
<td markdown="span">Only an entitled participant receives the case content. An invitee becomes entitled when it joins and, while an embargo is active, agrees to that embargo (CM-10-004).</td>
<td markdown="span">CSAF controls distribution of each document with a Traffic Light Protocol (TLP) label, not with entitlement.</td>
</tr>
<tr markdown="1">
<td markdown="span">Joining and removal: invitation, acceptance, [suggest-actor-to-case](../glossary.md#messaging-and-protocol), and removal ([§12 Participant Lifecycle Within a Case](../vultron-spec/interactions.md#12-participant-lifecycle-within-a-case-n))</td>
<td markdown="span">The case changes its list of participants only through these flows.</td>
<td markdown="span">A CSAF projection can record a join as a `notification` or `coordination` action, but CSAF has no rules for it.</td>
</tr>
<tr markdown="1">
<td markdown="span">[Case Ownership Transfer](../../topics/case_lifecycle/ownership_transfer.md)</td>
<td markdown="span">The Case Owner role moves from one participant to a different participant.</td>
<td markdown="span">No counterpart.</td>
</tr>
</tbody>
</table>

### Rules for change

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>What it does</th>
<th>Note</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Transitions and guards of the Report Management (RM), Embargo Management (EM), and Case State (CS) state machines ([§6 Report Management (RM) State Machine](../vultron-spec/tracking-models.md#6-report-management-rm-state-machine-n), [§7 Embargo Management (EM) State Machine](../vultron-spec/tracking-models.md#7-embargo-management-em-state-machine-n), [§8 Case State (CS) Dimensions](../vultron-spec/tracking-models.md#8-case-state-cs-dimensions-n))</td>
<td markdown="span">The state machines say which change is permitted from each state.</td>
<td markdown="span">CSAF enforces no order between action status values. The draft gives only an informative common order for a `notification`, and the design proposal calls the status "descriptive and observational".</td>
</tr>
<tr markdown="1">
<td markdown="span">[Model interactions and cascade rules](../vultron-spec/interactions.md#11-model-interactions-and-cascade-rules-n)</td>
<td markdown="span">A change in one state machine can cause a change in a different one, for example an embargo end when the vulnerability becomes known to be public.</td>
<td markdown="span">No counterpart.</td>
</tr>
<tr markdown="1">
<td markdown="span">Two times for each event: the time that the sender claims, and the commit time of the Case Manager</td>
<td markdown="span">Vultron keeps the claim and the record apart (CLP-14-002, CLP-15-005).</td>
<td markdown="span">CSAF has one `date` for each action.</td>
</tr>
</tbody>
</table>

### Embargo detail

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>What it does</th>
<th>Note</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Versions in the [embargo register](../../topics/process_models/em/index.md#the-embargo-register)</td>
<td markdown="span">The register keeps each proposed, revised, and ended embargo.</td>
<td markdown="span">**Proposal.** A CSAF document holds one disclosure date for each vulnerability, so the dates of earlier versions are lost. See [proposal 1](proposals.md#1-an-embargo-action-carries-its-own-end-date).</td>
</tr>
<tr markdown="1">
<td markdown="span">Early termination of an embargo ([Early Termination](../../topics/process_models/em/early_termination.md))</td>
<td markdown="span">An embargo can end before its end time.</td>
<td markdown="span">**Proposal.** CSAF has no way to record it. See [proposal 2](proposals.md#2-an-embargo-can-end-before-its-date).</td>
</tr>
<tr markdown="1">
<td markdown="span">Consent of each participant to each version, with deadlines to answer (RSVP deadlines) and the [pocket veto](../glossary.md#embargo-and-timing) ([§9 Participant Embargo Consent (PEC) State Machine](../vultron-spec/tracking-models.md#9-participant-embargo-consent-pec-state-machine-n))</td>
<td markdown="span">Vultron records who agreed to which version, and what occurs when an invitee does not answer.</td>
<td markdown="span">A projection records agreement as `confirmation` and refusal as `dispute`. CSAF has no deadline for an answer.</td>
</tr>
<tr markdown="1">
<td markdown="span">Embargo policies and [default embargoes](../../topics/process_models/em/defaults.md)</td>
<td markdown="span">An actor publishes its preferred embargo terms, and a case can start with a default embargo.</td>
<td markdown="span">No counterpart.</td>
</tr>
<tr markdown="1">
<td markdown="span">Embargo end apart from publication ([Embargo Termination is Not the Same as Publication](../../topics/process_models/em/principles.md#embargo-termination-is-not-the-same-as-publication))</td>
<td markdown="span">The end of an embargo and the public disclosure of the vulnerability are two events.</td>
<td markdown="span">**Proposal.** CSAF uses `disclosure_date` for both. See [proposal 1](proposals.md#1-an-embargo-action-carries-its-own-end-date).</td>
</tr>
</tbody>
</table>

### Case structure and integrity

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>What it does</th>
<th>Note</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Case ledger with a hash chain and a [genesis hash](../glossary.md#sync-authority-replication)</td>
<td markdown="span">Each entry includes the hash of the entry before it, so a participant can detect a change to the history.</td>
<td markdown="span">CSAF protects a whole document with signatures and hashes at distribution. It does not link the actions in a timeline.</td>
</tr>
<tr markdown="1">
<td markdown="span">[Participant case replicas](../../topics/case_lifecycle/case_manager_and_ledger.md#one-writer-many-copies)</td>
<td markdown="span">Each participant keeps a copy of the case that the ledger keeps current.</td>
<td markdown="span">A CSAF document is a copy at one time. It is not kept current.</td>
</tr>
<tr markdown="1">
<td markdown="span">Parent, child, and sibling cases: split and merge ([Case Splitting and Merging](../../topics/process_models/em/split_merge.md))</td>
<td markdown="span">The protocol defines how a case divides into child cases or joins a different case ([ADR-0105](../../adr/0105-case-merge-freeze-and-redirect-by-owner-consent.md), and [ADR-0125](../../adr/0125-case-split-child-case-inherits-the-embargo-only.md), which is provisionally accepted). The implementation is planned ([#3702](https://github.com/CERTCC/Vultron/issues/3702){:target="_blank"}, [#4242](https://github.com/CERTCC/Vultron/issues/4242){:target="_blank"}).</td>
<td markdown="span">CSAF documents can refer to other documents, but CSAF has no concept of a split or a merge.</td>
</tr>
<tr markdown="1">
<td markdown="span">Report and case as different objects</td>
<td markdown="span">One case can hold many reports, and one report can describe many vulnerabilities (CM-05-006).</td>
<td markdown="span">One CSAF document holds all of its vulnerabilities.</td>
</tr>
</tbody>
</table>

---

## Concepts that CSAF has and Vultron does not

### Products and remediation

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>CSAF concept</th>
<th>What it does</th>
<th>Note</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">`product_tree`: branches, full product names, relationships, and product groups</td>
<td markdown="span">Identifies each product and version that a document refers to.</td>
<td markdown="span">Vultron does not describe products. A description of products is the purpose of CSAF.</td>
</tr>
<tr markdown="1">
<td markdown="span">`vulnerabilities[].product_status`, with lists such as `known_affected`, `known_not_affected`, `fixed`, `under_investigation`, `recommended`, and `unknown`</td>
<td markdown="span">Gives the status of each product for each vulnerability.</td>
<td markdown="span">Vultron tracks whether a fix is ready (F) and deployed (D) once for each participant, not for each product. Concern [#5140](https://github.com/CERTCC/Vultron/issues/5140){:target="_blank"} asks whether Vultron could track F for each vendor and product, and D for each vendor, product, and deployer.</td>
</tr>
<tr markdown="1">
<td markdown="span">`vulnerabilities[].remediations[]`, with categories such as `vendor_fix`, `workaround`, `mitigation`, `no_fix_planned`, and `optional_patch`</td>
<td markdown="span">Describes each fix or workaround and the products it applies to.</td>
<td markdown="span">Vultron records that a fix is ready, not what the fix is.</td>
</tr>
<tr markdown="1">
<td markdown="span">`vulnerabilities[].flags[]`, with the Vulnerability Exploitability eXchange (VEX) justifications</td>
<td markdown="span">Tells why a product is not affected.</td>
<td markdown="span">No counterpart.</td>
</tr>
</tbody>
</table>

### Vulnerability detail

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>CSAF concept</th>
<th>What it does</th>
<th>Note</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">`vulnerabilities[]` as a structured object</td>
<td markdown="span">Holds identifiers, dates, notes, references, metrics, threats, and product status for each vulnerability.</td>
<td markdown="span">**Vultron could** add vulnerability records to the case, with CSAF or Common Vulnerabilities and Exposures (CVE) content. The Vultron object model has not yet reached this depth, and this gap is recognized. See the [concept mapping](concept_mapping.md#content-objects). Issue [#5132](https://github.com/CERTCC/Vultron/issues/5132){:target="_blank"} tracks this change.</td>
</tr>
<tr markdown="1">
<td markdown="span">`vulnerabilities[].metrics[]`: Common Vulnerability Scoring System (CVSS), Exploit Prediction Scoring System (EPSS), Stakeholder-Specific Vulnerability Categorization (SSVC), and qualitative severity</td>
<td markdown="span">Gives scores and ratings for each vulnerability.</td>
<td markdown="span">Vultron does not record scores. The SSVC Exploitation value maps to the CS model, as the [concept mapping](concept_mapping.md#case-state) shows.</td>
</tr>
<tr markdown="1">
<td markdown="span">`vulnerabilities[].threats[]` with `impact` and `target_set`</td>
<td markdown="span">Describes the effect of a vulnerability and the products or users at risk.</td>
<td markdown="span">No counterpart. The `exploit_status` category maps to Exploit Public (X).</td>
</tr>
<tr markdown="1">
<td markdown="span">`document.aggregate_severity`</td>
<td markdown="span">Gives one severity for the whole document.</td>
<td markdown="span">No counterpart.</td>
</tr>
<tr markdown="1">
<td markdown="span">`document.acknowledgments` and `vulnerabilities[].acknowledgments`</td>
<td markdown="span">Names the people and organizations that receive public credit. In the Vulnerability Report profile, no acknowledgments means that the discoverer does not want public credit.</td>
<td markdown="span">Undecided: Vultron could record which participants want public credit ([#5135](https://github.com/CERTCC/Vultron/issues/5135){:target="_blank"}). CSAF acknowledgments are not linked to involvement entities.</td>
</tr>
</tbody>
</table>

### Parties and events

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>CSAF concept</th>
<th>What it does</th>
<th>Note</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Entity category `adversary`, and the `exploitation` action</td>
<td markdown="span">Names a party that acts against the others, identified or not, and records its use of the vulnerability.</td>
<td markdown="span">An attacker is never a Vultron participant. Vultron records only that attacks were observed (A).</td>
</tr>
<tr markdown="1">
<td markdown="span">Entity category `multiplier`</td>
<td markdown="span">Names a party that uses or distributes data about a vulnerability.</td>
<td markdown="span">No counterpart.</td>
</tr>
<tr markdown="1">
<td markdown="span">Entity category `public`</td>
<td markdown="span">Names the general public as a party.</td>
<td markdown="span">In Vultron, public awareness is the P dimension, not a party.</td>
</tr>
<tr markdown="1">
<td markdown="span">Entity category `reporting_authority`</td>
<td markdown="span">Names a party that receives or requires a report, such as a national Computer Security Incident Response Team (CSIRT).</td>
<td markdown="span">No counterpart. Such an authority can be a Vultron participant with a different role, or the recipient of a projection.</td>
</tr>
<tr markdown="1">
<td markdown="span">Action status `planned` and `attempted`</td>
<td markdown="span">`attempted` records an action that did not reach its recipient. The draft gives `planned` the same definition as `outstanding`: a party waits for the action.</td>
<td markdown="span">Vultron records completed acts only. A failed delivery is a fact about the outbox, not about the case.</td>
</tr>
</tbody>
</table>

### Documents and distribution

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>CSAF concept</th>
<th>What it does</th>
<th>Note</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Profiles: CSAF Base, Security Incident Response, Informational Advisory, Security Advisory, VEX, Deprecated Security Advisory, Withdrawn, Superseded, and Vulnerability Report</td>
<td markdown="span">Each profile sets the required fields for one type of document.</td>
<td markdown="span">Vultron has no document types. A projection selects a profile.</td>
</tr>
<tr markdown="1">
<td markdown="span">TLP labels on each document</td>
<td markdown="span">Tells the recipient how far it can share the document.</td>
<td markdown="span">Vultron has no labels. The way TLP could appear in Vultron data and logic is an open concern ([#5133](https://github.com/CERTCC/Vultron/issues/5133){:target="_blank"}). See the [overview](overview.md#tlp-marks-a-projection-not-a-case).</td>
</tr>
<tr markdown="1">
<td markdown="span">Document language and translations</td>
<td markdown="span">Gives the language of a document and links to its translations.</td>
<td markdown="span">No counterpart.</td>
</tr>
<tr markdown="1">
<td markdown="span">Distribution requirements: provider metadata, feeds, signatures, and access control for restricted labels</td>
<td markdown="span">Tells how an issuing party publishes documents and how a reader finds and verifies them.</td>
<td markdown="span">Vultron delivers messages to inboxes. Publication of a projection is outside the protocol.</td>
</tr>
<tr markdown="1">
<td markdown="span">CSAF Modifier and converters</td>
<td markdown="span">A party that changes a document of a different party makes a new document with a new tracking ID and refers to the original.</td>
<td markdown="span">No counterpart.</td>
</tr>
</tbody>
</table>

## Further reading

- [CSAF 2.1 and Vultron](overview.md) — how a CSAF document relates to a Vultron case.
- [Proposals](proposals.md) — the changes that CSAF and Vultron could make, each with its reason and its cost if nothing changes.
- [Conclusions](conclusion.md) — what the comparison shows, and the issues that track the follow-up work.
- [Concept mapping](concept_mapping.md) — each Vultron concept, its CSAF counterpart, and the type of mapping in each direction.
