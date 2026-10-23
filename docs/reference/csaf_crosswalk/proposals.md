---
description: >
  Changes that the Common Security Advisory Framework (CSAF) 2.1 draft and
  the Vultron Protocol could make, each with its reason and its cost if
  nothing changes.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 300
page_type: explanation
---

# CSAF 2.1 and Vultron: Proposals

{% include-markdown "../../includes/not_normative.md" %}

This page gives the changes that a comparison of the Common Security Advisory Framework (CSAF) 2.1 draft with the Vultron Protocol suggests.
It is for members of the CSAF Technical Committee (TC) of the Organization for the Advancement of Structured Information Standards (OASIS) and for Vultron contributors.
Each proposal gives the problem, the evidence, the change, and what occurs if nothing changes.
The CSAF proposals are suggestions from the Vultron project, and the TC decides on them.

{% include-markdown "./_csaf_version.md" %}

---

## Context

Vultron is a protocol for Coordinated Vulnerability Disclosure (CVD) among many parties, from the CERT Coordination Center (CERT/CC).
It controls how a case proceeds: which changes are permitted, and who can make them.
CSAF 2.1 records what happened in a disclosure, in the `document.involvement` timeline of entities and actions.
The TC started the CSAF 2.1 involvement model from Vultron ([oasis-tcs/csaf#1486](https://github.com/oasis-tcs/csaf/issues/1486){:target="_blank"}).
The [overview](overview.md) explains how the two models relate, and the [concept mapping](concept_mapping.md) gives the detail.

Vultron keeps an embargo as a sequence of versions.
Each version has an end time, and each participant agrees to it or refuses it ([Embargo Management](../../topics/process_models/em/index.md)).
An embargo can be revised, and it can end before its end time ([Early Termination](../../topics/process_models/em/early_termination.md)).
The end of an embargo and the public disclosure of the vulnerability are two different events ([Embargo Termination is Not the Same as Publication](../../topics/process_models/em/principles.md#embargo-termination-is-not-the-same-as-publication)).
The two CSAF proposals below come from that experience.

---

## Proposals for CSAF

### 1. An embargo action carries its own end date

**Problem.**
A CSAF `embargo` action has no date for the end of the embargo.
The draft says: "The agreed date is the `disclosure_date` of each vulnerability that `dl_vuln_ids` names."
A document holds one `disclosure_date` for each vulnerability.
When an embargo is revised, the draft says that the issuing party "SHOULD produce an updated CSAF document to confirm that the vulnerability was in fact disclosed to the public at that time or update the `disclosure_date` with the new intended date in the future."
The new date replaces the old date.

**Consequences.**
A revised embargo can be a new `embargo` action that refers to the earlier action, and a `confirmation` that refers to each version shows who agreed to it.
But the timeline cannot show the date that each earlier version set, because only one `disclosure_date` remains.
That history is often the most important part of a disputed disclosure.
The `disclosure_date` also has two meanings before disclosure and after disclosure: the intended end of the embargo, and the time of the public disclosure.
An embargo can end without a disclosure, and a disclosure can occur before the embargo date, so one field cannot always hold both facts.

**Proposed change.**
CSAF could let an `embargo` action carry its own end date, as an optional property of the action.
A revised embargo then becomes a new `embargo` action that refers to the earlier action in `referenced_action_ids`, each with its own date.
The `disclosure_date` of each vulnerability keeps its meaning as the date of public disclosure.
A `confirmation` or `dispute` that refers to one `embargo` action then records agreement to that date only.

The design discussion considered a date on the action and rejected it: "An `expiry_date` on the action would hold a copy of `disclosure_date`, and two fields that hold one date can disagree" ([#1486, 6 October 2026](https://github.com/oasis-tcs/csaf/issues/1486#issuecomment-6016287102){:target="_blank"}).
This proposal does not make a copy.
The action holds the agreed end date of one embargo version, and the `disclosure_date` holds only the date of public disclosure.
The two dates are different facts, and they can be different when an embargo ends without a disclosure or a disclosure occurs before the embargo date.

**Benefit.**
The change records each embargo version in the timeline.
The design proposal for the involvement model describes that timeline as "an auditable timeline of the coordination effort" ([#1486, 14 August 2026](https://github.com/oasis-tcs/csaf/issues/1486#issuecomment-5291835024){:target="_blank"}).
The change also helps a multiplier to copy the involvement list to a different document without a change in meaning.
The TC discussion gives that as "one goal of the rework" ([#1486, 25 August 2026](https://github.com/oasis-tcs/csaf/issues/1486#issuecomment-5413838430){:target="_blank"}).

**If nothing changes.**
A projection from Vultron can show each embargo version as an action, but only the current version has a date that a tool can read.
Earlier dates appear only in the `summary` text of the `embargo` actions, where a tool cannot read them.

### 2. An embargo can end before its date

**Problem.**
CSAF has no way to record that an embargo ended before its date.
The action categories have no value for it, and the draft does not say what the status of an `embargo` action means after the embargo ends.

**Consequences.**
An early end is an important event in a disclosure.
It occurs, for example, when attacks are observed or when the vulnerability becomes known to be public before the agreed date.
A reader of the timeline cannot tell an embargo that ran to its date from one that ended early.

**Proposed change.**
CSAF could state how a document records the early end of an embargo.
One way that needs no change to the schema is the status lifecycle from the design discussion: "`planned` for an agreement that starts later, `in_progress` while it is in force, `completed` when it ran to its date, and `discontinued` when it ended early" ([#1486, 6 October 2026](https://github.com/oasis-tcs/csaf/issues/1486#issuecomment-6016287102){:target="_blank"}).
CSD04 does not include that lifecycle, and CSAF could add it to the normative text.
The draft already defines `discontinued` as an action that "started the work and then stopped it before it was complete."
A second way is a new action that refers to the `embargo` action and records the end, with its date and the party that ended it.

**Benefit.**
The timeline shows why and when an embargo ended, and a tool can read it.

**If nothing changes.**
A projection from Vultron records the early end as a `coordination` action, and it explains the end in `summary`.

---

## Items under discussion

These items are open.
The Vultron project has not decided whether to propose them.

| Item | Description | If nothing changes |
|---|---|---|
| Stable entity identifier | CSAF could let an entity carry an optional identifier that stays the same in different documents, for example a Uniform Resource Identifier (URI). A reader could then match one entity in two documents. | A reader matches entities in different documents by name and contact only. |
| Receipt and acceptance | A CSAF `confirmation` means that the actor "received or accepted" an action. Vultron keeps receipt and acceptance as two facts. CSAF could make the two meanings different. | A projection writes in `summary` which of the two a `confirmation` records. |

---

## Changes on the Vultron side

The comparison also shows changes that Vultron could make.
The Vultron project tracks each of them as a separate item for planning, under Epic [#5130](https://github.com/CERTCC/Vultron/issues/5130){:target="_blank"}.

| Issue | Change | Reason |
|---|---|---|
| [#5131](https://github.com/CERTCC/Vultron/issues/5131){:target="_blank"} | Vultron could identify CSAF content in a report by its `mediaType`, and read the process fields of that content as claims by the sender. A claim then changes the case only through a Vultron activity. | CSAF 2.1 has a Vulnerability Report profile for exchange during coordination, so CSAF reports will arrive inside cases. |
| [#5132](https://github.com/CERTCC/Vultron/issues/5132){:target="_blank"} | Vultron could add a list of vulnerability records to the case, and let a record carry a CSAF document or a Common Vulnerabilities and Exposures (CVE) record as its content. This could include a CSAF profile for one vulnerability without `involvement`. | The Vultron specification already expects vulnerability records on a case (CM-05-003), and the object model has not yet reached this depth. A projection needs the records to set `dl_vuln_ids`. |
| [#5133](https://github.com/CERTCC/Vultron/issues/5133){:target="_blank"} | Vultron could define how a Traffic Light Protocol (TLP) label appears in its data and logic, and how granular a label is. This item is a concern. | Vultron has no labels today. A projection needs a label, and a received document can carry one. |
| [#5134](https://github.com/CERTCC/Vultron/issues/5134){:target="_blank"} | Vultron could produce a CSAF document from the copy of a case that a participant keeps, at publication and during coordination. | A party outside Vultron, such as a vendor or a reporting authority, can then receive the case information in CSAF. |
| [#5140](https://github.com/CERTCC/Vultron/issues/5140){:target="_blank"} | Vultron could track Fix Readiness (F) for each vendor and product, and Fix Deployed (D) for each vendor, product, and deployer. This item is a concern. | CSAF records status for each product, and Vultron records the fix path once for each participant. |
| [#5135](https://github.com/CERTCC/Vultron/issues/5135){:target="_blank"} | Vultron could record which participants want public credit. This item is undecided. | CSAF acknowledgments carry this information, and Vultron has no counterpart. |

---

## Further reading

- [CSAF 2.1 and Vultron](overview.md) — how a CSAF document relates to a Vultron case.
- [Conclusions](conclusion.md) — what the comparison shows, and the issues that track the follow-up work.
- [Concept mapping](concept_mapping.md) — each Vultron concept, its CSAF counterpart, and the type of mapping in each direction.
- [Coverage differences](coverage.md) — concepts that only one of the two models has.
- [oasis-tcs/csaf#1486](https://github.com/oasis-tcs/csaf/issues/1486){:target="_blank"} — the TC issue for the CSAF 2.1 involvement model.
