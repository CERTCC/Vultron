---
description: >
  How the Common Security Advisory Framework (CSAF) 2.1 draft relates to a
  Vultron case, and a summary of where the two models are the same, close,
  or different.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 300
page_type: explanation
---

# CSAF 2.1 and Vultron

{% include-markdown "../../includes/not_normative.md" %}

This page explains how the Common Security Advisory Framework (CSAF) 2.1 draft and the Vultron Protocol relate to each other.
It is for readers who know one of the two models and want to know how the other one fits with it.
These readers include members of the CSAF Technical Committee (TC) of the Organization for the Advancement of Structured Information Standards (OASIS).
It describes three relations between a CSAF document and a Vultron [case](../glossary.md#core-cvd-concepts), and it gives a summary of each area where the two models meet.
Three other pages give the detail: the [concept mapping](concept_mapping.md), the [coverage differences](coverage.md), and the [proposals](proposals.md).
The [conclusions](conclusion.md) page gives the result and the follow-up work.

{% include-markdown "./_csaf_version.md" %}

---

## Why this comparison exists

CSAF is a machine-readable format for security advisories, published by OASIS.
CSAF 2.0 recorded the parties in a disclosure with a short `involvements` list on each vulnerability.
CSAF 2.1 replaces that list with one `document.involvement` object: a list of entities, optional entity groups, and a timeline of actions between the entities.

The TC started this change from Vultron.
The issue that opened the work, [oasis-tcs/csaf#1486](https://github.com/oasis-tcs/csaf/issues/1486){:target="_blank"}, says: "As a starting point, we can use Vultron."
The [TC meeting of 29 July 2026](https://github.com/oasis-tcs/csaf/blob/29b1e27aa126b820cbd6eee1830ca27ef02793d1/meeting_minutes/2026/2026-07-29.md){:target="_blank"} recorded the approach: study the Vultron project and its states, then design the involvement model from the start.
Because the TC used Vultron as an input, many concepts on the two sides are close, and a crosswalk can show where they agree and where they do not.

---

## Different levels of abstraction

CSAF and Vultron work at different levels of abstraction.
CSAF records what happened in a disclosure.
Vultron controls how a disclosure proceeds.

The design proposal for the CSAF 2.1 involvement model states this difference itself.
Its appendix "Comparison with Vultron" ([comment on #1486, 14 August 2026](https://github.com/oasis-tcs/csaf/issues/1486#issuecomment-5291835024){:target="_blank"}) says:

> The CSAF involvement model has a different purpose.
> It is a **documentation model**: it records interactions that were observed to occur, so that a reader of an advisory can reconstruct who coordinated with whom about what.

A later comment by the same author ([25 August 2026](https://github.com/oasis-tcs/csaf/issues/1486#issuecomment-5407212379){:target="_blank"}) adds that the purpose of involvement "is not to describe all involvements, but to allow a publishing party to describe selected involvements they consider relevant for their audience."

Vultron has the other purpose.
Its state machines for [Report Management (RM)](../../topics/process_models/rm/index.md), [Embargo Management (EM)](../../topics/process_models/em/index.md), and [Case State (CS)](../../topics/process_models/cs/cs_model.md) state which changes are permitted and who can make them.
Its [case ledger](../../topics/case_lifecycle/case_manager_and_ledger.md) records every change to the case, not a selection.
Neither purpose is better than the other.
The difference explains most of the gaps on the other pages, and it tells which gaps to keep.

---

## How a CSAF document relates to a Vultron case

A CSAF document can relate to a Vultron case in three ways.
It can replace the case, it can travel inside the case, or the case can produce it.
Vultron uses the second and the third relation, and it does not use the first.

### A CSAF document does not replace the case

A CSAF document is not the case of record in Vultron.
The reasons come from the CSAF design.

| CSAF property | Consequence for a case of record |
|---|---|
| The action `status` is "descriptive and observational", with no state machine. | CSAF cannot hold the rules that decide which change is permitted. |
| The involvement timeline holds selected events. | A case of record holds all events. |
| One issuing party publishes each document. | A case has many participants, and each one writes to it through the [Case Manager](../glossary.md#cvd-roles-and-participants). |
| Entity, vulnerability, and action identifiers are local to one document. | A case needs identifiers that stay the same in all messages. |
| CSAF has no rule to merge documents from different issuing parties. | A case combines the contributions of all participants. |
| CSAF has no concept of who can change the document. | Vultron gives that authority to the Case Owner and the Case Manager. |

For a small case between two parties, an exchange of CSAF documents can be sufficient without Vultron.
Vultron becomes necessary when more parties, an embargo, or a disagreement make the rules for change important.

### A CSAF document can travel inside a case

A participant can send a CSAF document as the content of a Vultron report, for example `Offer(VulnerabilityReport)` with the CSAF document in `content`.
The CSAF 2.1 [Vulnerability Report profile](https://github.com/oasis-tcs/csaf/blob/29b1e27aa126b820cbd6eee1830ca27ef02793d1/csaf_2.1/prose/edit/src/profiles.md){:target="_blank"} is made for this use.
That profile "SHALL be used to exchange a vulnerability report during the Coordinated Vulnerability Disclosure (CVD) process", and its Traffic Light Protocol (TLP) label SHOULD be `TLP:AMBER`.

Some fields of such a document describe the process, for example `involvement`, `disclosure_date`, the TLP label, and the Stakeholder-Specific Vulnerability Categorization (SSVC) exploitation value.
This crosswalk proposes three rules for those fields:

1. A receiving participant SHOULD read these fields as claims by the sender.
2. A receiving participant MUST NOT change the case state from the document content, except through Vultron's own activities.
3. A receiving participant MAY make the change from a claim to an activity automatic.

For example, a `disclosure_date` in a received report can cause an embargo proposal with that date.
The proposal then goes through the normal embargo process, and the case ledger records the result.
These rules are proposals for Vultron, not current requirements.
The [concept mapping](concept_mapping.md#content-objects) gives them as "Vultron could" rows, and issue [#5131](https://github.com/CERTCC/Vultron/issues/5131){:target="_blank"} tracks them.

### A case can produce a CSAF document

A Vultron participant can produce a CSAF document from its copy of the case.
This crosswalk calls such a document a **projection**.
A projection can occur at two times:

| Time | Example | Use |
|---|---|---|
| At publication | A CSAF Security Advisory or a CSAF Vulnerability Exploitability eXchange (VEX) document | The public record of the vulnerability. The [publication pipeline](../../adr/0030-publish-leaf-draft-review-submit-pipeline.md) (ADR-0030) already names CSAF as one output format. |
| During coordination | A CSAF Vulnerability Report for a party that does not use Vultron | A bridge to a vendor, a national Computer Security Incident Response Team (CSIRT), or a reporting authority outside the case. |

A projection during coordination copies embargoed information out of the protocol.
For this reason, a projection SHOULD NOT include information that the recipient is not entitled to see.
Each projection also states the ledger position that it shows, because the case continues to change after the projection.
The `involvement` timeline of a projection is a filtered view of the case ledger.
That agrees with the CSAF design, in which the issuing party selects the events that its audience needs.
Issue [#5134](https://github.com/CERTCC/Vultron/issues/5134){:target="_blank"} tracks the work to produce projections.

---

## TLP marks a projection, not a case

Vultron has no TLP labels.
It controls who sees what through the participants that are entitled to the case and through the embargo.
TLP becomes necessary only when information goes out of Vultron, which occurs in a projection.

For this reason, a TLP label belongs to one projection.
Its value depends on the content of the projection, on the recipient, and on the case state.
Different recipients can receive different projections of the same case at the same time.
For example, an observer can receive a projection marked `TLP:RED`, a coordinator one marked `TLP:AMBER`, and a vendor one marked `TLP:AMBER+STRICT`.

| TLP label | Fit for a projection |
|---|---|
| `TLP:AMBER+STRICT` | The usual fit before public disclosure. The recipient can share only inside its own organization. |
| `TLP:AMBER` | Fits only when the recipient can share with others at its own discretion. That sharing occurs outside the case, so Vultron cannot record it. The Vultron way to add a party is the [suggest-actor-to-case flow](../glossary.md#messaging-and-protocol). CSAF explains its `TLP:AMBER` default as sharing "on a need-to-know basis within the vendor's or coordinator's organization and, where appropriate, their clients". |
| `TLP:RED` | Fits only an observer. A `TLP:RED` recipient cannot tell its own team to act on the information. |
| `TLP:CLEAR` | Fits a projection with the content of a public advisory, after the vulnerability is known to be public. |

A projection can be `TLP:CLEAR` because it selects its content.
The full case history, with each message between participants and its time, can stay restricted after the advisory is public.
A more detailed projection of the same case can need a stricter label at the same time.

!!! note "Terminology for TLP and public status"

    A TLP label applies to a document, not to a case.
    The correct statement is "this document, which describes information derived from the case, is `TLP:CLEAR`".
    The statement "the case is `TLP:CLEAR`" is not correct.

    In the same way, public status applies to the vulnerability, not to the case.
    The correct statement is "the vulnerability described in the case is known to be public".
    This agrees with the *Public Awareness* (P) dimension of the [CS model](../../topics/process_models/cs/cs_model.md#the-public-awareness-substate-p-p).

When a received CSAF document has a label that is stricter than the Vultron entitlement rules, Vultron cannot enforce that label.
For example, a `TLP:RED` document can arrive in a case with five participants.
Only the policy of the receiving participant can obey the label.
This is a known limit, and concern [#5133](https://github.com/CERTCC/Vultron/issues/5133){:target="_blank"} tracks it.

---

## Summary by area

The table gives one row for each area where the two models meet.
**Similarity** is *Same* (same concept and shape), *Close* (same concept, different shape), or *Divergent* (same area, conflicting meaning).
**Proposed change** says what could change, or why nothing changes.
The links go to the detailed rows.

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Area</th>
<th>Similarity</th>
<th>Proposed change</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">[Parties and roles](concept_mapping.md#parties-and-roles)</td>
<td markdown="span">Close</td>
<td markdown="span">No change proposed. Both models put finder and reporter into one role with different names. The [Reporter](../glossary.md#cvd-roles-and-participants) role and the CSAF `discoverer` category are the same choice.</td>
</tr>
<tr markdown="1">
<td markdown="span">[Events and timeline](concept_mapping.md#events-and-timeline)</td>
<td markdown="span">Close</td>
<td markdown="span">No change proposed. A CSAF action has the same shape as an ActivityStreams activity: an actor, recipients, a time, and a referenced earlier event. Undecided: CSAF could let an entity carry an identifier that stays the same in different documents.</td>
</tr>
<tr markdown="1">
<td markdown="span">[Report management](concept_mapping.md#report-management)</td>
<td markdown="span">Close</td>
<td markdown="span">No change proposed. Vultron state names tell what already occurred, and CSAF status values tell what occurs now. Undecided: CSAF `confirmation` puts receipt and acceptance into one value.</td>
</tr>
<tr markdown="1">
<td markdown="span">[Embargo](concept_mapping.md#embargo)</td>
<td markdown="span">Close</td>
<td markdown="span">CSAF could let an `embargo` action carry its own end date, and CSAF could record the early end of an embargo. See [the proposals](proposals.md).</td>
</tr>
<tr markdown="1">
<td markdown="span">[Case state](concept_mapping.md#case-state)</td>
<td markdown="span">Close</td>
<td markdown="span">No change proposed. Both models keep exploit availability as a fact about the vulnerability, not as an event between parties.</td>
</tr>
<tr markdown="1">
<td markdown="span">[Content objects](concept_mapping.md#content-objects)</td>
<td markdown="span">Close</td>
<td markdown="span">Vultron could add vulnerability records to the case, with CSAF or Common Vulnerabilities and Exposures (CVE) content. Vultron could read process fields in a received CSAF document as claims. See [#5132](https://github.com/CERTCC/Vultron/issues/5132){:target="_blank"} and [#5131](https://github.com/CERTCC/Vultron/issues/5131){:target="_blank"}.</td>
</tr>
<tr markdown="1">
<td markdown="span">[Distribution and tracking](concept_mapping.md#distribution-and-tracking)</td>
<td markdown="span">Divergent</td>
<td markdown="span">No change proposed. Vultron derives a TLP label for each projection. The way TLP could appear inside Vultron is an open concern ([#5133](https://github.com/CERTCC/Vultron/issues/5133){:target="_blank"}).</td>
</tr>
</tbody>
</table>

The [coverage differences](coverage.md) page lists the concepts that only one of the two models has.

---

## Further reading

- [Concept mapping](concept_mapping.md) — each Vultron concept, its CSAF counterpart, and the type of mapping in each direction.
- [Coverage differences](coverage.md) — concepts that Vultron has and CSAF does not, and the reverse.
- [Proposals](proposals.md) — the changes that CSAF and Vultron could make, each with its cost if nothing changes.
- [Standards Crosswalks](../iso_crosswalks/index.md) — the other crosswalks of Vultron against related standards.
- [oasis-tcs/csaf#1486](https://github.com/oasis-tcs/csaf/issues/1486){:target="_blank"} — the TC issue for the CSAF 2.1 involvement model.
- [Conclusions](conclusion.md) — what the comparison shows, and the issues that track the follow-up work.
